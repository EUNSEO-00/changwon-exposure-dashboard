# 창원시 산업·배출시설 주변 취약계층 공간 노출 탐지 대시보드

공모전 시연용 지도 기반 대시보드입니다.
`pes/`, `msh/`, `data/` 의 분석 결과를 **읽기만** 하며 어떤 파일도 수정하지 않습니다.
새로운 weight·위험점수·순위·시나리오를 만들지 않습니다.

산출 지표명: **산업·배출시설 공간 노출도**
이 시스템은 실제 오염도·건강피해·위법 사업장을 판정하지 않습니다.

---

## 설치

분석 파이프라인용 가상환경(`pes/.venv`)을 그대로 사용합니다.

```bash
cd ~/changwon-ai-data-competition
pes/.venv/bin/python -m pip install -r dashboard/requirements.txt
```

별도 환경을 쓰려면:

```bash
python3 -m venv .venv-dashboard
.venv-dashboard/bin/python -m pip install -r dashboard/requirements.txt
```

| 패키지 | 버전 | 용도 |
|---|---|---|
| streamlit | 1.64.0 | 앱 프레임워크 |
| pydeck | 0.9.3 | 지도(시설 산점도·buffer·행정동 choropleth) |
| plotly | 7.1.0 | 분포·상관 차트 |
| pandas / numpy | 2.3.3 / 2.2.6 | 데이터 처리 |

## 실행

```bash
streamlit run dashboard/app.py
```

또는 프로젝트 venv를 직접 지정:

```bash
pes/.venv/bin/python -m streamlit run dashboard/app.py
```

브라우저에서 `http://localhost:8501` 로 접속합니다.

### 숫자 검증

```bash
pes/.venv/bin/python dashboard/qa_check.py
```

파일 존재 · KPI 숫자 · h_code 조인 · 금지 표현 · 원본 무수정을 점검합니다.

---

## 데이터 경로

앱은 아래 파일을 읽습니다. 경로는 `dashboard/utils/paths.py` 한 곳에서 관리합니다.

| 키 | 경로 | 내용 |
|---|---|---|
| `facility_candidates` | `pes/output/final/facility_management_candidates.csv` | 취약시설 1,605 · 노출 분류 · 근거 |
| `dong_profile` | `pes/output/final/dong_management_profile.csv` | 행정동 55 집계 |
| `air_validation` | `pes/output/final/air_quality_validation.csv` | 측정소 10 · 실측 + 주변 밀도 |
| `location_master` | `pes/output/analysis/source_location_master_v2.csv` | 배출원 물리적 위치 2,740 |
| `site_master` | `pes/output/analysis/source_site_master_v2.csv` | 배출 사업장 4,767 |
| `facility_excluded` | `pes/output/spatial/facility_excluded_from_spatial.csv` | 정밀 분석 제외 45 |
| `station_summary` | `pes/output/air_quality/station_period_summary.csv` | 측정소 기간평균 |
| `station_correlation` | `pes/output/air_quality/station_density_correlation.csv` | 탐색적 Spearman |
| `stations` | `pes/output/air_quality/stations.csv` | 경남 측정소 37 |
| `facilities_raw` | `msh/data/processed/facilities.csv` | 팀원 A 취약시설 원본 |
| `dong_boundary` | `msh/data/processed/changwon_dong_boundary.geojson` | 행정동 경계 55 |

> 행정동 경계와 지표는 **`h_code`(GeoJSON의 `adm_cd`)** 로 조인합니다.
> 법정동과 행정동 이름이 79.2%에서 다르므로 **이름 조인은 사용하지 않습니다.**

---

## 화면 구성

상단에 KPI 카드 6개(정밀 분석 시설 1,605 / 반복적 고노출 74 / 추가 확인 필요 192 /
미포함 1,339 / 제외 45 / 측정소 10)가 항상 표시되고, 아래에 6개 탭이 있습니다.

### 🗺 공간 노출 지도
- 취약시설 1,605개를 지도에 표시. **색 = 노출 분류**, **테두리·크기 = 시설 유형**
- 사이드바 필터: 시설 유형 · 노출 분류 · 행정구 · 행정동 · 최근접 배출원 거리 ·
  300m/500m 배출원 위치 수
