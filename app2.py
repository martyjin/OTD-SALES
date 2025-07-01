import streamlit as st
import pandas as pd
import os
from datetime import datetime

st.set_page_config(page_title="OTD SALES", layout="wide")

# 파일 경로
DAILY_FILE = os.path.expanduser("~/.streamlit/saved_daily.csv")
MONTHLY_FILE = os.path.expanduser("~/.streamlit/saved_monthly.csv")

# 유틸 함수들
def is_month_based(columns):
    import re
    date_cols = [col for col in columns if re.match(r'^\d{4}-\d{2}$', str(col))]
    if not date_cols:
        return False
    try:
        sample = pd.to_datetime(date_cols, format='%Y-%m', errors='coerce')
        return sample.notna().all()
    except:
        return False

def load_data(file_path):
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    return None

def save_data(df, file_path):
    df.to_csv(file_path, index=False)

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

def format_number(n):
    try:
        return f"{int(float(n)):,}".rjust(15)
    except:
        return str(n)

def safe_str_to_int(x):
    try:
        x = str(x).replace(',', '').strip()
        if '%' in x or x == '' or x == '-':
            return 0
        return int(float(x))
    except:
        return 0

def style_summary(df):
    return df.style.apply(lambda x: ['background-color: #ffe6ea' if x.name != '합계' and '[' in str(x.name) else 'background-color: #e6f0ff' if x.name == '합계' else ''] * len(x), axis=1)

def add_yoy_column(df, group_cols):
    df_2024 = df[df['기준'].str.startswith('2024')].copy()
    df_2025 = df[df['기준'].str.startswith('2025')].copy()
    df_2024['key'] = pd.to_datetime(df_2024['기준']) + pd.DateOffset(years=1)
    df_2024['key'] = df_2024['key'].dt.strftime('%Y-%m')
    df_2025['key'] = df_2025['기준']
    merged = pd.merge(df_2025, df_2024[['key', '매출']], on='key', how='left', suffixes=('', '_전년'))
    merged['전년비'] = ((merged['매출'] - merged['매출_전년']) / merged['매출_전년'] * 100).round(1)
    merged['전년비'] = merged['전년비'].apply(lambda x: f"{x:+.1f}%" if pd.notnull(x) else "-")
    merged.drop(columns=['key'], inplace=True)
    return merged

# UI
st.title("📊 OTD SALES")
user_type = st.sidebar.radio("접속 유형을 선택하세요:", ("일반 사용자", "관리자"))
view_mode = "월별"

if user_type == "관리자":
    password = st.sidebar.text_input("비밀번호를 입력하세요", type="password")
    if password == "1818":
        uploaded_file = st.sidebar.file_uploader("매출 데이터 엑셀 업로드", type=[".xlsx"])
        if uploaded_file:
            new_df = pd.read_excel(uploaded_file)
            if is_month_based(new_df.columns):
                daily_ref = load_data(DAILY_FILE)
                if daily_ref is not None:
                    ref_cols = ['사이트', '사업부', '유형', '브랜드']
                    ref_table = daily_ref[ref_cols].drop_duplicates()
                    new_df = pd.merge(new_df, ref_table, on='사이트', how='left')
                    for col in ['사업부', '유형', '브랜드']:
                        if col not in new_df.columns:
                            new_df[col] = '미정'
                        new_df[col] = new_df[col].fillna('미정')
                else:
                    for col in ['사업부', '유형', '브랜드']:
                        new_df[col] = '미정'
                old_df = load_data(MONTHLY_FILE)
                merged_df = merge_data(old_df, new_df)
                save_data(merged_df, MONTHLY_FILE)
            else:
                old_df = load_data(DAILY_FILE)
                merged_df = merge_data(old_df, new_df)
                save_data(merged_df, DAILY_FILE)
            st.success("데이터가 성공적으로 저장되었습니다.")
else:
    uploaded_file = None

daily_data = load_data(DAILY_FILE)
monthly_data = load_data(MONTHLY_FILE)
if daily_data is None and monthly_data is None:
    st.info("데이터가 없습니다. 관리자만 업로드할 수 있습니다.")
    st.stop()

