import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# ────────────────────── 페이지 설정 ──────────────────────
st.set_page_config(page_title="월별 매출 대시보드", layout="wide")

# ────────────────────── 전처리 함수 ──────────────────────
@st.cache_data
def preprocess_daily(file) -> pd.DataFrame:
    """엑셀 wide → long 변환 + ym(YYYY-MM) 컬럼 생성"""
    df = pd.read_excel(file, sheet_name="DATA")

    # 불필요 컬럼 제거
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])

    # 컬럼 영문 표준화
    df = df.rename(columns={"구분": "division", "사이트": "site", "매장": "brand"})

    # wide → long
    meta_cols = ["division", "site", "brand"]
    df = df.melt(id_vars=meta_cols, var_name="date", value_name="sales").reset_index(drop=True)

    # 타입/결측 처리
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce")
    df = df.dropna(subset=["sales"])
    df["sales"] = df["sales"].astype(int)

    # 날짜 파생
    df["date"] = pd.to_datetime(df["date"])
    df["ym"]   = df["date"].dt.to_period("M").astype(str)

    return df

# ────────────────────── 월별 가로 테이블 ──────────────────────
def monthly_wide_table(df: pd.DataFrame, months: list[str] | None = None) -> pd.DataFrame:
    """division·site 행 + 월별 열 구조의 가로 테이블 생성 (합계·소계 포함)"""
    monthly = df.groupby(["division", "site", "ym"])["sales"].sum().reset_index()

    # 월 열로 피벗
    pivoted = (
        monthly.pivot(index=["division", "site"], columns="ym", values="sales")
               .fillna(0)
               .astype(int)
    )

    # 전체 합계 행
    total_row = pd.DataFrame(pivoted.sum(axis=0)).T
    total_row.index = pd.MultiIndex.from_tuples([("합계", "")], names=["division", "site"])

    # 구분(division) 소계
    div_tot = (
        pivoted.reset_index()
               .groupby("division")
               .sum()
               .assign(site="")
    )
    div_tot = div_tot.set_index(
        pd.MultiIndex.from_product([div_tot.index, [""]], names=["division", "site"])
    )

    # 병합 후 reset_index (컬럼 중복 충돌 방지)
    combined = pd.concat([total_row, div_tot, pivoted])
    combined = combined.reset_index()  # 'division','site'가 이미 없으므로 안전

    # 월 컬럼 순서 & 필터
    if months:
        month_cols = [m for m in months if m in combined.columns]
        combined = combined[["division", "site"] + month_cols]

    return combined

# ────────────────────── 테이블 스타일 ──────────────────────
def style_table(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    """합계·소계 행을 연한 핑크, 숫자 천단위 콤마"""
    return (
        df.style
          .apply(
              lambda r: [
                  "background-color: #ffe6e6"
                  if ("합계" in str(r["division"]) or "소계" in str(r["division"]))
                  else ""
                  for _ in r
              ],
              axis=1,
          )
          .format("{:,.0f}")
    )

# ────────────────────── 사이드바 ──────────────────────
st.sidebar.title("📁 데이터 업로드")
uploaded_file = st.sidebar.file_uploader("일자별 매출 엑셀 업로드", type=["xlsx"])

# 파일이 없으면 안내 후 종료
if uploaded_file is None:
    st.warning("엑셀 파일을 업로드하면 분석 결과가 나타납니다.")
    st.stop()

# ────────────────────── 데이터 준비 ──────────────────────
df = preprocess_daily(uploaded_file)

# ym 컬럼 재확인(안전망)
if "ym" not in df.columns:
    df["ym"] = pd.to_datetime(df["date"]).dt.to_period("M").astype(str)

# 월, 사이트, 브랜드 필터
all_months = sorted(df["ym"].unique())
selected_months = st.sidebar.multiselect("표시할 월 선택", all_months, default=all_months)

sites  = st.sidebar.multiselect("사이트 선택",  df["site"].unique(),   default=list(df["site"].unique()))
brands = st.sidebar.multiselect("브랜드 선택", df["brand"].unique(), default=list(df["brand"].unique()))

df = df[df["site"].isin(sites) & df["brand"].isin(brands)]
df_sel = df[df["ym"].isin(selected_months)]

# ────────────────────── KPI ──────────────────────
st.title("📊 월별 매출 대시보드")

total_sales = df_sel["sales"].sum()
col1, col2 = st.columns(2)
col1.metric("선택 월 총매출", f"{total_sales:,.0f} 원")
col2.metric("선택 월 수", len(selected_months))

st.markdown("---")

# ────────────────────── 월별 테이블 ──────────────────────
pivot_tbl = monthly_wide_table(df_sel, selected_months)
st.subheader("월별 매출 테이블")
st.markdown(style_table(pivot_tbl).to_html(), unsafe_allow_html=True)

# ────────────────────── 꺾은선 그래프 ──────────────────────
st.subheader("선택 월 매출 추이 (합계)")
line_df = (
    df_sel.groupby("ym")["sales"]
          .sum()
          .reindex(selected_months)  # 선택 월 순서 유지
          .reset_index()
)
fig = px.line(line_df, x="ym", y="sales", markers=True, title="월별 총매출 꺾은선 그래프")
fig.update_layout(xaxis_title="월", yaxis_title="매출", yaxis_tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
