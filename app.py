import pandas as pd
import streamlit as st
import os
import matplotlib.pyplot as plt
from st_aggrid import AgGrid, GridOptionsBuilder

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

    if group_label:
        sum_df = df[
            ~df[group_label].astype(str).str.contains("소계", na=False) &
            (df[group_label].astype(str).str.strip() != "합계")
        ]
    else:
        sum_df = df

    sum_row = sum_df[keep_numeric_cols].sum()
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


def aggrid_table(df, pinned_column):
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(resizable=True, wrapText=True, autoHeight=True)
    if pinned_column in df.columns:
        gb.configure_column(pinned_column, pinned="left")
    grid_options = gb.build()
    AgGrid(
        df,
        gridOptions=grid_options,
        height=600,
        width="100%",
        fit_columns_on_grid_load=False,
        theme="material"
    )


# 엑셀 업로드 또는 저장된 CSV 불러오기
if uploaded_file:
    df_raw = pd.read_excel(uploaded_file, sheet_name=0)
    df_raw.to_csv(DATA_PATH, index=False, encoding="utf-8-sig")
    st.success("데이터가 업로드되어 저장되었습니다.")
elif os.path.exists(DATA_PATH):
    df_raw = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    st.info("저장된 데이터를 불러왔습니다. 새 파일을 업로드하면 자동으로 반영됩니다.")
else:
    st.warning("엑셀 파일을 업로드해주세요.")
    st.stop()

# 사업부별 매출 요약 테이블 생성 및 표시
st.subheader("1. 사업부별 매출 요약")
df_bu = df_raw.groupby("사업부").sum(numeric_only=True).reset_index()
df_bu_formatted = format_table_with_summary(df_bu, "사업부")
aggrid_table(df_bu_formatted, pinned_column="사업부")
