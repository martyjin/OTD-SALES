import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# ────────────────── 페이지 기본 설정 ──────────────────
st.set_page_config(page_title="OTD 월별 매출 대시보드", layout="wide")

# ────────────────── 데이터 전처리 함수 ──────────────────
@st.cache_data
def preprocess_daily(file) -> pd.DataFrame:
    """엑셀 wide→long 변환 + 'ym'(YYYY-MM) 컬럼 생성"""
    df = pd.read_excel(file, sheet_name="DATA")

    # 불필요 컬럼 제거
    if "Unnamed: 0" in df.columns:
        df.drop(columns=["Unnamed: 0"], inplace=True)

    # 한글 → 영문 컬럼명 통일 (가독성)
    df.rename(columns={"구분": "division", "사이트": "site",
                       "매장": "brand", "일자": "date",
                       "매출": "sales"}, inplace=True)

    # wide → long (date 컬럼이 헤더인 형태를 녹인다)
    meta = ["division", "site", "brand"]
    df = df.melt(id_vars=meta, var_name="date", value_name="sales")

    # 타입 정리
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
    df = df.dropna(subset=["sales"])
    df["sales"] = df["sales"].astype(int)

    df["date"] = pd.to_datetime(df["date"])
    df["ym"]   = df["date"].dt.to_period("M").astype(str)
    return df

# ────────────────── 월별 가로 피벗 테이블 ──────────────────
def monthly_wide_table(df: pd.DataFrame, months: list[str] | None = None) -> pd.DataFrame:
    """division·site 행, 월(열) 구조로 피벗 + 합계/소계 포함"""
    monthly = df.groupby(["division", "site", "ym"])["sales"].sum().reset_index()

    # 월을 열로
    pivoted = (
        monthly.pivot(index=["division", "site"], columns="ym", values="sales")
               .fillna(0)
               .astype(int)
    )

    # 전체 합계
    total = pd.DataFrame(pivoted.sum(axis=0)).T
    total.index = pd.MultiIndex.from_tuples([("합계", "")], names=["division", "site"])

    # division 소계
    div_tot = (
        pivoted.reset_index()
               .groupby("division")
               .sum()
               .assign(site="")
    )
    div_tot.index = pd.MultiIndex.from_product([div_tot.index, [""]], names=["division", "site"])

    # 병합
    combined = pd.concat([total, div_tot, pivoted])

    # 인덱스 이름 명시 후 reset -> 중복 방지
    combined.index = combined.index.set_names(["division", "site"])
    combined = combined.reset_index()

    # 월 컬럼 필터/정렬
    if months:
        month_cols = [m for m in months if m in combined.columns]
        combined = combined[["division", "site"] + month_cols]

    return combined

# ────────────────── 테이블 스타일 ──────────────────
def style_table(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    return (
        df.style
          .apply(
              lambda r: ["background-color:#ffe6e6"
                         if ("합계" in str(r["division"]) or "소계" in str(r["division"]))
                         else "" for _ in r], axis=1)
          .format("{:,.0f}")
    )

# ────────────────── 사이드바 (파일 & 필터) ──────────────────
st.sidebar.title("📂 데이터 업로드")
uploaded = st.sidebar.file_uploader("일자별 매출 엑셀 업로드", type=["xlsx"])

if uploaded is None:
    st.warning("엑셀 파일을 업로드하면 분석 결과가 표시됩니다.")
    st.stop()

df_raw = preprocess_daily(uploaded)

# 필터 선택
all_months = sorted(df_raw["ym"].unique())
all_sites  = sorted(df_raw["site"].unique())
all_brands = sorted(df_raw["brand"].unique())

sel_months = st.sidebar.multiselect("📅 월 선택", all_months, default=all_months)
sel_sites  = st.sidebar.multiselect("🏬 사이트 선택", all_sites,  default=all_sites)
sel_brands = st.sidebar.multiselect("🍽 브랜드 선택", all_brands, default=all_brands)

df_filtered = df_raw[
    df_raw["ym"].isin(sel_months) &
    df_raw["site"].isin(sel_sites) &
    df_raw["brand"].isin(sel_brands)
]

# ────────────────── KPI ──────────────────
st.title("📊 월별 매출 대시보드")
kpi_sales = df_filtered["sales"].sum()
kpi_months = df_filtered["ym"].nunique()

col1, col2 = st.columns(2)
col1.metric("선택 월 총매출", f"{kpi_sales:,.0f} 원")
col2.metric("선택 월 수", kpi_months)

st.markdown("---")

# ────────────────── 월별 가로 테이블 ──────────────────
st.subheader("월별 매출 테이블")
wide_tbl = monthly_wide_table(df_filtered, sel_months)
st.markdown(style_table(wide_tbl).to_html(), unsafe_allow_html=True)

# ────────────────── 꺾은선 그래프 ──────────────────
st.subheader("선택 월 매출 추이")
line_df = (
    df_filtered.groupby("ym")["sales"].sum()
               .reindex(sel_months)
               .reset_index()
)
fig = px.line(line_df, x="ym", y="sales", markers=True,
              title="월별 총매출 꺾은선 그래프",
              labels={"ym": "월", "sales": "매출"})
fig.update_layout(yaxis_tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
