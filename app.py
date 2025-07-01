import streamlit as st
import pandas as pd
import plotly.express as px

# ──────────────────────────────── 기본 설정 ────────────────────────────────
st.set_page_config(page_title="OTD 누적 전년비 대시보드", layout="wide")

# ───────────────────────── 1. 전처리 함수 ─────────────────────────
@st.cache_data
def preprocess(xlsx):
    df = pd.read_excel(xlsx, sheet_name="DATA")

    # ① 헤더를 문자열로 변환 후 공백 제거
    df.columns = df.columns.map(str).str.strip()

    # ② 한글 → 영문 컬럼명 매핑 (공백·대소문자 무시)
    mapping = {}
    for col in df.columns:
        k = col.replace(" ", "")
        if k == "구분": mapping[col] = "division"
        elif k == "사이트": mapping[col] = "site"
        elif k == "매장": mapping[col] = "brand"
        elif k == "일자": mapping[col] = "date"
        elif k == "매출": mapping[col] = "sales"
    df = df.rename(columns=mapping)

    # ③ wide → long  
    meta_cols = ["division", "site", "brand"]
    df = df.melt(id_vars=meta_cols, var_name="date", value_name="sales")

    # ④ 형 변환·날짜 파생
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0).astype(int)
    df["date"]  = pd.to_datetime(df["date"], errors="coerce")
    df.dropna(subset=["date"], inplace=True)

    df["ym"]    = df["date"].dt.to_period("M").astype(str)
    df["year"]  = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"]   = df["date"].dt.day

    df["division"] = df["division"].astype(str).fillna("기타")
    return df

# ───────────────────────── 2. 파일 업로드 ─────────────────────────
upl = st.sidebar.file_uploader("📂 매출 엑셀 업로드", type=["xlsx"])
if upl is None:
    st.stop()

df_raw = preprocess(upl)

# ───────────────────────── 3. 필터 영역 ─────────────────────────
st.title("📊 매장별 누적 전년비 대시보드")
with st.expander("🔎 필터", expanded=True):
    col1, col2 = st.columns([1.5, 3])
    all_months = sorted(df_raw["ym"].unique(), reverse=True)
    all_divs   = sorted(df_raw["division"].unique())

    sel_months = col1.multiselect("기준 월 (복수 선택 가능)", all_months, default=[all_months[0]])
    sel_divs   = col2.multiselect("구분 (division)", all_divs, default=all_divs)

if not sel_months:
    st.info("월을 한 개 이상 선택해 주세요.")
    st.stop()

ref_month = sel_months[0]                     # 첫 번째 선택 월을 기준으로 계산
cur_year, cur_month = int(ref_month[:4]), int(ref_month[-2:])
prev_year = cur_year - 1

df = df_raw[df_raw["division"].isin(sel_divs)]

# ───────────────────────── 4. 누적/전년비 계산 ─────────────────────────
def calc_ratio(cur, prev):
    if prev == 0 or cur == 0:
        return "-"                     # 전년 값이나 올해 값이 0 ➜ "-"
    return f'{((cur / prev) - 1) * 100:+.1f}%'

def agg_one_group(g):
    cur_rows = g[(g["year"] == cur_year) & (g["month"] == cur_month)]
    if cur_rows.empty:
        return pd.Series(dtype="float64")    # 당월 자체 데이터가 없으면 스킵

    cutoff = cur_rows["day"].max()           # 0 포함 마지막 일자

    month_cur = cur_rows["sales"].sum()
    month_prev = g[(g["year"] == prev_year) &
                   (g["month"] == cur_month) &
                   (g["day"] <= cutoff)]["sales"].sum()

    ytd_cur = g[(g["year"] == cur_year) &
                ((g["month"] < cur_month) | ((g["month"] == cur_month) & (g["day"] <= cutoff)))]["sales"].sum()
    ytd_prev = g[(g["year"] == prev_year) &
                 ((g["month"] < cur_month) | ((g["month"] == cur_month) & (g["day"] <= cutoff)))]["sales"].sum()

    return pd.Series({
        "division": g.iloc[0]["division"],
        "site":     g.iloc[0]["site"],
        f"{cur_year} 당월": month_cur,
        "당월 전년비(%)": calc_ratio(month_cur, month_prev),
        f"{cur_year} YTD": ytd_cur,
        "YTD 전년비(%)":  calc_ratio(ytd_cur, ytd_prev)
    })

