import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import matplotlib.pyplot as plt
import io
from email_utils import send_report_email
from dotenv import load_dotenv
import os

# 載入環境變數
load_dotenv()

# 設置頁面配置
st.set_page_config(
    page_title="工廠生產效率分析系統",
    layout="wide",
    initial_sidebar_state="expanded"
)

def calculate_metrics(df):
    """計算額外的效率指標"""
    # 創建數據副本
    df = df.copy()
    
    # 驗證必要的列是否存在
    required_columns = ['工站', '姓名', '效率', '標準CT', '實際CT']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要的列：{', '.join(missing_columns)}")
    
    # 處理效率列
    if '效率' in df.columns:
        # 移除百分比符號並轉換為數值
        try:
            # 先將所有值轉換為字符串
            df['效率'] = df['效率'].astype(str)
            # 移除可能存在的空格
            df['效率'] = df['效率'].str.strip()
            # 移除百分比符號
            df['效率'] = df['效率'].str.rstrip('%')
            # 轉換為浮點數
            df['效率'] = pd.to_numeric(df['效率'], errors='coerce') / 100
            # 檢查是否有無效值
            invalid_efficiency = df['效率'].isna().sum()
            if invalid_efficiency > 0:
                print(f"警告：發現 {invalid_efficiency} 個無效的效率值")
        except Exception as e:
            raise ValueError(f"效率數據轉換失敗：{str(e)}")
    
    # 確保CT時間為數值類型
    for ct_col in ['標準CT', '實際CT']:
        if ct_col in df.columns:
            try:
                df[ct_col] = pd.to_numeric(df[ct_col], errors='coerce')
            except Exception as e:
                raise ValueError(f"{ct_col}數據轉換失敗：{str(e)}")
    
    # 檢查並處理空值
    df = df.fillna({
        '效率': 0,
        '標準CT': 0,
        '實際CT': 0
    })
    
    # 驗證效率數據的合理性
    if (df['效率'] < 0).any():
        raise ValueError("發現負數效率值")
    if (df['效率'] > 2).any():  # 效率超過200%可能不合理
        print("警告：發現效率值超過200%")
    
    return df

