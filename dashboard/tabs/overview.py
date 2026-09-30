"""탭 1 — 공간 노출 지도.

선택 방식
  지도의 점을 **클릭**하면 오른쪽 상세가 바뀐다. (st.pydeck_chart on_select)
  이름으로 찾고 싶을 때를 위해 검색 드롭다운도 함께 두고, 둘은 같은 상태를 공유한다.
  선택 상태는 session_state에 facility_id로 보관한다.

지도 시점
  클릭으로 고를 때는 화면을 움직이지 않는다(클릭할 때마다 지도가 튀면 쓰기 어렵다).
  드롭다운으로 고를 때만 해당 시설로 이동한다.
"""

import pandas as pd
import pydeck as pdk
import streamlit as st

from components import detail
from tabs import candidates
from utils import data as D
from utils.text import (CLASS_COLOR, CLASS_LABEL, CLASS_MEANING, DISCLAIMER,
                        FACILITY_MARKER, SITE_LOCATION_NOTE, SK_NOTE,
                        SOURCE_FILL, SOURCE_LABEL, SOURCE_LINE)

# 취약시설 1,605곳의 실제 분포 중심(위 35.06~35.39 / 경 128.45~128.84).
CENTER = (35.2248, 128.6444)
DEFAULT_ZOOM = 10.6      # 창원 전역이 여유 있게 들어오는 배율
FOCUS_ZOOM = 14.0        # 이름으로 찾기로 한 곳을 골랐을 때
MIN_ZOOM = 6.4           # 더 축소하면 한반도 밖으로 나간다 — 여기서 멈춘다

# 좌우 두 칸의 높이를 고정해 항상 같은 줄에서 끝나게 한다.
# 오른쪽 상세는 시설마다 길이가 달라(배출 유형 수, 근거 문장 길이) 자동 높이로 두면
# 어떤 시설에서는 왼쪽이, 어떤 시설에서는 오른쪽이 남는다.
MAP_H = 742              # 지도. 이 값만 고정이고 나머지는 CSS가 맞춘다.
LEGEND_KEY = "ov_legend"

# 오른쪽 상세는 시설마다 길이가 달라 픽셀로 맞출 수 없다. 높이를 고정해 스크롤을 넣는
# 대신, **범례가 남는 세로 공간을 채우게** 해서 왼쪽 끝을 오른쪽 끝에 맞춘다.
# st.columns는 두 칸을 같은 높이로 늘려 주므로(flex stretch), 범례에 flex:1만 주면 된다.
# 양쪽 칸이 항상 같은 줄에서 끝나게 한다.
# st.columns가 두 칸을 같은 높이로 늘려 주므로, 각 칸의 '늘어나도 되는 블록'에
# flex:1을 주면 긴 쪽이 기준이 되고 짧은 쪽이 따라 늘어난다.
#   왼쪽 — 지도는 고정, 범례가 늘어난다
#   오른쪽 — 상세 패널이 늘어난다
# 주의: flex 아이템은 .st-key-* div 가 아니라 그 부모인 stLayoutWrapper 다.
# (DOM 확인: stColumn > stVerticalBlock > stLayoutWrapper > div.stVerticalBlock.st-key-*)
_GROW = ", ".join(f'div[data-testid="stLayoutWrapper"]:has(> .st-key-{k})'
                  for k in (LEGEND_KEY, detail.PANEL_KEY))
_FILL = ", ".join(f".st-key-{k}" for k in (LEGEND_KEY, detail.PANEL_KEY))
_COLS = ", ".join(f'div[data-testid="stColumn"]:has(.st-key-{k})'
                  f' > div[data-testid="stVerticalBlock"]'
                  for k in (LEGEND_KEY, detail.PANEL_KEY))
