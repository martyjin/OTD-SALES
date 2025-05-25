import streamlit as st
import pandas as pd
import os
from datetime import datetime

# Streamlit Cloud에서도 유지되는 경로로 저장
DATA_FILE = os.path.expanduser("~/.streamlit/saved_data.csv")

# 숫자 포맷 함수
def format_number(n):
    if pd.isna(n):
        return ""
    return f"{int(n):,}"

# 데이터 로드 함수
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return None

# 데이터 저장 함수
def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# 데이터 병합 함수
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

# 메인 앱
st.set_page_config(page_title="OTD SALES", layout="wide")
st.title("📊 OTD SALES 매출 분석")

# 로그인 구분
user_type = st.sidebar.radio("접속 유형을 선택하세요:", ("일반 사용자", "관리자"))
view_mode = st.sidebar.selectbox("분석 기준 선택", ["월별", "일별"])

# 관리자 파일명 표시용
existing_data = load_data()
if existing_data is not None:
    st.sidebar.caption(f"📁 저장된 파일 있음: {DATA_FILE.split('/')[-1]}")

# 관리자 전용 파일 업로드
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

# 데이터 로딩
data = load_data()
if data is None:
    st.info("데이터가 없습니다. 관리자만 업로드할 수 있습니다.")
    st.stop()

required_columns = ['사업부', '유형', '사이트', '브랜드']
value_columns = [col for col in data.columns if col not in required_columns]

# Melt
data_melted = data.melt(id_vars=required_columns, value_vars=value_columns,
                        var_name="일자", value_name="매출")
data_melted['일자'] = pd.to_datetime(data_melted['일자'], errors='coerce')
data_melted.dropna(subset=['일자'], inplace=True)
data_melted['매출'] = pd.to_numeric(data_melted['매출'], errors='coerce').fillna(0)

if view_mode == "월별":
    data_melted['기준'] = data_melted['일자'].dt.to_period("M").astype(str)
else:
    data_melted['기준'] = data_melted['일자'].dt.strftime("%Y-%m-%d")

# 소계 및 합계 스타일링 함수
def style_summary(df):
    return df.style.apply(lambda x: ['background-color: #ffe6ea' if x.name != '합계' else 'background-color: #e6f0ff'] * len(x), axis=1)

# 1️⃣ 사업부별 매출
summary = data_melted.groupby(['기준', '사업부'])['매출'].sum().reset_index()
summary_pivot = summary.pivot(index='사업부', columns='기준', values='매출').fillna(0).astype(int)
summary_pivot.loc['합계'] = summary_pivot.sum()
st.subheader("1️⃣ 사업부별 매출")
st.dataframe(style_summary(summary_pivot.applymap(format_number)), use_container_width=True)

# 2️⃣ 사이트별 매출 (유형 포함, 중복 제거)
st.subheader("2️⃣ 사이트별 매출")
site_grouped = data_melted.groupby(['기준', '유형', '사이트'])['매출'].sum().reset_index()
site_pivot = site_grouped.pivot(index=['유형', '사이트'], columns='기준', values='매출').fillna(0).astype(int)
site_pivot.loc[('합계', '')] = site_pivot.sum()
site_pivot = site_pivot.reset_index()

# 병합된 셀처럼 중복값 생략을 위해 표시용 컬럼 정리
site_pivot['유형 표시'] = site_pivot['유형'].mask(site_pivot['유형'] == site_pivot['유형'].shift())
site_pivot_display = site_pivot.drop(columns=['유형'])
site_pivot_display = site_pivot_display.rename(columns={'유형 표시': '유형'})
st.dataframe(style_summary(site_pivot_display.set_index(['유형', '사이트']).applymap(format_number).reset_index()), use_container_width=True)

# 3️⃣ 브랜드별 매출 (필터 포함)
st.subheader("3️⃣ 브랜드별 매출")
col1, col2, col3 = st.columns(3)
with col1:
    selected_dept = st.selectbox("사업부 선택", sorted(data_melted['사업부'].unique()))
with col2:
    selected_type = st.selectbox("유형 선택", sorted(data_melted['유형'].unique()))
with col3:
    selected_site = st.selectbox("사이트 선택", sorted(data_melted['사이트'].unique()))

filtered = data_melted[(data_melted['사업부'] == selected_dept) &
                       (data_melted['유형'] == selected_type) &
                       (data_melted['사이트'] == selected_site)]

brand_summary = filtered.groupby(['기준', '브랜드'])['매출'].sum().reset_index()
brand_pivot = brand_summary.pivot(index='브랜드', columns='기준', values='매출').fillna(0).astype(int)
if not brand_pivot.empty:
    brand_pivot.loc['합계'] = brand_pivot.sum()
    st.dataframe(style_summary(brand_pivot.applymap(format_number)), use_container_width=True, height=500)
else:
    st.info("해당 조건에 맞는 브랜드 매출 데이터가 없습니다.")

# 스크롤바 스타일 조정
st.markdown("""
<style>
::-webkit-scrollbar {
    height: 14px;
    width: 14px;
}
</style>
""", unsafe_allow_html=True)
