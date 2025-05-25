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
    AgGrid(df, gridOptions=grid_options, height=500, width="100%", fit_columns_on_grid_load=False, theme="material")
