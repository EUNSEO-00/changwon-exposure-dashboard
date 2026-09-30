"""대시보드 QA — UI에 표시되는 숫자를 실제 CSV로 검증한다.

  pes/.venv/bin/python dashboard/qa_check.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.paths import PATHS, check  # noqa: E402

# v4 기준. 배출원에 전국 등록공장현황(5개 구 전역) 반영 + 취약시설에 장애인복지관 4곳 추가.
EXPECTED = {"analyzed": 1609, "stable_high": 92, "sensitive": 153,
            "other": 1364, "excluded": 45, "stations": 10}
ok = True


def chk(name, actual, expected=None):
    global ok
    if expected is None:
        print(f"  {name:<46} {actual}")
        return
    good = actual == expected
    ok &= good
    print(f"  {name:<46} {actual:>8}  (기대 {expected}) {'OK' if good else '← 불일치'}")


print("=" * 78)
print("1) 파일 존재")
print("=" * 78)
for k, exists in check().items():
    print(f"  {'✅' if exists else '❌'} {k:<24} {PATHS[k]}")
    ok &= exists

print("\n" + "=" * 78)
print("2) KPI 숫자 검증 (실제 CSV 기준)")
print("=" * 78)
fac = pd.read_csv(PATHS["facility_candidates"])
vc = fac["map_class"].value_counts()
chk("정밀 공간분석 취약시설", len(fac), EXPECTED["analyzed"])
chk("stable_high", int(vc.get("stable_high", 0)), EXPECTED["stable_high"])
chk("sensitive", int(vc.get("sensitive", 0)), EXPECTED["sensitive"])
chk("stable_non_high (other)", int(vc.get("other", 0)), EXPECTED["other"])
chk("정밀거리 분석 제외", len(pd.read_csv(PATHS["facility_excluded"])), EXPECTED["excluded"])
chk("창원 AirKorea 측정소", len(pd.read_csv(PATHS["air_validation"])), EXPECTED["stations"])
chk("map_class 결측", int(fac["map_class"].isna().sum()), 0)
chk("좌표 결측", int(fac[["latitude", "longitude"]].isna().any(axis=1).sum()), 0)
chk("facility_id 중복", int(fac["facility_id"].duplicated().sum()), 0)

print("\n" + "=" * 78)
print("2-1) 어린이집 정원 검증")
print("=" * 78)
cc = fac[fac["facility_type"] == "어린이집"]
chk("분석 대상 어린이집", len(cc), 523)
chk("어린이집 정원 결측", int(cc["facility_capacity"].isna().sum()), 0)
chk("어린이집 외 시설에 정원 값",
    int(fac.loc[fac["facility_type"] != "어린이집", "facility_capacity"].notna().sum()), 0)
sh_cc = cc[cc["map_class"] == "stable_high"]
chk("stable_high 어린이집", len(sh_cc), 29)
chk("stable_high 어린이집 정원 합", int(sh_cc["facility_capacity"].sum()), 1501)
cap = pd.read_csv(PATHS["childcare_capacity"])
row = cap[cap["exposure_stability_class"] == "scenario_stable_high_exposure"].iloc[0]
chk("요약표 stable_high 어린이집 수", int(row["childcare_count"]), 29)
chk("요약표 stable_high 정원 합", int(row["capacity_sum"]), 1501)
chk("capacity_data_available == 어린이집 여부",
    int((fac["capacity_data_available"].astype(bool)
         != (fac["facility_type"] == "어린이집")).sum()), 0)

print("\n" + "=" * 78)
print("2-3) 노출 유형 · 행동 제안 검증 (②⑤)")
print("=" * 78)
prof = pd.read_csv(PATHS["exposure_profile"])
chk("노출 유형 행 수", len(prof), EXPECTED["stable_high"])
chk("노출 유형 facility_id 중복", int(prof["facility_id"].duplicated().sum()), 0)
chk("profile_reason 결측", int(prof["profile_reason"].isna().sum()), 0)
chk("노출 유형 == stable_high 집합",
    int(set(prof["facility_id"]) == set(fac.loc[fac["map_class"] == "stable_high", "facility_id"])), 1)

am = pd.read_csv(PATHS["action_matrix"])
# 행 수는 EXPECTED["analyzed"] 에서 끌어온다. 두 곳에 같은 숫자를 적어두면
# 모수가 바뀔 때 한쪽만 고쳐져 이번처럼 어긋난다.
chk("action_matrix 행 수", len(am), EXPECTED["analyzed"])
chk("action_matrix facility_id 중복", int(am["facility_id"].duplicated().sum()), 0)
chk("action_category 합계", int(am["action_category"].value_counts().sum()),
    EXPECTED["analyzed"])
# v4 재생성 결과에 맞춘 값. (v3: 1355/185/37/20/8 — 모수 1,605 · stable_high 74 기준)
EXP_ACT = {"정기 모니터링": 1383, "현장 확인": 153, "자료 보완": 32,
           "권역 관리": 24, "실측 보완": 17}
for k, v in EXP_ACT.items():
    chk(f"  {k}", int((am["action_category"] == k).sum()), v)
chk("action_matrix ↔ 후보 id 집합 일치",
    int(set(am["facility_id"]) == set(fac["facility_id"])), 1)
chk("map_class 불일치", int((am.set_index("facility_id")["map_class"]
                           != fac.set_index("facility_id")["map_class"]).sum()), 0)
banned_act = [c for c in am.columns if c in ("priority", "priority_level", "risk_grade", "rank")]
chk("행동 매트릭스 금지 컬럼", len(banned_act), 0)
rules = pd.read_csv(PATHS["decision_rules"])
chk("decision_rules 행 수", len(rules), 12)

print("\n" + "=" * 78)
print("2-4) 팀원 A 검증축 수치 (①③)")
print("=" * 78)
rb = pd.read_csv(PATHS["action_matrix"].parent / "random_baseline_summary.csv")
main = rb[rb["null_model"] == "dong_stratified"].set_index("metric")
for m, obs, nul in [("mean_sources_within_300m", 1.836, 1.323),
                    ("mean_sources_within_500m", 4.944, 3.690),
                    ("median_nearest_source_m", 236.842, 435.372)]:
    chk(f"random {m} 관측", float(main.loc[m, "observed"]), obs)
    chk(f"random {m} 랜덤평균", float(main.loc[m, "null_mean"]), nul)
chk("random p 전부 0.001", int((main["p_value"] == 0.001).all()), 1)
chk("random iters", int(main["iters"].iloc[0]), 1000)

ga = pd.read_csv(PATHS["action_matrix"].parent / "spatial_autocorr_global.csv")
q = ga[ga["weights"] == "Queen"].set_index("variable")
chk("Moran source_density I", round(float(q.loc["source_location_density", "I"]), 4), 0.2475)
chk("Moran source_density p", round(float(q.loc["source_location_density", "p_sim"]), 4), 0.0067)
chk("Moran stable_high_count I", round(float(q.loc["stable_high_count", "I"]), 4), -0.0514)
chk("Moran stable_high_ratio I", round(float(q.loc["stable_high_ratio", "I"]), 4), 0.0347)
chk("Moran permutations", int(q["permutations"].iloc[0]), 9999)

la = pd.read_csv(PATHS["action_matrix"].parent / "spatial_autocorr_local.csv")
chk("LISA FDR 유의", int(la["lisa_sig_fdr"].sum()), 0)
chk("Gi* FDR 유의", int(la["gistar_sig_fdr"].sum()), 0)
chk("LISA(EB) FDR 유의", int(la["lisa_ratio_EB_sig_fdr"].sum()), 0)

print("\n" + "=" * 78)
print("2-5) AirKorea 상관 재현")
print("=" * 78)
cor = pd.read_csv(PATHS["station_correlation"])
chk("검정 조합", len(cor), 42)
chk("측정소 n", int(cor["n"].unique()[0]), 10)
chk("raw p<0.05", int(cor["significant_at_0.05"].sum()), 6)
chk("Bonferroni 통과", int((cor["p_value"] < 0.05 / len(cor)).sum()), 0)
chk("최소 p", round(float(cor["p_value"].min()), 4), 0.0133)
minrow = cor.loc[cor["p_value"].idxmin()]
chk("최소 p 조합이 3000m×NO2",
    int(minrow["density_metric"] == "source_locations_within_3000m"
        and minrow["pollutant"] == "no2"), 1)

print("\n" + "=" * 78)
print("3) 행정동 choropleth — h_code 조인 검증 (이름 조인 금지)")
print("=" * 78)
prof = pd.read_csv(PATHS["dong_profile"])
prof["h_code"] = pd.to_numeric(prof["h_code"], errors="coerce").astype("Int64").astype(str)
gj = json.load(open(PATHS["dong_boundary"], encoding="utf-8"))
codes = {str(f["properties"]["adm_cd"]) for f in gj["features"]}
matched = codes & set(prof["h_code"])
chk("경계 폴리곤 수", len(codes))
chk("h_code로 매칭된 폴리곤", len(matched), len(codes))
extra = prof[~prof["h_code"].isin(codes)]
# master 단계에서 분석 범위를 창원시로 제한했으므로 경계 밖 h_code는 0이어야 한다.
chk("경계에 없는 h_code (프로필 잔여)", len(extra), 0)
if len(extra):
    print(f"    잔여 h_code: {sorted(extra['h_code'])} "
          f"| 취약시설 {int(extra['vulnerable_facility_count'].sum())}건")
chk("프로필에 없는 경계 폴리곤", len(codes - set(prof["h_code"])), 0)

print("\n" + "=" * 78)
print("4) 금지 표현 스캔 (UI 문자열)")
print("=" * 78)
BANNED = ["위험기업", "오염기업", "위험지역", "안전지역", "오염 원인",
          "건강피해 발생", "위험도 1위", "위험시설"]
hits = []
for p in sorted(Path("dashboard").rglob("*.py")):
    if p.name == "qa_check.py":        # 스캐너 자신의 금지어 목록은 제외
        continue
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if "qa-allow" in line:          # '쓰지 않는다'고 명시하는 문구는 허용
            continue
        for b in BANNED:
            if b in line:
                hits.append((p.name, i, b, line.strip()[:60]))
if hits:
    ok = False
    for h in hits:
        print(f"  ← {h[0]}:{h[1]} '{h[2]}' | {h[3]}")
else:
    print("  금지 표현 없음 ✓")

print("\n" + "=" * 78)
print("5) 원본 데이터 무수정 확인")
print("=" * 78)
import subprocess
w = subprocess.run(["grep", "-rnE", r"to_csv|\.write_text|open\(.*['\"]w", "dashboard"],
                   capture_output=True, text=True).stdout.strip()
lines = [l for l in w.splitlines()
         if "qa_check.py" not in l and "download_button" not in l
         and "to_csv(index=False).encode" not in l]
print(f"  쓰기 호출: {len(lines)}건 {'(다운로드 버튼용 메모리 직렬화만)' if not lines else ''}")
for l in lines:
    print("   ", l)
ok &= not lines

print("\n" + "=" * 78)
print(f"QA 전체: {'통과' if ok else '실패'}")
print("=" * 78)
sys.exit(0 if ok else 1)
