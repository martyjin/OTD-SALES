import streamlit as st
import pandas as pd
import plotly.express as px

# ────────────────── 기본 설정 ──────────────────
st.set_page_config(page_title="OTD 월별 매출 대시보드", layout="wide")

# ────────────────── 전처리 함수 ──────────────────
@st.cache_data
def preprocess_daily(file) -> pd.DataFrame:
    """엑셀 wide→long 변환 + ym(YYYY-MM) 컬럼 생성"""
    df = pd.read_excel(file, sheet_name="DATA")
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])

    df = df.rename(columns={"구분": "division", "사이트": "site",
                            "매장": "brand", "일자": "date",
                            "매출": "sales"})
    meta = ["division", "site", "brand"]
    df = df.melt(id_vars=meta, var_name="date", value_name="sales")

    df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
    df = df.dropna(subset=["sales"])
    df["sales"] = df["sales"].astype(int)

    df["date"] = pd.to_datetime(df["date"])
    df["ym"]   = df["date"].dt.to_period("M").astype(str)
    return df

# ────────────────── 월별 가로 테이블 ──────────────────
def monthly_wide_table(df: pd.DataFrame, months: list[str]) -> pd.DataFrame:
    monthly = df.groupby(["division", "site", "ym"])["sales"].sum().reset_index()

    pivoted = (
        monthly.pivot(index=["division", "site"], columns="ym", values="sales")
               .fillna(0).astype(int)
    )

    # 전체 합계
    total = pd.DataFrame(pivoted.sum(axis=0)).T
    total.index = pd.MultiIndex.from_tuples([("합계", "")],
                                            names=["division", "site"])

    # division 소계
    div_tot = (
        pivoted.groupby(level="division").sum()
    )
    div_tot.index = pd.MultiIndex.from_product(
        [div_tot.index, [""]], names=["division", "site"]
    )

    combined = pd.concat([total, div_tot, pivoted])

    # 인덱스 to 컬럼(중복 방지)
    combined = combined.reset_index()

    # 월 컬럼 순서 조정
    month_cols = [m for m in months if m in combined.columns]
    return combined[["division", "site"] + month_cols]

# ────────────────── 테이블 스타일 ──────────────────
def style_table(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    return (
        df.style
          .apply(lambda r: ["background-color:#ffe6e6"
                            if ("합계" in str(r["division"]) or "소계" in str(r["division"]))
                            else "" for _ in r], axis=1)
          .format("{:,.0f}")
    )

# ────────────────── 사이드바: 파일 업로드 ──────────────────
st.sidebar.header("📂 데이터 업로드")
uploaded = st.sidebar.file_uploader("일자별 매출 엑셀", type=["xlsx"])

if uploaded is None:
    st.warning("먼저 엑셀 파일을 업로드해 주세요.")
    st.stop()

# ────────────────── 데이터 로드 ──────────────────
df_raw = preprocess_daily(uploaded)

# ────────────────── 메인: 필터 UI ──────────────────
st.title("📊 월별 매출 대시보드")

with st.expander("🔎 필터", expanded=True):
    col_m, col_s, col_b = st.columns([2, 2, 2])

    all_months = sorted(df_raw["ym"].unique())
    all_sites  = sorted(df_raw["site"].unique())
    all_brands = sorted(df_raw["brand"].unique())

    sel_months = col_m.multiselect("월 선택", all_months, default=all_months)
    sel_sites  = col_s.multiselect("사이트 선택", all_sites, default=all_sites)
    sel_brands = col_b.multiselect("브랜드 선택", all_brands, default=all_brands)

# 필터 적용
df = df_raw[
    df_raw["ym"].isin(sel_months) &
    df_raw["site"].isin(sel_sites) &
    df_raw["brand"].isin(sel_brands)
]

# ────────────────── KPI ──────────────────
total_sales = df["sales"].sum()
kpi_cols = st.columns(2)
kpi_cols[0].metric("선택 월 총매출", f"{total_sales:,.0f} 원")
kpi_cols[1].metric("선택 월 수", len(sel_months))

st.divider()

# ────────────────── 월별 가로 테이블 ──────────────────
st.subheader("📆 월별 매출 테이블")
wide_tbl = monthly_wide_table(df, sel_months)
st.markdown(style_table(wide_tbl).to_html(), unsafe_allow_html=True)

# ────────────────── 꺾은선 그래프 ──────────────────
st.subheader("📈 매출 추이")
line_df = (
    df.groupby("ym")["sales"].sum()
      .reindex(sel_months).reset_index()
)
fig = px.line(line_df, x="ym", y="sales", markers=True,
              title="선택 월 매출 추이",
              labels={"ym": "월", "sales": "매출"})
fig.update_layout(yaxis_tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
