import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="OTD 누적 전년비 대시보드", layout="wide")

# ─────────────────── 1. 전처리 ───────────────────
@st.cache_data
def preprocess(xlsx):
    df = pd.read_excel(xlsx, sheet_name="DATA")
    df.columns = df.columns.map(str).str.strip()               # 헤더 → str

    # 한글→영문 매핑
    mapper = {}
    for c in df.columns:
        k = c.replace(" ", "")
        if k == "구분":   mapper[c] = "division"
        elif k == "사이트": mapper[c] = "site"
        elif k == "일자":   mapper[c] = "date"
        elif k == "매출":   mapper[c] = "sales"
    df = df.rename(columns=mapper)

    meta = ["division", "site"]                                # brand 제거
    df = df.melt(id_vars=meta, var_name="date", value_name="sales")

    df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0).astype(int)
    df["date"]  = pd.to_datetime(df["date"], errors="coerce")
    df.dropna(subset=["date"], inplace=True)

    df["ym"]    = df["date"].dt.to_period("M").astype(str)
    df["year"]  = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"]   = df["date"].dt.day
    df["division"] = df["division"].astype(str).fillna("기타")
    return df

# ─────────────────── 2. 업로드 ───────────────────
upl = st.sidebar.file_uploader("📂 매출 엑셀 업로드", type=["xlsx"])
if upl is None:
    st.stop()

df_raw = preprocess(upl)

# ─────────────────── 3. 필터 ───────────────────
st.title("📊 매장별 누적 전년비 대시보드")
with st.expander("🔎 필터", expanded=True):
    c1, c2 = st.columns([1.6, 3])
    months = sorted(df_raw["ym"].unique(), reverse=True)
    divs   = sorted(df_raw["division"].unique())

    sel_months = c1.multiselect("기준 월 (복수 선택 가능)", months, default=[months[0]])
    sel_divs   = c2.multiselect("구분 (division)",         divs,   default=divs)

if not sel_months:
    st.info("월을 선택하세요."); st.stop()

ref_month = sel_months[0]
cy, cm = int(ref_month[:4]), int(ref_month[-2:])
py = cy - 1
df = df_raw[df_raw["division"].isin(sel_divs)]

# ─────────────────── 4. 계산 ───────────────────
def ratio(cur, prev):
    if prev == 0 or cur == 0: return "-"   # en-dash
    return f'{((cur/prev)-1)*100:+.1f}%'

def agg(g):
    cur_rows = g[(g["year"] == cy) & (g["month"] == cm)]
    if cur_rows.empty: return pd.Series(dtype='float')
    cutoff = cur_rows["day"].max()

    m_cur = cur_rows["sales"].sum()
    m_pre = g[(g["year"] == py) & (g["month"] == cm) & (g["day"]<=cutoff)]["sales"].sum()

    y_cur = g[(g["year"] == cy) &
              ((g["month"] < cm) | ((g["month"] == cm) & (g["day"]<=cutoff)))]["sales"].sum()
    y_pre = g[(g["year"] == py) &
              ((g["month"] < cm) | ((g["month"] == cm) & (g["day"]<=cutoff)))]["sales"].sum()

    return pd.Series({
        "division": g.iloc[0]["division"],
        "site":     g.iloc[0]["site"],
        f"{cy} 당월": m_cur,
        "당월 전년비(%)": ratio(m_cur, m_pre),
        f"{cy} YTD":  y_cur,
        "YTD 전년비(%)": ratio(y_cur, y_pre)
    })

res = df.groupby(["division", "site"]).apply(agg)
if isinstance(res, pd.Series): res = res.to_frame().T
res = res.reset_index(drop=True)
if res.empty: st.info("해당 조건에 데이터가 없습니다."); st.stop()

# ─────────────────── 5. 합계·소계 ───────────────────
tot_num = res.select_dtypes("number").sum()
tot_row = pd.Series({"division":"합계","site":"",
                     f"{cy} 당월":tot_num[f"{cy} 당월"],
                     "당월 전년비(%)":"-",
                     f"{cy} YTD":tot_num[f"{cy} YTD"],
                     "YTD 전년비(%)":"-"})

div_sub = (res.groupby("division")
             .sum(numeric_only=True)
             .reset_index()
             .assign(site="",
                     **{"당월 전년비(%)":"-","YTD 전년비(%)":"-"},
                     division=lambda d: d["division"]+" 소계"))

table = pd.concat([tot_row.to_frame().T, div_sub, res], ignore_index=True)

# ─────────────────── 6. 숫자 포맷 · 정렬 ───────────────────
def fmt_int(x):
    try: return f"{int(x):,}"
    except: return x

num_cols = [f"{cy} 당월", f"{cy} YTD"]
table[num_cols] = table[num_cols].applymap(fmt_int)

# Styler
def style(df):
    sty = (df.style
           .hide(axis="index")
           .set_table_styles([
                {"selector":"th","props":[("background","#fafafa"),("text-align","center")]},
                {"selector":"td","props":[("text-align","right")]},                # 숫자 오른쪽 정렬
                {"selector":"tbody tr:first-child",
                 "props":[("background","mistyrose"),("position","sticky"),("top","0"),("z-index","1")]},
                {"selector":"thead tr",
                 "props":[("position","sticky"),("top","-1px"),("background","#ffffff"),("z-index","2")]}
            ])
           .apply(lambda r:["background-color:mistyrose"
                           if ("합계" in str(r["division"]) or "소계" in str(r["division"])) else ""
                           for _ in r], axis=1))
    return sty

st.subheader(f"📋 {ref_month} 기준 누적 매출 전년비")
st.markdown(style(table).to_html(), unsafe_allow_html=True)

# ─────────────────── 7. KPI ───────────────────
k1,k2 = st.columns(2)
k1.metric("전체 당월 누적",  fmt_int(tot_num[f"{cy} 당월"]))
k2.metric("전체 YTD 누적",   fmt_int(tot_num[f"{cy} YTD"]))

# ─────────────────── 8. 누적 추이 그래프 ───────────────────
st.subheader("연간 누적 매출 추이")
agg_line = (df.groupby(["year","date"])["sales"].sum()
              .groupby(level=0).cumsum().reset_index())
agg_line["ym"] = agg_line["date"].dt.to_period("M").astype(str)
fig = px.line(agg_line, x="ym", y="sales", color="year", markers=True,
              labels={"ym":"월","sales":"누적 매출","year":"연도"})
fig.update_layout(yaxis_tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