COLUMN_CSS = f"""
<style>
  {_COLS} {{ height: 100%; }}
  {_GROW} {{ flex: 1 1 auto; min-height: 0; height: auto; }}
  {_FILL} {{ height: 100%; }}

  /* 오른쪽 상세 카드만 글자를 줄인다. 한 장에 전부 담되 답답해 보이지 않도록.
     이 칸은 폭이 좁아(전체의 2/5) 기본 metric 크기(2.25rem)면 숫자만 보인다. */
  .st-key-{detail.PANEL_KEY} [data-testid="stMetricValue"] {{ font-size: 1.5rem; }}
  .st-key-{detail.PANEL_KEY} [data-testid="stMetricLabel"] p {{ font-size: 0.74rem; }}
  .st-key-{detail.PANEL_KEY} h3 {{ font-size: 1.3rem; padding-bottom: 0.1rem; }}
  .st-key-{detail.PANEL_KEY} [data-testid="stAlertContainer"] p {{ font-size: 0.82rem; }}
  .st-key-{detail.PANEL_KEY} div[data-testid="stVerticalBlock"] {{ gap: 0.5rem; }}
</style>
"""

SEL_KEY = "overview_selected_facility_id"
VIEW_KEY = "overview_view_center"
MAP_KEY = "overview_map"
SEARCH_KEY = "overview_search"
# 검색 목록을 좁히는 분류 필터. 지도 표시(CLASS_KEY)와는 별개로 검색에만 적용된다.
SEARCH_CLASS_KEY = "overview_search_class"
# 노출 분류 선택 상태. 사이드바 multiselect와 범례 버튼이 이 키 하나를 공유한다.
CLASS_KEY = "overview_classes"
ALL_CLASSES = ["stable_high", "sensitive", "other"]
DEFAULT_CLASSES = ["stable_high", "sensitive"]


def _init_classes():
    st.session_state.setdefault(CLASS_KEY, list(DEFAULT_CLASSES))


def _toggle_class(c: str):
    """범례 클릭 → 해당 분류를 켜고 끈다.

    위젯 키를 콜백에서 바꾸는 것은 허용된다(다음 실행 전에 반영된다).
    전부 꺼지면 지도가 비면서 범례까지 사라져 되돌릴 수 없으므로 최소 1개는 남긴다.
    """
    cur = list(st.session_state.get(CLASS_KEY, DEFAULT_CLASSES))
    if c in cur:
        if len(cur) == 1:
            return
        cur.remove(c)
    else:
        cur.append(c)
    # 원래 순서(고노출 → 민감 → 기타)를 유지한다
    st.session_state[CLASS_KEY] = [x for x in ALL_CLASSES if x in cur]


def _controls(fac: pd.DataFrame):
    """필터 + 지도 표시 옵션을 한 곳에 모은다(사이드바를 쓰지 않는다).

    지도보다 위에서 그려야 한다. 아래 코드가 필터 결과 f 로 레이어와 캡션을 만들기 때문이다.
    """
    _init_classes()
    classes = st.session_state[CLASS_KEY]

    c = st.columns(3)
    # 목록을 하드코딩하지 않는다. 유형이 늘면(장애인복지관 추가) 조용히 빠진다.
    all_types = sorted(fac["facility_type"].dropna().unique())
    types = c[0].multiselect("시설 유형", all_types, default=all_types, key="flt_types")
    gus = sorted(fac["gu"].dropna().unique())
    sel_gu = c[1].multiselect("행정구", gus, default=gus, key="flt_gu")
    pool = fac[fac["gu"].isin(sel_gu)] if sel_gu else fac
    dongs = sorted(pool["administrative_dong"].dropna().unique())
    sel_dong = c[2].multiselect("행정동 (비우면 전체)", dongs, default=[], key="flt_dong")

    c = st.columns(3)
    dmax = int(fac["nearest_source_distance_m"].max(skipna=True) or 1000)
    dist = c[0].slider("최근접 배출원 거리 (m) 이하", 0, min(dmax, 1000),
                       min(dmax, 1000), 50, key="flt_dist")
    l300 = c[1].slider("300m 내 배출원 위치 수 이상", 0,
                       int(fac["source_locations_within_300m"].max()), 0, key="flt_l300")
    l500 = c[2].slider("500m 내 배출원 위치 수 이상", 0,
                       int(fac["source_locations_within_500m"].max()), 0, key="flt_l500")

    st.divider()
    c = st.columns([1, 2, 1])
    show_buf = c[0].checkbox("선택 시설 주변 buffer 표시", value=True, key="opt_buf")
    radii = c[1].multiselect("buffer 반경 (m)", [300, 500, 1000], default=[300, 500],
                             disabled=not show_buf, key="opt_radii")
    show_src = c[2].checkbox("선택 시설 주변 배출원 표시", value=True, key="opt_src")
    st.caption("노출 분류(주황·노랑·회색)는 지도 아래 범례에서 켜고 끕니다.")

    f = fac[fac["facility_type"].isin(types) & fac["map_class"].isin(classes)]
    if sel_gu:
        f = f[f["gu"].isin(sel_gu)]
    if sel_dong:
        f = f[f["administrative_dong"].isin(sel_dong)]
    f = f[(f["nearest_source_distance_m"].fillna(1e9) <= dist)
          | (f["nearest_source_distance_m"].isna() & (dist >= 1000))]
    f = f[(f["source_locations_within_300m"] >= l300)
          & (f["source_locations_within_500m"] >= l500)]
    return f, show_buf, radii, show_src