data = monthly_data.copy() if monthly_data is not None else pd.DataFrame()
required_columns = ['사업부', '유형', '사이트', '브랜드']
value_columns = [col for col in data.columns if col not in required_columns]
if data.empty and daily_data is not None:
    data = daily_data.copy()
    data_melted = data.melt(id_vars=required_columns, value_vars=value_columns, var_name="일자", value_name="매출")
    data_melted['일자'] = pd.to_datetime(data_melted['일자'], errors='coerce')
    data_melted.dropna(subset=['일자'], inplace=True)
    data_melted['매출'] = pd.to_numeric(data_melted['매출'], errors='coerce').fillna(0)
    data_melted['기준'] = data_melted['일자'].dt.to_period("M").astype(str)
    data_melted = data_melted[data_melted['기준'] >= '2025-01']
else:
    data_melted = data.melt(id_vars=required_columns, value_vars=value_columns, var_name="일자", value_name="매출")
    data_melted['일자'] = pd.to_datetime(data_melted['일자'], errors='coerce')
    data_melted.dropna(subset=['일자'], inplace=True)
    data_melted['매출'] = pd.to_numeric(data_melted['매출'], errors='coerce').fillna(0)
    data_melted['기준'] = data_melted['일자'].dt.to_period("M").astype(str)
    data_melted = data_melted[data_melted['기준'] >= '2025-01']

# 1️⃣ 사업부별 매출
st.subheader("1️⃣ 사업부별 매출")
sum_dept = data_melted.groupby(['기준', '사업부'])['매출'].sum().reset_index()
sum_dept = add_yoy_column(sum_dept, ['사업부'])
sum_dept = sum_dept.pivot(index='사업부', columns='기준', values=['매출', '전년비'])
sum_dept.columns = [f"{col[1]} {'전년비' if col[0] == '전년비' else ''}".strip() for col in sum_dept.columns]
sum_dept = sum_dept.fillna(0)
sum_dept.reset_index(inplace=True)
sum_dept.set_index('사업부', inplace=True)
sum_dept = sum_dept.astype(str)
sum_dept = sum_dept.applymap(lambda x: x if '%' in x else format_number(x))
total = pd.DataFrame(sum_dept.apply(lambda s: s.map(safe_str_to_int)).sum()).T
total.index = ['합계']
total = total.applymap(lambda x: format_number(x))
sum_dept = pd.concat([total, sum_dept])
st.dataframe(style_summary(sum_dept).set_properties(**{'text-align': 'right'}), use_container_width=True)

# 2️⃣ 사이트별 매출
st.subheader("2️⃣ 사이트별 매출")

for dept in sorted(data_melted['사업부'].unique()):
    st.markdown(f"### 📍 {dept} 사업부")
    sub_data = data_melted[data_melted['사업부'] == dept].copy()
    df_list = []
    for t in sorted(sub_data['유형'].unique()):
        df_u = sub_data[sub_data['유형'] == t].copy()
        sum_site = df_u.groupby(['기준', '사이트'])['매출'].sum().reset_index()
        sum_site = add_yoy_column(sum_site, ['사이트'])
        sum_site = sum_site.pivot(index='사이트', columns='기준', values=['매출', '전년비'])
        sum_site = sum_site.sort_index(axis=1, key=lambda x: x.str.replace(' 전년비', ''))
        new_columns = []
        for col in sorted(set(c.replace(' 전년비', '') for c in sum_site.columns.get_level_values(1))):
            new_columns.append(('매출', col))
            new_columns.append(('전년비', col))
        sum_site = sum_site.reindex(columns=pd.MultiIndex.from_tuples(new_columns))
        sum_site.columns = ["전년비" if col[0] == '전년비' else col[1] for col in sum_site.columns]
        sum_site = sum_site.fillna(0)
        sum_site.reset_index(inplace=True)
        sum_site.set_index('사이트', inplace=True)
        sum_site = sum_site.astype(str)
        sum_site = sum_site.applymap(lambda x: x if '%' in x else format_number(x))
        subtotal = pd.DataFrame(sum_site.applymap(parse_sales_value).sum()).T
        subtotal.index = [f"[{t} 소계]"]
        subtotal = subtotal.applymap(lambda x: format_number(x))
        df_list.append(pd.concat([subtotal, sum_site]))

    combined = pd.concat(df_list)
    total_only = combined[~combined.index.str.startswith('[')]
    total_sum = pd.DataFrame(total_only.applymap(parse_sales_value).sum()).T
    total_sum.index = ['합계']
    final_df = pd.concat([total_sum, combined])

    styled = final_df.applymap(format_number).reset_index().rename(columns={'index': '사이트'})
    styled = styled.style.apply(lambda x: [
        'background-color: #e6f0ff' if x['사이트'] == '합계' else
        'background-color: #ffe6ea' if '[' in x['사이트'] else ''
    ] * len(x), axis=1)

    st.dataframe(styled.set_properties(**{'text-align': 'right'}), use_container_width=True)

