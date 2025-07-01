import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="OTD 누적 전년비 대시보드", layout="wide")

# ────────────────── 전처리 ──────────────────
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
    df["month"] = df["date"].dt.month
    df["day"]   = df["date"].dt.day
    return df

# ────────────────── 업로드 ──────────────────
uploaded = st.sidebar.file_uploader("📂 일자별 매출 엑셀 업로드", type=["xlsx"])
if uploaded is None:
    st.warning("엑셀 파일을 업로드해 주세요.")
    st.stop()

df_raw = preprocess(uploaded)

# ────────── 필터 UI (메인) ──────────
st.title("📊 매장별 누적 전년비 대시보드")

with st.expander("🔎 필터", expanded=True):
    col_m, col_s, col_b = st.columns(3)
    all_months = sorted(df_raw["ym"].unique())[::-1]  # 최신이 위
    all_sites  = sorted(df_raw["site"].unique())
    all_brands = sorted(df_raw["brand"].unique())

    sel_month = col_m.selectbox("기준 월(당월)", all_months[0])
    sel_sites = col_s.multiselect("사이트",  all_sites,  default=all_sites)
    sel_brands= col_b.multiselect("브랜드", all_brands, default=all_brands)

# 필터 적용
df = df_raw[
    df_raw["site"].isin(sel_sites) &
    df_raw["brand"].isin(sel_brands)
]

cur_year  = int(sel_month.split("-")[0])
cur_month = int(sel_month.split("-")[1])
prev_year = cur_year - 1

# ────────── 핵심 계산 함수 ──────────
def calc_row(grp: pd.DataFrame) -> pd.Series:
    # 당월 데이터(0 제외)
    this_month = grp[(grp["year"] == cur_year) & (grp["month"] == cur_month) & (grp["sales"] > 0)]
    if this_month.empty:
        return pd.Series(dtype="float")  # 데이터 없으면 skip

    last_date   = this_month["date"].max()          # 마지막 매출 발생일
    day_cutoff  = last_date.day

    # 당월 누적
    month_curr = this_month["sales"].sum()

    # 전년 동월 동일일자 누적
    prev_same = grp[(grp["year"] == prev_year) &
                    (grp["month"] == cur_month) &
                    (grp["day"]   <= day_cutoff)]
    month_prev = prev_same["sales"].sum()

    # 연간 누적 (해당 cutoff일까지)
    ytd_curr = grp[(grp["year"] == cur_year) &
                   ((grp["month"] <  cur_month) |
                    ((grp["month"] == cur_month) & (grp["day"] <= day_cutoff)))
                  ]["sales"].sum()
    ytd_prev = grp[(grp["year"] == prev_year) &
                   ((grp["month"] <  cur_month) |
                    ((grp["month"] == cur_month) & (grp["day"] <= day_cutoff)))
                  ]["sales"].sum()

    return pd.Series({
        "division": grp.iloc[0]["division"],
        "site":     grp.iloc[0]["site"],
        "brand":    grp.iloc[0]["brand"],
        f"{cur_year} 당월누적": month_curr,
        f"{prev_year} 당월누적": month_prev,
        "당월 전년비(%)": None if month_prev == 0 else (month_curr / month_prev - 1) * 100,
        f"{cur_year} YTD": ytd_curr,
        f"{prev_year} YTD": ytd_prev,
        "YTD 전년비(%)": None if ytd_prev == 0 else (ytd_curr / ytd_prev - 1) * 100
    })

# ────────── 테이블 생성 ──────────
result_df = (
    df.groupby(["division", "site", "brand"])
      .apply(calc_row)
      .dropna(subset=[f"{cur_year} 당월누적"])   # 당월 데이터 없는 행 제거
      .reset_index(drop=True)
)

# 총합 / division 소계
totals = result_df.select_dtypes("number").sum()
total_row = pd.Series({
    "division": "합계", "site": "", "brand": "",
    **totals
})

div_sub = (
    result_df.groupby("division")
             .sum(numeric_only=True)
             .reset_index()
             .assign(site="", brand="", division=lambda x: x["division"]+" 소계")
)

final_tbl = pd.concat([pd.DataFrame([total_row]), div_sub, result_df], ignore_index=True)

# ────────── 스타일 & 출력 ──────────
num_cols = final_tbl.select_dtypes("number").columns
styled = (final_tbl
          .style
          .apply(lambda r: ["background-color:#ffe6e6"
                            if ("합계" in str(r["division"]) or "소계" in str(r["division"]))
                            else "" for _ in r], axis=1)
          .format({col: "{:,.0f}" for col in num_cols if "누적" in col})
          .format({"당월 전년비(%)":"{:+.1f}%", "YTD 전년비(%)":"{:+.1f}%"}))

st.subheader(f"📋 {sel_month} 기준 누적 매출 전년비 (0 매출일 이후 제외)")
st.markdown(styled.to_html(), unsafe_allow_html=True)

# ────────── 요약 KPI ──────────
sum_month_curr = final_tbl.loc[0, f"{cur_year} 당월누적"]
sum_month_prev = final_tbl.loc[0, f"{prev_year} 당월누적"]
sum_ytd_curr   = final_tbl.loc[0, f"{cur_year} YTD"]
sum_ytd_prev   = final_tbl.loc[0, f"{prev_year} YTD"]

k1,k2 = st.columns(2)
k1.metric("전체 당월 누적", f"{sum_month_curr:,.0f} 원",
          f"{(sum_month_curr/sum_month_prev-1)*100:+.1f}%" if sum_month_prev else "N/A")
k2.metric("전체 YTD 누적",  f"{sum_ytd_curr:,.0f} 원",
          f"{(sum_ytd_curr/sum_ytd_prev-1)*100:+.1f}%" if sum_ytd_prev else "N/A")

# ────────── 누적 추이 그래프 ──────────
st.subheader("연간 누적 매출 추이 (전체 선택 기준)")
agg_line = (
    df[df["site"].isin(sel_sites) & df["brand"].isin(sel_brands)]
      .groupby(["year", "date"])["sales"].sum()
      .groupby(level=0).cumsum()
      .reset_index()
)
agg_line["ym"] = agg_line["date"].dt.to_period("M").astype(str)
fig = px.line(agg_line, x="ym", y="sales", color="year", markers=True,
              labels={"ym":"월","sales":"누적 매출","year":"연도"},
              title="전체 선택 매장의 연간 누적 추이")
fig.update_layout(yaxis_tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
