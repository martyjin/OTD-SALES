import streamlit as st
import pandas as pd
import os

# ---------------------- 파일 저장 경로 ----------------------
DATA_FOLDER = "data_storage"
DAILY_DATA_PATH = os.path.join(DATA_FOLDER, "daily_data.csv")
MONTHLY_DATA_PATH = os.path.join(DATA_FOLDER, "monthly_data.csv")
os.makedirs(DATA_FOLDER, exist_ok=True)

# ---------------------- 데이터 처리 함수 ----------------------
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

# ---------------------- Streamlit 앱 시작 ----------------------
st.title("📊 매출 분석 웹앱")
st.markdown("""
    <style>
    ::-webkit-scrollbar {height: 8px; width: 3px;}
    ::-webkit-scrollbar-thumb {background: #999; border-radius: 10px;}
    ::-webkit-scrollbar-track {background: #f0f0f0;}
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
        if not {'사업부', '구분', '사이트', '브랜드'}.issubset(df.columns):
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

# ---------------------- 데이터 출력 ----------------------
if updated_df is not None:
    df_long = updated_df.melt(id_vars=['사업부', '구분', '사이트', '브랜드'], var_name='날짜', value_name='매출')
    df_long['날짜'] = pd.to_datetime(df_long['날짜'], errors='coerce')
    df_long['매출'] = pd.to_numeric(df_long['매출'], errors='coerce')
    df_long['기간'] = df_long['날짜'].dt.to_period('M').astype(str)

    st.markdown("<h4>📌 1. 사업부별 매출 합계</h4>", unsafe_allow_html=True)
    business_summary = df_long.groupby(['사업부', '기간'])['매출'].sum().reset_index()
    overall_total = business_summary.groupby('기간')['매출'].sum().reset_index()
    overall_total['사업부'] = '합계'
    business_summary = pd.concat([business_summary, overall_total[['사업부', '기간', '매출']]])
    business_summary['sort_order'] = business_summary['사업부'].apply(lambda x: -1 if x == '합계' else 0)
    business_summary = business_summary.sort_values(by=['sort_order', '사업부']).drop(columns='sort_order')
    pivot1 = business_summary.pivot(index='사업부', columns='기간', values='매출').fillna(0).astype(int)
    pivot1 = pivot1.reset_index()
    # 합계가 0번 인덱스로 가도록 정렬
    pivot1 = pd.concat([pivot1[pivot1['사업부'] == '합계'], pivot1[pivot1['사업부'] != '합계']])
    st.dataframe(pivot1, use_container_width=True)

    st.markdown("<h4>📌 2. 사업부 → 구분 → 사이트 매출 요약</h4>", unsafe_allow_html=True)
    site_summary = df_long.groupby(['사업부', '구분', '사이트', '기간'])['매출'].sum().reset_index()
    for bu in site_summary['사업부'].unique():
        st.markdown(f"### 🏢 사업부: {bu}")
        bu_df = site_summary[site_summary['사업부'] == bu].copy()
        all_rows = []
        for div in bu_df['구분'].unique():
            div_df = bu_df[bu_df['구분'] == div].copy()
            subtotal = div_df.groupby('기간')['매출'].sum().reset_index()
            subtotal['구분'] = div
            subtotal['사이트'] = '합계'
            subtotal['row_order'] = -1
            div_df['row_order'] = div_df['사이트'].rank(method='first').astype(int)
            combined = pd.concat([subtotal[['구분', '사이트', '기간', '매출', 'row_order']], div_df[['구분', '사이트', '기간', '매출', 'row_order']]])
            all_rows.append(combined)

        combined_df = pd.concat(all_rows)
        combined_df = combined_df.sort_values(by=['구분', 'row_order', '사이트']).drop(columns='row_order')
        pivot2 = combined_df.pivot_table(index=['구분', '사이트'], columns='기간', values='매출', fill_value=0).astype(int)
        pivot2 = pivot2.reset_index()
        # 합계 행이 각 구분의 첫 번째로 오도록 정렬
        for g in pivot2['구분'].unique():
            sub_df = pivot2[pivot2['구분'] == g]
            sub_df = pd.concat([sub_df[sub_df['사이트'] == '합계'], sub_df[sub_df['사이트'] != '합계']])
            st.dataframe(sub_df, use_container_width=True)

    st.markdown("<h4>📌 3. 브랜드별 상세 매출 (선택 기반)</h4>", unsafe_allow_html=True)
    selected_bu = st.selectbox("1️⃣ 사업부 선택", df_long['사업부'].unique())
    selected_div = st.selectbox("2️⃣ 구분 선택", df_long[df_long['사업부'] == selected_bu]['구분'].unique())
    selected_site = st.selectbox("3️⃣ 사이트 선택", df_long[(df_long['사업부'] == selected_bu) & (df_long['구분'] == selected_div)]['사이트'].unique())

    brand_df = df_long[(df_long['사업부'] == selected_bu) & (df_long['구분'] == selected_div) & (df_long['사이트'] == selected_site)]
    brand_summary = brand_df.groupby(['브랜드', '기간'])['매출'].sum().reset_index()
    brand_pivot = brand_summary.pivot(index='브랜드', columns='기간', values='매출').fillna(0).astype(int)
    st.dataframe(brand_pivot.reset_index(), use_container_width=True)
