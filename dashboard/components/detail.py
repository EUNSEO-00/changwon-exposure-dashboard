"""시설 상세 패널.

테두리 칸을 주제별로 다섯 개 쌓았더니, 같은 숫자가 여러 칸에 되풀이되면서
화면이 어수선해졌다(300m 배출원 개수가 '주변 배출원' 칸 · '노출 근거' 문장 ·
아래 반경별 표에 세 번 나왔다).

그래서 **테두리는 하나만 두고 안을 요약/상세 탭으로 나눈다.**
  요약 — 왜 이 분류인지 + 얼마나 가까운지. 처음 보는 사람이 필요한 것만.
  상세 — 배출 특성별 내역과 문장 근거.
반경별 전체 수치는 지도 아래 넓은 표가 담당하므로 여기서 다시 늘어놓지 않는다.
"""

import pandas as pd
import streamlit as st

from utils.text import CLASS_ACTION_HINT, CLASS_LABEL, CLASS_MEANING

from utils import data as D

# 오른쪽 상세 패널 컨테이너의 CSS 키. overview.py가 이 키로 높이를 맞춘다.
PANEL_KEY = "ov_detail"


def render(row: pd.Series):
    """오른쪽 상세 패널. 테두리 하나 + 요약/상세 탭.

    면책 문구는 여기서 띄우지 않는다. 좁은 칸에 경고 박스를 넣으면 그만큼 칸이
    길어져 왼쪽 지도와 높이가 어긋난다. 다른 탭처럼 페이지 맨 아래에 한 번만 둔다.
    """
    # key는 overview.py의 CSS가 이 칸을 왼쪽 높이에 맞추고 글자 크기를 줄이는 데 쓴다.
    with st.container(border=True, key=PANEL_KEY):
        _header(row)
        _scenario(row)
        _sources(row)
        _emission_types(row)
        _reason(row)


def _header(row: pd.Series):
    """시설이 무엇인지. 탭을 바꿔도 항상 보이도록 탭 바깥에 둔다."""
    st.subheader(f"{row['facility_name']}")
    cls = row["map_class"]
    st.markdown(
        f"{row['facility_type']} · {row.get('gu') or '-'} · "
        f"{row.get('administrative_dong') or '-'} · **{CLASS_LABEL.get(cls, cls)}**")
    st.caption(f"분류 의미 — {CLASS_MEANING.get(cls, '')}")


def _scenario(row: pd.Series):
    """분류 근거. 빈도는 뺄 수 없다.

    주황/노랑/회색을 가른 유일한 기준이라 이걸 빼면 분류 근거가 화면에서 사라진다.
    """
    hits = int(round(float(row["top10pct_frequency"]) * 36))
    c = st.columns([1, 2])
    c[0].metric("36개 가정 중 상위 노출", f"{hits} / 36",
                help="거리·대기등급·지정폐기물 가정을 바꿔 가며 36번 계산했을 때 "
                     "상위 10% 노출군에 들어온 횟수입니다.")
    c[1].markdown(CLASS_ACTION_HINT.get(row["map_class"], ""))


def _sources(row: pd.Series):
    st.markdown("**주변 배출원** (물리적 위치 기준)")
    c = st.columns(4)
    # '물리적 위치 기준'이므로 최근접 거리도 location 컬럼을 쓴다.
    # (site 기준 값과는 1,605곳 중 2곳만, 최대 2m 다르다)
    d = row.get("nearest_source_location_distance_m")
    if pd.isna(d):
        d = row.get("nearest_source_distance_m")
    c[0].metric("최근접", f"{d:,.0f} m" if pd.notna(d) else "1km 내 없음")
    c[1].metric("300m 이내", f"{int(row['source_locations_within_300m']):,}")
    c[2].metric("500m 이내", f"{int(row['source_locations_within_500m']):,}")
    c[3].metric("1,000m 이내", f"{int(row['source_locations_within_1000m']):,}")


def _emission_types(row: pd.Series):
    st.markdown("**500m 이내 배출 특성별**")
    c = st.columns(4)
    c[0].metric("대기 배출업소", f"{int(row['air_emission_sites_within_500m']):,}")
    c[1].metric("지정폐기물", f"{int(row['designated_waste_sites_within_500m']):,}")
    c[2].metric("소각 관련", f"{int(row['incineration_sites_within_500m']):,}")
    c[3].metric("공장", f"{int(row['factory_sites_within_500m']):,}")


