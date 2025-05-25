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

    numeric_cols = df.select_dtypes(include='number').columns.tolist()
    existing_numeric_cols = [col for col in numeric_cols if col in df.columns]

    if not existing_numeric_cols:
        return df

    df = df.loc[(df[existing_numeric_cols] != 0).any(axis=1)]

    non_zero_cols = (df[existing_numeric_cols] != 0).any(axis=0)
    keep_numeric_cols = non_zero_cols[non_zero_cols].index.tolist()

    non_numeric_cols = [col for col in df.columns if col not in existing_numeric_cols]
    keep_cols = non_numeric_cols + keep_numeric_cols

    mask_numeric = (df[existing_numeric_cols] != 0).any(axis=0)
    mask_numeric.index = existing_numeric_cols

    is_numeric_col = df.columns.to_series().isin(existing_numeric_cols)
    is_keep_numeric = df.columns.to_series().isin(mask_numeric[mask_numeric].index)
    keep_mask = is_keep_numeric | ~is_numeric_col

    df = df.loc[:, keep_mask]

    if df.empty:
        return pd.DataFrame()

    sum_row = df[keep_numeric_cols].sum()
    for col in df.columns:
        if col not in keep_numeric_cols:
            sum_row[col] = ""
    sum_row = pd.DataFrame([sum_row])
    if group_label:
        sum_row[group_label] = "합계"
    df = pd.concat([sum_row, df], ignore_index=True)

    formatted_df = df.copy()
    for col in keep_numeric_cols:
        formatted_df[col] = formatted_df[col].apply(format_number)

    return formatted_df

def highlight_summary_rows(row, column):
    return ['background-color: #fde2e2'] * len(row) if row[column] == "합계" else [''] * len(row)

if os.path.exists(DATA_PATH):
    saved_df = pd.read_csv(DATA_PATH, encoding="cp949", parse_dates=["날짜"])
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
    df_bu_formatted = format_table_with_summary(df_bu.reset_index(), "사업부")
    if not df_bu_formatted.empty:
        df_bu_formatted = df_bu_formatted[["사업부"] + [col for col in df_bu_formatted.columns if col != "사업부"]]
        st.dataframe(df_bu_formatted.style.hide(axis="index").apply(lambda row: highlight_summary_rows(row, "사업부"), axis=1))

    st.markdown("---")
    st.markdown("### 2. 사이트별 매출 (사업부 / 유형 기준)")

    for bu in sorted(updated_df["사업부"].dropna().unique()):
        st.markdown(f"**▶ 사업부: {bu}**")
        df_filtered = updated_df[updated_df["사업부"] == bu]
        df_site = df_filtered.groupby(["유형", "사이트", "기준일"])["매출"].sum().unstack(fill_value=0).reset_index()
        df_site.columns.name = None

        summary_rows = []
        for group, group_df in df_site.groupby("유형"):
            group_sum = group_df.drop(columns=["유형", "사이트"]).sum()
            summary_row = {"유형": group, "사이트": f"{group} 소계"}
            summary_row.update(group_sum)
            summary_rows.append(summary_row)
            summary_rows.extend(group_df.to_dict("records"))
        df_site_expanded = pd.DataFrame(summary_rows)

        df_site_formatted = format_table_with_summary(df_site_expanded, None)
        if not df_site_formatted.empty:
            df_site_formatted.insert(0, "사이트", df_site_formatted.pop("사이트"))
            df_site_formatted.insert(0, "유형", df_site_formatted.pop("유형"))
            df_site_formatted.columns = ["유형", "사이트"] + df_site_formatted.columns[2:].tolist()

            last_type = None
            for i in range(len(df_site_formatted)):
                if df_site_formatted.loc[i, "유형"] == last_type:
                    df_site_formatted.loc[i, "유형"] = ""
                else:
                    last_type = df_site_formatted.loc[i, "유형"]

            st.dataframe(df_site_formatted.dropna(how='all', axis=1).style.hide(axis="index"), use_container_width=True)

        st.markdown("---")

    st.markdown("---")
    st.markdown("### 3. 브랜드별 매출")

    col1, col2, col3 = st.columns(3)
    bu_list = sorted(updated_df["사업부"].dropna().unique())
    selected_bu = col1.selectbox("사업부 선택", bu_list)

    type_list = sorted(updated_df[updated_df["사업부"] == selected_bu]["유형"].dropna().unique())
    selected_type = col2.selectbox("유형 선택", type_list)

    site_list = sorted(updated_df[(updated_df["사업부"] == selected_bu) & (updated_df["유형"] == selected_type)]["사이트"].dropna().unique())
    selected_site = col3.selectbox("사이트 선택", site_list)

    if selected_site:
        st.markdown(f"**▶ 선택된 사이트: {selected_site}**")
        filtered = updated_df[updated_df["사이트"] == selected_site]
        if not filtered.empty:
            df_brand = filtered.groupby(["브랜드", "기준일"])["매출"].sum().unstack(fill_value=0).reset_index()
            df_brand_formatted = format_table_with_summary(df_brand, "브랜드")
            if not df_brand_formatted.empty:
                df_brand_formatted = df_brand_formatted[["브랜드"] + [col for col in df_brand_formatted.columns if col != "브랜드"]]
                st.dataframe(df_brand_formatted.style.hide(axis="index").apply(lambda row: highlight_summary_rows(row, "브랜드"), axis=1))
    else:
        st.markdown("_사이트를 선택하면 브랜드별 매출이 표시됩니다._")
else:
    st.warning("저장된 데이터가 없습니다. 엑셀 파일을 업로드해주세요.")
