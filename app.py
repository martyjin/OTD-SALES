import streamlit as st
import pandas as pd
import os
from datetime import datetime

DATA_FILE = os.path.expanduser("~/.streamlit/saved_data.csv")

def format_number(n):
    if pd.isna(n):
        return ""
    return f"{int(n):,}"

def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return None

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def merge_data(old_df, new_df):
    id_cols = ['사업부', '유형', '사이트', '브랜드']
    merged = old_df.copy() if old_df is not None else pd.DataFrame(columns=new_df.columns)
    for _, row in new_df.iterrows():
        mask = (
            (merged['사업부'] == row['사업부']) &
            (merged['유형'] == row['유형']) &
            (merged['사이트'] == row['사이트']) &
            (merged['브랜드'] == row['브랜드'])
        ) if not merged.empty else pd.Series([False] * len(merged))
        if mask.any():
            for col in new_df.columns[4:]:
                if col in merged.columns:
                    merged.loc[mask, col] = row[col]
                else:
                    merged[col] = row[col]
        else:
            merged = pd.concat([merged, pd.DataFrame([row])], ignore_index=True)
    return merged

st.set_page_config(page_title="OTD SALES", layout="wide")
st.title("📊 OTD SALES 매출 분석")

user_type = st.sidebar.radio("접속 유형을 선택하세요:", ("일반 사용자", "관리자"))
view_mode = st.sidebar.selectbox("분석 기준 선택", ["월별", "일별"])
existing_data = load_data()
if existing_data is not None:
    st.sidebar.caption(f"📁 저장된 파일 있음: {DATA_FILE.split('/')[-1]}")

uploaded_filename = None
if user_type == "관리자":
    password = st.sidebar.text_input("비밀번호를 입력하세요", type="password")
    if password == "1818":
        uploaded_file = st.sidebar.file_uploader("매출 데이터 엑셀 업로드", type=[".xlsx"])
        if uploaded_file:
            uploaded_filename = uploaded_file.name
            new_df = pd.read_excel(uploaded_file)
            old_df = load_data()
            merged_df = merge_data(old_df, new_df)
            save_data(merged_df)
            st.success("데이터가 성공적으로 저장되었습니다.")
            st.sidebar.caption(f"✅ 업로드된 파일: {uploaded_filename}")
    else:
        st.warning("올바른 비밀번호를 입력하세요.")
else:
    uploaded_file = None

data = load_data()
if data is None:
    st.info("데이터가 없습니다. 관리자만 업로드할 수 있습니다.")
    st.stop()

required_columns = ['사업부', '유형', '사이트', '브랜드']
value_columns = [col for col in data.columns if col not in required_columns]

data_melted = data.melt(id_vars=required_columns, value_vars=value_columns, var_name="일자", value_name="매출")
data_melted['일자'] = pd.to_datetime(data_melted['일자'], errors='coerce')
data_melted.dropna(subset=['일자'], inplace=True)
data_melted['매출'] = pd.to_numeric(data_melted['매출'], errors='coerce').fillna(0)

data_melted['기준'] = data_melted['일자'].dt.to_period("M").astype(str) if view_mode == "월별" else data_melted['일자'].dt.strftime("%Y-%m-%d")

def style_summary(df):
    return df.style.apply(lambda x: ['background-color: #ffe6ea' if x.name != '합계' and '[' in str(x.name) else 'background-color: #e6f0ff' if x.name == '합계' else ''] * len(x), axis=1)

# 1️⃣ 사업부별 매출
summary = data_melted.groupby(['기준', '사업부'])['매출'].sum().reset_index()
summary_pivot = summary.pivot(index='사업부', columns='기준', values='매출').fillna(0).astype(int)
sum_row = pd.DataFrame(summary_pivot.sum()).T
sum_row.index = ['합계']
summary_pivot = pd.concat([sum_row, summary_pivot])
st.subheader("1️⃣ 사업부별 매출")
st.dataframe(style_summary(summary_pivot.applymap(format_number)), use_container_width=True)