result = df.groupby(["division", "site"]).apply(agg_one_group)
if isinstance(result, pd.Series):
    result = result.to_frame().T
result = result.reset_index(drop=True)

if result.empty:
    st.info("선택한 조건의 매출 데이터가 없습니다.")
    st.stop()

# ───────────────────────── 5. 합계·소계 생성 ─────────────────────────
totals = result.select_dtypes("number").sum()
tot_row = pd.Series({"division": "합계", "site": "", **totals,
                     "당월 전년비(%)": "-", "YTD 전년비(%)": "-"})

div_sub = (result.groupby("division")
           .sum(numeric_only=True).reset_index()
           .assign(site="", division=lambda d: d["division"] + " 소계",
                   **{"당월 전년비(%)": "-", "YTD 전년비(%)": "-"}))

final_tbl = pd.concat([tot_row.to_frame().T, div_sub, result], ignore_index=True)

# ───────────────────────── 6. 숫자 포맷 & 오른쪽 정렬 ─────────────────────────
def fmt_int(x):
    if isinstance(x, (int, float)):
        return f"{int(x):,}"
    return x

display_tbl = final_tbl.copy()
display_tbl[ [f"{cur_year} 당월", f"{cur_year} YTD"] ] = \
    display_tbl[ [f"{cur_year} 당월", f"{cur_year} YTD"] ].applymap(fmt_int)

# ── pandas Styler로 테이블 렌더 + CSS
def style_tbl(df):
    sty = (df.style
           .hide(axis="index")
           .set_properties(**{
               "text-align": "right"
           })
           .set_table_styles([
               {"selector": "th", "props": [("background-color", "#f8f8f8"), ("text-align", "center")]},
               {"selector": "tbody tr:first-child",
                "props": [("background-color", "mistyrose"), ("position", "sticky"), ("top", "0"), ("z-index", "1")]},
               {"selector": "thead tr",
                "props": [("position", "sticky"), ("top", "-1px"), ("background-color", "#ffffff"), ("z-index", "2")]}
           ])
           .apply(lambda r: ["background-color: mistyrose"
                             if ("합계" in str(r["division"]) or "소계" in str(r["division"]))
                             else "" for _ in r], axis=1))
    return sty

st.subheader(f"📋 {ref_month} 기준 누적 매출 전년비")
st.markdown(style_tbl(display_tbl).to_html(), unsafe_allow_html=True)

# ───────────────────────── 7. KPI 카드 ─────────────────────────
kpi_month = totals[f"{cur_year} 당월"]
kpi_ytd   = totals[f"{cur_year} YTD"]

k1, k2 = st.columns(2)
k1.metric("전체 당월 누적", f"{kpi_month:,.0f} 원")
k2.metric("전체 YTD 누적", f"{kpi_ytd:,.0f} 원")

# ───────────────────────── 8. 누적 추이 그래프 ─────────────────────────
st.subheader("연간 누적 매출 추이")
agg_line = (df.groupby(["year", "date"])["sales"].sum()
              .groupby(level=0).cumsum().reset_index())
agg_line["ym"] = agg_line["date"].dt.to_period("M").astype(str)

fig = px.line(agg_line, x="ym", y="sales", color="year", markers=True,
              labels={"ym": "월", "sales": "누적 매출", "year": "연도"})
fig.update_layout(yaxis_tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
