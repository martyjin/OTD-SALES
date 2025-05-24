...

    # --------- 3. 선택한 사이트 내 브랜드 매출 ---------
    view_mode3 = st.radio("📅 보기 방식 (브랜드 매출)", ["월별", "일별"], horizontal=True)
    if view_mode3 == "월별":
        df_long['기간3'] = df_long['날짜'].dt.to_period('M').astype(str)
    else:
        df_long['기간3'] = df_long['날짜'].dt.strftime('%Y-%m-%d')

    st.markdown("<h4>📌 3. 선택한 사이트 내 브랜드 매출</h4>", unsafe_allow_html=True)

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
