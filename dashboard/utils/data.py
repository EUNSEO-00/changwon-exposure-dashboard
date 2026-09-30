"""데이터 로더 — Streamlit 캐시로 최초 1회만 읽는다. 원본 파일을 수정하지 않는다."""

import json

import numpy as np
import pandas as pd
import streamlit as st

from utils.paths import PATHS

EARTH_R = 6371000.0


def _hcode(s: pd.Series) -> pd.Series:
    """h_code를 문자열 정수로 통일. 행정동 조인은 반드시 이 키로 한다(이름 조인 금지)."""
    return pd.to_numeric(s, errors="coerce").astype("Int64").astype(str)


@st.cache_data(show_spinner=False)
def load_facilities() -> pd.DataFrame:
    df = pd.read_csv(PATHS["facility_candidates"])
    df["h_code"] = _hcode(df["h_code"])
    df["map_class"] = df["map_class"].fillna("other")
    return df


@st.cache_data(show_spinner=False)
def load_dong_profile() -> pd.DataFrame:
    """행정동 관리현황. 민원은 시스템에서 제외했다(archive/complaint_attempt 참고)."""
    df = pd.read_csv(PATHS["dong_profile"])
    df["h_code"] = _hcode(df["h_code"])
    return df


@st.cache_data(show_spinner=False)
def load_locations() -> pd.DataFrame:
    return pd.read_csv(PATHS["location_master"])


@st.cache_data(show_spinner=False)
def load_sites() -> pd.DataFrame:
    return pd.read_csv(PATHS["site_master"])


@st.cache_data(show_spinner=False)
def load_air_validation() -> pd.DataFrame:
    return pd.read_csv(PATHS["air_validation"])


@st.cache_data(show_spinner=False)
def load_station_summary() -> pd.DataFrame:
    return pd.read_csv(PATHS["station_summary"])


@st.cache_data(show_spinner=False)
def load_station_correlation() -> pd.DataFrame:
    return pd.read_csv(PATHS["station_correlation"])


@st.cache_data(show_spinner=False)
def load_action_matrix() -> pd.DataFrame:
    """행동 제안 매트릭스 (팀원 A 산출물, 읽기 전용). 위험점수가 아니다."""
    df = pd.read_csv(PATHS["action_matrix"])
    df["h_code"] = _hcode(df["h_code"])
    return df


@st.cache_data(show_spinner=False)
def load_decision_rules() -> pd.DataFrame:
    """행동 제안 rule 정의 (팀원 A 산출물, 읽기 전용)."""
    return pd.read_csv(PATHS["decision_rules"])


@st.cache_data(show_spinner=False)
def load_exposure_profile() -> pd.DataFrame:
    """stable_high 74곳 노출 유형. 위험등급이 아니다."""
    return pd.read_csv(PATHS["exposure_profile"])


@st.cache_data(show_spinner=False)
def load_facilities_with_action() -> pd.DataFrame:
    """후보 목록에 행동 제안·노출 유형을 facility_id로 붙인다. 행 수는 1,605로 유지."""
    fac = load_facilities()
    am = load_action_matrix()[[
        "facility_id", "primary_action", "action_category", "context_actions",
        "all_actions", "action_count", "nearest_station_km", "primary_rule_id",
        "primary_reason", "matrix_note"]]
    prof = load_exposure_profile()[[
        "facility_id", "primary_profile", "primary_profile_label", "profile_reason"]]
    n = len(fac)
    out = fac.merge(am, on="facility_id", how="left", validate="one_to_one")
    out = out.merge(prof, on="facility_id", how="left", validate="one_to_one")
    assert len(out) == n, "행동·유형 조인으로 행 수가 바뀌었다"
    return out


# 분석 파이프라인과 같은 투영(EPSG:5186)을 쓴다. haversine 으로 세면 경계 사례에서
# 표의 숫자와 어긋난다(500m 5/300, 1km 20/300 불일치 확인). 5186이면 400/400 일치.
METRIC_CRS = "EPSG:5186"

# 표의 지표행 → location master 에서 그 지표를 가진 행을 고르는 조건
SOURCE_KIND_FILTER = {
    "source_locations": None,
    "source_sites": None,
    "factory_sites": ("factory_site_count", "gt0"),
    "air_emission_sites": ("has_air_emission", "flag"),
    "designated_waste_sites": ("has_designated_waste", "flag"),
    "incineration_sites": ("has_incineration", "flag"),
    "waste_sites": ("waste_site_count", "gt0"),
}


@st.cache_resource(show_spinner=False)
def _to_metric():
    from pyproj import Transformer
    return Transformer.from_crs("EPSG:4326", METRIC_CRS, always_xy=True)


@st.cache_data(show_spinner=False)
def _locations_projected() -> pd.DataFrame:
    loc = load_locations().copy()
    x, y = _to_metric().transform(loc["longitude"].values, loc["latitude"].values)
    loc["_x"], loc["_y"] = x, y
    return loc


def sources_within(lat: float, lng: float, radius_m: float, kind: str = "source_locations"):
    """반경 내 배출원 위치. 거리 계산은 분석과 동일한 EPSG:5186 평면거리다."""
    loc = _locations_projected()
    fx, fy = _to_metric().transform(lng, lat)
    d = np.hypot(loc["_x"].values - fx, loc["_y"].values - fy)
    out = loc.loc[d <= radius_m].copy()
    out["distance_m"] = np.round(d[d <= radius_m]).astype(int)
    cond = SOURCE_KIND_FILTER.get(kind)
    if cond:
        col, how = cond
        if col in out.columns:
            out = out[out[col].astype(bool)] if how == "flag" else out[out[col].fillna(0) > 0]
    return out.sort_values("distance_m").reset_index(drop=True)


