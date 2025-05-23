import streamlit as st
import pandas as pd
import os

# 데이터 저장용 캐시
@st.cache_data
def load_data():
    if os.path.exists("sales_data.csv"):
        return pd.read_csv("sales_data.csv")
    return None

def save_data(df):
    df.to_csv("sales_data.csv", index=False)

# 앱 시작
st.title("매출 분석 웹앱")

# 파일 업로드
uploaded_file = st.file_uploader("엑셀 파일을 업로드하세요", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)
    save_data(df)
    st.success("데이터 업로드 및 저장 완료!")

# 저장된 데이터 불러오기
df = load_data()
if df is not None:
    st.subheader("원본 데이터 미리보기")
    st.dataframe(df.head())

    # 계층별 집계
    brand_level = df.copy()
    site_level = df.groupby(['사업부', '구분', '사이트']).sum(numeric_only=True).reset_index()
    division_level = df.groupby(['사업부', '구분']).sum(numeric_only=True).reset_index()
    business_unit_level = df.groupby(['사업부']).sum(numeric_only=True).reset_index()

    st.subheader("계층별 매출 요약")

    # 사업부 선택
    selected_bu = st.selectbox("사업부 선택", business_unit_level["사업부"].unique())
    bu_filtered = division_level[division_level["사업부"] == selected_bu]
    st.write(f"✅ **{selected_bu}** 매출 요약")
    st.dataframe(bu_filtered)

    # 구분 선택
    selected_division = st.selectbox("구분 선택", bu_filtered["구분"].unique())
    division_filtered = site_level[
        (site_level["사업부"] == selected_bu) & (site_level["구분"] == selected_division)
    ]
    st.write(f"✅ **{selected_division}** 매출 요약")
    st.dataframe(division_filtered)

    # 사이트 선택
    selected_site = st.selectbox("사이트 선택", division_filtered["사이트"].unique())
    site_filtered = brand_level[
        (brand_level["사업부"] == selected_bu)
        & (brand_level["구분"] == selected_division)
        & (brand_level["사이트"] == selected_site)
    ]
    st.write(f"✅ **{selected_site}** 브랜드별 매출")
    st.dataframe(site_filtered)
