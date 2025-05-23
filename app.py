import streamlit as st
import pandas as pd
import os

# 데이터 저장 경로 설정
DATA_FOLDER = "data_storage"
DAILY_DATA_PATH = os.path.join(DATA_FOLDER, "daily_data.csv")
MONTHLY_DATA_PATH = os.path.join(DATA_FOLDER, "monthly_data.csv")
os.makedirs(DATA_FOLDER, exist_ok=True)

# 월별 데이터인지 확인
def is_monthly_data(df):
    try:
        pd.to_datetime(df.columns[-1], format="%Y-%m")
        return True
    except:
        return False

# 기존 데이터 불러오기
def load_existing_data(is_monthly):
    path = MONTHLY_DATA_PATH if is_monthly else DAILY_DATA_PATH
    return pd.read_csv(path) if os.path.exists(path) else None

# 새 데이터에서 변경된 항목만 기존 데이터에 반영
def update_only_changed(existing_df, new_df):
    id_vars = ['사이트', '브랜드']
    date_cols = [col for col in new_df.columns if col not in id_vars]

    # melt → long format
    new_melted = new_df.melt(id_vars=id_vars, var_name='날짜', value_name='매출')
    new_melted['매출'] = pd.to_numeric(new_melted['매출'], errors='coerce')

    if existing_df is not None:
        existing_melted = existing_df.melt(id_vars=id_vars, var_name='날짜', value_name='매출')
        existing_melted['매출'] = pd.to_numeric(existing_melted['매출'], errors='coerce')

        merged = pd.merge(existing_melted, new_melted, on=['사이트', '브랜드', '날짜'], how='outer', suffixes=('_old', '_new'))

        # 매출이 달라진 항목만 new로 선택
        changed = merged[(merged['매출_old'] != merged['매출_new']) & (~merged['매출_new'].isna())]
        unchanged = merged[merged['매출_old'] == merged['매출_new']]

        updated_melted = pd.concat([unchanged[['사이트', '브랜드', '날짜', '매출_old']].rename(columns={'매출_old': '매출'}),
                                    changed[['사이트', '브랜드', '날짜', '매출_new']].rename(columns={'매출_new': '매출'})])

        # pivot → wide format
        final_df = updated_melted.pivot_table(index=['사이트', '브랜드'], columns='날짜', values='매출').reset_index()
        return final_df.fillna(0)
    else:
        return new_df

# 데이터 저장
def save_data(df, is_monthly):
    path = MONTHLY_DATA_PATH if is_monthly else DAILY_DATA_PATH
    df.to_csv(path, index=False)

# Streamlit 앱 시작
st.title("📊 매출 분석 웹앱")
st.markdown("사이트/브랜드별 매출 데이터를 업로드하세요. 변경된 항목만 자동 반영됩니다.")

# 엑셀 업로드
uploaded_file = st.file_uploader("엑셀 파일 업로드", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    # 병합 셀 대응
    if '사이트' in df.columns:
        df['사이트'].fillna(method='ffill', inplace=True)

    if not {'사이트', '브랜드'}.issubset(df.columns):
        st.error("❌ '사이트'와 '브랜드' 컬럼이 누락되었습니다.")
    else:
        is_monthly = is_monthly_data(df)
        existing_df = load_existing_data(is_monthly)

        # 변경된 항목만 반영
        updated_df = update_only_changed(existing_df, df)
        save_data(updated_df, is_monthly)

        st.success("✅ 데이터가 반영되었습니다 (변경된 항목만 적용됨).")
        st.write("📄 현재 저장된 데이터:")
        st.dataframe(updated_df.head())

        # 📆 월별 매출 요약
        date_cols = [col for col in updated_df.columns if col not in ['사이트', '브랜드']]
        date_df = updated_df[['사이트', '브랜드'] + date_cols].copy()

        melted = date_df.melt(id_vars=['사이트', '브랜드'], var_name='일자', value_name='매출')
        melted['일자'] = pd.to_datetime(melted['일자'], errors='coerce')
        melted['월'] = melted['일자'].dt.to_period('M').astype(str)
        melted['매출'] = pd.to_numeric(melted['매출'], errors='coerce')

        grouped = melted.groupby(['사이트', '월'])['매출'].sum().reset_index()
        pivot = grouped.pivot(index='사이트', columns='월', values='매출').fillna(0).astype(int)
        pivot_formatted = pivot.applymap(lambda x: f"{x:,}")

        st.subheader("📆 각 사이트별 월별 매출")
        st.dataframe(pivot_formatted)

# 앱 실행 시 자동 표시 (기존 데이터가 있을 경우)
else:
    st.subheader("📂 저장된 데이터 미리보기")
    for label, path in [("📅 일자별 데이터", DAILY_DATA_PATH), ("🗓 월별 데이터", MONTHLY_DATA_PATH)]:
        if os.path.exists(path):
            st.markdown(label)
            st.dataframe(pd.read_csv(path).head())

