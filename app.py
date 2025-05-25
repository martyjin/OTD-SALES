import streamlit as st
import pandas as pd
import os
from datetime import datetime

DATA_FILE = "saved_data.csv"

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
    if old_df is None:
        return new_df
    merged = old_df.copy()
    for _, row in new_df.iterrows():
        mask = (
            (merged['사업부'] == row['사업부']) &
            (merged['구분'] == row['구분']) &
            (merged['사이트'] == row['사이트']) &
            (merged['브랜드'] == row['브랜드'])
        )
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

# 로그인 구분 (간단한 비밀번호)
user_type = st.sidebar.radio("접속 유형을 선택하세요:", ("일반 사용자", "관리자"))
if user_type == "관리자":
    password = st.sidebar.text_input("비밀번호를 입력하세요", type="password")
    if password != "181818":
        st.warning("비밀번호가 틀렸습니다.")
        st.stop()

uploaded_file = st.sidebar.file_uploader("매출 데이터 엑셀 업로드", type=[".xlsx"])

if uploaded_file and user_type == "관리자":
    new_df = pd.read_excel(uploaded_file)
    old_df = load_data()
    merged_df = merge_data(old_df, new_df)
    save_data(merged_df)
    st.success("데이터가 성공적으로 저장되었습니다.")

data = load_data()
if data is None:
    st.info("데이터가 없습니다. 관리자만 업로드할 수 있습니다.")
    st.stop()

# 사용자 선택 필터
view_mode = st.selectbox("분석 기준 선택", ["월별", "일별"])

# 날짜 열 필터링
value_columns = [col for col in data.columns if col not in ['사업부', '구분', '사이트', '브랜드']]

# melt로 구조 변경
data_melted = data.melt(id_vars=['사업부', '구분', '사이트', '브랜드'], value_vars=value_columns,
                        var_name="일자", value_name="매출")
data_melted['일자'] = pd.to_datetime(data_melted['일자'], errors='coerce')
data_melted.dropna(subset=['일자'], inplace=True)

data_melted['매출'] = pd.to_numeric(data_melted['매출'], errors='coerce').fillna(0)

# 기준 단위
if view_mode == "월별":
    data_melted['기준'] = data_melted['일자'].dt.to_period("M").astype(str)
else:
    data_melted['기준'] = data_melted['일자'].dt.strftime("%Y-%m-%d")

# 그룹화 및 합계
summary = data_melted.groupby(['사업부', '구분', '사이트', '브랜드', '기준'], as_index=False)['매출'].sum()
summary['매출'] = summary['매출'].astype(int)

# 피벗
pivot = summary.pivot_table(index=['사업부', '구분', '사이트', '브랜드'], columns='기준', values='매출', fill_value=0).reset_index()

# 숫자 포맷 적용
formatted_pivot = pivot.copy()
for col in formatted_pivot.columns[4:]:
    formatted_pivot[col] = formatted_pivot[col].apply(format_number)

# 합계 행 추가
sum_row = pivot.iloc[:, 4:].sum().to_frame().T
sum_row[['사업부', '구분', '사이트', '브랜드']] = ['합계', '', '', '']
sum_row = sum_row[pivot.columns]  # 열 순서 맞춤
sum_row_formatted = sum_row.copy()
for col in sum_row.columns[4:]:
    sum_row_formatted[col] = sum_row_formatted[col].apply(format_number)

final_df = pd.concat([sum_row_formatted, formatted_pivot], ignore_index=True)

# 스타일 적용 후 출력
styled_df = final_df.style.apply(lambda x: ['background-color: #ffe6ea' if x.name == 0 else '' for _ in x], axis=1)
st.dataframe(styled_df, use_container_width=True, height=600)
