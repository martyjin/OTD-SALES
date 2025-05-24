import pandas as pd
import streamlit as st
import os
from prophet import Prophet
import matplotlib.pyplot as plt

st.set_page_config(page_title="OTD SALES", layout="wide")
st.title("\ud83d\udcca OTD \ub9e4\uc8fc \ubc30\uce58 \uc2dc\uc2a4\ud15c")

DATA_PATH = "saved_data.csv"
FORMAT_TAG = "FORMAT_001"

st.sidebar.header("\uc5d8\ucf69 \uc5c5\ub85c\ub4dc \ubc0f \ubcf4\uae30 \uc635\uc158")
uploaded_file = st.sidebar.file_uploader("\uc5d8\ucf69 \ud30c\uc77c \uc5c5\ub85c\ub4dc", type=["xlsx"])
date_view = st.sidebar.radio("\ubcf4\uae30 \ub2e8\uc704", ["\uc6d4\ubcc4", "\uc77c\ubcc4"], horizontal=True)

def format_number(x):
    try:
        return f"{int(x):,}"
    except:
        return x

def format_table_with_summary(df, group_label):
    df = df.copy()
    df.loc["\ud569\uacc4"] = df.sum(numeric_only=True)
    df = df.astype(int).applymap(format_number)
    df = df.loc[["\ud569\uacc4"] + [i for i in df.index if i != "\ud569\uacc4"]]
    df.index.name = group_label
    return df

if os.path.exists(DATA_PATH):
    saved_df = pd.read_csv(DATA_PATH, parse_dates=["\ub0a0\uc9dc"])
