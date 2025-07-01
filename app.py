import streamlit as st, pandas as pd, plotly.express as px

st.set_page_config("OTD 누적 전년비", layout="wide")

# ── 전처리
@st.cache_data
def preprocess(path):
    df = pd.read_excel(path, sheet_name="DATA")
    if "Unnamed: 0" in df.columns:
        df = df.drop(columns=["Unnamed: 0"])
    df = df.rename(columns={"구분":"division","사이트":"site",
                            "매장":"brand","일자":"date","매출":"sales"})
    df = df.melt(id_vars=["division","site","brand"],
                 var_name="date", value_name="sales")
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0).astype(int)
    df["date"]  = pd.to_datetime(df["date"])
    df["ym"]    = df["date"].dt.to_period("M").astype(str)
    df["year"]  = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"]   = df["date"].dt.day
    return df

upl = st.sidebar.file_uploader("📂 일자별 매출 엑셀", type=["xlsx"])
if not upl:
    st.stop()

df_raw = preprocess(upl)

# ── 필터
st.title("📊 매장별 누적 전년비 대시보드")
with st.expander("🔎 필터", expanded=True):
    c1,c2 = st.columns(2)
    all_months = sorted(df_raw["ym"].unique(), reverse=True)
    all_div    = sorted(df_raw["division"].unique())
    sel_months = c1.multiselect("월(복수 선택)", all_months, default=[all_months[0]])
    sel_div    = c2.multiselect("구분", all_div, default=all_div)

if not sel_months:
    st.info("월을 한 개 이상 선택하세요.")
    st.stop()

df = df_raw[df_raw["division"].isin(sel_div)]

# 편의상 **기준월 = sel_months[0]**
ref_month = sel_months[0]
cur_year  = int(ref_month[:4])
cur_month = int(ref_month[-2:])
prev_year = cur_year - 1

# ── 누적 계산 함수 (0 매출 허용)
def calc(g):
    # 당월 레코드(0 포함)
    cur_mon_rows  = g[(g["year"]==cur_year)  & (g["month"]==cur_month)]
    prev_mon_rows = g[(g["year"]==prev_year) & (g["month"]==cur_month)]

    if cur_mon_rows.empty and prev_mon_rows.empty:
        return pd.Series(dtype='float')

    # 0이 아닌 마지막 날짜 기준
    positive = cur_mon_rows[cur_mon_rows["sales"]>0]
    cutoff   = positive["day"].max() if not positive.empty else cur_mon_rows["day"].max()

    month_curr = cur_mon_rows[cur_mon_rows["day"]<=cutoff]["sales"].sum()
    month_prev = prev_mon_rows[prev_mon_rows["day"]<=cutoff]["sales"].sum()

    ytd_curr = g[(g["year"]==cur_year) &
                 ((g["month"]<cur_month) | ((g["month"]==cur_month)&(g["day"]<=cutoff)))]["sales"].sum()
    ytd_prev = g[(g["year"]==prev_year) &
                 ((g["month"]<cur_month) | ((g["month"]==cur_month)&(g["day"]<=cutoff)))]["sales"].sum()

    return pd.Series({
        "division":g.iat[0, g.columns.get_loc("division")],
        "site":g.iat[0, g.columns.get_loc("site")],
        "brand":g.iat[0, g.columns.get_loc("brand")],
        f"{cur_year} 당월":month_curr,
        f"{prev_year} 당월":month_prev,
        "당월 전년비(%)":None if month_prev==0 else (month_curr/month_prev-1)*100,
        f"{cur_year} YTD":ytd_curr,
        f"{prev_year} YTD":ytd_prev,
        "YTD 전년비(%)":None if ytd_prev==0 else (ytd_curr/ytd_prev-1)*100
    })

result = df.groupby(["division","site","brand"]).apply(calc)
if isinstance(result, pd.Series):
    result = result.to_frame().T
result = result.reset_index(drop=True)

if result.empty:
    st.info("선택한 조건에 해당하는 매출 데이터가 없습니다.")
    st.stop()

# ── 합계·소계·표
totals = result.select_dtypes('number').sum()
tot_row = pd.Series({"division":"합계","site":"","brand":"",**totals})
div_sub = (result.groupby("division").sum(numeric_only=True)
           .reset_index()
           .assign(site="",brand="",division=lambda d:d["division"]+" 소계"))
final = pd.concat([tot_row.to_frame().T, div_sub, result], ignore_index=True)

num_cols = final.select_dtypes('number').columns
sty = (final.style
       .apply(lambda r:["background-color:#ffe6e6"
                       if ("합계" in str(r["division"]) or "소계" in str(r["division"]))
                       else "" for _ in r],axis=1)
       .format({c:"{:,.0f}" for c in num_cols if "당월" in c or "YTD" in c})
       .format({"당월 전년비(%)":"{:+.1f}%","YTD 전년비(%)":"{:+.1f}%"}))

st.subheader(f"📋 {ref_month} 기준 누적 매출 전년비")
st.markdown(sty.to_html(), unsafe_allow_html=True)

# ── KPI
sum_m_cur,sum_m_pre = totals[f"{cur_year} 당월"], totals[f"{prev_year} 당월"]
sum_y_cur,sum_y_pre = totals[f"{cur_year} YTD"], totals[f"{prev_year} YTD"]
k1,k2=st.columns(2)
k1.metric("전체 당월 누적",f"{sum_m_cur:,.0f}",f"{(sum_m_cur/sum_m_pre-1)*100:+.1f}%" if sum_m_pre else "N/A")
k2.metric("전체 YTD 누적",f"{sum_y_cur:,.0f}",f"{(sum_y_cur/sum_y_pre-1)*100:+.1f}%" if sum_y_pre else "N/A")

# ── 누적 추이 그래프
agg = (df.groupby(["year","date"])["sales"].sum()
         .groupby(level=0).cumsum().reset_index())
agg["ym"]=agg["date"].dt.to_period("M").astype(str)
fig=px.line(agg,x="ym",y="sales",color="year",markers=True,
            labels={"ym":"월","sales":"누적 매출","year":"연도"})
fig.update_layout(yaxis_tickformat=",.0f")
st.plotly_chart(fig,use_container_width=True)