# 3️⃣ 브랜드별 매출
st.subheader("3️⃣ 브랜드별 매출")
view_mode = st.selectbox("분석 기준 선택", ["월별", "일별"])
col1, col2, col3 = st.columns(3)
with col1:
    selected_dept = st.selectbox("사업부 선택", sorted(data_melted['사업부'].unique()))
with col2:
    selected_type = st.selectbox("유형 선택", sorted(data_melted[data_melted['사업부'] == selected_dept]['유형'].unique()))
with col3:
    selected_site = st.selectbox("사이트 선택", sorted(data_melted[(data_melted['사업부'] == selected_dept) & (data_melted['유형'] == selected_type)]['사이트'].unique()))

filtered = data_melted[
    (data_melted['사업부'] == selected_dept) &
    (data_melted['유형'] == selected_type) &
    (data_melted['사이트'] == selected_site)
]

sum_brand = filtered.groupby(['기준', '브랜드'])['매출'].sum().reset_index()
sum_brand = add_yoy_column(sum_brand, ['브랜드']) if view_mode == "월별" else sum_brand
if view_mode == "월별":
    sum_brand = sum_brand.pivot(index='브랜드', columns='기준', values=['매출', '전년비'])
    sum_brand.columns = [f"{col[1]} {'전년비' if col[0] == '전년비' else ''}".strip() for col in sum_brand.columns]
    sum_brand = sum_brand.fillna(0)
    sum_brand = sum_brand.astype(str)
    sum_brand = sum_brand.applymap(lambda x: x if '%' in x else format_number(x))
else:
    sum_brand = sum_brand.pivot(index='브랜드', columns='기준', values='매출').fillna(0).astype(int)
    sum_brand = sum_brand.applymap(format_number)

if not sum_brand.empty:
    total = pd.DataFrame(sum_brand.applymap(parse_sales_value).sum()).T
    total.index = ['합계']
    total = total.applymap(lambda x: format_number(x))
    sum_brand = pd.concat([total, sum_brand])
    st.dataframe(style_summary(sum_brand).set_properties(**{'text-align': 'right'}), use_container_width=True, height=500)
else:
    st.info("해당 조건에 맞는 브랜드 매출 데이터가 없습니다.")

# 📈 추이 그래프
st.subheader("📈 매출 추이 그래프")
trend = data_melted.groupby(['기준', '사업부'])['매출'].sum().reset_index()
trend = trend[trend['사업부'] != '타분류']
for dept in sorted(trend['사업부'].unique()):
    st.markdown(f"#### 📊 {dept} 매출 추이")
    t = trend[trend['사업부'] == dept].copy()
    pivot = t.pivot(index='기준', columns='사업부', values='매출').fillna(0)
    st.line_chart(pivot)

st.markdown("---")
st.subheader("📈 사업부별 유형 매출 추이")
for dept in sorted(data_melted['사업부'].unique()):
    if dept == '타분류': continue
    st.markdown(f"#### 🔹 {dept} 사업부")
    t = data_melted[data_melted['사업부'] == dept].copy()
    if dept == "F&B":
        t = t[t['유형'] != '직영']
    t = t.groupby(['기준', '유형'])['매출'].sum().reset_index()
    if not t.empty:
        pivot = t.pivot(index='기준', columns='유형', values='매출').fillna(0)
        st.line_chart(pivot)