else:
    saved_df = pd.DataFrame(columns=["\ud3ec\ub9f7", "\uc0ac\uc5c5\ubd80", "\uc720\ud615", "\uc0ac\uc774\ud2b8", "\ube0c\ub79c\ub4dc", "\ub0a0\uc9dc", "\ub9e4\uc8fc"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    date_cols = df.columns[4:]
    df_melted = df.melt(id_vars=df.columns[:4], value_vars=date_cols,
                        var_name="\ub0a0\uc9dc", value_name="\ub9e4\uc8fc")

    df_melted["\ub0a0\uc9dc"] = pd.to_datetime(df_melted["\ub0a0\uc9dc"])
    df_melted["\ub9e4\uc8fc"] = pd.to_numeric(df_melted["\ub9e4\uc8fc"], errors="coerce").fillna(0)
    df_melted["\ud3ec\ub9f7"] = FORMAT_TAG

    merged = pd.merge(saved_df, df_melted,
                      on=["\ud3ec\ub9f7", "\uc0ac\uc5c5\ubd80", "\uc720\ud615", "\uc0ac\uc774\ud2b8", "\ube0c\ub79c\ub4dc", "\ub0a0\uc9dc"],
                      how="outer", suffixes=("_old", ""))
    merged["\ub9e4\uc8fc"] = merged["\ub9e4\uc8fc"].combine_first(merged["\ub9e4\uc8fc_old"])
    updated_df = merged[["\ud3ec\ub9f7", "\uc0ac\uc5c5\ubd80", "\uc720\ud615", "\uc0ac\uc774\ud2b8", "\ube0c\ub79c\ub4dc", "\ub0a0\uc9dc", "\ub9e4\uc8fc"]]
    updated_df.to_csv(DATA_PATH, index=False)

    st.success("\u2705 \ub370\uc774\ud130\uac00 \uc800\uc7a5\ub418\uc5b4\uc788\uace0, \uae30\uc874 \ub370\uc774\ud130\uc640 \ube44\uad50\ud574 \uc5c5\ub370\uc774\ud2b8\ub418\uc5c8\uc2b5\ub2c8\ub2e4.")
else:
    updated_df = saved_df.copy()
    st.info("\u2139\ufe0f \uc800\uc7a5\ub41c \ub370\uc774\ud130\ub97c \ubd88\ub7ec\uc640\uc694. \uc0c8 \ud30c\uc77c\uc744 \uc5c5\ub85c\ub4dc\ud558\uba74 \uc790\ub3d9\uc73c\ub85c \ubc18\uc601\ub429\ub2c8\ub2e4.")

if not updated_df.empty:
    updated_df["\ub0a0\uc9dc"] = pd.to_datetime(updated_df["\ub0a0\uc9dc"])
    updated_df["\uae30\uc900\uc77c"] = (
        updated_df["\ub0a0\uc9dc"].dt.to_period("M").astype(str)
        if date_view == "\uc6d4\ubcc4"
        else updated_df["\ub0a0\uc9dc"].dt.strftime("%Y-%m-%d")
    )

    st.markdown("### 1. \uc0ac\uc5c5\ubd80\ubcc4 \ub9e4\uc8fc \uc694\uc57d")
    df_bu = updated_df.groupby(["\uc0ac\uc5c5\ubd80", "\uae30\uc900\uc77c"])["\ub9e4\uc8fc"].sum().unstack(fill_value=0)
    df_bu_formatted = format_table_with_summary(df_bu, "\uc0ac\uc5c5\ubd80")
    st.dataframe(df_bu_formatted.style.set_properties(
        subset=pd.IndexSlice[["\ud569\uacc4"], :],
        **{'background-color': '#fde2e2'}
    ), height=600)

    st.markdown("---")
    st.markdown("### 2. \uc0ac\uc774\ud2b8\ubcc4 \ub9e4\uc8fc (개칭: \uc0ac\uc5c5\ubd80 / \uc720\ud615)")
    bu_list = updated_df["\uc0ac\uc5c5\ubd80"].unique().tolist()
    selected_bu = st.selectbox("\uc0ac\uc5c5\ubd80 \uc120\ud0dd", bu_list)
    df_filtered = updated_df[updated_df["\uc0ac\uc5c5\ubd80"] == selected_bu]
    df_site = df_filtered.groupby(["\uc720\ud615", "\uc0ac\uc774\ud2b8", "\uae30\uc900\uc77c"])["\ub9e4\uc8fc"].sum().unstack(fill_value=0)
    df_site_formatted = format_table_with_summary(df_site, "\uc720\ud615/\uc0ac\uc774\ud2b8")
    st.dataframe(df_site_formatted.style.set_properties(
        subset=pd.IndexSlice[["\ud569\uacc4"], :],
        **{'background-color': '#fde2e2'}
    ), height=600)

    st.markdown("---")
    st.markdown("### 3. \ube0c\ub79c\ub4dc\ubcc4 \ub9e4\uc8fc")
    unit = st.selectbox("\uc120\ud0dd: \uc0ac\uc5c5\ubd80 / \uc720\ud615 / \uc0ac\uc774\ud2b8", ["\uc0ac\uc5c5\ubd80", "\uc720\ud615", "\uc0ac\uc774\ud2b8"])
    unit_list = updated_df[unit].unique().tolist()
    selected_unit = st.selectbox(f"{unit} \uc120\ud0dd", unit_list)
    df_filtered_brand = updated_df[updated_df[unit] == selected_unit]
    df_brand = df_filtered_brand.groupby(["\uc0ac\uc774\ud2b8", "\ube0c\ub79c\ub4dc", "\uae30\uc900\uc77c"])["\ub9e4\uc8fc"].sum().unstack(fill_value=0)
    df_brand_formatted = format_table_with_summary(df_brand, "\uc0ac\uc774\ud2b8/\ube0c\ub79c\ub4dc")
    st.dataframe(df_brand_formatted.style.set_properties(
        subset=pd.IndexSlice[["\ud569\uacc4"], :],
        **{'background-color': '#fde2e2'}
    ), height=600)

    # ---- 예측 기능 ----
    st.markdown("---")
    st.markdown("### 4. \uc6d4\ubcc4 \ub9e4\uc8fc \uc608\ucc28")

    df_month = updated_df.copy()
    df_month["\uc6d4"] = df_month["\ub0a0\uc9dc"].dt.to_period("M").astype(str)
    monthly_sales = df_month.groupby("\uc6d4")["\ub9e4\uc8fc"].sum().reset_index()
    monthly_sales["ds"] = pd.to_datetime(monthly_sales["\uc6d4"] + "-01")
    monthly_sales = monthly_sales.rename(columns={"\ub9e4\uc8fc": "y"})[["ds", "y"]]

    model = Prophet()
    model.fit(monthly_sales)
    future = model.make_future_dataframe(periods=2, freq="MS")
    forecast = model.predict(future)

    forecast_result = forecast[["ds", "yhat"]].tail(2)
    forecast_result["\uc608\ucc28\uc6d4"] = forecast_result["ds"].dt.to_period("M").astype(str)
    forecast_result["\uc608\uc0c1\ub9e4\uc8fc"] = forecast_result["yhat"].round().astype(int).apply(lambda x: f"{x:,}")
    forecast_result = forecast_result[["\uc608\ucc28\uc6d4", "\uc608\uc0c1\ub9e4\uc8fc"]]
    st.dataframe(forecast_result)

    fig, ax = plt.subplots(figsize=(10, 4))
    model.plot(forecast, ax=ax)
    ax.set_title("\ud83d\udcc8 \uc6d4\ubcc4 \ub9e4\uc8fc \ucd94\uc774 \ubc0f \uc608\ucc28")
    ax.set_xlabel("\uc6d4")
    ax.set_ylabel("\ub9e4\uc8fc")
    st.pyplot(fig)
else:
    st.warning("\u2757 \uc800\uc7a5\ub41c \ub370\uc774\ud130\uac00 \uc5c6\uc2b5\ub2c8\ub2e4. \uc5d8\ucf69 \ud30c\uc77c\uc744 \uc5c5\ub85c\ub4dc\ud574\uc8fc\uc138\uc694.")
