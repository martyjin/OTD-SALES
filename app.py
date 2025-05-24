import pandas as pd
import streamlit as st
import os
import matplotlib.pyplot as plt

st.set_page_config(page_title="OTD SALES", layout="wide")
st.title("OTD Sales")

DATA_PATH = "saved_data.csv"
FORMAT_TAG = "FORMAT_001"

st.sidebar.header("엑셀 업로드 및 보기 옵션")
uploaded_file = st.sidebar.file_uploader("엑셀 파일 업로드", type=["xlsx"])
date_view = st.sidebar.radio("보기 단위", ["월별", "일별"], horizontal=True)

def format_number(x):
    try:
        return f"{int(x):,}"
    except:
        return x

def format_table_with_summary(df, group_label):
    df = df.copy()
    df = df[df.sum(axis=1) != 0]  # 빈 행 제거
    df = df.loc[(df != 0).any(axis=1)]  # 모든 셀 값이 0인 행 제거 (추가 필터)
    if df.empty:
        return df
    df.loc["합계"] = df.sum(numeric_only=True)
    df = df.astype(int).applymap(format_number)
    df = df.loc[["합계"] + [i for i in df.index if i != "합계"]]
    df.index.name = group_label
    return df

if os.path.exists(DATA_PATH):
    saved_df = pd.read_csv(DATA_PATH, parse_dates=["날짜"])
else:
    saved_df = pd.DataFrame(columns=["포맷", "사업부", "유형", "사이트", "브랜드", "날짜", "매출"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    date_cols = df.columns[4:]
    df_melted = df.melt(id_vars=df.columns[:4], value_vars=date_cols,
                        var_name="날짜", value_name="매출")

    df_melted["날짜"] = pd.to_datetime(df_melted["날짜"])
    df_melted["매출"] = pd.to_numeric(df_melted["매출"], errors="coerce").fillna(0)
    df_melted["포맷"] = FORMAT_TAG

    merged = pd.merge(saved_df, df_melted,
                      on=["포맷", "사업부", "유형", "사이트", "브랜드", "날짜"],
                      how="outer", suffixes=("_old", ""))
    merged["매출"] = merged["매출"].combine_first(merged["매출_old"])
    updated_df = merged[["포맷", "사업부", "유형", "사이트", "브랜드", "날짜", "매출"]]
    updated_df.to_csv(DATA_PATH, index=False)

    st.success("데이터가 저장되었고, 기존 데이터와 비교하여 업데이트되었습니다.")
else:
    updated_df = saved_df.copy()
    st.info("저장된 데이터를 불러왔습니다. 새 파일을 업로드하면 자동으로 반영됩니다.")

if not updated_df.empty:
    updated_df["날짜"] = pd.to_datetime(updated_df["날짜"])
    updated_df = updated_df[
    updated_df["사업부"].notna() &
    (updated_df["사업부"].astype(str).str.strip() != "") &
    (updated_df["사업부"].astype(str).str.lower() != "nan")
]
    updated_df["기준일"] = (
        updated_df["날짜"].dt.to_period("M").astype(str)
        if date_view == "월별"
        else updated_df["날짜"].dt.strftime("%Y-%m-%d")
    )

    st.markdown("### 1. 사업부별 매출 요약")
    df_bu = updated_df.groupby(["사업부", "기준일"])["매출"].sum().unstack(fill_value=0)
    df_bu_formatted = format_table_with_summary(df_bu, "사업부")
    if not df_bu_formatted.empty:
        st.dataframe(df_bu_formatted.style.set_properties(
            subset=pd.IndexSlice[["합계"], :],
            **{'background-color': '#fde2e2'}
        ), height=600)

    st.markdown("---")
    st.markdown("### 2. 사이트별 매출 (사업부 / 유형 기준)")
    bu_list = updated_df["사업부"].unique().tolist()
    selected_bu = st.selectbox("사업부 선택", bu_list)
    df_filtered = updated_df[updated_df["사업부"] == selected_bu]
    df_site = df_filtered.groupby(["유형", "사이트", "기준일"])["매출"].sum().unstack(fill_value=0)
    df_site_formatted = format_table_with_summary(df_site, "유형/사이트")
    if not df_site_formatted.empty:
        st.dataframe(df_site_formatted.style.set_properties(
            subset=pd.IndexSlice[["합계"], :],
            **{'background-color': '#fde2e2'}
        ), height=600)

    st.markdown("---")
    st.markdown("### 3. 브랜드별 매출")
    unit = st.selectbox("선택: 사업부 / 유형 / 사이트", ["사업부", "유형", "사이트"])
    unit_list = updated_df[unit].unique().tolist()
    selected_unit = st.selectbox(f"{unit} 선택", unit_list)
    df_filtered_brand = updated_df[updated_df[unit] == selected_unit]
    df_brand = df_filtered_brand.groupby(["사이트", "브랜드", "기준일"])["매출"].sum().unstack(fill_value=0)
    df_brand_formatted = format_table_with_summary(df_brand, "사이트/브랜드")
    if not df_brand_formatted.empty:
        st.dataframe(df_brand_formatted.style.set_properties(
            subset=pd.IndexSlice[["합계"], :],
            **{'background-color': '#fde2e2'}
        ), height=600)
else:
    st.warning("저장된 데이터가 없습니다. 엑셀 파일을 업로드해주세요.")
