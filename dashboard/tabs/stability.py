"""탭 3 — 모델 안정성 (36개 시나리오)."""

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import data as D
from utils.text import CLASS_HEX, CLASS_LABEL, CLASS_MEANING, DISCLAIMER


def _frequency_chart(fac):
    """반복성 분포. 가로축은 0~1 소수가 아니라 '36개 중 진입 횟수' 정수로 쓴다.

    0회가 1,300곳을 넘어 그대로 그리면 축이 거기에 맞춰져 나머지가 바닥에 깔린다.
    빼지 않고 **세로축을 잘라(axis break)** 표시한다. 잘린 지점에 물결 표시를 넣고
    실제 값은 막대 위 라벨과 hover 에 그대로 남긴다.
    """
    YCLIP = 95                       # 0회를 뺀 나머지 최대값(74)보다 조금 위
    hits = (fac["top10pct_frequency"] * 36).round().astype(int)
    d = fac.assign(_hits=hits)
    zero = int((hits == 0).sum())
    n35 = int((hits == 35).sum())

    st.markdown("##### 반복성 분포 — 36개 가정 중 몇 번 상위 10%에 들었나")

    cnt = (d.groupby(["_hits", "map_class"]).size().reset_index(name="시설 수"))
    fig = px.bar(cnt, x="_hits", y="시설 수", color="map_class", barmode="stack",
                 color_discrete_map=CLASS_HEX,
                 category_orders={"map_class": ["stable_high", "sensitive", "other"]},
                 labels={"_hits": "36개 가정 중 상위 10% 진입 횟수",
                         "시설 수": "시설 수", "map_class": "노출 분류"})

    # --- 0회 막대 축 잘림 표시 (물결) ---------------------------------------
    xs = (-0.45, -0.225, 0.0, 0.225, 0.45)
    for lo, hi in ((83, 88), (87, 92)):
        path = (f"M {xs[0]},{lo} L {xs[1]},{hi} L {xs[2]},{lo} "
                f"L {xs[3]},{hi} L {xs[4]},{lo}")
        fig.add_shape(type="path", path=path, xref="x", yref="y",
                      line=dict(color="#ffffff", width=3), layer="above")
    fig.add_annotation(x=0, y=YCLIP * 0.96, text=f"<b>{zero:,}</b>", showarrow=False,
                       font=dict(size=13, color="#4a5260"), yanchor="top")
    fig.add_annotation(x=2.6, y=YCLIP * 0.72, ax=48, ay=0, showarrow=True, arrowhead=2,
                       text=f"세로축을 잘랐습니다<br>실제 {zero:,}곳", align="left",
                       font=dict(size=11))

    # --- 분류 임계선 ---------------------------------------------------------
    fig.add_vline(x=1.5, line_dash="dot", line_width=1.5, line_color="#8a8a8a",
                  annotation_text="5% 경계 · 1회 이하", annotation_position="top right",
                  annotation_font_size=11)
    fig.add_vline(x=34.5, line_dash="dot", line_width=1.5, line_color="#8a8a8a",
                  annotation_text="95% 경계 · 35회 이상", annotation_position="top left",
                  annotation_font_size=11)
    fig.add_annotation(x=35, y=46, ax=-70, ay=-25, showarrow=True, arrowhead=2,
                       text=f"35/36 = <b>{n35}곳</b><br>임계값 바로 위가 비어 있다",
                       font=dict(size=11), align="left")

    fig.update_layout(height=430, bargap=0.15, legend_title_text="노출 분류",
                      xaxis=dict(dtick=5, tick0=0, range=[-0.7, 36.7]),
                      yaxis=dict(range=[0, YCLIP]))
    fig.update_traces(hovertemplate="36개 중 %{x}회<br>%{y:,}곳<extra></extra>")
    st.plotly_chart(fig, width="stretch")


AXIS_ROWS = [("distance", "거리"), ("waste", "폐기물"), ("air", "대기 등급")]
AXIS_BAR = "#6b7a8c"


def _axis_impact_chart():
    """축 하나만 바꿨을 때 순위가 얼마나 움직였나.

    분류 색(주황·노랑·회색)을 쓰지 않는다. 노출 분류와 무관한 지표라
    같은 색을 쓰면 분류로 오독된다.
    """
    drv = D.load_sensitivity_drivers()
    rows = [{"축": lab, "순위 변동폭": float(drv[f"{k}_rank_swing"].median())}
            for k, lab in AXIS_ROWS if f"{k}_rank_swing" in drv.columns]
    if not rows:
        return
    df = pd.DataFrame(rows).sort_values("순위 변동폭")

    st.markdown("##### 어느 가정이 결과를 흔드나")
    fig = px.bar(df, x="순위 변동폭", y="축", orientation="h",
                 text=df["순위 변동폭"].round(1),
                 labels={"순위 변동폭": "축 하나만 바꿨을 때 순위가 움직인 폭 (중앙값)",
                         "축": ""})
    fig.update_traces(marker_color=AXIS_BAR, textposition="outside",
                      cliponaxis=False,
                      hovertemplate="%{y}<br>순위 변동폭 중앙 %{x:.1f}<extra></extra>")
    fig.update_layout(height=260, showlegend=False,
                      xaxis=dict(range=[0, df["순위 변동폭"].max() * 1.18]),
                      margin=dict(t=10, b=10))
    st.plotly_chart(fig, width="stretch")


def render():
    fac = D.load_facilities()
    vc = fac["map_class"].value_counts()

    st.markdown("#### 모델 안정성 — 36개 시나리오")
    st.caption(
        "대기 weight 3종 × 거리 4종 × 지정폐기물 배수 3종 = 36개 가정 조합에서 "
        "각 시설이 상위 10% 노출군에 몇 번 포함되는지를 측정했습니다. "
        "단일 위험 순위표를 만들지 않는 이유는, 상위 5%만 보면 시나리오 간 겹침이 "
        "최소 40%까지 떨어지기 때문입니다.")

    with st.container(border=True):
        st.markdown("##### 분류 요약")
        c = st.columns(3)
        for i, k in enumerate(["stable_high", "sensitive", "other"]):
            c[i].metric(f"{k} · {CLASS_LABEL[k]}", f"{int(vc.get(k,0)):,}",
                        help=CLASS_MEANING[k])
        fixed = int(vc.get("stable_high", 0)) + int(vc.get("other", 0))
        st.info(f"전체 {len(fac):,}곳 중 **{fixed:,}곳({fixed/len(fac)*100:.0f}%)** 은 "
                f"어떤 가정을 쓰더라도 분류가 바뀌지 않습니다. "
                f"판단이 갈리는 시설은 **{int(vc.get('sensitive',0)):,}곳**입니다.")

    with st.container(border=True):
        _frequency_chart(fac)

    with st.container(border=True):
        _axis_impact_chart()

    with st.container(border=True):
        st.markdown("##### 시설 유형별 구성")
        comp = (fac.groupby(["facility_type", "map_class"]).size()
                .reset_index(name="count"))
        fig = px.bar(comp, x="facility_type", y="count", color="map_class",
                     barmode="stack",
                     category_orders={"map_class": ["stable_high", "sensitive", "other"]},
                     color_discrete_map=CLASS_HEX,
                     labels={"facility_type": "시설 유형", "count": "시설 수",
                             "map_class": "노출 분류"})
        fig.update_layout(height=340)
        st.plotly_chart(fig, width="stretch")

    st.caption(DISCLAIMER)
