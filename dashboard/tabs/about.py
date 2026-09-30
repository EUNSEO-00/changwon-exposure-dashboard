"""탭 6 — 프로젝트 소개 · 분석 방법 · 한계."""

import streamlit as st

from utils import data as D
from utils.paths import PATHS
from utils.text import (CORE_QUESTION, DISCLAIMER, LIMITS, PIPELINE_STEPS,
                        PROHIBITED_INTERPRETATIONS, PROJECT_TITLE, SCORE_NAME,
                        SITE_LOCATION_NOTE)


def render():
    st.markdown(f"#### {PROJECT_TITLE}")
    st.caption(f"산출 지표명 — **{SCORE_NAME}**")
    st.info(f"**핵심 질문**  \n{CORE_QUESTION}")
    st.markdown(
        "이 시스템은 실제 오염도·건강피해·위법 사업장을 판정하지 않습니다. "
        "산업·배출시설과 **공간적으로 가까운 취약시설**을 찾아 "
        "**추가 측정·점검의 우선 후보**를 제시합니다.")

    st.markdown("##### 분석 흐름")
    for title, desc in PIPELINE_STEPS:
        with st.expander(title, expanded=False):
            st.write(desc)

    st.markdown("##### 핵심 설계 — 사업장(site)과 물리적 위치(location) 분리")
    st.write(SITE_LOCATION_NOTE)

    st.markdown("##### 결과 활용 범위")
    c1, c2 = st.columns(2)
    c1.success("**활용 가능**\n\n"
               "- 이동식 대기측정 후보지역\n"
               "- 환경점검 우선 후보\n"
               "- 추가 조사 필요지역\n"
               "- 취약시설 주변 환경관리 검토\n"
               "- 측정망 보완 후보")
    c2.error("**사용하지 않는 해석**\n\n"
             + "\n".join(f"- {x}" for x in PROHIBITED_INTERPRETATIONS))

    st.markdown("##### 반드시 함께 읽어야 할 한계")
    for x in LIMITS:
        st.markdown(f"- {x}")

    st.markdown("##### 사용 데이터 파일")
    rows = [{"키": k, "경로": str(p.relative_to(PATHS['facility_candidates'].parents[3])),
             "존재": "✅" if p.exists() else "❌"} for k, p in PATHS.items()]
    st.dataframe(rows, width="stretch", hide_index=True)
    st.caption("대시보드는 위 파일을 **읽기만** 하며 분석 결과를 수정하지 않습니다.")

    st.markdown("##### 정밀 거리 분석에서 제외된 취약시설")
    ex = D.load_excluded()
    st.write(f"총 **{len(ex)}건** — {ex['facility_type'].value_counts().to_dict()}")
    st.caption("동 중심점 좌표(geo_level=dong)라 건물 단위 거리 계산에 쓸 수 없는 시설입니다. "
               "삭제하지 않고 보존하며, 동 단위 집계에는 포함됩니다.")
    st.dataframe(ex[["facility_id", "facility_name", "facility_type", "gu",
                     "administrative_dong", "geo_level"]],
                 width="stretch", hide_index=True, height=240)
    st.caption(DISCLAIMER)
