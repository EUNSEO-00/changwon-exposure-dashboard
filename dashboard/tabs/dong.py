"""탭 2 — 행정동 관리현황 (choropleth). 조인 키는 h_code(adm_cd)."""

import pandas as pd
import pydeck as pdk
import streamlit as st

from utils import data as D
from utils.text import DISCLAIMER

METRICS = {
    "stable_high_facility_count": "반복적 고노출 패턴 시설 수",
    "sensitive_facility_count": "추가 확인 필요 시설 수",
    "vulnerable_facility_count": "전체 취약시설 수",
    "source_location_count": "배출원 위치(location) 수",
    "air_emission_site_count": "대기 배출업소 수",
}

# 지도에서 고른 행정동. 지도 클릭과 아래 드롭다운이 이 키 하나를 공유한다.
DONG_SEL_KEY = "dong_selected_hcode"
DONG_PICK_KEY = "dong_pick_idx"
LAYER_ID = "dong_poly"

SELECTED_FILL = [211, 47, 47, 205]      # 선택된 행정동 — 빨강
SELECTED_LINE = [140, 20, 20, 255]
DEFAULT_LINE = [80, 80, 90, 200]


def _apply_dong_click(ev):
    """지도 클릭을 선택 상태에 반영한다. 바뀐 경우에만 rerun."""
    objs = (getattr(ev, "selection", None) or {}).get("objects") or {}
    rows = objs.get(LAYER_ID) or []
    if not rows:
        return
    o = rows[0]
    code = o.get("adm_cd")
    if code is None:
        code = (o.get("properties") or {}).get("adm_cd")
    if code is None:
        return
    if str(code) != str(st.session_state.get(DONG_SEL_KEY) or ""):
        st.session_state[DONG_SEL_KEY] = str(code)
        st.rerun()


def render():
    prof = D.load_dong_profile()
    st.markdown("#### 행정동 관리현황")
    st.caption("행정동 경계와 지표는 **h_code(adm_cd)** 로 조인합니다. "
               "법정동과 행정동 이름이 달라 이름 조인은 사용하지 않습니다.")


    metric = st.selectbox("지도에 표시할 지표", list(METRICS), format_func=METRICS.get)
    # 선택 대상 목록을 지도보다 먼저 만든다(선택된 동을 빨갛게 칠해야 하므로).
    cw = prof[prof["administrative_dong"].notna()].sort_values(
        metric, ascending=False).reset_index(drop=True)
    codes = cw["h_code"].astype(str).tolist()
    if str(st.session_state.get(DONG_SEL_KEY) or "") not in codes:
        st.session_state[DONG_SEL_KEY] = codes[0] if codes else ""
    sel_code = str(st.session_state.get(DONG_SEL_KEY) or "")

    # cache_data 는 호출마다 복사본을 주므로 여기서 색을 덮어써도 캐시가 오염되지 않는다.
    gj = D.boundary_with_metric(metric)
    for feat in gj["features"]:
        pr = feat["properties"]
        picked = str(pr.get("adm_cd")) == sel_code
        pr["_line"] = SELECTED_LINE if picked else DEFAULT_LINE
        if picked:
            pr["_fill"] = SELECTED_FILL

    left, right = st.columns([3, 2])
    with left:
        ev = st.pydeck_chart(pdk.Deck(
            layers=[pdk.Layer(
                "GeoJsonLayer", data=gj, pickable=True, stroked=True, filled=True,
                get_fill_color="properties._fill",
                get_line_color="properties._line", line_width_min_pixels=1,
                auto_highlight=True, id=LAYER_ID)],
            initial_view_state=pdk.ViewState(latitude=35.2280, longitude=128.6300,
                                             zoom=9.7, min_zoom=6.4, max_zoom=14,
                                             pitch=0),
            map_style=None,
            tooltip={"html": "<b>{emd}</b> ({gu})<br/>"
                             + METRICS[metric] + ": {_metric}"
                             "<br/>취약시설 {vulnerable_facility_count} · "
                             "반복 고노출 {stable_high_facility_count}"}),
            width="stretch", height=560,
            on_select="rerun", selection_mode="single-object",
            key=f"dong_map_{metric}")
        _apply_dong_click(ev)
        st.caption("행정동을 클릭하면 **빨간색**으로 표시되고 오른쪽에 상세가 나옵니다. "
                   "나머지 색은 진할수록 선택한 지표 값이 큽니다 — 위험/안전을 뜻하지 않습니다.")

    with right:
        st.markdown("##### 행정동 선택")
        names = cw.apply(lambda r: f"{r['gu']} {r['administrative_dong']}", axis=1)
        idx = codes.index(sel_code) if sel_code in codes else 0

        def _on_pick():
            st.session_state[DONG_SEL_KEY] = codes[st.session_state[DONG_PICK_KEY]]

        # 지도 클릭으로 바뀐 선택을 드롭다운도 가리키게 맞춘다.
        # (이 줄이 없으면 위젯에 남은 옛 값이 클릭 결과를 되돌린다)
        st.session_state[DONG_PICK_KEY] = idx
        i = st.selectbox("행정동", range(len(cw)), format_func=lambda k: names.iloc[k],
                         key=DONG_PICK_KEY, on_change=_on_pick)
        r = cw.iloc[i]

        st.markdown(f"### {r['administrative_dong']}")
        st.caption(f"{r['gu']} · 면적 {r['area_km2']:.2f} km² · h_code {r['h_code']}")
        c = st.columns(3)
        c[0].metric("취약시설 수", f"{int(r['vulnerable_facility_count']):,}")
        c[1].metric("반복적 고노출 패턴", f"{int(r['stable_high_facility_count']):,}")
        c[2].metric("추가 확인 필요", f"{int(r['sensitive_facility_count']):,}")
        c = st.columns(3)
        c[0].metric("배출원 위치(location) 수", f"{int(r['source_location_count']):,}")
        c[1].metric("대기 배출업소 수", f"{int(r['air_emission_site_count']):,}")
        c[2].metric("지정폐기물 배출사업장 수", f"{int(r['designated_waste_site_count']):,}")

    st.markdown("##### 행정동 표 (반복적 고노출 패턴 시설 보유 동)")
    cols = ["gu", "administrative_dong", "vulnerable_facility_count",
            "stable_high_facility_count", "sensitive_facility_count",
            "source_location_count", "air_emission_site_count",
            "designated_waste_site_count", "median_nearest_source_m"]
    t = prof[prof["stable_high_facility_count"] > 0][cols].sort_values(
        "stable_high_facility_count", ascending=False)
    st.dataframe(t, width="stretch", hide_index=True)
    st.caption(DISCLAIMER)
