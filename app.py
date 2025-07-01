import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="OTD 누적 전년비 대시보드", layout="wide")

# ────────── 전처리 ──────────
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

    df["date"]  = pd.to_datetime(df["date"])
    df["ym"]    = df["date"].dt.to_period("M").astype(str)
    df["year"]  = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"]   = df["date"].dt.day
    return df

# ────────── 업로드 ──────────
upl = st.sidebar.file_uploader("📂 일자별 매출 엑셀", type=["xlsx"])
if upl is None:
    st.warning("엑셀 파일을 업로드해 주세요.")
    st.stop()

df_raw = preprocess(upl)

# ────────── 필터 ──────────
st.title("📊 매장별 누적 전년비 대시보드")
with st.expander("🔎 필터", expanded=True):
    col_m, col_s, col_b = st.columns(3)
    all_months = sorted(df_raw["ym"].unique(), reverse=True)
    all_sites  = sorted(df_raw["site"].unique())
    all_brands = sorted(df_raw["brand"].unique())

    sel_month = col_m.selectbox("기준 월(당월)", all_months[0])
    sel_sites = col_s.multiselect("사이트",  all_sites,  default=all_sites)
    sel_brands= col_b.multiselect("브랜드", all_brands, default=all_brands)

df = df_raw[df_raw["site"].isin(sel_sites) & df_raw["brand"].isin(sel_brands)]

cur_year  = int(sel_month[:4])
cur_month = int(sel_month[-2:])
prev_year = cur_year - 1

# ────────── 그룹 계산 ──────────
def calc(grp: pd.DataFrame) -> pd.Series:
    this_m = grp[(grp["year"] == cur_year) & (grp["month"] == cur_month) & (grp["sales"] > 0)]
    if this_m.empty:
        return pd.Series(dtype="float64")  # 반환 안 함

    cutoff = this_m["day"].max()

    month_curr = this_m["sales"].sum()
    month_prev = grp[(grp["year"] == prev_year) &
                     (grp["month"] == cur_month) &
                     (grp["day"]   <= cutoff)]["sales"].sum()

    ytd_curr = grp[(grp["year"] == cur_year) &
                   ((grp["month"] < cur_month) |
                    ((grp["month"] == cur_month) & (grp["day"] <= cutoff))) ]["sales"].sum()
    ytd_prev = grp[(grp["year"] == prev_year) &
                   ((grp["month"] < cur_month) |
                    ((grp["month"] == cur_month) & (grp["day"] <= cutoff))) ]["sales"].sum()

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

result_df = (
    df.groupby(["division", "site", "brand"])
      .apply(calc)
      .reset_index(drop=True)
)

# ────────── 데이터 존재 확인 ──────────
if result_df.empty or f"{cur_year} 당월누적" not in result_df.columns:
    st.info("선택한 조건에 해당하는 매출 데이터가 없습니다.")
    st.stop()

# ────────── 합계·소계 ──────────
totals = result_df.select_dtypes("number").sum()
total_row = pd.Series({"division":"합계","site":"","brand":"",**totals})

div_sub = (result_df.groupby("division").sum(numeric_only=True)
           .reset_index()
           .assign(site="", brand="", division=lambda x: x["division"]+" 소계"))

final_tbl = pd.concat([total_row.to_frame().T, div_sub, result_df],
                      ignore_index=True)

# ────────── 표 스타일 & 출력 ──────────
num_cols = final_tbl.select_dtypes("number").columns
styled = (final_tbl.style
          .apply(lambda r: ["background-color:#ffe6e6"
                            if ("합계" in str(r["division"]) or "소계" in str(r["division"]))
                            else "" for _ in r], axis=1)
          .format({c:"{:,.0f}" for c in num_cols if "누적" in c})
          .format({"당월 전년비(%)":"{:+.1f}%","YTD 전년비(%)":"{:+.1f}%"}))

st.subheader(f"📋 {sel_month} 기준 누적 매출 전년비")
st.markdown(styled.to_html(), unsafe_allow_html=True)

# ────────── KPI ──────────
sum_month_curr, sum_month_prev = totals[f"{cur_year} 당월누적"], totals[f"{prev_year} 당월누적"]
sum_ytd_curr,   sum_ytd_prev   = totals[f"{cur_year} YTD"], totals[f"{prev_year} YTD"]

k1,k2 = st.columns(2)
k1.metric("전체 당월 누적", f"{sum_month_curr:,.0f} 원",
          f"{(sum_month_curr/sum_month_prev-1)*100:+.1f}%" if sum_month_prev else "N/A")
k2.metric("전체 YTD 누적",  f"{sum_ytd_curr:,.0f} 원",
          f"{(sum_ytd_curr/sum_ytd_prev-1)*100:+.1f}%" if sum_ytd_prev else "N/A")

# ────────── 추이 그래프 ──────────
st.subheader("연간 누적 매출 추이 (전체 선택 기준)")
agg = (df.groupby(["year","date"])["sales"].sum()
         .groupby(level=0).cumsum().reset_index())
agg["ym"] = agg["date"].dt.to_period("M").astype(str)
fig = px.line(agg, x="ym", y="sales", color="year", markers=True,
              labels={"ym":"월","sales":"누적 매출","year":"연도"})
fig.update_layout(yaxis_tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