def _default_selection(f: pd.DataFrame):
    """처음 들어왔을 때 미리 골라 둘 시설.

    비워 두면 오른쪽 정보창이 통째로 비어 화면이 허전하고, 무엇을 눌러야 하는지도
    드러나지 않는다. 반복적 고노출 중 500m 이내 배출원이 가장 많은 곳을 기본으로 둔다
    (설명하기 가장 쉬운 사례). 해당 분류가 필터로 빠졌으면 남은 것 중 첫 번째를 쓴다.
    """
    pool = f[f["map_class"] == "stable_high"]
    if pool.empty:
        pool = f
    col = "source_locations_within_500m"
    if col in pool.columns and pool[col].notna().any():
        return pool.sort_values([col, "facility_id"], ascending=[False, True]).iloc[0]
    return pool.sort_values("facility_id").iloc[0]


def _resolve_selection(f: pd.DataFrame):
    """현재 선택된 시설. 필터에서 빠졌으면 기본 시설로 되돌린다."""
    cur = st.session_state.get(SEL_KEY)
    if cur is not None:
        hit = f[f["facility_id"] == cur]
        if not hit.empty:
            return hit.iloc[0]
    # 첫 진입이거나, 필터가 바뀌어 선택이 사라진 경우
    row = _default_selection(f)
    st.session_state[SEL_KEY] = row["facility_id"]
    return row


def _radius_tip(d: pd.DataFrame, radii) -> object:
    """선택한 buffer 반경별 공장·배출원 수를 툴팁 한 줄씩으로 만든다.

    값은 파이프라인 산출물(EPSG:5186)을 그대로 읽는다. 화면에서 다시 세면
    경계 사례에서 아래 집계표와 어긋난다.
    """
    rf = D.load_radius_features()
    block = ""
    for r in sorted(radii):
        fc, lc = f"factory_sites_within_{r}m", f"source_locations_within_{r}m"
        if fc not in rf.columns or lc not in rf.columns:
            continue
        fv = d["facility_id"].map(rf[fc]).fillna(0).astype(int).astype(str)
        lv = d["facility_id"].map(rf[lc]).fillna(0).astype(int).astype(str)
        # deck 툴팁은 치환된 값의 HTML 태그를 이스케이프한다. 줄바꿈 문자를 쓰고
        # 툴팁 style 의 white-space 로 실제 줄바꿈이 되게 한다.
        line = f"{r:,}m  공장 " + fv + " · 배출원 " + lv
        block = line if isinstance(block, str) and block == "" else block + "\n" + line
    return (block + "\n") if not isinstance(block, str) else ""


