import streamlit as st
import pandas as pd
import plotly.express as px

# ───────────────────────── 페이지 설정 ─────────────────────────
st.set_page_config(page_title="OTD 누적 전년비 대시보드", layout="wide")

# ───────────────────────── 1. 전처리 ─────────────────────────
@st.cache_data
def preprocess(path):
    df = pd.read_excel(path, sheet_name="DATA")

    # 헤더 → 문자열 & 공백 제거
    df.columns = df.columns.map(str).str.strip()

    # 한글→영문 safe 매핑
    mapping = {}
    for col in df.columns:
        key = col.replace(" ", "")
        if key == "구분": mapping[col] = "division"
        elif key == "사이트": mapping[col] = "site"
        elif key == "매장":  mapping[col] = "brand"
        elif key == "일자":  mapping[col] = "date"
        elif key == "매출":  mapping[col] = "sales"
    df = df.rename(columns=mapping)

    meta = ["division", "site", "brand"]
    df = df.melt(id_vars=meta, var_name="date", value_name="sales")

    df["sales"] = pd.to_numeric(df["sales"], errors="coerce").fillna(0).astype(int)
    df["date"]  = pd.to_datetime(df["date"], errors="coerce")
    df.dropna(subset=["date"], inplace=True)

    df["ym"]    = df["date"].dt.to_period("M").astype(str)
    df["year"]  = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["day"]   = df["date"].dt.day

    # division 을 문자열로 통일 →  숫자·NaN 혼재 방지
    df["division"] = df["division"].astype(str).fillna("기타")
    return df

# ───────────────────────── 2. 업로드 ─────────────────────────
upl = st.sidebar.file_uploader("📂 매출 엑셀 업로드", type=["xlsx"])
if upl is None:
    st.stop()

df_raw = preprocess(upl)

# ───────────────────────── 3. 필터 ─────────────────────────
st.title("📊 매장별 누적 전년비 대시보드")
with st.expander("🔎 필터", expanded=True):
    c1, c2 = st.columns(2)

    all_months = sorted(df_raw["ym"].unique(), reverse=True)
    # ⬇️ division 항목을 문자열로 변환 후 정렬
    all_divs   = sorted(df_raw["division"].astype(str).unique())

    sel_months = c1.multiselect("기준 월(복수 선택 가능)", all_months, default=[all_months[0]])
    sel_divs   = c2.multiselect("구분(division)", all_divs, default=all_divs)

if not sel_months:
    st.info("월을 한 개 이상 선택하세요.")
    st.stop()

ref_month = sel_months[0]                # 첫 월을 기준으로
cur_year, cur_month = int(ref_month[:4]), int(ref_month[-2:])
prev_year = cur_year - 1

df = df_raw[df_raw["division"].astype(str).isin(sel_divs)]

# ───────────────────────── 4. 누적 계산 ─────────────────────────
def calc(g):
    cur_rows = g[(g["year"] == cur_year) & (g["month"] == cur_month)]
    if cur_rows.empty:
        return pd.Series(dtype="float64")

    cutoff = cur_rows["day"].max()  # 0 포함 마지막 날짜

    month_cur = cur_rows[cur_rows["day"] <= cutoff]["sales"].sum()
    month_pre = g[(g["year"] == prev_year) & (g["month"] == cur_month) &
                  (g["day"] <= cutoff)]["sales"].sum()

    ytd_cur = g[(g["year"] == cur_year) &
                ((g["month"] < cur_month) | ((g["month"] == cur_month) & (g["day"] <= cutoff)))]["sales"].sum()
    ytd_pre = g[(g["year"] == prev_year) &
                ((g["month"] < cur_month) | ((g["month"] == cur_month) & (g["day"] <= cutoff)))]["sales"].sum()

    return pd.Series({
        "division": g.iloc[0]["division"],
        "site":     g.iloc[0]["site"],
        "brand":    g.iloc[0]["brand"],
        f"{cur_year} 당월": month_cur,
        f"{prev_year} 당월": month_pre,
        "당월 전년비(%)": None if month_pre == 0 else (month_cur / month_pre - 1) * 100,
        f"{cur_year} YTD": ytd_cur,
        f"{prev_year} YTD": ytd_pre,
        "YTD 전년비(%)": None if ytd_pre == 0 else (ytd_cur / ytd_pre - 1) * 100
    })

result = df.groupby(["division", "site", "brand"]).apply(calc)
if isinstance(result, pd.Series):
    result = result.to_frame().T
result = result.reset_index(drop=True)

if result.empty:
    st.info("선택 조건에 해당하는 매출 데이터가 없습니다.")
    st.stop()

# ───────────────────────── 5. 합계·소계·테이블 ─────────────────────────
totals = result.select_dtypes("number").sum()
tot_row = pd.Series({"division": "합계", "site": "", "brand": "", **totals})

div_sub = (result.groupby("division")
           .sum(numeric_only=True).reset_index()
           .assign(site="", brand="", division=lambda d: d["division"] + " 소계"))

final_tbl = pd.concat([tot_row.to_frame().T, div_sub, result], ignore_index=True)

num_cols = final_tbl.select_dtypes("number").columns
styled = (final_tbl.style
          .apply(lambda r: ["background-color:#ffe6e6"
                            if ("합계" in str(r["division"]) or "소계" in str(r["division"]))
                            else "" for _ in r], axis=1)
          .format({c: "{:,.0f}" for c in num_cols if "당월" in c or "YTD" in c})
          .format({"당월 전년비(%)": "{:+.1f}%", "YTD 전년비(%)": "{:+.1f}%"}))

st.subheader(f"📋 {ref_month} 기준 누적 매출 전년비")
st.markdown(styled.to_html(), unsafe_allow_html=True)

# ───────────────────────── 6. KPI ─────────────────────────
sum_m_cur, sum_m_pre = totals[f"{cur_year} 당월"], totals[f"{prev_year} 당월"]
sum_y_cur, sum_y_pre = totals[f"{cur_year} YTD"], totals[f"{prev_year} YTD"]

kc1, kc2 = st.columns(2)
kc1.metric("전체 당월 누적", f"{sum_m_cur:,.0f} 원",
           f"{(sum_m_cur / sum_m_pre - 1) * 100:+.1f}%" if sum_m_pre else "N/A")
kc2.metric("전체 YTD 누적", f"{sum_y_cur:,.0f} 원",
           f"{(sum_y_cur / sum_y_pre - 1) * 100:+.1f}%" if sum_y_pre else "N/A")

# ───────────────────────── 7. 누적 추이 그래프 ─────────────────────────
st.subheader("연간 누적 매출 추이")
agg = (df.groupby(["year", "date"])["sales"].sum()
         .groupby(level=0).cumsum().reset_index())
agg["ym"] = agg["date"].dt.to_period("M").astype(str)
fig = px.line(agg, x="ym", y="sales", color="year", markers=True,
              labels={"ym": "월", "sales": "누적 매출", "year": "연도"})
fig.update_layout(yaxis_tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)
