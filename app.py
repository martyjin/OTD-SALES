import streamlit as st, pandas as pd, plotly.express as px

st.set_page_config("OTD 누적 전년비", layout="wide")

# ── 전처리
@st.cache_data
def preprocess(path):
    df = pd.read_excel(path, sheet_name="DATA")
    df.columns = df.columns.map(str).str.strip()

    mapper = {}
    for c in df.columns:
        k = c.replace(" ", "")
        if k=="구분": mapper[c]="division"
        elif k=="사이트": mapper[c]="site"
        elif k=="매장": mapper[c]="brand"
        elif k=="일자": mapper[c]="date"
        elif k=="매출": mapper[c]="sales"
    df = df.rename(columns=mapper)

    meta = ["division","site","brand"]
    df = df.melt(id_vars=meta, var_name="date", value_name="sales")
    df["sales"] = pd.to_numeric(df["sales"],errors="coerce").fillna(0).astype(int)
    df["date"]  = pd.to_datetime(df["date"], errors="coerce"); df.dropna(subset=["date"], inplace=True)
    df["ym"] = df["date"].dt.to_period("M").astype(str)
    df["year"]= df["date"].dt.year; df["month"]=df["date"].dt.month; df["day"]=df["date"].dt.day
    df["division"] = df["division"].astype(str)
    return df

upl = st.sidebar.file_uploader("📂 매출 엑셀 업로드", type=["xlsx"])
if not upl: st.stop()
df_raw = preprocess(upl)

# ── 필터
st.title("📊 매장별 누적 전년비 대시보드")
with st.expander("🔎 필터", expanded=True):
    c1,c2 = st.columns(2)
    months = sorted(df_raw["ym"].unique(), reverse=True)
    divs   = sorted(df_raw["division"].unique())
    sel_months = c1.multiselect("기준 월(복수 가능)", months, default=[months[0]])
    sel_divs   = c2.multiselect("구분", divs, default=divs)

if not sel_months: st.info("월을 선택하세요."); st.stop()
ref_month = sel_months[0]
cy, cm = int(ref_month[:4]), int(ref_month[-2:])
py = cy-1
df = df_raw[df_raw["division"].isin(sel_divs)]

# ── 누적 계산
def calc(g):
    cur = g[(g["year"]==cy)&(g["month"]==cm)]
    if cur.empty: return pd.Series(dtype='float')
    cutoff = cur["day"].max()
    m_cur = cur[cur["day"]<=cutoff]["sales"].sum()
    m_pre = g[(g["year"]==py)&(g["month"]==cm)&(g["day"]<=cutoff)]["sales"].sum()
    y_cur = g[(g["year"]==cy)&((g["month"]<cm)|((g["month"]==cm)&(g["day"]<=cutoff)))]["sales"].sum()
    y_pre = g[(g["year"]==py)&((g["month"]<cm)|((g["month"]==cm)&(g["day"]<=cutoff)))]["sales"].sum()
    return pd.Series({"division":g.iloc[0]["division"],"site":g.iloc[0]["site"],"brand":g.iloc[0]["brand"],
                      f"{cy} 당월":m_cur,"당월 전년비(%)":None if m_pre==0 else (m_cur/m_pre-1)*100,
                      f"{cy} YTD":y_cur,"YTD 전년비(%)":None if y_pre==0 else (y_cur/y_pre-1)*100})

res = df.groupby(["division","site","brand"]).apply(calc)
if isinstance(res,pd.Series): res=res.to_frame().T
res=res.reset_index(drop=True)
if res.empty: st.info("선택 조건에 데이터가 없습니다."); st.stop()

# ── 합계·소계·테이블
tot = res.select_dtypes('number').sum()
tot_row = pd.Series({"division":"합계","site":"","brand":"",**tot})
div_sub = (res.groupby("division").sum(numeric_only=True).reset_index()
           .assign(site="",brand="",division=lambda d:d["division"]+" 소계"))
final = pd.concat([tot_row.to_frame().T, div_sub, res], ignore_index=True)

# 포맷 함수
def fmt(x): return "{:,.0f}".format(int(x))
num_cols = final.select_dtypes('number').columns
styled = (final.style
          .apply(lambda r:["background-color:#ffe6e6"
                          if ("합계" in str(r["division"]) or "소계" in str(r["division"])) else ""
                          for _ in r],axis=1)
          .format({c: fmt for c in num_cols if "당월" in c or "YTD" in c})
          .format({"당월 전년비(%)":"{:+.1f}%","YTD 전년비(%)":"{:+.1f}%"}))

# CSS: 첫 행 sticky
table_html = styled.to_html()
custom_css = """
<style>
tbody tr:first-child {position: sticky; top: 0; background: #ffe6e6; z-index: 1;}
thead tr {position: sticky; top: -1px; background: #fff; z-index: 2;}
</style>
"""
st.markdown(custom_css + table_html, unsafe_allow_html=True)

# ── KPI
smc, syc = tot[f"{cy} 당월"], tot[f"{cy} YTD"]
k1,k2=st.columns(2)
k1.metric("전체 당월 누적", fmt(smc))
k2.metric("전체 YTD 누적", fmt(syc))

# ── 누적 추이 그래프
st.subheader("연간 누적 매출 추이")
agg=(df.groupby(["year","date"])["sales"].sum().groupby(level=0).cumsum().reset_index())
agg["ym"]=agg["date"].dt.to_period("M").astype(str)
fig=px.line(agg,x="ym",y="sales",color="year",markers=True,labels={"ym":"월","sales":"누적","year":"연도"})
fig.update_layout(yaxis_tickformat=",.0f"); st.plotly_chart(fig,use_container_width=True)
