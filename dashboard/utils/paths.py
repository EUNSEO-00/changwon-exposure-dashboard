"""데이터 파일 경로 — 실제 존재하는 경로만 사용한다(추측 금지).

모든 경로는 프로젝트 루트 기준으로 계산하며, 대시보드는 이 파일들을 **읽기만** 한다.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FINAL = ROOT / "pes" / "output" / "final"
ANALYSIS = ROOT / "pes" / "output" / "analysis"
SPATIAL = ROOT / "pes" / "output" / "spatial"
RISK = ROOT / "pes" / "output" / "risk"
AIR = ROOT / "pes" / "output" / "air_quality"
MSH = ROOT / "msh" / "data" / "processed"
MSH_VALID = MSH / "validation"
MSH_VALID2 = MSH / "validation_v2"

# v4 = 배출원에 전국 등록공장현황(2024-12-31, 5개 구 전역)을 반영하고,
#      취약시설에 장애인복지관 4곳을 더한 판. 취약시설 1,609곳 · 92/153/1,364.
# 배출원 master 는 공장 반영이 끝난 v3 가 최신이며 v4 에서 다시 만들지 않았다.
PATHS = {
    "facility_candidates": FINAL / "facility_management_candidates_v4.csv",
    "dong_profile": FINAL / "dong_management_profile_v4.csv",
    "air_validation": FINAL / "air_quality_validation.csv",
    "childcare_capacity": FINAL / "childcare_capacity_by_exposure_v4.csv",
    "site_master": ANALYSIS / "source_site_master_v3.csv",
    "location_master": ANALYSIS / "source_location_master_v3.csv",
    "facility_excluded": SPATIAL / "facility_excluded_from_spatial_v4.csv",
    "facility_features": SPATIAL / "facility_source_features_v4.csv",
    "sensitivity_driver": FINAL / "sensitivity_driver_analysis_v4.csv",
    "scenario_scores": RISK / "scenario_scores_v4.csv",
    "stations": AIR / "stations.csv",
    "station_summary": AIR / "station_period_summary.csv",
    "station_context": AIR / "station_source_context.csv",
    "station_correlation": AIR / "station_density_correlation.csv",
    "facilities_raw": MSH / "facilities.csv",
    "action_matrix": MSH / "facility_action_matrix.csv",
    "decision_rules": MSH / "decision_rules.csv",
    "exposure_profile": FINAL / "facility_exposure_profile_v4.csv",
    "dong_boundary": MSH / "changwon_dong_boundary.geojson",
    # 민원 관련 경로는 전부 뺐다. 시도 기록과 배제 사유는
    # archive/complaint_attempt/README.md 에 있다.
}


def check() -> dict:
    """존재 여부 점검. 대시보드 기동 시 한 번 호출한다."""
    return {k: p.exists() for k, p in PATHS.items()}
