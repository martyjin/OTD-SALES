import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# ────────── 페이지 설정 ──────────
st.set_page_config(page_title="OTD 매출 전년비 대시보드", layout="wide")

# ────────── 데이터 전처리 ──────────
@st.cache_data
def preprocess(file) -> pd.DataFrame:
    df = pd.read_excel(file, sheet_name="DATA")
    if "Unnamed: 0" in df.columns:
        df.drop(columns=["Unnamed: 0"], inplace=True)

    df.rename(columns={"구분": "division", "사이트": "site",
                       "매장": "brand", "일자": "date",
                       "매출": "sales"}, inplace=True)
    meta = ["division", "site", "brand"]
    df = df.melt(id_vars=meta, var_name="date", value_name="sales")

    df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
    df.dropna(subset=["sales"], inplace=True)
    df["sales"] = df["sales"].astype(int)

    df["date"] = pd.to_datetime(df["date"])
    df["ym"]   = df["date"].dt.to_period("M").astype(str)
    df["year"] = df["date"].dt.year
    df["month_num"] = df["date"].dt.month
    return df

# ────────── 파일 업로드 ──────────
st.sidebar.header("📂 데이터 업로드")
uploaded = st.sidebar.file_uploader("일자별 매출 엑셀", type=["xlsx"])

if uploaded is None:
    st.warning("먼저 엑셀 파일을 업로드해 주세요.")
    st.stop()

df_raw = preprocess(uploaded)

# ────────── 필터 (메인 화면) ──────────
st.title("📊 전년비 누적 매출 대시보드")

with st.expander("🔎 필터", expanded=True):
    col_m, col_s, col_b = st.columns(3)
    all_months = sorted(df_raw["ym"].unique())
    all_sites  = sorted(df_raw["site"].unique())
    all_brands = sorted(df_raw["brand"].unique())

    sel_month = col_m.selectbox("기준 월 선택 (당월)", all_months[-1::-1])  # 최신월 기본
    sel_sites = col_s.multiselect("사이트",  all_sites,  default=all_sites)
    sel_brands= col_b.multiselect("브랜드", all_brands, default=all_brands)

# 필터 적용
df = df_raw[
    (df_raw["site"].isin(sel_sites)) &
    (df_raw["brand"].isin(sel_brands))
]

# ────────── 기준 연도 및 전년 계산 ──────────
cur_year  = int(sel_month.split("-")[0])
prev_year = cur_year - 1
cur_month_num = int(sel_month.split("-")[1])

# 당월 누적 (선택 월의 1일~말일) -------------------------
month_curr = df[(df["year"] == cur_year)  & (df["ym"] == sel_month)]["sales"].sum()
month_prev = df[(df["year"] == prev_year) & (df["ym"] == f"{prev_year}-{sel_month[-2:]}")]["sales"].sum()
month_yoy  = None if month_prev == 0 else (month_curr / month_prev - 1) * 100

# 연간 누적 (해당 월까지) -------------------------------
ytd_curr = df[(df["year"] == cur_year) &
              (df["month_num"] <= cur_month_num)]["sales"].sum()
ytd_prev = df[(df["year"] == prev_year) &
              (df["month_num"] <= cur_month_num)]["sales"].sum()
ytd_yoy  = None if ytd_prev == 0 else (ytd_curr / ytd_prev - 1) * 100

# ────────── KPI & 표 출력 ──────────
st.subheader(f"📈 {sel_month} 기준 누적 매출 전년비")
k1,k2 = st.columns(2)
k1.metric("당월 누적 매출", f"{month_curr:,.0f} 원",
          f"{month_yoy:+.1f}%" if month_yoy is not None else "N/A")
k2.metric("연간 누적 매출", f"{ytd_curr:,.0f} 원",
          f"{ytd_yoy:+.1f}%" if ytd_yoy is not None else "N/A")

# 표 요약
summary_df = pd.DataFrame({
    "구분": ["당월 누적", "연간 누적"],
    f"{cur_year} 매출": [month_curr, ytd_curr],
    f"{prev_year} 매출": [month_prev, ytd_prev],
    "전년비(%)": [month_yoy, ytd_yoy]
})
st.table(summary_df.style.format({f"{cur_year} 매출":"{:,.0f}",
                                  f"{prev_year} 매출":"{:,.0f}",
                                  "전년비(%)":"{:+.1f}%"}))

# ────────── 추이 그래프 (선택) ──────────
st.subheader("월별 누적 매출 추이")
line_df = (
    df[df["year"].isin([prev_year, cur_year])]
      .groupby(["year", "ym"])["sales"].sum()
      .groupby(level=0).cumsum()        # 누적값
      .reset_index()
)
fig = px.line(line_df, x="ym", y="sales", color="year",
              markers=True, labels={"ym":"월", "sales":"누적 매출", "year":"연도"},
              title="연간 누적 매출 추이")
fig.update_layout(yaxis_tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