- 시설 선택 시 상세 패널(분류·시나리오 반복성·반경별 배출원 수·배출 특성별 수·노출 근거)
- **buffer 토글** 300 / 500 / 1,000m
- 선택 시설 **주변 1km 배출원만** 렌더링(전체 2,740개를 그리지 않음)
- 하단 expander: 사업장(site) vs 물리적 위치(location) 비교

### 🏘 행정동 관리현황
- choropleth 지표 선택: 반복 고노출 시설 수 / 추가 확인 필요 수 / 전체 취약시설 수 /
  배출원 위치 수 / 대기 배출업소 수
- 행정동 선택 시 상세(취약시설·분류별 수·배출원·지정폐기물·민원)
- 민원 옆에 "위험도 계산에 사용하지 않은 지역 맥락 정보" 표기

### 📊 모델 안정성
- 36개 시나리오에서 분류가 얼마나 안정적인지
- `top10pct_frequency` 히스토그램, `scenario_rank_std` 박스플롯, 유형별 구성 막대
- 단일 위험 순위표를 만들지 않습니다

### 🌫 실측 대기질 검증
- 창원 AirKorea 측정소 10곳 지도(원 크기 = 선택 오염물질 기간평균)
- 측정소별 PM10·PM2.5·NO2·SO2·CO·O3 3개월 평균 + 주변 1km 밀도
- 밀도 × 농도 산점도와 탐색적 Spearman ρ(n=10, 다중비교 한계 명시)
- **봉암동 · 웅남동 사례 비교**

### 📋 환경관리 후보
- 반복적 고노출 패턴 / 추가 확인 필요 시설을 표로 탐색, CSV 내려받기
- 정렬 가능하되 "위험순위"라는 이름을 쓰지 않습니다

### ℹ 프로젝트 소개
- 7단계 분석 흐름, site/location 설계, 활용 범위와 한계, 사용 파일 목록, 제외 시설 45건

---

## 폴더 구조

```text
dashboard/
├─ app.py                 진입점 (탭 구성)
├─ requirements.txt
├─ qa_check.py            숫자·표현·조인 검증
├─ utils/
│  ├─ paths.py            데이터 경로 (한 곳에서 관리)
│  ├─ data.py             @st.cache_data 로더 · 공간 헬퍼
│  └─ text.py             UI 문구 · 금지 표현 통제
├─ components/
│  ├─ kpi.py              상단 KPI 카드
│  └─ detail.py           시설 상세 패널
└─ tabs/
   ├─ overview.py  dong.py  stability.py
   ├─ airquality.py  candidates.py  about.py
```

> Streamlit은 진입점 옆의 `pages/` 폴더를 **자동 멀티페이지**로 인식합니다.
> 이 앱은 한 화면에서 탭으로 전환하는 구성이라 탭 렌더러를 `tabs/`에 두었습니다.

---

## 성능

- 모든 CSV·GeoJSON은 `@st.cache_data`로 최초 1회만 로드
- 지도에는 **필터를 통과한 시설만** 렌더링
- 배출원(location)은 전체를 그리지 않고 **선택 시설 반경 1km 이내만** 계산해 표시
  (위경도 박스로 1차 필터 후 실거리 계산)

---

## 표현 원칙

`utils/text.py` 한 곳에서 문구를 관리하고 `qa_check.py`가 금지 표현을 검사합니다.

| 사용 | 사용하지 않음 |
|---|---|
| 공간 노출 · 반복적 고노출 패턴 · 추가 확인 필요 | 위험/안전 · 위험도 순위 |
| 환경관리 후보 · 측정·점검 후보 · 실측 검증 | 오염·위법 단정, 건강피해 단정 |

모든 화면 하단에 다음 문구가 표시됩니다.

> 본 결과는 실제 오염도나 건강피해를 의미하지 않으며,
> 추가 환경측정·점검 후보 선정을 위한 공간노출 지표입니다.
