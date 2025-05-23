import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 데이터 저장 폴더 설정
DATA_FOLDER = "data_storage"
DAILY_DATA_PATH = os.path.join(DATA_FOLDER, "daily_data.csv")
MONTHLY_DATA_PATH = os.path.join(DATA_FOLDER, "monthly_data.csv")

# 폴더 없으면 생성
os.makedirs(DATA_FOLDER, exist_ok=True)

# 데이터 구분 함수
def is_monthly_data(df):
    date_col = df.columns[-1]
    try:
        pd.to_datetime(df[date_col], format="%Y-%m")  # 월별 (예: 2024-01)
        return True
    except:
        return False

# 데이터 업데이트 함수
def update_data(new_df, is_monthly):
    path = MONTHLY_DATA_PATH if is_monthly else DAILY_DATA_PATH

    # 기존 데이터 불러오기
    if os.path.exists(path):
        existing_df = pd.read_csv(path)
        # 사이트와 브랜드 기준으로 덮어쓰기
        updated_df = pd.concat([existing_df, new_df])
        updated_df.drop_duplicates(subset=['사이트', '브랜드'], keep='last', inplace=True)
    else:
        updated_df = new_df

    updated_df.to_csv(path, index=False)
    return updated_df

# 웹앱 시작
st.title("📊 매출 분석 웹앱")
st.markdown("사이트/브랜드별 로우데이터를 업로드하세요.")

# 파일 업로드
uploaded_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    # 🔧 병합 셀 대응: 사이트 값이 비어 있으면 위에서 채워넣기
    if '사이트' in df.columns:
        df['사이트'].fillna(method='ffill', inplace=True)

    # 기본 컬럼 확인
    if not {'사이트', '브랜드'}.issubset(df.columns):
        st.error("❌ '사이트'와 '브랜드' 컬럼이 존재해야 합니다.")
    else:
        is_monthly = is_monthly_data(df)

        st.success("✅ 데이터 업로드 성공")
        st.write("📄 업로드된 데이터 미리보기:")
        st.dataframe(df.head())

        # 📊 데이터 요약 출력
        st.subheader("📊 데이터 요약")
        total_sites = df['사이트'].nunique()
        total_brands = df['브랜드'].nunique()
        date_cols = [col for col in df.columns if str(col).startswith("202")]
        total_days = len(date_cols)
        total_sales = df[date_cols].apply(pd.to_numeric, errors='coerce').sum().sum()
        avg_daily_sales = total_sales / total_days if total_days else 0
        avg_sales_per_brand = total_sales / total_brands if total_brands else 0

        st.markdown(f"- 전체 **사이트 수**: {total_sites}개")
        st.markdown(f"- 전체 **브랜드 수**: {total_brands}개")
        st.markdown(f"- 포함된 **일자 수**: {total_days}일")
        st.markdown(f"- **총 매출 합계**: {int(total_sales):,}원")
        st.markdown(f"- **일평균 매출**: {int(avg_daily_sales):,}원")
        st.markdown(f"- **브랜드당 평균 매출**: {int(avg_sales_per_brand):,}원")

        # 🔘 업데이트 버튼
        if st.button("데이터 저장 및 갱신"):
            updated_df = update_data(df, is_monthly)
            st.success("📝 데이터가 성공적으로 저장되었습니다.")
            st.write("📁 현재 저장된 데이터:")
            st.dataframe(updated_df)
