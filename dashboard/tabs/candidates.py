"""탭 5 — 관리 후보 상세 탐색 (반복적 고노출 / 추가 확인 필요)."""

import pandas as pd
import streamlit as st

from utils import data as D
from utils.text import (ACTION_CATEGORIES, ACTION_CONTEXT_NOTE,
                        ACTION_NOTE, CLASS_LABEL, CLASS_MEANING)

COLS = ["facility_name", "facility_type", "gu", "administrative_dong",
        "nearest_source_distance_m", "source_locations_within_300m",
        "source_locations_within_500m", "air_emission_sites_within_500m",
        "incineration_sites_within_500m", "designated_waste_sites_within_500m",
        "exposure_reason"]
RENAME = {"facility_name": "시설명", "facility_type": "시설유형", "gu": "행정구",
          "administrative_dong": "행정동", "nearest_source_distance_m": "최근접 배출원(m)",
          "source_locations_within_300m": "300m location",
          "source_locations_within_500m": "500m location",
          "air_emission_sites_within_500m": "500m 대기배출업소",
          "incineration_sites_within_500m": "500m 소각",
          "designated_waste_sites_within_500m": "500m 지정폐기물",
          "exposure_reason": "노출 근거"}
SORTABLE = {"최근접 배출원(m)": "nearest_source_distance_m",
            "300m location": "source_locations_within_300m",
            "500m location": "source_locations_within_500m",
            "500m 대기배출업소": "air_emission_sites_within_500m"}