def _reason(row: pd.Series):
    """문장 근거 + 맥락. 카드 아래 남는 공간을 이걸로 채운다."""
    st.markdown("**노출 근거**")
    st.info(row["exposure_reason"])
    st.caption("반경별 전체 수치는 아래 ‘반경별 배출원 집계’ 표에서 봅니다.")


RADIUS_ROWS = [("source_locations", "배출원 위치"), ("source_sites", "사업장"),
               ("factory_sites", "공장"), ("air_emission_sites", "대기 배출업소"),
               ("designated_waste_sites", "지정폐기물"), ("incineration_sites", "소각")]


def render_radius_table(row: pd.Series):
    """반경별 집계 + 칸 클릭 드릴다운.

    상세 패널(오른쪽 좁은 칸)이 아니라 지도 아래 넓은 칸에서 부른다.
    표가 6행 × 4열이고 드릴다운 목록에 주소가 들어가 폭이 필요하다.
    """
    feats = D.load_radius_features()
    fid = row["facility_id"]
    if fid not in feats.index:
        return
    f = feats.loc[fid]
    data = {"지표": [], "300m": [], "500m": [], "1,000m": []}
    for prefix, label in RADIUS_ROWS:
        cols = [f"{prefix}_within_{r}m" for r in (300, 500, 1000)]
        if not all(c in f.index for c in cols):
            continue
        data["지표"].append(label)
        for key, c in zip(("300m", "500m", "1,000m"), cols):
            data[key].append(int(f[c]) if pd.notna(f[c]) else 0)
    if not data["지표"]:
        return
    table = pd.DataFrame(data)
    with st.container(border=True):
        st.markdown(f"##### 반경별 배출원 집계 — {row['facility_name']}")
        ev = st.dataframe(table, width="stretch", hide_index=True,
                          on_select="rerun", selection_mode="single-cell",
                          key=f"radius_tbl_{fid}")
        st.caption("칸을 클릭하면 그 반경의 배출원 목록이 아래에 나옵니다. "
                   "배출원 위치는 location, 나머지는 사업장(site) 기준입니다.")
        _drilldown(row, table, ev)


def _parse_cell(ev):
    """선택 페이로드에서 (행 위치, 열 이름)을 뽑는다. 버전별 모양 차이를 흡수한다."""
    sel = getattr(ev, "selection", None) or {}
    cells = sel.get("cells") or []
    if cells:
        c = cells[0]
        if isinstance(c, dict):
            return c.get("row"), c.get("column")
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            return c[0], c[1]
    rows, cols = sel.get("rows") or [], sel.get("columns") or []
    return (rows[0] if rows else None), (cols[0] if cols else None)


def _drilldown(row, table, ev):
    r_pos, col = _parse_cell(ev)
    if r_pos is None or not col or col == "지표":
        return
    radius = {"300m": 300, "500m": 500, "1,000m": 1000}.get(str(col))
    if radius is None:
        return
    try:
        label = table["지표"].iloc[int(r_pos)]
    except (ValueError, TypeError, IndexError):
        return
    prefix = next((p for p, lab in RADIUS_ROWS if lab == label), None)
    if prefix is None:
        return

    sub = D.sources_within(row["latitude"], row["longitude"], radius, prefix)
    total = int(table.loc[table["지표"] == label, col].iloc[0])
    st.markdown(f"**{radius:,}m 이내 · {label} {total:,}** — 배출원 위치 {len(sub)}곳")
    if prefix != "source_locations" and len(sub) != total:
        st.caption("집계는 사업장(site) 수, 목록은 그 사업장이 있는 물리적 위치(location)입니다. "
                   "한 위치에 여러 사업장이 입주해 있어 두 숫자는 다를 수 있습니다.")
    if sub.empty:
        st.caption("해당 조건에 맞는 배출원이 없습니다.")
        return

    def tags(r):
        t = []
        if r.get("has_air_emission"): t.append("대기")
        if r.get("has_water_emission"): t.append("폐수")
        if r.get("has_designated_waste"): t.append("지정폐")
        if r.get("has_incineration"): t.append("소각")
        return " · ".join(t) or "-"

    view = pd.DataFrame({
        "거리(m)": sub["distance_m"],
        "주소": sub["address_clean"].astype(str).str.slice(0, 40),
        "사업장": sub["site_count"].fillna(0).astype(int),
        "공장": sub["factory_site_count"].fillna(0).astype(int),
        "배출 특성": [tags(r) for _, r in sub.iterrows()],
    })
    st.dataframe(view, width="stretch", hide_index=True, height=230)