def _facility_layers(f: pd.DataFrame, selected_id, radii=()):
    """시설 점 레이어. 선택된 시설은 테두리를 굵게 해서 지도에서 바로 보이게 한다."""
    layers = []
    for ftype, style in FACILITY_MARKER.items():
        sub = f[f["facility_type"] == ftype]
        if sub.empty:
            continue
        d = sub.copy()
        d["_color"] = d["map_class"].map(lambda c: list(CLASS_COLOR.get(c, (120, 132, 148))) + [205])
        is_sel = d["facility_id"] == selected_id
        d["_line"] = [[20, 20, 20, 255] if s else list(style["line"]) for s in is_sel]
        d["_lw"] = [4.0 if s else 1.5 for s in is_sel]
        d["tip_title"] = d["facility_name"]
        # 반경 개수는 원이 그려진 시설(= 선택된 시설)에만 붙인다.
        tail = pd.Series("클릭하면 상세를 봅니다", index=d.index)
        rblock = _radius_tip(d, radii)
        if not isinstance(rblock, str):
            tail = tail.mask(is_sel, rblock.str.rstrip("\n"))
        d["tip_body"] = (d["facility_type"].astype(str) + " · "
                         + d["administrative_dong"].astype(str) + "\n" + tail)
        layers.append(pdk.Layer(
            "ScatterplotLayer", data=d, get_position=["longitude", "latitude"],
            get_fill_color="_color", get_line_color="_line",
            get_radius=style["radius"], radius_min_pixels=4, radius_max_pixels=22,
            stroked=True, filled=True, get_line_width="_lw", line_width_min_pixels=1.5,
            pickable=True, auto_highlight=True, id=f"fac_{ftype}"))
    return layers


BUFFER_ROWS = [("source_locations", "배출원 위치"), ("source_sites", "사업장"),
               ("factory_sites", "공장"), ("air_emission_sites", "대기 배출업소"),
               ("designated_waste_sites", "지정폐기물"), ("incineration_sites", "소각")]


def _buffer_tip(r, feat):
    """반경 r 안의 집계 문구. 값은 파이프라인 산출물 그대로이며 화면에서 재계산하지 않는다."""
    if feat is None:
        return f"반경 {r:,}m", "집계 자료 없음"
    parts = []
    for prefix, label in BUFFER_ROWS:
        col = f"{prefix}_within_{r}m"
        if col in feat.index and pd.notna(feat[col]):
            parts.append(f"{label} <b>{int(feat[col]):,}</b>")
    body = " · ".join(parts[:2]) + "<br/>" + " · ".join(parts[2:]) if len(parts) > 2 \
        else " · ".join(parts)
    return f"반경 {r:,}m 이내", body or "집계 자료 없음"


def _buffer_layers(lat, lng, radii, feat=None):
    out = []
    shades = {300: [214, 96, 41, 34], 500: [232, 178, 46, 26], 1000: [70, 130, 180, 20]}
    for r in radii:
        title, body = _buffer_tip(r, feat)
        out.append(pdk.Layer(
            "ScatterplotLayer",
            data=pd.DataFrame([{"lat": lat, "lng": lng,
                                "tip_title": title, "tip_body": body}]),
            get_position=["lng", "lat"], get_radius=r,
            get_fill_color=shades[r], get_line_color=[60, 60, 60, 160],
            stroked=True, filled=True, line_width_min_pixels=1,
            # 클릭이 통과해야 원 안의 시설을 고를 수 있다. 반경별 집계는 상세 패널의 표로 보여준다.
            pickable=False, id=f"buffer_{r}"))
    return out


def _apply_map_click(event):
    """지도 클릭 결과를 선택 상태에 반영한다. 바뀐 경우에만 rerun한다."""
    objects = (getattr(event, "selection", None) or {}).get("objects") or {}
    for layer_id, rows in objects.items():
        # 배출원(nearby_src) 레이어 클릭은 선택을 바꾸지 않는다
        if not layer_id.startswith("fac_") or not rows:
            continue
        picked = rows[0].get("facility_id")
        if picked and picked != st.session_state.get(SEL_KEY):
            st.session_state[SEL_KEY] = picked
            # 클릭 선택에서는 시점을 그대로 둔다 (지도가 튀지 않게)
            st.rerun()
        return


