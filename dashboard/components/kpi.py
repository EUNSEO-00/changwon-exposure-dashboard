"""상단 KPI 카드 — 숫자는 전부 실제 CSV에서 계산한다(하드코딩 금지)."""

import streamlit as st

from utils import data as D
from utils.text import CLASS_MEANING, SCORE_NAME


def compute_kpis() -> dict:
    fac = D.load_facilities()
    vc = fac["map_class"].value_counts()
    return {
        "analyzed": len(fac),
        "stable_high": int(vc.get("stable_high", 0)),
        "sensitive": int(vc.get("sensitive", 0)),
        "other": int(vc.get("other", 0)),
        "excluded": len(D.load_excluded()),
    }


def render():
    k = compute_kpis()
    # 실측 대기질 검증 탭을 내리면서 측정소 카드도 뺐다(갈 곳이 없는 지표였다).
    c = st.columns(5)
    c[0].metric("정밀 공간분석 취약시설", f"{k['analyzed']:,}",
                help="좌표가 건물 단위로 확보된 어린이집·경로당·지역아동센터·장애인복지관")
    c[1].metric("반복적 고노출 패턴", f"{k['stable_high']:,}",
                help=CLASS_MEANING["stable_high"])
    c[2].metric("추가 확인 필요", f"{k['sensitive']:,}",
                help=CLASS_MEANING["sensitive"])
    c[3].metric("반복 상위 노출군 미포함", f"{k['other']:,}",
                help=CLASS_MEANING["other"])
    c[4].metric("정밀거리 분석 제외", f"{k['excluded']:,}",
                help="동 중심점 좌표 등으로 정밀 거리 계산에서 제외(삭제하지 않고 보존)")
    st.caption(
        f"지표명: **{SCORE_NAME}** — "
        f"‘반복적 고노출 패턴 {k['stable_high']:,}곳’은 다양한 모델 가정에서도 반복적으로 "
        "높은 공간 노출을 보인 시설을 뜻하며, 오염이나 피해가 확인된 시설이 아닙니다."
    )
