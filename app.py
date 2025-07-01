import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="OTD 누적 전년비 대시보드", layout="wide")

# ───────────────── 1. 전처리 ─────────────────
@st.cache_data
def preprocess(xlsx):
    df = pd.read_excel(xlsx, sheet_name="DATA")
    df.columns = df.columns.map(str).str.strip()

    mapper = {}
    for c in df.columns:
        k = c.replace(" ", "")
        if k == "구분":   mapper[c] = "division"
        elif k == "사이트": mapper[c] = "site"
        elif k == "일자":  mapper[c] = "date"
        elif k == "매출":  mapper[c] = "sales"
    df = df.rename(columns=mapper)

    meta = ["division", "site"]
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

# ───────────────── 2. 업로드 ─────────────────
upl = st.sidebar.file_uploader("📂 매출 엑셀 업로드", type=["xlsx"])
if upl is None:
    st.stop()
df_raw = preprocess(upl)

# ───────────────── 3. 필터 ─────────────────
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
CY, CM = int(ref_month[:4]), int(ref_month[-2:])
PY = CY - 1
df = df_raw[df_raw["division"].isin(sel_divs)]

# ───────────────── 4. 누적·전년비 계산 ─────────────────
def calc_row(g):
    cur_rows = g[(g["year"] == CY) & (g["month"] == CM)]
    if cur_rows.empty:
        return pd.Series(dtype="float64")

    cutoff = cur_rows["day"].max()
    m_cur  = cur_rows["sales"].sum()
    m_prev = g[(g["year"] == PY) & (g["month"] == CM) & (g["day"] <= cutoff)]["sales"].sum()

    y_cur = g[(g["year"] == CY) &
              ((g["month"] < CM) | ((g["month"] == CM) & (g["day"] <= cutoff)))]["sales"].sum()
    y_prev = g[(g["year"] == PY) &
               ((g["month"] < CM) | ((g["month"] == CM) & (g["day"] <= cutoff)))]["sales"].sum()

    return pd.Series({
        "division": g.iloc[0]["division"],
        "site":     g.iloc[0]["site"],
        "month_cur": m_cur,
        "month_prev": m_prev,
        "ytd_cur":  y_cur,
        "ytd_prev": y_prev
    })

agg = df.groupby(["division", "site"]).apply(calc_row)
if isinstance(agg, pd.Series):
    agg = agg.to_frame().T
agg = agg.reset_index(drop=True)

# 전년비 계산
def ratio(c, p): return "-" if p == 0 or c == 0 else f"{((c/p)-1)*100:+.1f}%"
agg["당월 전년비(%)"] = agg.apply(lambda r: ratio(r.month_cur, r.month_prev), axis=1)
agg["YTD 전년비(%)"]  = agg.apply(lambda r: ratio(r.ytd_cur,  r.ytd_prev ), axis=1)

# ───── 합계·소계 계산 ─────
tot = agg[["month_cur", "month_prev", "ytd_cur", "ytd_prev"]].sum()
tot_row = pd.Series({
    "division": "합계", "site": "",
    "month_cur": tot.month_cur, "month_prev": tot.month_prev,
    "ytd_cur": tot.ytd_cur, "ytd_prev": tot.ytd_prev,
    "당월 전년비(%)": ratio(tot.month_cur, tot.month_prev),
    "YTD 전년비(%)":  ratio(tot.ytd_cur,  tot.ytd_prev )
})

div_sub = (agg.groupby("division")
            .sum(numeric_only=True)
            .reset_index()
            .assign(site="",
                    당월전년비=lambda d: d.apply(lambda r: ratio(r.month_cur, r.month_prev), axis=1),
                    YTD전년비=lambda d: d.apply(lambda r: ratio(r.ytd_cur, r.ytd_prev), axis=1))
            .rename(columns={"month_cur":"month_cur",
                             "month_prev":"month_prev",
                             "ytd_cur":"ytd_cur",
                             "ytd_prev":"ytd_prev",
                             "당월전년비":"당월 전년비(%)",
                             "YTD전년비":"YTD 전년비(%)"})
            .assign(division=lambda d: d["division"]+" 소계"))

full = pd.concat([tot_row.to_frame().T, div_sub, agg], ignore_index=True)

# ───── 숫자 포맷 및 열 정리 ─────
full = full.rename(columns={
    "month_cur": f"{CY} 당월",
    "ytd_cur":   f"{CY} YTD"
})
full = full[[ "division","site", f"{CY} 당월","당월 전년비(%)", f"{CY} YTD","YTD 전년비(%)" ]]

def fmt_int(x):
    return f"{int(x):,}" if isinstance(x,(int,float)) else x
full[[f"{CY} 당월", f"{CY} YTD"]] = full[[f"{CY} 당월", f"{CY} YTD"]].applymap(fmt_int)

# ───────────────── 5. 테이블 표시 ─────────────────
def style(df):
    return (df.style.hide(axis="index")
            .set_table_styles([
                {"selector":"th","props":[("background","#f6f6f6"),("text-align","center")]},
                {"selector":"td","props":[("text-align","right")]},
                {"selector":"tbody tr:first-child","props":[("background","mistyrose"),
                                                           ("position","sticky"),("top","0"),("z-index","1")]},
                {"selector":"thead tr","props":[("position","sticky"),("top","-1px"),
                                                ("background","#fff"),("z-index","2")]}
            ])
            .apply(lambda r:["background-color:mistyrose"
                             if ("합계" in str(r["division"]) or "소계" in str(r["division"])) else ""
                             for _ in r], axis=1))

st.subheader(f"📋 {ref_month} 기준 누적 매출 전년비")
html_table = style(full).to_html()
wrapper = """
<div style="max-height:600px; overflow-y:auto;">
{table}
</div>
""".format(table=html_table)
st.markdown(wrapper, unsafe_allow_html=True)

# ───────────────── 6. KPI ─────────────────
k1,k2 = st.columns(2)
k1.metric("전체 당월 누적", fmt_int(tot.month_cur),
          f"{ratio(tot.month_cur, tot.month_prev)}")
k2.metric("전체 YTD 누적",  fmt_int(tot.ytd_cur),
          f"{ratio(tot.ytd_cur,  tot.ytd_prev)}")

# ───────────────── 7. 누적 추이 그래프 ─────────────────
st.subheader("연간 누적 매출 추이 (선택 구분 기준)")
cumsum = (df.groupby(["year","date"])["sales"].sum()
            .groupby(level=0).cumsum().reset_index())
cumsum["ym"] = cumsum["date"].dt.to_period("M").astype(str)

fig = px.line(cumsum, x="ym", y="sales", color="year", markers=True,
              labels={"ym":"월","sales":"누적 매출","year":"연도"})
fig.update_layout(yaxis_tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
