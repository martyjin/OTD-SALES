import streamlit as st
import pandas as pd
import plotly.express as px

# ───────────────────── 페이지 설정 ─────────────────────
st.set_page_config(page_title="OTD 누적 전년비 대시보드", layout="wide")

# ────────────────── 1. 데이터 전처리 ──────────────────
@st.cache_data
def preprocess(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="DATA")

    # 헤더를 문자열로 변환하고 공백 제거
    df.columns = df.columns.map(str).str.strip()

    # 한글 → 영문 매핑 (공백‧대소문자 무시)
    mapping = {}
    for col in df.columns:
        key = col.replace(" ", "")
        if key == "구분": mapping[col] = "division"
        elif key == "사이트": mapping[col] = "site"
        elif key == "매장": mapping[col] = "brand"
        elif key == "일자": mapping[col] = "date"
        elif key == "매출": mapping[col] = "sales"
    df = df.rename(columns=mapping)

    meta = ["division", "site", "brand"]
    df = df.melt(id_vars=meta, var_name="date", value_name="sales")

    df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0).astype(int)
    df["date"]  = pd.to_datetime(df["date"], errors="coerce")
    df.dropna(subset=["date"], inplace=True)

    df["ym"]    = df["date"].dt.to_period("M").astype(str)
    df["year"]  = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"]   = df["date"].dt.day
    return df

# ────────────────── 2. 파일 업로드 ──────────────────
upl = st.sidebar.file_uploader("📂 매출 엑셀 업로드", type=["xlsx"])
if upl is None:
    st.warning("엑셀 파일을 업로드해 주세요.")
    st.stop()

df_raw = preprocess(upl)

# ────────────────── 3. 필터 UI ──────────────────
st.title("📊 매장별 누적 전년비 대시보드")
with st.expander("🔎 필터", expanded=True):
    c1, c2 = st.columns(2)
    all_months = sorted(df_raw["ym"].unique(), reverse=True)
    all_divs   = sorted(df_raw["division"].unique())

    sel_months = c1.multiselect("기준 월(복수 선택 가능)", all_months, default=[all_months[0]])
    sel_divs   = c2.multiselect("구분(division)", all_divs, default=all_divs)

if not sel_months:
    st.info("월을 한 개 이상 선택하세요.")
    st.stop()

ref_month = sel_months[0]              # 첫 번째 월을 기준으로 계산
cur_year, cur_month = int(ref_month[:4]), int(ref_month[-2:])
prev_year = cur_year - 1

df = df_raw[df_raw["division"].isin(sel_divs)]

# ────────────────── 4. 누적 계산 함수 ──────────────────
def calc(g: pd.DataFrame) -> pd.Series:
    cur_rows = g[(g["year"] == cur_year) & (g["month"] == cur_month)]
    if cur_rows.empty:
        return pd.Series(dtype="float64")

    cutoff = cur_rows["day"].max()                 # 0 포함 마지막 날짜

    month_curr = cur_rows[cur_rows["day"] <= cutoff]["sales"].sum()
    month_prev = g[(g["year"] == prev_year) &
                   (g["month"] == cur_month) &
                   (g["day"] <= cutoff)]["sales"].sum()

    ytd_curr = g[(g["year"] == cur_year) &
                 ((g["month"] < cur_month) |
                  ((g["month"] == cur_month) & (g["day"] <= cutoff)))]["sales"].sum()
    ytd_prev = g[(g["year"] == prev_year) &
                 ((g["month"] < cur_month) |
                  ((g["month"] == cur_month) & (g["day"] <= cutoff)))]["sales"].sum()

    return pd.Series({
        "division": g.iloc[0]["division"],
        "site":     g.iloc[0]["site"],
        "brand":    g.iloc[0]["brand"],
        f"{cur_year} 당월": month_curr,
        f"{prev_year} 당월": month_prev,
        "당월 전년비(%)": None if month_prev == 0 else (month_curr / month_prev - 1) * 100,
        f"{cur_year} YTD": ytd_curr,
        f"{prev_year} YTD": ytd_prev,
        "YTD 전년비(%)": None if ytd_prev == 0 else (ytd_curr / ytd_prev - 1) * 100
    })

result = df.groupby(["division", "site", "brand"]).apply(calc)
if isinstance(result, pd.Series):
    result = result.to_frame().T
result = result.reset_index(drop=True)

if result.empty:
    st.info("선택한 조건의 매출 데이터가 없습니다.")
    st.stop()

# ────────────────── 5. 합계·소계·테이블 ──────────────────
totals = result.select_dtypes("number").sum()
total_row = pd.Series({"division": "합계", "site": "", "brand": "", **totals})

div_sub = (result.groupby("division")
           .sum(numeric_only=True).reset_index()
           .assign(site="", brand="", division=lambda d: d["division"] + " 소계"))

final_tbl = pd.concat([total_row.to_frame().T, div_sub, result], ignore_index=True)

num_cols = final_tbl.select_dtypes("number").columns
styled = (final_tbl.style
          .apply(lambda r: ["background-color:#ffe6e6"
                            if ("합계" in str(r["division"]) or "소계" in str(r["division"]))
                            else "" for _ in r], axis=1)
          .format({c: "{:,.0f}" for c in num_cols if "당월" in c or "YTD" in c})
          .format({"당월 전년비(%)": "{:+.1f}%", "YTD 전년비(%)": "{:+.1f}%"}))

st.subheader(f"📋 {ref_month} 기준 누적 매출 전년비")
st.markdown(styled.to_html(), unsafe_allow_html=True)

# ────────────────── 6. KPI 카드 ──────────────────
sum_m_cur = totals[f"{cur_year} 당월"]
sum_m_pre = totals[f"{prev_year} 당월"]
sum_y_cur = totals[f"{cur_year} YTD"]
sum_y_pre = totals[f"{prev_year} YTD"]

c_kpi1, c_kpi2 = st.columns(2)
c_kpi1.metric("전체 당월 누적", f"{sum_m_cur:,.0f} 원",
              f"{(sum_m_cur / sum_m_pre - 1) * 100:+.1f}%" if sum_m_pre else "N/A")
c_kpi2.metric("전체 YTD 누적", f"{sum_y_cur:,.0f} 원",
              f"{(sum_y_cur / sum_y_pre - 1) * 100:+.1f}%" if sum_y_pre else "N/A")

# ────────────────── 7. 누적 추이 그래프 ──────────────────
st.subheader("연간 누적 매출 추이 (선택 구분 기준)")
agg = (df.groupby(["year", "date"])["sales"].sum()
         .groupby(level=0).cumsum().reset_index())
agg["ym"] = agg["date"].dt.to_period("M").astype(str)

fig = px.line(agg, x="ym", y="sales", color="year", markers=True,
              labels={"ym": "월", "sales": "누적 매출", "year": "연도"},
              title="연간 누적 매출 추이")
fig.update_layout(yaxis_tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
