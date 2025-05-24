import streamlit as st
import pandas as pd
import numpy as np

# --------- 데이터 업로드 ---------
uploaded_file = st.file_uploader("📂 데이터 업로드 및 불러오기 설정", type=['xlsx'])
if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    df['날짜'] = pd.to_datetime(df['날짜'])

    df_long = df.melt(id_vars=['사업부', '구분', '사이트', '브랜드', '날짜'], var_name='항목', value_name='매출')
    df_long = df_long[df_long['항목'] == '매출']

    def format_int(x):
        return f"{int(x):,}" if pd.notnull(x) else ""

    # --------- 1. 사업부별 매출 합계 ---------
    st.markdown("<h4>📅 보기 방식 (사업부별 합계)</h4>", unsafe_allow_html=True)
    view_mode1 = st.radio("", ["월별", "일별"], horizontal=True, key="vm1")
    if view_mode1 == "월별":
        df_long['기간1'] = df_long['날짜'].dt.to_period('M').astype(str)
    else:
        df_long['기간1'] = df_long['날짜'].dt.strftime('%Y-%m-%d')

    st.markdown("<h3>📌 1. 사업부별 매출 합계</h3>", unsafe_allow_html=True)
    business_summary = df_long.groupby(['사업부', '기간1'])['매출'].sum().reset_index()
    overall_total = business_summary.groupby('기간1')['매출'].sum().reset_index()
    overall_total['사업부'] = '합계'
    business_summary = pd.concat([overall_total[['사업부', '기간1', '매출']], business_summary], ignore_index=True)
    business_summary['row_order'] = business_summary['사업부'].apply(lambda x: -1 if x == '합계' else 0)
    business_summary = business_summary.sort_values(by='row_order', ascending=False).drop(columns='row_order')

    pivot1 = business_summary.pivot(index='사업부', columns='기간1', values='매출').fillna(0).reset_index()
    pivot1_fmt = pivot1.copy()
    for col in pivot1_fmt.columns[1:]:
        pivot1_fmt[col] = pivot1_fmt[col].apply(format_int)

    def highlight_total(row):
        return ['background-color: #ffecec' if row['사업부'] == '합계' else '' for _ in row]

    styled_pivot1 = pivot1_fmt.style.apply(highlight_total, axis=1)
    st.dataframe(styled_pivot1, use_container_width=True, hide_index=True, height=350)

    # --------- 2. 사업부 → 구분 → 사이트 매출 요약 ---------
    st.markdown("<h4>📅 보기 방식 (사이트 요약)</h4>", unsafe_allow_html=True)
    view_mode2 = st.radio("", ["월별", "일별"], horizontal=True, key="vm2")
    if view_mode2 == "월별":
        df_long['기간2'] = df_long['날짜'].dt.to_period('M').astype(str)
    else:
        df_long['기간2'] = df_long['날짜'].dt.strftime('%Y-%m-%d')

    st.markdown("<h3>📌 2. 사업부 → 구분 → 사이트 매출 요약</h3>", unsafe_allow_html=True)
    site_summary = df_long.groupby(['사업부', '구분', '사이트', '기간2'])['매출'].sum().reset_index()

    all_site_tables = []
    for bu in site_summary['사업부'].unique():
        st.markdown(f"<h4>🏢 사업부: {bu}</h4>", unsafe_allow_html=True)
        bu_df = site_summary[site_summary['사업부'] == bu]

        all_rows = []
        for div in bu_df['구분'].unique():
            div_df = bu_df[bu_df['구분'] == div]
            subtotal = div_df.groupby(['기간2'])['매출'].sum().reset_index()
            subtotal['사이트'] = '합계'
            subtotal['구분'] = div
            combined = pd.concat([subtotal[['구분', '사이트', '기간2', '매출']], div_df[['구분', '사이트', '기간2', '매출']]])
            combined['row_order'] = combined['사이트'].apply(lambda x: -1 if x == '합계' else 0)
            combined = combined.sort_values(by='row_order', ascending=False).drop(columns='row_order')
            all_rows.append(combined)

        bu_table = pd.concat(all_rows, ignore_index=True)
        pivot2 = bu_table.pivot(index=['구분', '사이트'], columns='기간2', values='매출').fillna(0).reset_index()
        pivot2_fmt = pivot2.copy()
        for col in pivot2_fmt.columns[2:]:
            pivot2_fmt[col] = pivot2_fmt[col].apply(format_int)

        def highlight_site_total(row):
            return ['background-color: #ffecec' if row['사이트'] == '합계' else '' for _ in row]

        styled_pivot2 = pivot2_fmt.style.apply(highlight_site_total, axis=1)
        st.dataframe(styled_pivot2, use_container_width=True, hide_index=True, height=400)

    # --------- 3. 선택한 사이트 내 브랜드 매출 ---------
    st.markdown("<h4>📅 보기 방식 (브랜드 매출)</h4>", unsafe_allow_html=True)
    view_mode3 = st.radio("", ["월별", "일별"], horizontal=True, key="vm3")
    if view_mode3 == "월별":
        df_long['기간3'] = df_long['날짜'].dt.to_period('M').astype(str)
    else:
        df_long['기간3'] = df_long['날짜'].dt.strftime('%Y-%m-%d')

    st.markdown("<h3>📌 3. 선택한 사이트 내 브랜드 매출</h3>", unsafe_allow_html=True)

    selected_bu = st.selectbox("사업부 선택", df_long['사업부'].unique())
    filtered_df = df_long[df_long['사업부'] == selected_bu]
    selected_div = st.selectbox("구분 선택", filtered_df['구분'].unique())
    filtered_df = filtered_df[filtered_df['구분'] == selected_div]
    selected_site = st.selectbox("사이트 선택", filtered_df['사이트'].unique())
    brand_df = filtered_df[filtered_df['사이트'] == selected_site]

    brand_summary = brand_df.groupby(['브랜드', '기간3'])['매출'].sum().reset_index()
    total_brand = brand_summary.groupby('기간3')['매출'].sum().reset_index()
    total_brand['브랜드'] = '합계'

    brand_summary = pd.concat([total_brand[['브랜드', '기간3', '매출']], brand_summary], ignore_index=True)
    brand_summary['row_order'] = brand_summary['브랜드'].apply(lambda x: -1 if x == '합계' else 0)
    brand_summary = brand_summary.sort_values(by='row_order', ascending=False).drop(columns='row_order')

    pivot3 = brand_summary.pivot(index='브랜드', columns='기간3', values='매출').fillna(0).reset_index()
    pivot3_fmt = pivot3.copy()
    for col in pivot3_fmt.columns[1:]:
        pivot3_fmt[col] = pivot3_fmt[col].apply(format_int)

    def highlight_brand_total(row):
        return ['background-color: #ffecec' if row['브랜드'] == '합계' else '' for _ in row]

    styled_pivot3 = pivot3_fmt.style.apply(highlight_brand_total, axis=1)
    st.dataframe(styled_pivot3, use_container_width=True, hide_index=True, height=400)
else:
    st.warning("먼저 엑셀 파일을 업로드해주세요.")
