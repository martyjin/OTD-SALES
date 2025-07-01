
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(layout="wide", page_title="매출 분석 대시보드")

@st.cache_data
def preprocess_daily(file) -> pd.DataFrame:
    df = pd.read_excel(file, sheet_name="DATA")
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])
    df = df.rename(columns={"구분": "division", "사이트": "site", "매장": "brand"})
    meta_cols = ["division", "site", "brand"]
    df_long = df.melt(id_vars=meta_cols, var_name="date", value_name="sales").reset_index(drop=True)
    df_long["sales"] = pd.to_numeric(df_long["sales"], errors="coerce")
    df_long = df_long.dropna(subset=["sales"])
    df_long["sales"] = df_long["sales"].astype(int)
    df_long["date"] = pd.to_datetime(df_long["date"])
    df_long["year"] = df_long["date"].dt.year
    df_long["month"] = df_long["date"].dt.to_period("M").astype(str)
    return df_long

# 사이드바 - 파일 업로드 및 필터 설정
st.sidebar.title("📁 데이터 업로드")
uploaded_file = st.sidebar.file_uploader("일자별 매출 엑셀 업로드", type=["xlsx"])
if uploaded_file:
    df = preprocess_daily(uploaded_file)

    # 필터
    sites = st.sidebar.multiselect("사이트 선택", options=df["site"].unique(), default=list(df["site"].unique()))
    brands = st.sidebar.multiselect("브랜드 선택", options=df["brand"].unique(), default=list(df["brand"].unique()))
    df = df[(df["site"].isin(sites)) & (df["brand"].isin(brands))]

    # KPI Section
    st.markdown("## 📊 핵심 지표")
    total_sales = df["sales"].sum()
    avg_sales = df.groupby("date")["sales"].sum().mean()
    active_sites = df["site"].nunique()
    active_brands = df["brand"].nunique()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 매출", f"{total_sales:,.0f} 원")
    col2.metric("일평균 매출", f"{avg_sales:,.0f} 원")
    col3.metric("사이트 수", active_sites)
    col4.metric("브랜드 수", active_brands)

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(["📈 대시보드", "🔍 인사이트", "📅 예측/시뮬레이션", "📂 Raw Data"])

    # 대시보드 탭
    with tab1:
        st.subheader("Top 10 사이트 매출")
        top_sites = df.groupby("site")["sales"].sum().sort_values(ascending=False).head(10).reset_index()
        st.dataframe(top_sites.style.format({"sales": "{:,.0f}"}))

        st.subheader("일자별 매출 추이")
        daily_sum = df.groupby("date")["sales"].sum().reset_index()
        fig = px.line(daily_sum, x="date", y="sales", title="일자별 매출 추이")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("사이트-브랜드 트리맵")
        treemap_df = df.groupby(["site", "brand"])["sales"].sum().reset_index()
        fig2 = px.treemap(treemap_df, path=["site", "brand"], values="sales")
        st.plotly_chart(fig2, use_container_width=True)

    # 인사이트 탭
    with tab2:
        st.subheader("요일별 평균 매출")
        df["weekday"] = df["date"].dt.day_name()
        weekday_avg = df.groupby("weekday")["sales"].mean().reindex(
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        )
        st.bar_chart(weekday_avg)

    # 예측/시뮬레이션 탭 (기초 틀만 제공)
    with tab3:
        st.subheader("예측 및 시뮬레이션 (예정 기능)")
        st.info("향후 Prophet 기반 예측 그래프, 비용 입력 기반 시뮬레이터 기능이 이곳에 추가될 예정입니다.")

    # Raw Data 탭
    with tab4:
        st.subheader("📂 업로드된 Raw Data 미리보기")
        st.dataframe(df.head(100).style.format({"sales": "{:,.0f}"}))
else:
    st.warning("엑셀 파일을 업로드하면 분석 결과가 나타납니다.")