def render():
    fac = D.load_facilities()
    with st.expander("지도 표시 옵션 · 필터", expanded=False):
        f, show_buf, radii, show_src = _controls(fac)

    if f.empty:
        st.warning("필터 조건에 맞는 시설이 없습니다. 위의 ‘지도 표시 옵션 · 필터’에서 "
                   "조건을 넓혀 주세요.")
        return

    sel = _resolve_selection(f)
    has_sel = sel is not None

    # 아무것도 안 골랐으면 창원 전체가 보이게 둔다. (위도, 경도, 배율)
    if VIEW_KEY not in st.session_state or len(st.session_state[VIEW_KEY]) != 3:
        st.session_state[VIEW_KEY] = (CENTER[0], CENTER[1], DEFAULT_ZOOM)

    # 정보창을 항상 띄워 둔다(닫기 버튼 없음). 선택이 없으면 오른쪽에 안내가 나온다.
    st.markdown(COLUMN_CSS, unsafe_allow_html=True)
    left, right = st.columns([3, 2])

    with left:
        st.markdown("#### 취약시설 공간 노출 지도")
        st.caption(f"표시 {len(f):,} / 전체 {len(fac):,} · "
                   "색 = 노출 분류, 테두리·크기 = 시설 유형 (굵은 테두리 = 선택됨)")

    # 반경 원이 실제로 화면에 떠 있을 때만 툴팁에 개수를 넣는다.
    # (원이 없는데 "500m 공장 21"이 뜨면 어느 범위 얘기인지 알 수 없다)
    tip_radii = radii if (show_buf and has_sel) else ()
    layers = _facility_layers(f, sel["facility_id"] if has_sel else None, tip_radii)
    nearby = pd.DataFrame()
    if has_sel and show_src:
        nearby = D.nearby_locations(sel["latitude"], sel["longitude"], 1000.0)
        if not nearby.empty:
            nearby = nearby.copy()
            nearby["tip_title"] = nearby["address_clean"].astype(str).str.slice(0, 38)
            nearby["tip_body"] = (
                "사업장 " + nearby["site_count"].astype(int).astype(str)
                + " · 공장 " + nearby["factory_site_count"].astype(int).astype(str) + "\n"
                + nearby["distance_m"].round(0).astype(int).astype(str)
                + "m 거리 · 취약시설 아님")
            # 선택 시설 주변만 렌더링 (전체 2,740개를 그리지 않는다)
            layers.insert(0, pdk.Layer(
                "ScatterplotLayer", data=nearby,
                get_position=["longitude", "latitude"],
                get_fill_color=list(SOURCE_FILL), get_line_color=list(SOURCE_LINE),
                get_radius=55, radius_min_pixels=3, radius_max_pixels=12,
                stroked=True, filled=True, pickable=True, id="nearby_src"))
    if has_sel and show_buf and radii:
        rf = D.load_radius_features()
        fid = sel["facility_id"]
        frow = rf.loc[fid] if fid in rf.index else None
        layers = _buffer_layers(sel["latitude"], sel["longitude"],
                                sorted(radii, reverse=True), frow) + layers

    with left:
        vlat, vlng, vzoom = st.session_state[VIEW_KEY]
        event = st.pydeck_chart(
            pdk.Deck(
                layers=layers,
                initial_view_state=pdk.ViewState(latitude=vlat, longitude=vlng,
                                                 zoom=vzoom, min_zoom=MIN_ZOOM,
                                                 max_zoom=18, pitch=0),
                map_style=None,
                # 레이어가 셋(시설·배출원·buffer)인데 deck 툴팁은 하나뿐이다.
                # 공용 필드(tip_title/tip_body)를 각 레이어가 채운다.
                tooltip={
                    "html": "<b>{tip_title}</b><br/>{tip_body}",
                    # 값 안의 \n 이 실제 줄바꿈이 되게 하고, 폭을 제한해 잘리지 않게 한다
                    "style": {"whiteSpace": "pre-line", "maxWidth": "260px",
                              "fontSize": "12px", "lineHeight": "1.5"},
                }),
            width="stretch", height=MAP_H,
            on_select="rerun", selection_mode="single-object",
            key=MAP_KEY)
        _apply_map_click(event)

        # 접이식(expander)이면 펼침 여부에 따라 왼쪽 칸 길이가 달라져 오른쪽과 어긋난다.
        # 항상 펼쳐진 블록으로 두고, 높이는 CSS(flex:1)가 오른쪽에 맞춰 늘린다.
        with st.container(border=True, key=LEGEND_KEY):
            st.markdown("**범례 · 노출 분류** — 클릭하면 켜고 끕니다")
            active = st.session_state.get(CLASS_KEY, DEFAULT_CLASSES)
            lg = st.columns(3)
            for i, c in enumerate(ALL_CLASSES):
                on = c in active
                r, g, b = CLASS_COLOR[c]
                with lg[i]:
                    st.button(f"{'●' if on else '○'}  {c} · {CLASS_LABEL[c]}",
                              key=f"legend_btn_{c}", on_click=_toggle_class, args=(c,),
                              type="primary" if on else "secondary",
                              width="stretch", help=CLASS_MEANING[c])
                    st.markdown(
                        f"<span style='display:inline-block;width:12px;height:12px;"
                        f"border-radius:50%;background:rgb({r},{g},{b});margin-right:6px;"
                        f"opacity:{'1' if on else '0.3'}'></span>"
                        f"<span style='font-size:0.82em;color:#666'>{CLASS_MEANING[c]}</span>",
                        unsafe_allow_html=True)
            st.caption("켜진 분류만 지도에 표시됩니다. 최소 한 개는 켜져 있어야 합니다.")
            st.caption("시설 유형 구분 — " + " · ".join(
                f"{k}: {v['shape_note']}" for k, v in FACILITY_MARKER.items())
                + f" ({SOURCE_LABEL} = 선택 시설 주변 배출원 위치 — 시설이 아님)")

    with right:
        # 검색은 정보창 맨 위에 둔다(예전 ✕ 버튼 자리).
        # 이름 앞에 [분류]를 붙이면 이름이 밀려서 읽기 어렵다. 접두어 대신 위에
        # 분류 필터를 두고, 목록에는 이름만 남긴다.
        cnt = f["map_class"].value_counts()
        scope_opts = ["all"] + [c for c in ALL_CLASSES if int(cnt.get(c, 0)) > 0]
        # 범례에서 분류를 끄면 그 분류가 scope_opts에서 사라진다. 세션에 남은 옛 값이
        # 목록에 없으면 위젯이 오류를 내므로 전체로 되돌린다.
        if st.session_state.get(SEARCH_CLASS_KEY) not in scope_opts:
            st.session_state[SEARCH_CLASS_KEY] = "all"
        pick = st.segmented_control(
            "검색 범위", scope_opts,
            format_func=lambda c: (f"전체 {len(f):,}" if c == "all"
                                   else f"{CLASS_LABEL[c]} {int(cnt.get(c, 0)):,}"),
            key=SEARCH_CLASS_KEY)
        scope = f if pick in (None, "all") else f[f["map_class"] == pick]

        opts = scope.sort_values("facility_name").reset_index(drop=True)
        labels = dict(zip(opts["facility_id"], opts.apply(
            lambda r: f"{r['facility_name']} "
                      f"({r['facility_type']}, {r['administrative_dong']})", axis=1)))

        def _on_search_change():
            """드롭다운으로 고른 경우에만 지도를 그 시설로 옮긴다."""
            new_id = st.session_state.get(SEARCH_KEY)
            if new_id is None:
                return
            st.session_state[SEL_KEY] = new_id
            row = opts[opts["facility_id"] == new_id].iloc[0]
            st.session_state[VIEW_KEY] = (float(row["latitude"]),
                                          float(row["longitude"]), FOCUS_ZOOM)

        # 지도 클릭으로 선택이 바뀌었으면 드롭다운도 같은 값을 가리키게 맞춘다.
        # (이 줄이 없으면 위젯에 남은 옛 값이 클릭 결과를 되돌린다)
        # 단, 선택된 시설이 현재 검색 범위 밖이면 selectbox에 넣을 수 없다(값 오류).
        # 그 경우 검색창만 비우고 상세 패널은 그대로 둔다.
        in_scope = has_sel and sel["facility_id"] in labels
        st.session_state[SEARCH_KEY] = sel["facility_id"] if in_scope else None
        st.selectbox("이름으로 찾기", opts["facility_id"].tolist(), index=None,
                     format_func=lambda i: labels[i],
                     placeholder="시설 이름으로 검색",
                     key=SEARCH_KEY, on_change=_on_search_change)
        if has_sel and not in_scope:
            st.caption(f"선택된 **{sel['facility_name']}** 은(는) 현재 검색 범위"
                       f"({CLASS_LABEL[sel['map_class']]})에 없어 위 목록에는 표시되지 "
                       f"않습니다. 상세는 아래에 그대로 나옵니다.")

        # 높이를 고정하지 않는다(스크롤 없음). 왼쪽 범례가 이 길이에 맞춰 늘어난다.
        if has_sel:
            detail.render(sel)
        else:
            st.info("지도의 점을 클릭하거나 위에서 시설을 검색하면 "
                    "이 자리에 상세 정보가 나옵니다.")

    # 아래는 전체 폭. 표와 목록에 주소가 들어가 폭이 필요하다.
    if has_sel:
        detail.render_radius_table(sel)

    with st.expander("사업장(site) vs 물리적 위치(location) 비교", expanded=False):
        st.markdown(SITE_LOCATION_NOTE)
        st.caption(SK_NOTE)
        unit = st.radio("비교 단위", ["location (기본)", "site"], horizontal=True)
        col = ("source_locations_within_500m" if unit.startswith("location")
               else "source_sites_within_500m")
        c = st.columns(4)
        c[0].metric(f"500m 이내 평균 ({unit.split()[0]})", f"{f[col].mean():.2f}")
        c[1].metric("500m location 평균", f"{f['source_locations_within_500m'].mean():.2f}")
        c[2].metric("500m site 평균", f"{f['source_sites_within_500m'].mean():.2f}")
        ratio = f["site_location_ratio_500m"].dropna()
        c[3].metric("site/location 배율 최대", f"{ratio.max():.2f}" if len(ratio) else "-")
        top = f.nlargest(8, "site_location_ratio_500m")[
            ["facility_name", "administrative_dong", "source_sites_within_500m",
             "source_locations_within_500m", "site_location_ratio_500m"]]
        st.dataframe(top, width="stretch", hide_index=True)
        st.caption("배율이 큰 곳은 한 건물에 여러 사업장이 입주한 지역입니다. "
                   "사업장 수 기준으로 보면 배출지점이 과대계상됩니다.")

    # 환경관리 후보는 별도 탭이 아니라 이 페이지 하단에 둔다.
    # (탭에 남긴 채 여기서도 부르면 위젯 키가 중복돼 실행이 멈춘다)
    n_sh = int((fac["map_class"] == "stable_high").sum())
    n_sn = int((fac["map_class"] == "sensitive").sum())
    with st.expander(f"환경관리 후보 탐색 — 반복적 고노출 {n_sh:,}곳 · "
                     f"추가 확인 필요 {n_sn:,}곳", expanded=False):
        candidates.render()

    # 면책 문구는 상세 패널(좁은 오른쪽 칸)이 아니라 여기에 전체 폭으로 한 번만 둔다.
    # 다른 탭도 모두 이 위치·이 형식이다.
    st.caption(DISCLAIMER)