# 2️⃣ 사이트별 매출
st.subheader("2️⃣ 사이트별 매출")
site_grouped_all = data_melted.groupby(['기준', '사업부', '유형', '사이트'])['매출'].sum().reset_index()
사업부_리스트 = sorted(site_grouped_all['사업부'].unique())
for dept in 사업부_리스트:
    st.markdown(f"### 📍 {dept} 사업부")
    sub_data = site_grouped_all[site_grouped_all['사업부'] == dept].copy()
    유형_리스트 = sub_data['유형'].unique()
    df_combined = []
    for 유형 in 유형_리스트:
        df_u = sub_data[sub_data['유형'] == 유형].copy()
        pivot_sites = df_u.pivot(index='사이트', columns='기준', values='매출').fillna(0).astype(int)
        subtotal = pd.DataFrame(pivot_sites.sum()).T
        subtotal.index = [f"[{유형} 소계]"]
        유형_df = pd.concat([subtotal, pivot_sites])
        df_combined.append(유형_df)
    dept_df = pd.concat(df_combined)
    total_row = pd.DataFrame(dept_df.sum()).T
    total_row.index = ['합계']
    dept_df = pd.concat([total_row, dept_df])
    styled = dept_df.applymap(format_number)
    styled = styled.reset_index().rename(columns={'index': '사이트'})
    styled = styled.style.apply(lambda x: [
        'background-color: #e6f0ff' if x['사이트'] == '합계' else
        'background-color: #ffe6ea' if '[' in x['사이트'] else ''
    ] * len(x), axis=1)
    st.dataframe(styled, use_container_width=True)

# 3️⃣ 브랜드별 매출
st.subheader("3️⃣ 브랜드별 매출")
col1, col2, col3 = st.columns(3)
with col1:
    selected_dept = st.selectbox("사업부 선택", sorted(data_melted['사업부'].unique()))
with col2:
    filtered_type_options = sorted(data_melted[data_melted['사업부'] == selected_dept]['유형'].unique())
    selected_type = st.selectbox("유형 선택", filtered_type_options)
with col3:
    filtered_site_options = sorted(data_melted[(data_melted['사업부'] == selected_dept) & (data_melted['유형'] == selected_type)]['사이트'].unique())
    selected_site = st.selectbox("사이트 선택", filtered_site_options)

filtered = data_melted[(data_melted['사업부'] == selected_dept) & (data_melted['유형'] == selected_type) & (data_melted['사이트'] == selected_site)]
brand_summary = filtered.groupby(['기준', '브랜드'])['매출'].sum().reset_index()
brand_pivot = brand_summary.pivot(index='브랜드', columns='기준', values='매출').fillna(0).astype(int)
if not brand_pivot.empty:
    total = pd.DataFrame(brand_pivot.sum()).T
    total.index = ['합계']
    brand_pivot = pd.concat([total, brand_pivot])
    st.dataframe(style_summary(brand_pivot.applymap(format_number)), use_container_width=True, height=500)
else:
    st.info("해당 조건에 맞는 브랜드 매출 데이터가 없습니다.")

# 4️⃣ 매출 추이 그래프
st.subheader("📈 매출 추이 그래프")

with st.expander("사업부별 매출 추이 보기"):
    selected_dept_graph = st.selectbox("그래프용 사업부 선택", sorted(data_melted['사업부'].unique()), key="graph_dept")
    graph_df = data_melted[data_melted['사업부'] == selected_dept_graph]
    trend = graph_df.groupby(['기준'])['매출'].sum().reset_index()
    st.line_chart(trend.set_index('기준'))

with st.expander("유형별 매출 추이 보기"):
    if selected_dept_graph:
        filtered_types = sorted(data_melted[data_melted['사업부'] == selected_dept_graph]['유형'].unique())
        selected_type_graph = st.selectbox("그래프용 유형 선택", filtered_types, key="graph_type")
        graph_df = data_melted[(data_melted['사업부'] == selected_dept_graph) & (data_melted['유형'] == selected_type_graph)]
        trend = graph_df.groupby(['기준'])['매출'].sum().reset_index()
        st.line_chart(trend.set_index('기준'))

with st.expander("브랜드별 매출 추이 보기"):
    if selected_dept_graph and selected_type_graph:
        filtered_brands = sorted(data_melted[(data_melted['사업부'] == selected_dept_graph) & (data_melted['유형'] == selected_type_graph)]['브랜드'].unique())
        selected_brand_graph = st.selectbox("그래프용 브랜드 선택", filtered_brands, key="graph_brand")
        graph_df = data_melted[(data_melted['사업부'] == selected_dept_graph) & (data_melted['유형'] == selected_type_graph) & (data_melted['브랜드'] == selected_brand_graph)]
        trend = graph_df.groupby(['기준'])['매출'].sum().reset_index()
        st.line_chart(trend.set_index('기준'))

st.markdown("""
<style>
::-webkit-scrollbar {
    height: 14px;
    width: 14px;
}
</style>
""", unsafe_allow_html=True)
