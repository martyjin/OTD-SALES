
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(layout="wide", page_title="월별 매출 대시보드")

###############################################################################
#                               데이터 전처리                                  #
###############################################################################
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
    df_long["ym"]   = df_long["date"].dt.to_period("M").astype(str)
    return df_long

###############################################################################
#                         월별 가로 테이블 생성 함수                            #
###############################################################################
def monthly_wide_table(df: pd.DataFrame, months: list[str] | None = None) -> pd.DataFrame:
    monthly = df.groupby(["division", "site", "ym"])["sales"].sum().reset_index()
    pivoted = monthly.pivot(index=["division", "site"], columns="ym", values="sales")                      .fillna(0).astype(int)

    # 합계(맨 위)
    total_row = pd.DataFrame(pivoted.sum(axis=0)).T
    total_row.index = pd.MultiIndex.from_tuples([("합계", "")], names=["division","site"])

    # 구분 소계
    div_tot = (
        pivoted.reset_index()
               .groupby("division")
               .sum()
               .assign(site="")
    )
    div_tot = div_tot.set_index(pd.MultiIndex.from_product([div_tot.index, [""]], names=["division","site"]))

    # 최종 테이블
    final = pd.concat([total_row, div_tot, pivoted])
    final.reset_index(inplace=True)

    # 원하는 월만 순서대로
    if months:
        month_cols = [m for m in months if m in final.columns]
        final = final[["division","site"] + month_cols]

    return final

###############################################################################
#                              스타일 함수                                     #
###############################################################################
def style_table(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    return (
        df.style
          .apply(lambda r: ["background-color: #ffe6e6"
                            if ("합계" in str(r["division"]) or "소계" in str(r["division"]))
                            else "" for _ in r], axis=1)
          .format("{:,.0f}")
    )

###############################################################################
#                               SIDEBAR UI                                    #
###############################################################################
st.sidebar.title("📁 데이터 업로드")
uploaded_file = st.sidebar.file_uploader("일자별 매출 엑셀 업로드", type=["xlsx"])

if not uploaded_file:
    st.warning("엑셀 파일을 업로드하면 분석 결과가 나타납니다.")
    st.stop()

df = preprocess_daily(uploaded_file)

# 필터: 사이트 / 브랜드
sites = st.sidebar.multiselect("사이트 선택", df["site"].unique(), default=list(df["site"].unique()))
brands = st.sidebar.multiselect("브랜드 선택", df["brand"].unique(), default=list(df["brand"].unique()))
df = df[df["site"].isin(sites) & df["brand"].isin(brands)]

# 월 리스트 & 월 필터
all_months = sorted(df["ym"].unique())
selected_months = st.sidebar.multiselect("표시할 월 선택", all_months, default=all_months)

###############################################################################
#                               KPI 영역                                      #
###############################################################################
st.title("📊 월별 매출 대시보드")

latest_year = max(int(m.split('-')[0]) for m in selected_months) if selected_months else df["date"].dt.year.max()
total_sales = df[df["ym"].isin(selected_months)]["sales"].sum()

c1, c2 = st.columns(2)
c1.metric("선택 월 총매출", f"{total_sales:,.0f} 원")
c2.metric("선택 월 수", len(selected_months))

st.markdown("---")

###############################################################################
#                           월별 가로 테이블 & 그래프                           #
###############################################################################
# 가로 테이블
pivoted_df = monthly_wide_table(df[df["ym"].isin(selected_months)], selected_months)
st.subheader("월별 매출 테이블")
st.markdown(style_table(pivoted_df).to_html(), unsafe_allow_html=True)

# 꺾은선 그래프 (합계 기준)
line_df = (
    df[df["ym"].isin(selected_months)]
      .groupby("ym")["sales"]
      .sum()
      .reindex(selected_months)
      .reset_index()
)
st.subheader("선택 월 매출 추이 (합계)")
fig = px.line(line_df, x="ym", y="sales", markers=True, title="월별 총매출 꺾은선 그래프")
fig.update_layout(xaxis_title="월", yaxis_title="매출", yaxis_tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