def main():
    st.title("工廠生產效率分析系統 🏭")
    
    # 添加使用說明
    with st.expander("📖 使用說明（點擊展開）"):
        st.markdown("""
        ### 使用步驟：
        1. 準備 CSV 檔案，必須包含以下欄位：
           - `工站`：工作站名稱
           - `姓名`：作業人員姓名
           - `效率`：生產效率（可以是百分比或小數）
           - `標準CT`：標準工時
           - `實際CT`：實際工時
        
        2. CSV 檔案格式要求：
           - 支援編碼：UTF-8、Big5、GBK
           - 效率數據可以是 "90%" 或 "0.9" 格式
           - 請確保數據完整且正確
        
        ### 💡 小提示：
        - 系統會自動處理各種編碼格式
        - 可以使用篩選功能查看特定效率區間的數據
        - 可以下載分析後的數據和報告
        - 建議使用最新版本的瀏覽器以獲得最佳體驗
        """)
        
        # 添加示例檔案下載
        st.markdown("""
        ### 📝 示例檔案
        不確定格式？下載示例檔案參考：
        """)
        
        example_data = '''工站,姓名,效率,標準CT,實際CT
A站,張三,95%,120,125
B站,李四,85%,180,200
C站,王五,105%,150,142
A站,趙六,78%,120,155'''
        
        st.download_button(
            label="下載示例CSV檔案",
            data=example_data,
            file_name="example.csv",
            mime="text/csv"
        )
    
    st.sidebar.header("檔案上傳與設定")
    
    # 原有的檔案上傳功能
    uploaded_file = st.sidebar.file_uploader("選擇CSV檔案", type=['csv'])
    
    if uploaded_file is not None:
        try:
            # 自動嘗試不同的編碼格式
            encodings = ['utf-8', 'utf-8-sig', 'big5', 'gbk', 'cp950']
            success = False
            df = None
            
            for encoding in encodings:
                try:
                    # 嘗試讀取檔案的前幾行來測試編碼
                    df_test = pd.read_csv(
                        uploaded_file,
                        encoding=encoding,
                        nrows=5  # 先讀取前5行測試
                    )
                    # 如果成功，重新讀取整個檔案
                    uploaded_file.seek(0)  # 重置檔案指針
                    df = pd.read_csv(
                        uploaded_file,
                        encoding=encoding
                    )
                    success = True
                    st.sidebar.success(f"成功使用 {encoding} 編碼讀取檔案")
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    st.sidebar.error(f"使用 {encoding} 編碼時發生錯誤：{str(e)}")
                    continue
            
            if not success or df is None:
                st.error("無法自動判斷檔案編碼，請嘗試以下方法：")
                st.info("""
                1. 在Excel中重新儲存檔案：
                   - 點選「另存新檔」
                   - 選擇「CSV UTF-8」格式
                   - 儲存後再次上傳
                2. 如果仍然無法讀取，請確認：
                   - 檔案是否包含特殊字元
                   - CSV檔案是否完整
                   - 是否可以在記事本中正常開啟
                """)
                st.stop()
            
            # 在處理數據之前先顯示原始數據的狀態
            st.sidebar.markdown("### 數據預覽")
            st.sidebar.dataframe(df.head())
            
            # 顯示效率列的原始狀態
            if '效率' in df.columns:
                st.sidebar.markdown("### 效率數據狀態")
                st.sidebar.write("效率列數據類型:", df['效率'].dtype)
                st.sidebar.write("效率列前5個值:", df['效率'].head().tolist())
            
            # 處理數據
            try:
                df = calculate_metrics(df)
                st.sidebar.success("數據處理成功")
            except Exception as e:
                st.error(f"數據處理失敗：{str(e)}")
                st.stop()
            
            # 顯示處理後的效率數據狀態
            st.sidebar.markdown("### 處理後的效率數據")
            st.sidebar.write("效率列數據類型:", df['效率'].dtype)
            st.sidebar.write("效率列前5個值:", df['效率'].head().tolist())
            
            # 建立分析選項
            st.header("生產效率分析面板")

            # 建立三列版面
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # 計算總體效率統計
                avg_efficiency = df['效率'].mean() * 100
                st.metric(
                    label="平均生產效率",
                    value=f"{avg_efficiency:.1f}%",
                    delta=f"{(avg_efficiency - 100):.1f}%"
                )

            with col2:
                # 計算達標人數
                above_standard = (df['效率'] >= 1).sum()
                total_workers = len(df)
                st.metric(
                    label="達標人數比例",
                    value=f"{(above_standard/total_workers*100):.1f}%",
                    delta=f"{above_standard}/{total_workers}"
                )

            with col3:
                # 計算最佳工站
                best_station = df.groupby('工站')['效率'].mean().idxmax()
                best_efficiency = df.groupby('工站')['效率'].mean().max() * 100
                st.metric(
                    label="最佳工站",
                    value=best_station,
                    delta=f"效率 {best_efficiency:.1f}%"
                )

            # 建立分析頁籤
            tab1, tab2, tab3, tab4 = st.tabs([
                "工站效率分析",
                "個人效率排名",
                "CT時間分析",
                "詳細資料"
            ])

            with tab1:
                st.subheader("工站效率分析")
                
                # 計算工站平均效率
                station_metrics = df.groupby('工站').agg({
                    '效率': 'mean',
                    '姓名': 'count'
                }).reset_index()
                station_metrics['效率'] *= 100
                
                # 建立工站效率柱狀圖
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=station_metrics['工站'],
                    y=station_metrics['效率'],
                    text=station_metrics['效率'].round(1).astype(str) + '%',
                    textposition='auto',
                    name='效率'
                ))
                fig.add_trace(go.Scatter(
                    x=station_metrics['工站'],
                    y=[100] * len(station_metrics),
                    mode='lines',
                    name='標準線',
                    line=dict(color='red', dash='dash')
                ))
                fig.update_layout(
                    title="各工站平均效率",
                    xaxis_title="工站",
                    yaxis_title="效率 (%)",
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)

            with tab2:
                st.subheader("個人效率排名")
                
                # 建立個人效率排名圖
                person_metrics = df.sort_values('效率', ascending=False)
                fig = px.bar(
                    person_metrics,
                    x='姓名',
                    y='效率',
                    color='工站',
                    text=person_metrics['效率'].apply(lambda x: f'{x*100:.1f}%'),
                    title="個人效率排名",
                    height=500
                )
                fig.add_hline(
                    y=1,
                    line_dash="dash",
                    line_color="red",
                    annotation_text="標準線"
                )
                fig.update_layout(
                    xaxis_title="姓名",
                    yaxis_title="效率",
                    showlegend=True
                )
                st.plotly_chart(fig, use_container_width=True)

            with tab3:
                st.subheader("CT時間分析")
                
                # 建立CT時間對比圖
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name='標準CT',
                    x=df['工站'],
                    y=df['標準CT'],
                    text=df['標準CT'].round(2),
                    textposition='auto'
                ))
                fig.add_trace(go.Bar(
                    name='實際CT',
                    x=df['工站'],
                    y=df['實際CT'],
                    text=df['實際CT'].round(2),
                    textposition='auto'
                ))
                fig.update_layout(
                    title="標準CT vs 實際CT對比",
                    xaxis_title="工站",
                    yaxis_title="時間",
                    barmode='group',
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)

            with tab4:
                st.subheader("詳細資料表")
                
                # 添加效率區間篩選
                efficiency_range = st.slider(
                    "選擇效率區間 (%)",
                    0, 200, (0, 200),
                    step=5
                )
                
                # 篩選資料
                filtered_df = df[
                    (df['效率'] * 100 >= efficiency_range[0]) &
                    (df['效率'] * 100 <= efficiency_range[1])
                ]
                
                # 顯示篩選後的資料
                st.dataframe(
                    filtered_df.style.format({
                        '效率': '{:.1%}',
                        '標準CT': '{:.2f}',
                        '實際CT': '{:.2f}'
                    }),
                    use_container_width=True
                )

                # 添加資料下載功能
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    label="下載資料",
                    data=csv,
                    file_name="efficiency_data.csv",
                    mime="text/csv"
                )
                
                # 添加在線報告顯示
                st.header("📊 生產效率分析報告")
                
                # 報告概述
                st.markdown("""
                ### 報告內容包括：
                1. 📊 整體效率指標
                2. 📈 詳細分析圖表
                3. ⚠️ 異常數據分析
                """)

                # 1. 整體效率指標
                st.subheader("1. 整體效率指標")
                metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
                
                with metrics_col1:
                    avg_efficiency = df['效率'].mean() * 100
                    st.metric(
                        label="平均生產效率",
                        value=f"{avg_efficiency:.1f}%",
                        delta=f"{(avg_efficiency - 100):.1f}%"
                    )

                with metrics_col2:
                    above_standard = (df['效率'] >= 1).sum()
                    total_workers = len(df)
                    st.metric(
                        label="達標人數比例",
                        value=f"{(above_standard/total_workers*100):.1f}%",
                        delta=f"{above_standard}/{total_workers}"
                    )

                with metrics_col3:
                    best_station = df.groupby('工站')['效率'].mean().idxmax()
                    best_efficiency = df.groupby('工站')['效率'].mean().max() * 100
                    st.metric(
                        label="最佳工站",
                        value=best_station,
                        delta=f"效率 {best_efficiency:.1f}%"
                    )

                # 2. 詳細分析圖表
                st.subheader("2. 詳細分析圖表")
                
                # 工站效率分析
                st.markdown("#### 2.1 工站效率分析")
                station_metrics = df.groupby('工站').agg({
                    '效率': ['mean', 'count'],
                    '姓名': 'count'
                }).round(3)
                station_metrics.columns = ['平均效率', '樣本數', '人數']
                station_metrics['平均效率'] = (station_metrics['平均效率'] * 100).round(1).astype(str) + '%'
                st.dataframe(station_metrics, use_container_width=True)
                
                # 個人效率排名（前10名）
                st.markdown("#### 2.2 個人效率排名（前10名）")
                top_performers = df.nlargest(10, '效率')[['工站', '姓名', '效率']]
                top_performers['效率'] = (top_performers['效率'] * 100).round(1).astype(str) + '%'
                st.dataframe(top_performers, use_container_width=True)
                
                # CT時間分析
                st.markdown("#### 2.3 CT時間分析")
                ct_analysis = df.groupby('工站').agg({
                    '標準CT': 'mean',
                    '實際CT': 'mean'
                }).round(2)
                ct_analysis['差異'] = (ct_analysis['實際CT'] - ct_analysis['標準CT']).round(2)
                st.dataframe(ct_analysis, use_container_width=True)

                # 3. 異常數據分析
                st.subheader("3. 異常數據分析")
                
                # 效率異常分析
                st.markdown("#### 3.1 效率異常分析")
                
                # 定義效率區間
                too_low = 0.8    # 80%
                too_high = 1.05  # 105%
                
                # 計算各區間的統計
                low_efficiency = df[df['效率'] < too_low]
                high_efficiency = df[df['效率'] > too_high]
                normal_efficiency = df[(df['效率'] >= too_low) & (df['效率'] <= too_high)]
                
                # 顯示效率分布
                st.markdown("##### 效率分布概況")
                dist_col1, dist_col2, dist_col3 = st.columns(3)
                
                with dist_col1:
                    st.metric(
                        label="效率偏低 (<80%)",
                        value=f"{len(low_efficiency)}人",
                        delta=f"{len(low_efficiency)/len(df)*100:.1f}%",
                        delta_color="inverse"
                    )
                
                with dist_col2:
                    st.metric(
                        label="效率正常 (80-105%)",
                        value=f"{len(normal_efficiency)}人",
                        delta=f"{len(normal_efficiency)/len(df)*100:.1f}%"
                    )
                
                with dist_col3:
                    st.metric(
                        label="效率偏高 (>105%)",
                        value=f"{len(high_efficiency)}人",
                        delta=f"{len(high_efficiency)/len(df)*100:.1f}%",
                        delta_color="inverse"
                    )
                
                # 工站效率異常分析
                st.markdown("##### 工站效率異常分析")
                station_analysis = df.groupby('工站').agg({
                    '效率': ['mean', 'min', 'max', 'count']
                }).round(3)
                station_analysis.columns = ['平均效率', '最低效率', '最高效率', '人數']
                
                # 標記異常工站
                station_analysis['狀態'] = '正常'
                station_analysis.loc[station_analysis['平均效率'] < too_low, '狀態'] = '需改善'
                station_analysis.loc[station_analysis['平均效率'] > too_high, '狀態'] = '標準工時過鬆'
                
                # 格式化效率顯示
                for col in ['平均效率', '最低效率', '最高效率']:
                    station_analysis[col] = (station_analysis[col] * 100).round(1).astype(str) + '%'
                
                st.dataframe(station_analysis, use_container_width=True)
                
                # 效率異常人員清單
                st.markdown("##### 效率異常人員清單")
                abnormal_df = pd.concat([
                    low_efficiency[['工站', '姓名', '效率']].assign(異常類型='效率偏低'),
                    high_efficiency[['工站', '姓名', '效率']].assign(異常類型='效率偏高')
                ]).sort_values(['工站', '效率'])
                
                if len(abnormal_df) > 0:
                    # 格式化效率顯示
                    abnormal_df['效率'] = (abnormal_df['效率'] * 100).round(1).astype(str) + '%'
                    st.dataframe(abnormal_df, use_container_width=True)
                    
                    # 添加改善建議
                    st.markdown("#### 3.2 改善建議")
                    
                    # 工站層面的建議
                    if len(high_efficiency) > 0:
                        high_stations = df[df['效率'] > too_high]['工站'].unique()
                        st.warning(f"""
                        ⚠️ 標準工時定義過鬆的工站（{len(high_stations)}個）：
                        - 影響工站：{', '.join(high_stations)}
                        - 建議措施：
                          1. 重新評估標準工時的合理性
                          2. 分析高效率人員的作業方法，優化標準作業程序
                          3. 考慮調整工站的人力配置
                        """)
                    
                    if len(low_efficiency) > 0:
                        low_stations = df[df['效率'] < too_low]['工站'].unique()
                        st.error(f"""
                        🔧 需要製程改善的工站（{len(low_stations)}個）：
                        - 影響工站：{', '.join(low_stations)}
                        - 改善方向：
                          1. 進行製程分析，找出效率瓶頸
                          2. 評估是否需要工具/設備改善
                          3. 檢查工作環境是否影響效率
                          4. 重新設計工作流程，消除浪費動作
                        """)
                    
                    # 人員層面的建議
                    if len(low_efficiency) > 0:
                        st.info(f"""
                        👥 人員效率改善建議（{len(low_efficiency)}人）：
                        1. 技能提升：
                           - 安排專人進行一對一技能輔導
                           - 提供標準作業流程培訓
                           - 建立技能認證制度
                        
                        2. 工作支援：
                           - 提供必要的工具和輔具
                           - 改善工作指導文件
                           - 建立問題諮詢管道
                        
                        3. 追蹤改善：
                           - 設定階段性改善目標
                           - 定期檢討改善成效
                           - 建立獎勵機制鼓勵進步
                        """)
                else:
                    st.success("✅ 沒有發現效率異常的人員")

        except Exception as e:
            st.error(f"處理檔案時發生錯誤：{str(e)}")
            st.info("""
            如果檔案無法正確讀取，請嘗試：
            1. 在Excel中重新儲存檔案時，選擇「CSV UTF-8」格式
            2. 確認檔案內容是否完整
            3. 確認欄位名稱是否正確（需要：工站、姓名、效率、標準CT、實際CT）
            """)

if __name__ == "__main__":
    main()