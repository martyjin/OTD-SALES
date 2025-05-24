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
    numeric_cols = df.select_dtypes(include='number').columns

    df = df.loc[(df[numeric_cols] != 0).any(axis=1)]
    df = df.loc[:, (df[numeric_cols] != 0).any(axis=0) | ~df.columns.isin(numeric_cols)]

    if df.empty:
        return pd.DataFrame()

    df.loc["합계", numeric_cols] = df[numeric_cols].sum()

    formatted_df = df.copy()
    for col in numeric_cols:
        formatted_df[col] = formatted_df[col].apply(format_number)

    rows = ["합계"] + [idx for idx in formatted_df.index if idx != "합계"]
    formatted_df = formatted_df.loc[rows]

    if group_label:
        formatted_df.index.name = group_label

    return formatted_df

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
    df_bu = df_bu.loc[(df_bu != 0).any(axis=1)]
    df_bu_formatted = format_table_with_summary(df_bu, "사업부")
    if not df_bu_formatted.empty:
        st.dataframe(df_bu_formatted.style.set_properties(
    subset=pd.IndexSlice[["합계"], :],
    **{'background-color': '#fde2e2'}
))

    st.markdown("---")
    st.markdown("### 2. 사이트별 매출 (사업부 / 유형 기준)")
    for bu in sorted(updated_df["사업부"].dropna().unique()):
        st.markdown(f"**▶ 사업부: {bu}**")
        df_filtered = updated_df[updated_df["사업부"] == bu]
        df_site = df_filtered.groupby(["유형", "사이트", "기준일"])["매출"].sum().unstack(fill_value=0).reset_index()
        df_site.columns.name = None
        df_site_formatted = format_table_with_summary(df_site, None)
        if not df_site_formatted.empty:
            df_site_formatted.insert(0, "사이트", df_site_formatted.pop("사이트"))
            df_site_formatted.insert(0, "유형", df_site_formatted.pop("유형"))
            df_site_formatted.columns = ["유형", "사이트"] + df_site_formatted.columns[2:].tolist()
            st.dataframe(df_site_formatted.style.set_properties(
                subset=pd.IndexSlice[["합계"], :],
                **{'background-color': '#fde2e2'}
            ))
        st.markdown("---")

    st.markdown("---")
    st.markdown("### 3. 브랜드별 매출")

    col1, col2, col3 = st.columns(3)
    with col1:
        selected_bu = st.selectbox("사업부 선택 (브랜드 분석)", [""] + sorted(updated_df["사업부"].dropna().unique().tolist()))
    with col2:
        selected_type = st.selectbox("유형 선택 (선택사항)", [""] + sorted(updated_df["유형"].dropna().unique().tolist()))
    with col3:
        selected_site = st.selectbox("사이트 선택 (선택사항)", [""] + sorted(updated_df["사이트"].dropna().unique().tolist()))

    filtered = updated_df.copy()
    if selected_bu:
        filtered = filtered[filtered["사업부"] == selected_bu]
    if selected_type:
        filtered = filtered[filtered["유형"] == selected_type]
    if selected_site:
        filtered = filtered[filtered["사이트"] == selected_site]

    if not filtered.empty:
        df_brand = filtered.groupby(["사이트", "브랜드", "기준일"])["매출"].sum().unstack(fill_value=0)
        df_brand_formatted = format_table_with_summary(df_brand, "사이트/브랜드")
    if not df_brand_formatted.empty:
        st.dataframe(df_brand_formatted.style.set_properties(
    subset=pd.IndexSlice[["합계"], :],
    **{'background-color': '#fde2e2'}
))
else:
    st.warning("저장된 데이터가 없습니다. 엑셀 파일을 업로드해주세요.")
