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
st.set_page_config(layout="wide")
st.markdown("""
    <style>
    ::-webkit-scrollbar {
        height: 8px;
        width: 6px;
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

st.title("📊 매출 분석 웹앱")
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

if updated_df is not None:
    def format_int(x):
        try:
            return f"{int(x):,}"
        except:
            return ""

    df_long = updated_df.melt(id_vars=['사업부', '구분', '사이트', '브랜드'], var_name='날짜', value_name='매출')
    df_long['날짜'] = pd.to_datetime(df_long['날짜'], errors='coerce')
    df_long['매출'] = pd.to_numeric(df_long['매출'], errors='coerce')

    # --------- 1. 사업부별 ---------
    view_mode1 = st.radio("📅 보기 방식 (사업부별 합계)", ["월별", "일별"], horizontal=True)
    if view_mode1 == "월별":
        df_long['기간1'] = df_long['날짜'].dt.to_period('M').astype(str)
    else:
        df_long['기간1'] = df_long['날짜'].dt.strftime('%Y-%m-%d')

    st.markdown("<h4>📌 1. 사업부별 매출 합계</h4>", unsafe_allow_html=True)
    business_summary = df_long.groupby(['사업부', '기간1'])['매출'].sum().reset_index()
    overall_total = business_summary.groupby('기간1')['매출'].sum().reset_index()
    overall_total['사업부'] = '합계'
    business_summary = pd.concat([
        overall_total.rename(columns={'기간1': '기간'})[['사업부', '기간', '매출']],
        business_summary.rename(columns={'기간1': '기간'})
    ], ignore_index=True)
    business_summary['row_order'] = business_summary['사업부'].apply(lambda x: -1 if x == '합계' else 0)
    business_summary = business_summary.sort_values(by='row_order', ascending=False).drop(columns='row_order')
    pivot1 = business_summary.pivot(index='사업부', columns='기간', values='매출').fillna(0).reset_index()

    pivot1['sort_order'] = pivot1['사업부'].apply(lambda x: -1 if x == '합계' else 0)
    pivot1 = pivot1.sort_values(by='sort_order', ascending=False).drop(columns='sort_order')

    pivot1_fmt = pivot1.copy()
    for col in pivot1_fmt.columns[1:]:
        pivot1_fmt[col] = pivot1_fmt[col].apply(format_int)

    def highlight_total(row):
        return ['background-color: #ffecec' if row['사업부'] == '합계' else '' for _ in row]

    styled_pivot1 = pivot1_fmt.style.apply(highlight_total, axis=1)
    st.dataframe(styled_pivot1, use_container_width=True, hide_index=True, height=350)

    # (2, 3번 표 생략된 부분은 별도 복구 필요)
