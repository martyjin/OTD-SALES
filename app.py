import streamlit as st
import pandas as pd
import os

# 데이터 경로 설정
DATA_FOLDER = "data_storage"
DAILY_DATA_PATH = os.path.join(DATA_FOLDER, "daily_data.csv")
MONTHLY_DATA_PATH = os.path.join(DATA_FOLDER, "monthly_data.csv")
os.makedirs(DATA_FOLDER, exist_ok=True)

# 월별 판단
def is_monthly_data(df):
    try:
        pd.to_datetime(df.columns[-1], format="%Y-%m")
        return True
    except:
        return False

# 기존 로드
def load_existing_data(is_monthly):
    path = MONTHLY_DATA_PATH if is_monthly else DAILY_DATA_PATH
    return pd.read_csv(path) if os.path.exists(path) else None

# 업데이트된 항목만 병합
def update_only_changed(existing_df, new_df):
    id_vars = ['사이트', '브랜드']
    date_cols = [col for col in new_df.columns if col not in id_vars]
    new_long = new_df.melt(id_vars=id_vars, var_name='날짜', value_name='매출')
    new_long['매출'] = pd.to_numeric(new_long['매출'], errors='coerce')

    if existing_df is not None:
        old_long = existing_df.melt(id_vars=id_vars, var_name='날짜', value_name='매출')
        old_long['매출'] = pd.to_numeric(old_long['매출'], errors='coerce')
        merged = pd.merge(old_long, new_long, on=['사이트', '브랜드', '날짜'], how='outer', suffixes=('_old', '_new'))
        changed = merged[(merged['매출_old'] != merged['매출_new']) & (~merged['매출_new'].isna())]
        unchanged = merged[merged['매출_old'] == merged['매출_new']]
        combined = pd.concat([
            unchanged[['사이트', '브랜드', '날짜', '매출_old']].rename(columns={'매출_old': '매출'}),
            changed[['사이트', '브랜드', '날짜', '매출_new']].rename(columns={'매출_new': '매출'})
        ])
        # 중복된 (사이트, 브랜드, 날짜) 조합이 있다면 합산
        combined = combined.groupby(['사이트', '브랜드', '날짜'], as_index=False)['매출'].sum()

        final_df = combined.pivot(index=['사이트', '브랜드'], columns='날짜', values='매출').reset_index()
        return final_df.fillna(0)
    else:
        return new_df

# 저장
def save_data(df, is_monthly):
    path = MONTHLY_DATA_PATH if is_monthly else DAILY_DATA_PATH
    df.to_csv(path, index=False)

# ---------------------- Streamlit 인터페이스 ----------------------

st.title("📊 매출 분석 웹앱")
st.markdown("""
    <style>
    /* 모든 스크롤바 두껍게 */
    ::-webkit-scrollbar {
        height: 8px;  /* 가로 스크롤바 */
        width: 3px;   /* 세로 스크롤바 */
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

uploaded_file = st.file_uploader("엑셀 업로드", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    if '사이트' in df.columns:
        df['사이트'].fillna(method='ffill', inplace=True)

    if not {'사이트', '브랜드'}.issubset(df.columns):
        st.error("❌ '사이트', '브랜드' 컬럼이 필요합니다.")
    else:
        is_monthly = is_monthly_data(df)
        existing_df = load_existing_data(is_monthly)
        updated_df = update_only_changed(existing_df, df)
        save_data(updated_df, is_monthly)
        st.success("✅ 데이터 반영 완료")

# 🔄 앱 실행 시 기존 데이터 불러오기
else:
    updated_df = None
    for label, path in [("일자별", DAILY_DATA_PATH), ("월별", MONTHLY_DATA_PATH)]:
        if os.path.exists(path):
            updated_df = pd.read_csv(path)
            st.markdown(f"✅ 저장된 **{label} 데이터** 자동 불러오기 완료")
            break

# ▼ 출력 영역
if updated_df is not None:
    view_mode = st.radio("보기 모드 선택", ["📆 월별 매출", "📅 일별 매출"])
    site_list = updated_df['사이트'].unique().tolist()

    # 날짜 컬럼 분리
    date_cols = [col for col in updated_df.columns if col not in ['사이트', '브랜드']]

    df_long = updated_df.melt(id_vars=['사이트', '브랜드'], var_name='날짜', value_name='매출')
    df_long['날짜'] = pd.to_datetime(df_long['날짜'], errors='coerce')
    df_long['매출'] = pd.to_numeric(df_long['매출'], errors='coerce')

    if view_mode == "📆 월별 매출":
        df_long['기간'] = df_long['날짜'].dt.to_period('M').astype(str)
    else:
        df_long['기간'] = df_long['날짜'].dt.strftime("%Y-%m-%d")

    # 사이트 요약
    site_summary = df_long.groupby(['사이트', '기간'])['매출'].sum().reset_index()
    site_pivot = site_summary.pivot(index='사이트', columns='기간', values='매출').fillna(0).astype(int)
    site_pivot_fmt = site_pivot.applymap(lambda x: f"{x:,}")
    st.markdown("<h5>🏬 사이트별 매출 요약</h5>", unsafe_allow_html=True)

    row_count = site_pivot_fmt.shape[0]
    max_rows = 14
    row_height = 35
    height = min(row_count, max_rows) * row_height + 40

    st.dataframe(site_pivot_fmt, use_container_width=True, height=height)

    # 🔽 선택박스: 브랜드 매출용 (한 사이트만 선택 가능, 기본 None)
    selected_site = st.selectbox("🔍 브랜드별 매출을 보고 싶은 사이트를 선택하세요:", options=[""] + site_list)

    # 0원 브랜드 제거
  
    
    # 선택된 사이트의 브랜드 매출
    if selected_site:
            st.markdown(f"<h6>🏷 {selected_site} - 브랜드별 매출</h6>", unsafe_allow_html=True)
            brand_df = df_long[df_long['사이트'] == selected_site]
            brand_summary = brand_df.groupby(['브랜드', '기간'])['매출'].sum().reset_index()
            brand_pivot = brand_summary.pivot(index='브랜드', columns='기간', values='매출').fillna(0).astype(int)
            brand_pivot = brand_pivot[brand_pivot.sum(axis=1) != 0]
            brand_pivot_fmt = brand_pivot.applymap(lambda x: f"{x:,}")
    row_count = brand_pivot_fmt.shape[0]
    max_rows = 14
    row_height = 35
    height = min(row_count, max_rows) * row_height + 40

    st.dataframe(brand_pivot_fmt, use_container_width=True, height=height)