RADII = (300, 500, 1000)
# buffer 툴팁에 쓸 반경별 집계. 화면에서 다시 계산하지 않고 파이프라인 산출값을 그대로 쓴다.
# (지도는 haversine, 분석은 EPSG:5186이라 경계 사례에서 1~2건 어긋난다 — 상세 패널과 어긋나면 안 된다.)
RADIUS_PREFIXES = ("source_locations", "source_sites", "factory_sites",
                   "air_emission_sites", "designated_waste_sites",
                   "incineration_sites", "waste_sites")


@st.cache_data(show_spinner=False)
def load_radius_features() -> pd.DataFrame:
    """facility_id로 색인된 반경별 배출원 집계 (300/500/1000m)."""
    cols = [f"{p}_within_{r}m" for p in RADIUS_PREFIXES for r in RADII]
    df = pd.read_csv(PATHS["facility_features"])
    keep = ["facility_id"] + [c for c in cols if c in df.columns]
    return df[keep].set_index("facility_id")


@st.cache_data(show_spinner=False)
def load_score_tie_groups() -> pd.DataFrame:
    """36개 시나리오 점수가 소수점까지 완전히 같은 시설 묶음.

    같은 건물에 있어 점수가 동일한데, 160번째 자리 동점 처리로 분류가 갈리는
    경계 사례를 찾기 위한 것이다. 새 점수를 만들지 않고 기존 값을 비교만 한다.
    """
    sc = pd.read_csv(PATHS["scenario_scores"])
    w = sc.pivot(index="facility_id", columns="scenario",
                 values="scenario_composite_index")
    key = w.round(4).astype(str).agg("|".join, axis=1)
    dup = key[key.duplicated(keep=False)]
    if dup.empty:
        return pd.DataFrame(columns=["facility_id", "_group"])
    return pd.DataFrame({"facility_id": dup.index,
                         "_group": pd.factorize(dup.values)[0]})


@st.cache_data(show_spinner=False)
def load_sensitivity_drivers() -> pd.DataFrame:
    """시설별 민감도 분해. 행동 제안의 '왜'를 숫자로 설명하는 데 쓴다."""
    return pd.read_csv(PATHS["sensitivity_driver"]).set_index("facility_id")


@st.cache_data(show_spinner=False)
def load_excluded() -> pd.DataFrame:
    return pd.read_csv(PATHS["facility_excluded"])


@st.cache_data(show_spinner=False)
def load_boundary() -> dict:
    with open(PATHS["dong_boundary"], encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def boundary_with_metric(metric: str) -> dict:
    """경계 GeoJSON에 행정동 지표를 h_code(adm_cd)로 조인해 넣는다.

    ⚠ 행정동 '이름'으로 조인하지 않는다. 법정동과 행정동 이름이 달라 대부분 틀리기 때문이다.
    """
    gj = json.loads(json.dumps(load_boundary()))     # 캐시 원본 보호용 깊은 복사
    prof = load_dong_profile().set_index("h_code")
    vals = []
    for feat in gj["features"]:
        code = str(feat["properties"].get("adm_cd"))
        row = prof.loc[code] if code in prof.index else None
        v = float(row[metric]) if row is not None and pd.notna(row.get(metric)) else 0.0
        feat["properties"]["_metric"] = v
        feat["properties"]["_matched"] = row is not None
        for c in ("vulnerable_facility_count", "stable_high_facility_count",
                  "sensitive_facility_count", "source_location_count",
                  "source_site_count", "air_emission_site_count",
                  "designated_waste_site_count", "incineration_site_count",
                  "area_km2"):
            feat["properties"][c] = (float(row[c]) if row is not None and pd.notna(row.get(c))
                                     else 0.0)
        vals.append(v)
    hi = max(vals) if vals else 1.0
    for feat in gj["features"]:
        t = (feat["properties"]["_metric"] / hi) if hi > 0 else 0.0
        # 연속 단일 색조(낮음 → 높음). '위험/안전' 의미가 아니라 값의 크기 표현이다.
        feat["properties"]["_fill"] = [
            int(238 - 170 * t), int(238 - 120 * t), int(244 - 80 * t), 175]
    return gj


def haversine_m(lat1, lng1, lat2, lng2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lng2 - lng1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def nearby_locations(lat: float, lng: float, radius_m: float = 1000.0) -> pd.DataFrame:
    """선택 시설 주변 배출원만 잘라낸다. 전체 2,740개를 통째로 그리지 않기 위한 최적화."""
    loc = load_locations()
    # 1차: 위경도 박스로 굵게 거르고 2차: 실거리 계산
    dlat = radius_m / 111_000.0
    dlng = radius_m / (111_000.0 * max(np.cos(np.radians(lat)), 0.1))
    box = loc[(loc.latitude.between(lat - dlat, lat + dlat))
              & (loc.longitude.between(lng - dlng, lng + dlng))].copy()
    if box.empty:
        return box.assign(distance_m=[])
    box["distance_m"] = haversine_m(lat, lng, box.latitude.values, box.longitude.values).round(1)
    return box[box.distance_m <= radius_m].sort_values("distance_m")
