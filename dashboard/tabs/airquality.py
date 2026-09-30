"""탭 4 — AirKorea 실측 대기질 검증축."""

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from utils import data as D
from utils.text import AIRQ_NOTE, CASE_MESSAGE, DISCLAIMER

POLL = {"pm10_mean": "PM10 (㎍/㎥)", "pm25_mean": "PM2.5 (㎍/㎥)",
        "no2_mean": "NO2 (ppm)", "so2_mean": "SO2 (ppm)",
        "co_mean": "CO (ppm)", "o3_mean": "O3 (ppm)"}
DENS = {"source_locations_within_1000m": "1km 내 배출원 위치 수",
        "source_sites_within_1000m": "1km 내 사업장(site) 수",
        "air_emission_sites_within_1000m": "1km 내 대기 배출업소 수",
        "factory_area_sum_within_1000m": "1km 내 공장면적 합(㎡)"}


def render():
    v = D.load_air_validation()
    st.markdown("#### 실측 대기질 검증 (AirKorea)")
    st.warning(AIRQ_NOTE)
    st.caption("출처: 한국환경공단 에어코리아 대기오염정보 OpenAPI · "
               "창원 10개 도시대기 측정소 · 최근 3개월 실측 21,793 시간자료")

    left, right = st.columns([3, 2])
    metric = right.selectbox("지도 크기로 표시할 지표", list(POLL), format_func=POLL.get)

    d = v.copy()
    m = d[metric]
    d["_r"] = 300 + 900 * (m - m.min()) / max(m.max() - m.min(), 1e-9)
    with left:
        st.pydeck_chart(pdk.Deck(
            layers=[pdk.Layer(
                "ScatterplotLayer", data=d, get_position=["longitude", "latitude"],
                get_radius="_r", get_fill_color=[46, 134, 171, 175],
                get_line_color=[20, 60, 90, 220], stroked=True, filled=True,
                line_width_min_pixels=1.5, radius_min_pixels=8, radius_max_pixels=36,
                pickable=True)],
            initial_view_state=pdk.ViewState(latitude=35.2100, longitude=128.6200,
                                             zoom=10.2),
            map_style=None,
            tooltip={"html": "<b>{station_name}</b> ({sigungu})<br/>"
                             "PM10 {pm10_mean} · PM2.5 {pm25_mean}<br/>"
                             "NO2 {no2_mean} · SO2 {so2_mean}<br/>"
                             "1km 배출원 위치 {source_locations_within_1000m}"}),
            width="stretch", height=470)
        st.caption("원 크기 = 선택 지표 값. 측정소는 도시 생활권 대표를 목적으로 설치되며 "
                   "배출원 최근접 지점을 겨냥하지 않습니다.")

    with right:
        st.markdown("##### 측정소별 실측 기간평균과 주변 밀도")
        cols = ["station_name"] + list(POLL) + list(DENS)
        st.dataframe(v[cols].sort_values("source_locations_within_1000m", ascending=False),
                     width="stretch", hide_index=True, height=400)

    st.markdown("##### 주변 배출원 밀도 × 실측 농도 (탐색적)")
    c1, c2 = st.columns([2, 3])
    dm = c1.selectbox("밀도 지표", list(DENS), format_func=DENS.get)
    pm = c1.selectbox("오염물질", list(POLL), format_func=POLL.get, index=2)
    corr = D.load_station_correlation()
    hit = corr[(corr.density_metric == dm) & (corr.pollutant == pm.replace("_mean", ""))]
    if len(hit):
        h = hit.iloc[0]
        c1.metric("Spearman ρ", f"{h.spearman_rho:+.3f}", help=f"p = {h.p_value:.3f}, n = {h.n}")
    c1.caption("n=10 표본입니다. 42개 조합을 검정했고 Bonferroni 보정 시 유의 조합이 "
               "남지 않습니다. **탐색적 관찰이며 인과관계를 의미하지 않습니다.**")
    fig = px.scatter(v, x=dm, y=pm, text="station_name",
                     labels={dm: DENS[dm], pm: POLL[pm]})
    fig.update_traces(textposition="top center", marker=dict(size=13, color="#2e86ab"))
    fig.update_layout(height=380)
    c2.plotly_chart(fig, width="stretch")

    st.markdown("---")
    st.markdown("##### 사례 비교 — 봉암동 · 웅남동")
    st.info(f"**{CASE_MESSAGE}**")
    two = v[v.station_name.isin(["봉암동", "웅남동"])].set_index("station_name")
    if len(two) == 2:
        a, b = st.columns(2)
        for col, name, desc in ((a, "봉암동", "1km 대기 배출업소 밀도가 높은 측정소"),
                                (b, "웅남동", "공장면적·종업원·site 규모가 매우 큰 측정소")):
            r = two.loc[name]
            col.markdown(f"**{name}** — {desc}")
            col.metric("1km 내 대기 배출업소", f"{int(r.air_emission_sites_within_1000m):,}")
            col.metric("1km 내 배출원 위치(location)", f"{int(r.source_locations_within_1000m):,}")
            col.metric("1km 내 사업장(site)", f"{int(r.source_sites_within_1000m):,}")
            col.metric("1km 내 공장면적 합", f"{r.factory_area_sum_within_1000m:,.0f} ㎡")
            col.markdown(
                f"NO2 **{r.no2_mean:.4f}** · SO2 **{r.so2_mean:.4f}** · "
                f"CO **{r.co_mean:.3f}**  \nPM10 {r.pm10_mean:.2f} · PM2.5 {r.pm25_mean:.2f}")
        ratio_b = two.loc["봉암동", "source_sites_within_1000m"] / max(
            two.loc["봉암동", "source_locations_within_1000m"], 1)
        ratio_w = two.loc["웅남동", "source_sites_within_1000m"] / max(
            two.loc["웅남동", "source_locations_within_1000m"], 1)
        st.caption(
            f"봉암동은 site/location 배율 {ratio_b:.1f}, 웅남동은 {ratio_w:.1f}입니다. "
            "웅남동은 규모 지표에서 가장 크지만 연소 관련 물질(NO2·SO2·CO) 관측값은 "
            "봉암동이 더 높게 나타납니다. 측정값은 이동오염원·항만·난방·기상 등 여러 요인이 "
            "함께 반영된 결과이며, 특정 시설군의 기여로 해석하지 않습니다.")
    st.caption(DISCLAIMER)
