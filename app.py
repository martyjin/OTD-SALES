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

# ---------------------- 계층별 매출 출력 ----------------------

if updated_df is not None:
    df_long = updated_df.melt(id_vars=['사업부', '구분', '사이트', '브랜드'], var_name='날짜', value_name='매출')
    df_long['날짜'] = pd.to_datetime(df_long['날짜'], errors='coerce')
    df_long['매출'] = pd.to_numeric(df_long['매출'], errors='coerce')
    df_long['기간'] = df_long['날짜'].dt.to_period('M').astype(str)

    st.markdown("<h5>📚 계층별 매출 요약 (사업부 → 구분 → 사이트 → 브랜드)</h5>", unsafe_allow_html=True)

    summary = df_long.groupby(['사업부', '구분', '사이트', '브랜드', '기간'])['매출'].sum().reset_index()
    pivot = summary.pivot_table(index=['사업부', '구분', '사이트', '브랜드'], columns='기간', values='매출', fill_value=0).reset_index()

    def format_df(df):
        df_fmt = df.copy()
        date_cols = df_fmt.columns[df_fmt.columns.str.match(r'\d{4}-\d{2}')]
        df_fmt[date_cols] = df_fmt[date_cols].astype(int).applymap(lambda x: f"{x:,}")
        return df_fmt

    formatted = format_df(pivot)

    for bu in formatted['사업부'].unique():
        st.markdown(f"### 📦 사업부: **{bu}**")
        bu_df = formatted[formatted['사업부'] == bu]

        for div in bu_df['구분'].unique():
            st.markdown(f"#### 📂 구분: {div}")
            div_df = bu_df[bu_df['구분'] == div]

            for site in div_df['사이트'].unique():
                st.markdown(f"##### 🏬 사이트: {site}")
                site_df = div_df[div_df['사이트'] == site].drop(columns=['사업부', '구분', '사이트'])
                site_df = site_df.set_index('브랜드')
                st.dataframe(site_df, use_container_width=True)