def _view(df, cls):
    st.caption(CLASS_MEANING[cls])
    c = st.columns([2, 2, 2])
    key = c[0].selectbox("정렬 기준", list(SORTABLE), key=f"sort_{cls}",
                         help="정렬은 탐색 편의를 위한 것이며 위험 순위가 아닙니다.")
    asc = c[1].radio("정렬 방향", ["내림차순", "오름차순"], horizontal=True,
                     key=f"dir_{cls}") == "오름차순"
    # 목록을 하드코딩하지 않는다. 유형이 늘면(장애인복지관 추가) 조용히 빠진다.
    all_types = sorted(df["facility_type"].dropna().unique())
    types = c[2].multiselect("시설 유형", all_types, default=all_types, key=f"t_{cls}")
    present = [a for a in ACTION_CATEGORIES if a in set(df["action_category"].dropna())]
    acts = st.multiselect("행동 유형 (종류 구분이며 우선순위가 아닙니다)", present,
                          default=present, key=f"a_{cls}")
    # 두 필터 모두 '비우면 제한 없음'으로 통일한다.
    # (예전엔 시설 유형만 비우면 0곳이 돼 같은 화면에서 반대로 동작했다)
    d = df
    if types:
        d = d[d.facility_type.isin(types)]
    if acts:
        d = d[d["action_category"].isin(acts)]
    d = d.sort_values(SORTABLE[key], ascending=asc)
    st.caption(f"{len(d):,}곳 · 표의 순서는 선택한 정렬 기준일 뿐 위험 순위가 아닙니다.")
    st.dataframe(d[COLS].rename(columns=RENAME), width="stretch",
                 hide_index=True, height=430)
    st.download_button(f"{CLASS_LABEL[cls]} 목록 CSV 내려받기",
                       d[COLS].rename(columns=RENAME).to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{cls}_facilities.csv", mime="text/csv", key=f"dl_{cls}")


def render():
    fac = D.load_facilities_with_action()
    # 제목은 감싸는 expander 라벨이 대신한다
    st.caption("이동식 대기측정 후보지역 · 환경점검 우선 후보 · 추가 조사 필요지역 "
               "선정을 위한 탐색 화면입니다.")
    t1, t2 = st.tabs([f"반복적 고노출 패턴 ({int((fac.map_class=='stable_high').sum())})",
                      f"추가 확인 필요 ({int((fac.map_class=='sensitive').sum())})"])
    with t1:
        _view(fac[fac.map_class == "stable_high"], "stable_high")
    with t2:
        st.info("거리 및 weight 가정에 따라 판단이 달라 현장 확인 가치가 높은 시설입니다.")
        _view(fac[fac.map_class == "sensitive"], "sensitive")

    _action_overview(fac)


def _action_overview(fac):
    """행동 유형 분포와 rule 설명. 우선순위처럼 보이지 않게 한다."""
    st.divider()
    st.markdown("##### 다음 확인 제안 — 행동 유형 분포")
    st.caption(ACTION_NOTE)
    vc = fac["action_category"].value_counts()
    t = pd.DataFrame({"행동 유형": [a for a in ACTION_CATEGORIES if a in vc.index]})
    t["시설 수"] = t["행동 유형"].map(vc).astype(int)
    ev = st.dataframe(t, width="stretch", hide_index=True,
                      on_select="rerun", selection_mode="single-row",
                      key="action_dist")
    st.caption(f"합계 {int(t['시설 수'].sum()):,}곳 · 행을 클릭하면 그 행동이 제안된 "
               f"시설과 판단 근거가 나옵니다. {ACTION_CONTEXT_NOTE}")
    _action_drilldown(fac, t, ev)


AXIS_LABEL = {"distance": "거리", "air": "대기 등급", "waste": "폐기물",
              "no_axis_variation": "특정 축 없음"}
TOP10_CUT = 160          # 시나리오당 상위 10% = 1,605 × 0.10


def _judgement(row, drv):
    """모델 판단을 시설별 숫자로 풀어 쓴다.

    decision_rules 의 고정 문장은 rule 단위라 1,605곳에 9종류뿐이다.
    여기서는 그 시설의 실제 값만 쓴다(새 점수·분류를 만들지 않는다).
    """
    hits = int(round(float(row.get("top10pct_frequency") or 0) * 36))
    cls = row.get("map_class")
    out = []

    if cls == "stable_high":
        rmax = row.get("scenario_rank_max")
        t = "36개 가정 전부에서 상위 10%"
        if pd.notna(rmax):
            t += f", 가장 불리한 설정에서도 {int(rmax)}위로 컷({TOP10_CUT}위)보다 안쪽"
        out.append(t)
    elif cls == "sensitive":
        out.append(f"36개 중 {hits}번만 상위 10% — 가정에 따라 갈림")
    else:
        out.append("36개 가정 어디에서도 상위 10% 미포함" if hits == 0
                   else f"36개 중 {hits}번만 상위 10%")

    if drv is not None:
        ax = drv.get("dominant_sensitivity_axis")
        sh = drv.get("dominance_share")
        if isinstance(ax, str) and pd.notna(sh) and cls != "stable_high":
            out.append(f"갈림의 {float(sh) * 100:.0f}%가 {AXIS_LABEL.get(ax, ax)} 가정에서 발생")
        if ax == "distance":
            rates = [("buffer", drv.get("distance_top10_rate_buffer")),
                     ("감쇠150m", drv.get("distance_top10_rate_decay150")),
                     ("감쇠300m", drv.get("distance_top10_rate_decay300")),
                     ("감쇠500m", drv.get("distance_top10_rate_decay500"))]
            txt = " · ".join(f"{k} {float(v) * 100:.0f}%" for k, v in rates if pd.notna(v))
            if txt:
                out.append(f"거리 설정별 진입률 {txt}")
        if drv.get("distance_flip_driver") == "decay150_only":
            out.append("감쇠 150m에서만 빠짐 — 배출원이 대체로 300m 밖에 분포한다는 뜻")

    km = row.get("nearest_station_km")
    if pd.notna(km) and float(km) > 2.0:
        out.append(f"최근접 고정측정소가 {float(km):.1f}km로 실측 공백 구간")
    return ". ".join(out) + "."


DRILL_COLS = {
    "facility_name": "시설명", "facility_type": "시설유형", "gu": "행정구",
    "administrative_dong": "행정동", "_cls": "노출 분류",
    "primary_profile_label": "노출 유형",
    "nearest_source_distance_m": "최근접 배출원(m)",
    "source_locations_within_500m": "500m location",
    "air_emission_sites_within_500m": "500m 대기배출업소",
    "exposure_reason": "① 관측 사실",
    "_judgement": "② 모델 판단 (시설별)",
    "primary_rule_id": "rule",
}


def _action_drilldown(fac, t, ev):
    """행동 유형 한 줄을 고르면 그 행동이 붙은 시설과 근거를 펼친다."""
    rows = (getattr(ev, "selection", None) or {}).get("rows") or []
    if not rows:
        return
    try:
        cat = t["행동 유형"].iloc[int(rows[0])]
    except (ValueError, TypeError, IndexError):
        return
    d = fac[fac["action_category"] == cat].copy()
    if d.empty:
        st.caption("해당 행동 유형의 시설이 없습니다.")
        return

    st.markdown(f"**{cat}** — {len(d):,}곳")
    by_rule = (d.groupby(["primary_rule_id", "primary_action", "primary_reason"],
                         dropna=False).size().reset_index(name="시설 수")
                 .sort_values("시설 수", ascending=False))
    st.caption("적용된 rule과 근거")
    st.dataframe(by_rule.rename(columns={"primary_rule_id": "rule",
                                         "primary_action": "제안 행동",
                                         "primary_reason": "근거"}),
                 width="stretch", hide_index=True)

    d["_cls"] = d["map_class"].map(CLASS_LABEL).fillna(d["map_class"])
    drv = D.load_sensitivity_drivers()
    d["_judgement"] = [
        _judgement(r, drv.loc[r["facility_id"]] if r["facility_id"] in drv.index else None)
        for _, r in d.iterrows()]
    cols = [c for c in DRILL_COLS if c in d.columns]
    st.caption("해당 시설 목록")
    st.dataframe(d[cols].rename(columns=DRILL_COLS),
                 width="stretch", hide_index=True, height=300)
    st.caption("① 관측 사실 → ② 모델 판단 → ③ 제안 행동(위 rule 표) 순으로 읽습니다. "
               "②는 그 시설의 실제 값으로 생성하며 새 점수·분류를 만들지 않습니다.")
    st.caption("행동 제안은 취약시설에 부여됩니다. 특정 사업장에 대한 조치 지시가 아닙니다.")


