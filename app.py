import streamlit as st, pandas as pd, plotly.express as px

st.set_page_config("OTD 누적 전년비", layout="wide")

# ───────── 전처리 ─────────
@st.cache_data
def preprocess(path):
    df = pd.read_excel(path, sheet_name="DATA")
    df.columns = df.columns.str.strip()          # 공백 제거

    # 안전 매핑 (한글 → 영문)
    map_dict = {}
    for c in df.columns:
        key = c.replace(" ", "")
        if key == "구분": map_dict[c] = "division"
        elif key == "사이트": map_dict[c] = "site"
        elif key == "매장": map_dict[c] = "brand"
        elif key == "일자": map_dict[c] = "date"
        elif key == "매출": map_dict[c] = "sales"
    df = df.rename(columns=map_dict)

    # wide → long
    meta = ["division","site","brand"]
    df = df.melt(id_vars=meta, var_name="date", value_name="sales")

    df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0).astype(int)
    df["date"]  = pd.to_datetime(df["date"])
    df["ym"]    = df["date"].dt.to_period("M").astype(str)
    df["year"]  = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"]   = df["date"].dt.day
    return df

upl = st.sidebar.file_uploader("📂 매출 엑셀 업로드", type=["xlsx"])
if not upl: st.stop()

df_raw = preprocess(upl)

# ───────── 필터 ─────────
st.title("📊 매장별 누적 전년비 대시보드")
with st.expander("🔎 필터", expanded=True):
    c1,c2 = st.columns(2)
    months = sorted(df_raw["ym"].unique(), reverse=True)
    divisions = sorted(df_raw["division"].unique())

    sel_months = c1.multiselect("기준 월(다중 선택)", months, default=[months[0]])
    sel_divs   = c2.multiselect("구분", divisions, default=divisions)

if not sel_months:
    st.info("월을 선택하세요."); st.stop()

ref_month = sel_months[0]       # 기준 월
cur_year  = int(ref_month[:4])
cur_month = int(ref_month[-2:])
prev_year = cur_year - 1

df = df_raw[df_raw["division"].isin(sel_divs)]

# ───────── 누적 계산 (함수 동일) ─────────
def calc(g):
    mon_cur = g[(g["year"]==cur_year)&(g["month"]==cur_month)&(g["sales"]>0)]
    if mon_cur.empty: return pd.Series(dtype='float')

    cutoff = mon_cur["day"].max()
    m_cur = mon_cur["sales"].sum()
    m_pre = g[(g["year"]==prev_year)&(g["month"]==cur_month)&(g["day"]<=cutoff)]["sales"].sum()

    y_cur = g[(g["year"]==cur_year)&((g["month"]<cur_month)|((g["month"]==cur_month)&(g["day"]<=cutoff)))]["sales"].sum()
    y_pre = g[(g["year"]==prev_year)&((g["month"]<cur_month)|((g["month"]==cur_month)&(g["day"]<=cutoff)))]["sales"].sum()

    return pd.Series({"division":g.iloc[0]["division"],"site":g.iloc[0]["site"],"brand":g.iloc[0]["brand"],
                      f"{cur_year} 당월":m_cur,  f"{prev_year} 당월":m_pre,
                      "당월 전년비(%)":None if m_pre==0 else (m_cur/m_pre-1)*100,
                      f"{cur_year} YTD":y_cur, f"{prev_year} YTD":y_pre,
                      "YTD 전년비(%)":None if y_pre==0 else (y_cur/y_pre-1)*100})

res = df.groupby(["division","site","brand"]).apply(calc)
res = res.to_frame().T if isinstance(res,pd.Series) else res
res = res.reset_index(drop=True)

if res.empty:
    st.info("해당 조건의 매출 데이터가 없습니다."); st.stop()

# ───────── 합계/소계/표 출력 ─────────
tot = res.select_dtypes("number").sum()
total_row = pd.Series({"division":"합계","site":"","brand":"",**tot})
div_sub = (res.groupby("division").sum(numeric_only=True)
            .reset_index()
            .assign(site="",brand="",division=lambda d:d["division"]+" 소계"))
final = pd.concat([total_row.to_frame().T, div_sub, res], ignore_index=True)

num_cols = final.select_dtypes("number").columns
sty = (final.style
       .apply(lambda r:["background-color:#ffe6e6" if ("합계" in str(r["division"]) or "소계" in str(r["division"])) else "" for _ in r], axis=1)
       .format({c:"{:,.0f}" for c in num_cols if "당월" in c or "YTD" in c})
       .format({"당월 전년비(%)":"{:+.1f}%","YTD 전년비(%)":"{:+.1f}%"}))
st.markdown(sty.to_html(), unsafe_allow_html=True)
