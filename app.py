import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

st.set_page_config(layout="wide", page_title="매출 분석 대시보드")

###############################################################################
#                               데이터 전처리 함수                             #
###############################################################################
@st.cache_data
def preprocess_daily(file) -> pd.DataFrame:
    """엑셀 Wide → Long 변환 + 파생컬럼."""
    df = pd.read_excel(file, sheet_name="DATA")
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])
    # 한글 → 영문 표준화
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

###############################################################################
#                 월별 매출 및 전년비(구분/사이트 소계 포함) 계산               #
###############################################################################
def monthly_yoy_table(df: pd.DataFrame) -> pd.DataFrame:
    """최종년도 월별 매출 + 전년비, 구분/사이트 소계 포함해 리턴"""
    latest_year = df["year"].max()
    prev_year   = latest_year - 1

    # 두 해만 필터링
    use = df[df["year"].isin([prev_year, latest_year])]
    grp = (
        use.groupby(["division", "site", "year", "month"])["sales"]
            .sum()
            .reset_index()
    )

    # 피벗 (월별)
    piv = grp.pivot_table(
        index   = ["division", "site", "month"],
        columns = "year",
        values  = "sales",
        aggfunc = "sum",
        fill_value = 0,
    )

    # 보정 컬럼
    if latest_year not in piv.columns: piv[latest_year] = 0
    if prev_year   not in piv.columns: piv[prev_year] = 0

    piv["YoY(%)"] = np.where(
        piv[prev_year]==0, np.nan,
        (piv[latest_year] / piv[prev_year] - 1) * 100
    )

    piv = piv.reset_index()
    piv.columns = ["division","site","month",
                   f"{prev_year} 매출",f"{latest_year} 매출","YoY(%)"]

    # ─── 구분 소계 ────────────────────────────────────────
    div_tot = (
        piv.groupby(["division","month"])[[f"{prev_year} 매출",f"{latest_year} 매출"]]
           .sum()
           .reset_index()
    )
    div_tot["division"] += " 소계"
    div_tot["site"]      = ""
    div_tot["YoY(%)"] = np.where(
        div_tot[f"{prev_year} 매출"]==0, np.nan,
        (div_tot[f"{latest_year} 매출"]/div_tot[f"{prev_year} 매출"] - 1)*100
    )

    # ─── 전체 합계 ────────────────────────────────────────
    all_tot = (
        piv.groupby("month")[[f"{prev_year} 매출",f"{latest_year} 매출"]]
           .sum()
           .reset_index()
    )
    all_tot["division"] = "합계"
    all_tot["site"]     = ""
    all_tot["YoY(%)"] = np.where(
        all_tot[f"{prev_year} 매출"]==0, np.nan,
        (all_tot[f"{latest_year} 매출"]/all_tot[f"{prev_year} 매출"] - 1)*100
    )

    # 컬럼 순서 통일
    div_tot = div_tot[["division","site","month",
                       f"{prev_year} 매출",f"{latest_year} 매출","YoY(%)"]]
    all_tot = all_tot[["division","site","month",
                       f"{prev_year} 매출",f"{latest_year} 매출","YoY(%)"]]

    # 병합: 합계 → 구분소계 → 상세
    final = pd.concat([all_tot, div_tot, piv], ignore_index=True)
    return final

###############################################################################
#                           테이블 스타일 함수                                 #
###############################################################################
def style_sales_table(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """합계·소계 행 핑크, 숫자 서식 적용"""
    styler = (
        df.style
          .apply(lambda r: ["background-color: #ffe6e6"
                            if ("합계" in str(r["division"]) or "소계" in str(r["division"]))
                            else "" for _ in r], axis=1)
          .format({col: "{:,.0f}" for col in df.columns if "매출" in col})
          .format({"YoY(%)": "{:+.1f}%"})
    )
    return styler

###############################################################################
#                          SIDEBAR – 데이터 업로드                              #
###############################################################################
st.sidebar.title("📁 데이터 업로드")
uploaded_file = st.sidebar.file_uploader("일자별 매출 엑셀 업로드", type=["xlsx"])

if not uploaded_file:
    st.warning("엑셀 파일을 업로드하면 분석 결과가 나타납니다.")
    st.stop()

# ─── 전처리 & 필터 ─────────────────────────────────────────
df = preprocess_daily(uploaded_file)

sites  = st.sidebar.multiselect("사이트 선택",
                                options=df["site"].unique(),
                                default=list(df["site"].unique()))
brands = st.sidebar.multiselect("브랜드 선택",
                                options=df["brand"].unique(),
                                default=list(df["brand"].unique()))
df = df[(df["site"].isin(sites)) & (df["brand"].isin(brands))]

###############################################################################
#                              KPI (간결 버전)                                 #
###############################################################################
latest_year = df["year"].max(); prev_year = latest_year - 1
latest_sales = df[df["year"]==latest_year]["sales"].sum()
prev_sales   = df[df["year"]==prev_year]["sales"].sum()
yoy_total    = (latest_sales/prev_sales - 1)*100 if prev_sales else np.nan

c1,c2,c3 = st.columns(3)
c1.metric(f"{latest_year} 총 매출", f"{latest_sales:,.0f} 원")
c2.metric(f"{prev_year} 대비", f"{yoy_total:+.1f}%")
c3.metric("사이트 수", df["site"].nunique())

st.markdown("---")

###############################################################################
#                                   탭 구성                                    #
###############################################################################
tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 월별 매출 & 전년비", "🔍 인사이트", "📅 예측/시뮬레이션", "📂 Raw Data"]
)

# ────────── 📈 Tab 1 ──────────
with tab1:
    st.subheader(f"최종년도({latest_year}) 월별 매출 및 전년비")
    monthly_tbl = monthly_yoy_table(df)
    st.dataframe(
        style_sales_table(monthly_tbl).to_html(),
        use_container_width=True,
        height=600,
        unsafe_allow_html=True,
    )

# ────────── 🔍 Tab 2 ──────────
with tab2:
    st.subheader("요일별 평균 매출")
    df["weekday"] = df["date"].dt.day_name()
    order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    weekday_avg = (df.groupby("weekday")["sales"].mean().reindex(order).reset_index())
    st.bar_chart(weekday_avg, x="weekday", y="sales")

# ────────── 📅 Tab 3 ──────────
with tab3:
    st.subheader("예측 및 시뮬레이션 (예정)")
    st.info("Prophet 기반 예측, 비용·손익 시뮬레이터 기능이 이곳에 추가될 예정입니다.")

# ────────── 📂 Tab 4 ──────────
with tab4:
    st.subheader("Raw Data (상위 15행)")
    st.dataframe(
        df.head(15).style.format({"sales": "{:,.0f}"}),
        use_container_width=True,
        height=400,
    )
