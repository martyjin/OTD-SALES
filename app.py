import streamlit as st
import pandas as pd
import os

# 데이터 경로 설정
DATA_FOLDER = "data_storage"
DAILY_DATA_PATH = os.path.join(DATA_FOLDER, "daily_data.csv")
MONTHLY_DATA_PATH = os.path.join(DATA_FOLDER, "monthly_data.csv")
os.makedirs(DATA_FOLDER, exist_ok=True)

def is_monthly_data(df):
    try:
        pd.to_datetime(df.columns[-1], format="%Y-%m")
        return True
    except:
        return False

def load_existing_data(is_monthly):
    path = MONTHLY_DATA_PATH if is_monthly else DAILY_DATA_PATH
    return pd.read_csv(path) if os.path.exists(path) else None

def update_only_changed(existing_df, new_df):
    id_vars = ['사업부', '구분', '사이트', '브랜드']
    date_cols = [col for col in new_df.columns if col not in id_vars]
    new_long = new_df.melt(id_vars=id_vars, var_name='날짜', value_name='매출')
    new_long['매출'] = pd.to_numeric(new_long['매출'], errors='coerce')

    if existing_df is not None:
        old_long = existing_df.melt(id_vars=id_vars, var_name='날짜', value_name='매출')
        old_long['매출'] = pd.to_numeric(old_long['매출'], errors='coerce')
        merged = pd.merge(old_long, new_long, on=['사업부', '구분', '사이트', '브랜드', '날짜'], how='outer', suffixes=('_old', '_new'))
        changed = merged[(merged['매출_old'] != merged['매출_new']) & (~merged['매출_new'].isna())]
        unchanged = merged[merged['매출_old'] == merged['매출_new']]
        combined = pd.concat([
            unchanged[['사업부', '구분', '사이트', '브랜드', '날짜', '매출_old']].rename(columns={'매출_old': '매출'}),
            changed[['사업부', '구분', '사이트', '브랜드', '날짜', '매출_new']].rename(columns={'매출_new': '매출'})
        ])
        combined = combined.groupby(['사업부', '구분', '사이트', '브랜드', '날짜'], as_index=False)['매출'].sum()
        final_df = combined.pivot(index=['사업부', '구분', '사이트', '브랜드'], columns='날짜', values='매출').reset_index()
        return final_df.fillna(0)
    else:
        return new_df

def save_data(df, is_monthly):
    path = MONTHLY_DATA_PATH if is_monthly else DAILY_DATA_PATH
    df.to_csv(path, index=False)

# ---------------------- Streamlit 인터페이스 ----------------------

st.title("📊 매출 분석 웹앱")
st.markdown("""
    <style>
    ::-webkit-scrollbar {
        height: 8px;
        width: 3px;
    }
    ::-webkit-scrollbar-thumb {
        background: #999; 
        border-radius: 10px;
    }
    ::-webkit-scrollbar-track {
        background: #f0f0f0;
    }
    </style>
""", unsafe_allow_html=True)

updated_df = None
with st.expander("📂 데이터 업로드 및 불러오기 설정", expanded=False):
    uploaded_file = st.file_uploader("엑셀 업로드", type=["xlsx"])

    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)
        for col in ['사업부', '구분', '사이트', '브랜드']:
            if col in df.columns:
                df[col].fillna(method='ffill', inplace=True)
        required_cols = {'사업부', '구분', '사이트', '브랜드'}
        if not required_cols.issubset(df.columns):
            st.error("❌ '사업부', '구분', '사이트', '브랜드' 컬럼이 필요합니다.")
        else:
            is_monthly = is_monthly_data(df)
            existing_df = load_existing_data(is_monthly)
            updated_df = update_only_changed(existing_df, df)
            save_data(updated_df, is_monthly)
            st.success("✅ 데이터 반영 완료")
    else:
        for label, path in [("일자별", DAILY_DATA_PATH), ("월별", MONTHLY_DATA_PATH)]:
            if os.path.exists(path):
                updated_df = pd.read_csv(path)
                st.markdown(f"✅ 저장된 **{label} 데이터** 자동 불러오기 완료")
                break

if updated_df is not None:
    df_long = updated_df.melt(id_vars=['사업부', '구분', '사이트', '브랜드'], var_name='날짜', value_name='매출')
    df_long['날짜'] = pd.to_datetime(df_long['날짜'], errors='coerce')
    df_long['매출'] = pd.to_numeric(df_long['매출'], errors='coerce')

    st.markdown("<h5>🏗️ 계층별 매출 탐색</h5>", unsafe_allow_html=True)

    selected_bu = st.selectbox("1️⃣ 사업부 선택", options=[""] + sorted(df_long['사업부'].unique()))
    df_filtered = None
    if selected_bu:
        df_filtered = df_long[df_long['사업부'] == selected_bu]
        selected_div = st.selectbox("2️⃣ 구분 선택", options=[""] + sorted(df_filtered['구분'].unique()))
        if selected_div:
            df_filtered = df_filtered[df_filtered['구분'] == selected_div]
            selected_site = st.selectbox("3️⃣ 사이트 선택", options=[""] + sorted(df_filtered['사이트'].unique()))
            if selected_site:
                df_filtered = df_filtered[df_filtered['사이트'] == selected_site]

    if df_filtered is not None:
        view_mode = st.radio("📅 보기 방식", ["월별", "일별"], horizontal=True)

        if view_mode == "월별":
            df_filtered['기간'] = df_filtered['날짜'].dt.to_period('M').astype(str)
        else:
            df_filtered['기간'] = df_filtered['날짜'].dt.strftime("%Y-%m-%d")

        level = '브랜드'
        st.markdown("### 📈 선택 항목별 매출 요약")
        summary = df_filtered.groupby([level, '기간'])['매출'].sum().reset_index()
        pivot = summary.pivot(index=level, columns='기간', values='매출').fillna(0).astype(int)
        pivot_fmt = pivot.applymap(lambda x: f"{x:,}")

        row_count = pivot_fmt.shape[0]
        height = min(row_count, 14) * 35 + 40
        st.dataframe(pivot_fmt, use_container_width=True, height=height)
