import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="OTD 누적 전년비 대시보드", layout="wide")

# ───────── 1. 전처리 ─────────
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

    df = df.melt(id_vars=["division","site"], var_name="date", value_name="sales")
    df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0).astype(int)
    df["date"]  = pd.to_datetime(df["date"], errors="coerce")
    df.dropna(subset=["date"], inplace=True)

    df["ym"]    = df["date"].dt.to_period("M").astype(str)
    df["year"]  = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"]   = df["date"].dt.day
    df["division"] = df["division"].astype(str).fillna("기타")
    return df

# ───────── 2. 업로드 ─────────
upl = st.sidebar.file_uploader("📂 매출 엑셀 업로드", type=["xlsx"])
if upl is None:
    st.stop()
df_raw = preprocess(upl)

# ───────── 3. 필터 ─────────
st.title("📊 매장별 누적 전년비 대시보드")
with st.expander("🔎 필터", expanded=True):
    c1,c2 = st.columns([1.6,3])
    months = sorted(df_raw["ym"].unique(), reverse=True)
    divs   = sorted(df_raw["division"].unique())
    sel_months = c1.multiselect("기준 월(복수 선택)", months, default=[months[0]])
    sel_divs   = c2.multiselect("구분", divs, default=divs)

if not sel_months:
    st.info("월을 선택하세요."); st.stop()

ref_month = sel_months[0]
CY, CM = int(ref_month[:4]), int(ref_month[-2:])
PY = CY - 1
df = df_raw[df_raw["division"].isin(sel_divs)]

# ───────── 4. 누적·전년비 계산 ─────────
def ratio(cur, prev):
    return "-" if prev == 0 or cur == 0 else f"{((cur/prev)-1)*100:+.1f}%"

def agg_row(g):
    cur_rows = g[(g["year"]==CY) & (g["month"]==CM)]
    if cur_rows.empty: return pd.Series(dtype="float64")
    cutoff = cur_rows["day"].max()

    m_cur  = cur_rows["sales"].sum()
    m_prev = g[(g["year"]==PY) & (g["month"]==CM) & (g["day"]<=cutoff)]["sales"].sum()

    y_cur = g[(g["year"]==CY) &
              ((g["month"]<CM)|((g["month"]==CM)&(g["day"]<=cutoff)))]["sales"].sum()
    y_prev= g[(g["year"]==PY) &
              ((g["month"]<CM)|((g["month"]==CM)&(g["day"]<=cutoff)))]["sales"].sum()

    return pd.Series({"division":g.iloc[0]["division"],"site":g.iloc[0]["site"],
                      "month_cur":m_cur,"month_prev":m_prev,
                      "ytd_cur":y_cur,"ytd_prev":y_prev})

base = (df.groupby(["division","site"])
          .apply(agg_row)
          .reset_index(drop=True))

# Same Store Flag
base["SSS"] = (base["month_cur"]>0) & (base["month_prev"]>0)

# 전년비 컬럼
base["당월 전년비(%)"] = base.apply(lambda r: ratio(r.month_cur, r.month_prev), axis=1)
base["YTD 전년비(%)"]  = base.apply(lambda r: ratio(r.ytd_cur,  r.ytd_prev ), axis=1)

# ───────── 5. 합계·소계·SSS 집계 ─────────
def make_total(df_part, div_name):
    s = df_part.select_dtypes("number").sum()
    return pd.Series({"division":div_name,"site":"",
                      f"{CY} 당월":s.month_cur,
                      f"{CY} YTD":s.ytd_cur,
                      "당월 전년비(%)":ratio(s.month_cur, s.month_prev),
                      "YTD 전년비(%)": ratio(s.ytd_cur,  s.ytd_prev)})

# 전체 합계 & SSS 합계
tot_row     = make_total(base, "합계")
sss_tot_row = make_total(base[base["SSS"]], "SSS 합계")

# division 소계 & SSS 소계
div_tot_list, div_sss_list = [], []
for div, grp in base.groupby("division"):
    div_tot_list.append(make_total(grp, f"{div} 소계"))
    div_sss_list.append(make_total(grp[grp["SSS"]], f"{div} SSS 소계"))

# 상세(원본) 테이블 준비
detail = base.rename(columns={
    "month_cur":f"{CY} 당월",
    "ytd_cur":  f"{CY} YTD"
})[["division","site",f"{CY} 당월","당월 전년비(%)",f"{CY} YTD","YTD 전년비(%)"]]

# ───────── 테이블 병합 (합계 → SSS 합계 → 소계 → SSS 소계 → 상세) ─────────
table_parts = [tot_row.to_frame().T,
               sss_tot_row.to_frame().T,
               pd.DataFrame(div_tot_list),
               pd.DataFrame(div_sss_list),
               detail]

final = pd.concat(table_parts, ignore_index=True)

# 숫자 포맷
num_cols = [f"{CY} 당월", f"{CY} YTD"]
for c in num_cols:
    final[c] = final[c].apply(lambda x: f"{int(x):,}" if isinstance(x,(int,float)) else x)

# ───────── 6. 스타일 · sticky ─────────
def style(df):
    sty = (df.style.hide(axis="index")
           .set_table_styles([
              {"selector":"th","props":[("background","#f3f3f3"),("text-align","center")]},
              {"selector":"td","props":[("text-align","right")]},
              {"selector":"tbody tr:first-child",
               "props":[("background","mistyrose"),("position","sticky"),("top","0"),("z-index","1")]},
              {"selector":"thead tr",
               "props":[("position","sticky"),("top","-1px"),("background","#ffffff"),("z-index","2")]}
           ])
           .apply(lambda r:["background-color:mistyrose"
                            if ("합계" in str(r["division"]) or "소계" in str(r["division"]))
                            else "" for _ in r], axis=1))
    return sty

st.subheader(f"📋 {ref_month} 기준 누적 매출 · Same Store Sales")
tbl_html = style(final).to_html()
st.markdown(f'<div style="max-height:600px; overflow-y:auto;">{tbl_html}</div>', unsafe_allow_html=True)

# ───────── 7. KPI ─────────
tot_num = base.select_dtypes("number").sum()
k1,k2 = st.columns(2)
k1.metric("전체 당월 누적", f"{tot_num.month_cur:,.0f}")
k2.metric("전체 YTD 누적",  f"{tot_num.ytd_cur:,.0f}")

# ───────── 8. 누적 추이 그래프 ─────────
st.subheader("연간 누적 매출 추이 (선택 구분 기준)")
cumsum = (df.groupby(["year","date"])["sales"].sum()
            .groupby(level=0).cumsum().reset_index())
cumsum["ym"] = cumsum["date"].dt.to_period("M").astype(str)
fig = px.line(cumsum, x="ym", y="sales", color="year", markers=True,
              labels={"ym":"월","sales":"누적","year":"연도"})
fig.update_layout(yaxis_tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
