"""창원시 산업·배출시설 주변 취약계층 공간 노출 탐지 대시보드.

실행:  streamlit run dashboard/app.py

이 앱은 pes/·msh/·data/ 의 결과 파일을 **읽기만** 한다. 분석 결과를 수정하지 않고
새로운 weight·점수·순위·시나리오를 만들지 않는다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

from components import kpi  # noqa: E402
from tabs import dong, overview, stability  # noqa: E402
from utils.paths import PATHS, check  # noqa: E402
from utils.text import (CORE_QUESTION, PROJECT_SHORT, PROJECT_TITLE,  # noqa: E402
                        SCORE_NAME)

# 사이드바에 넣는 요소가 없다. 면책 문구는 각 탭 하단과 상세 패널에 그대로 있다.
st.set_page_config(page_title=PROJECT_SHORT, layout="wide",
                   initial_sidebar_state="collapsed")


# 탭을 가로 전체로 균등 분할한다.
# 탭 요소는 button 이 아니라 div[data-testid="stTab"] 이고, 감싸는 컨테이너에 key 를 줘
# st-key-<key> 클래스로 범위를 좁힌다(펼침 안의 하위 탭까지 늘어나면 어색하다).
MAIN_TABS_KEY = "main_tabs"
TAB_CSS = f"""
<style>
  .st-key-{MAIN_TABS_KEY} div[role="tablist"] {{
      display: flex;
      width: 100%;
      gap: 6px;
  }}
  .st-key-{MAIN_TABS_KEY} div[data-testid="stTab"] {{
      flex: 1 1 0;
      justify-content: center;
      padding: 12px 8px;
  }}
  .st-key-{MAIN_TABS_KEY} div[data-testid="stTab"] div[data-testid="stMarkdownContainer"] {{
      width: 100%;
      text-align: center;
  }}
  .st-key-{MAIN_TABS_KEY} div[data-testid="stTab"] p {{
      font-size: 1.02rem;
      font-weight: 600;
  }}

  /* 헤더 — 글자만 놓이지 않도록 띠와 배경을 준다.
     글자색은 지정하지 않는다(Streamlit 라이트/다크 테마를 그대로 따르게). */
  .app-header {{
      display: flex;
      gap: 16px;
      background: rgba(214, 96, 41, 0.07);
      border-radius: 10px;
      padding: 20px 24px;
      /* 아래 KPI 5칸과 너무 붙으면 제목과 숫자가 한 덩어리로 읽힌다. 띄워 둔다. */
      margin: 4px 0 40px;
  }}
  .app-header-accent {{
      flex: none;
      width: 4px;
      border-radius: 2px;
      background: #d66029;
  }}
  .app-eyebrow {{
      font-size: 0.76rem;
      font-weight: 700;
      letter-spacing: 0.09em;
      color: #d66029;
      margin-bottom: 7px;
  }}
  .app-title {{
      font-size: 1.85rem;
      font-weight: 700;
      line-height: 1.34;
      letter-spacing: -0.02em;
      margin: 0;
      word-break: keep-all;
  }}
  .app-sub {{
      font-size: 0.9rem;
      line-height: 1.6;
      opacity: 0.72;
      margin: 10px 0 0;
      word-break: keep-all;
  }}
</style>
"""


def main():
    missing = [k for k, ok in check().items() if not ok]
    if missing:
        st.error("필요한 데이터 파일을 찾지 못했습니다:\n\n"
                 + "\n".join(f"- `{k}` → `{PATHS[k]}`" for k in missing))
        st.stop()

    st.markdown(TAB_CSS, unsafe_allow_html=True)
    st.markdown(
        f'<div class="app-header">'
        f'<div class="app-header-accent"></div>'
        f'<div>'
        f'<div class="app-eyebrow">{SCORE_NAME}</div>'
        f'<h1 class="app-title">{PROJECT_TITLE}</h1>'
        f'<p class="app-sub">핵심 질문 — {CORE_QUESTION}</p>'
        f'</div></div>',
        unsafe_allow_html=True)
    kpi.render()
    st.divider()

    # 실측 대기질 검증·프로젝트 소개 탭은 화면에서 내렸다(보고서 부록으로 이관).
    # tabs/airquality.py, tabs/about.py 는 지우지 않고 남겨 둔다.
    # 환경관리 후보는 공간 노출 지도 페이지 하단으로 옮겼다(tabs/candidates.py 유지).
    # 민원은 시스템에서 제외했다. 시도 기록과 배제 사유는
    # archive/complaint_attempt/README.md 참고.
    with st.container(key=MAIN_TABS_KEY):
        t = st.tabs(["🗺 공간 노출 지도", "🏘 행정동 관리현황", "📊 모델 안정성"])
        with t[0]:
            overview.render()
        with t[1]:
            dong.render()
        with t[2]:
            stability.render()


if __name__ == "__main__":
    main()
