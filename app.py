import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# --- 페이지 설정
st.set_page_config(page_title="OTD 월별 매출 대시보드", layout="wide")

# --- 파일 업로드
st.sidebar.title("📂 데이터 업로드")
uploaded_file = st.sidebar.file_uploader("일자별 매출 엑셀 업로드", type=["xlsx"])
df = None

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # 컬럼명 통일
    df.columns = df.columns.str.strip()
    
    # 월 컬럼 생성
    df["ym"] = pd.to_datetime(df["일자"]).dt.strftime("%Y-%m")

    # 필터 영역
    all_months = sorted(df["ym"].unique())
    all_sites = sorted(df["사이트"].unique())
    all_brands = sorted(df["브랜드"].unique())

    selected_months = st.sidebar.multiselect("📅 표시할 월 선택", all_months, default=all_months[-6:])
    selected_sites = st.sidebar.multiselect("🏬 사이트 선택", all_sites, default=all_sites)
    selected_brands = st.sidebar.multiselect("🍽️ 브랜드 선택", all_brands, default=all_brands)

    # 필터링
    df_sel = df[
        (df["ym"].isin(selected_months)) &
        (df["사이트"].isin(selected_sites)) &
        (df["브랜드"].isin(selected_brands))
    ]

    # --- KPI
    total_sales = df_sel["매출"].sum()
    site_count = df_sel["사이트"].nunique()
    month_count = df_sel["ym"].nunique()

    st.title("📊 월별 매출 대시보드")
    col1, col2 = st.columns(2)
    col1.metric("선택 월 총매출", f"{total_sales:,.0f} 원")
    col2.metric("선택 월 수", f"{month_count}")

    # --- 피벗 테이블 함수
    def monthly_wide_table(df, months=None):
        monthly = df.groupby(["구분", "사이트", "ym"])["매출"].sum().reset_index()

        pivoted = (
            monthly.pivot(index=["구분", "사이트"], columns="ym", values="매출")
                   .fillna(0)
                   .astype(int)
        )

        total_row = pd.DataFrame(pivoted.sum(axis=0)).T
        total_row.index = pd.MultiIndex.from_tuples([("합계", "")], names=["구분", "사이트"])

        div_tot = (
            pivoted.reset_index()
                   .groupby("구분")
                   .sum()
                   .assign(사이트="")
        )
        div_tot = div_tot.set_index(
            pd.MultiIndex.from_product([div_tot.index, [""]], names=["구분", "사이트"])
        )

        combined = pd.concat([total_row, div_tot, pivoted])
        combined = combined.reset_index()  # 수정: drop 제거로 '구분', '사이트' 컬럼 살림

        if months:
            month_cols = [m for m in months if m in combined.columns]
            combined = combined[["구분", "사이트"] + month_cols]

        return combined

    # --- 월별 매출 테이블
    st.subheader("📆 월별 매출 테이블")
    pivot_tbl = monthly_wide_table(df_sel, selected_months)
    styled_tbl = pivot_tbl.style.format(thousands=",") \
        .apply(lambda x: ['background-color: #fdd' if i == 0 else '' for i in range(len(x))], axis=1)

    st.dataframe(styled_tbl, use_container_width=True, height=500)

    # --- 꺾은선 그래프
    st.subheader("📈 월별 매출 추이 그래프")
    graph_df = df_sel.groupby("ym")["매출"].sum().reindex(selected_months).fillna(0)

    fig, ax = plt.subplots()
    ax.plot(graph_df.index, graph_df.values, marker='o')
    ax.set_ylabel("매출 (원)")
    ax.set_xlabel("월")
    ax.set_title("선택된 월의 매출 추이")
    ax.grid(True)
    st.pyplot(fig)
