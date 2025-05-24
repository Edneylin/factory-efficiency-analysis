import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
from pathlib import Path
import os
import pdfkit
from jinja2 import Template
import base64
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# 設置頁面配置
st.set_page_config(
    page_title="工廠生產效率分析系統",
    page_icon="🏭",
    layout="wide"
)

# 設置中文字體
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

def generate_pdf_report(df, station_metrics, top_performers, low_efficiency, high_efficiency, ct_abnormal):
    # 創建HTML模板
    html_template = """
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; }
            .header { text-align: center; margin-bottom: 30px; }
            .section { margin-bottom: 20px; }
            table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            .alert { color: red; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>工廠生產效率分析報告</h1>
            <p>生成日期：{{ date }}</p>
        </div>
        
        <div class="section">
            <h2>1. 整體效率指標</h2>
            <p>平均生產效率：{{ avg_efficiency }}%</p>
            <p>達標率（≥80%）：{{ qualified_rate }}%</p>
            <p>最佳工站：{{ best_station }} ({{ best_efficiency }}%)</p>
        </div>

        <div class="section">
            <h2>2. 工站效率分析</h2>
            <table>
                <tr>
                    <th>工站</th>
                    <th>效率</th>
                    <th>人數</th>
                </tr>
                {% for _, row in station_metrics.iterrows() %}
                <tr>
                    <td>{{ row['工站'] }}</td>
                    <td>{{ "%.1f"|format(row['效率']) }}%</td>
                    <td>{{ row['姓名']|int }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="section">
            <h2>3. 效率異常分析</h2>
            {% if low_efficiency|length > 0 %}
            <h3>效率偏低人員 (<80%)</h3>
            <table>
                <tr>
                    <th>工站</th>
                    <th>姓名</th>
                    <th>效率</th>
                </tr>
                {% for _, row in low_efficiency.iterrows() %}
                <tr>
                    <td>{{ row['工站'] }}</td>
                    <td>{{ row['姓名'] }}</td>
                    <td>{{ "%.1f"|format(row['效率']*100) }}%</td>
                </tr>
                {% endfor %}
            </table>
            {% endif %}

            {% if high_efficiency|length > 0 %}
            <h3>效率偏高人員 (>105%)</h3>
            <table>
                <tr>
                    <th>工站</th>
                    <th>姓名</th>
                    <th>效率</th>
                </tr>
                {% for _, row in high_efficiency.iterrows() %}
                <tr>
                    <td>{{ row['工站'] }}</td>
                    <td>{{ row['姓名'] }}</td>
                    <td>{{ "%.1f"|format(row['效率']*100) }}%</td>
                </tr>
                {% endfor %}
            </table>
            {% endif %}
        </div>

        {% if ct_abnormal|length > 0 %}
        <div class="section">
            <h2>4. CT時間異常分析</h2>
            <table>
                <tr>
                    <th>工站</th>
                    <th>姓名</th>
                    <th>標準CT</th>
                    <th>實際CT</th>
                    <th>CT差異</th>
                    <th>CT差異率</th>
                </tr>
                {% for _, row in ct_abnormal.iterrows() %}
                <tr>
                    <td>{{ row['工站'] }}</td>
                    <td>{{ row['姓名'] }}</td>
                    <td>{{ "%.1f"|format(row['標準CT']) }}</td>
                    <td>{{ "%.1f"|format(row['實際CT']) }}</td>
                    <td>{{ "%.1f"|format(row['CT差異']) }}</td>
                    <td>{{ "%.1f"|format(row['CT差異率']) }}%</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        {% endif %}
    </body>
    </html>
    """

    # 準備數據
    from datetime import datetime
    template_data = {
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'avg_efficiency': f"{df['效率'].mean() * 100:.1f}",
        'qualified_rate': f"{(df['效率'] >= 0.8).mean() * 100:.1f}",
        'best_station': df.groupby('工站')['效率'].mean().idxmax(),
        'best_efficiency': f"{df.groupby('工站')['效率'].mean().max() * 100:.1f}",
        'station_metrics': station_metrics,
        'low_efficiency': low_efficiency,
        'high_efficiency': high_efficiency,
        'ct_abnormal': ct_abnormal
    }

    # 生成HTML
    template = Template(html_template)
    html_content = template.render(**template_data)

    # 生成PDF
    pdf = pdfkit.from_string(html_content, False)
    return pdf

def plot_efficiency_distribution(df):
    """繪製效率分布直方圖"""
    fig = px.histogram(
        df,
        x='效率',
        nbins=20,
        title='效率分布圖',
        labels={'效率': '效率值', 'count': '人數'},
        color_discrete_sequence=['#1f77b4']
    )
    
    fig.add_vline(x=0.8, line_dash="dash", line_color="red", annotation_text="最低要求(80%)")
    fig.add_vline(x=1.05, line_dash="dash", line_color="orange", annotation_text="過高警告(105%)")
    
    # 更新布局
    fig.update_layout(
        title_x=0.5,
        title_font_size=20,
        xaxis_title="效率值",
        yaxis_title="人數",
        bargap=0.1
    )
    
    return fig

def plot_station_boxplot(df):
    """繪製工站效率箱型圖"""
    fig = px.box(
        df,
        x='工站',
        y='效率',
        title='工站效率分布箱型圖',
        points='all',  # 顯示所有數據點
        labels={'工站': '工站名稱', '效率': '效率值'}
    )
    
    # 添加參考線
    fig.add_hline(y=0.8, line_dash="dash", line_color="red", annotation_text="最低要求(80%)")
    fig.add_hline(y=1.05, line_dash="dash", line_color="orange", annotation_text="過高警告(105%)")
    
    # 更新布局
    fig.update_layout(
        title_x=0.5,
        title_font_size=20,
        boxmode='group',
        showlegend=False
    )
    
    return fig

def plot_ct_scatter(df):
    """繪製標準CT vs 實際CT散點圖"""
    fig = px.scatter(
        df,
        x='標準CT',
        y='實際CT',
        color='工站',
        title='標準CT vs 實際CT對比圖',
        labels={'標準CT': '標準CT時間', '實際CT': '實際CT時間', '工站': '工站'},
        hover_data=['姓名', '效率']
    )
    
    # 添加對角線（理想情況）
    max_ct = max(df['標準CT'].max(), df['實際CT'].max())
    fig.add_trace(
        go.Scatter(
            x=[0, max_ct],
            y=[0, max_ct],
            mode='lines',
            name='理想線',
            line=dict(dash='dash', color='gray')
        )
    )
    
    # 更新布局
    fig.update_layout(
        title_x=0.5,
        title_font_size=20,
        showlegend=True
    )
    
    return fig

def plot_efficiency_heatmap(df):
    """繪製效率熱力圖"""
    # 計算每個工站的平均效率
    pivot_data = df.pivot_table(
        values='效率',
        index='工站',
        aggfunc='mean'
    )
    
    # 準備數據
    values = pivot_data.values.flatten()  # 將數組轉為一維
    text_values = []
    for val in values:
        percentage = val * 100
        text_values.append(f'{percentage:.1f}%')
    
    # 創建熱力圖
    fig = go.Figure(data=go.Heatmap(
        z=[values],  # 使用一維數組
        x=pivot_data.index,
        y=['平均效率'],
        text=[text_values],  # 使用處理好的文本列表
        texttemplate='%{text}',
        textfont={'size': 14},
        colorscale='RdYlGn',  # 紅黃綠配色
        zmin=0.8,  # 最小值（80%）
        zmax=1.05  # 最大值（105%）
    ))
    
    # 更新布局
    fig.update_layout(
        title='工站效率熱力圖',
        title_x=0.5,
        title_font_size=20,
        height=200,
        yaxis_visible=False,
        xaxis_title='工站'
    )
    
    return fig

def process_dataframe(df):
    """安全處理數據框"""
    try:
        # 創建副本避免修改原始數據
        df = df.copy()
        
        # 處理效率數據
        df['效率'] = pd.to_numeric(df['效率'].astype(str).str.rstrip('%'), errors='coerce') / 100
        
        # 確保CT時間為數值型
        df['標準CT'] = pd.to_numeric(df['標準CT'], errors='coerce')
        df['實際CT'] = pd.to_numeric(df['實際CT'], errors='coerce')
        
        # 計算CT相關指標
        df['CT差異'] = df['實際CT'] - df['標準CT']
        df['CT差異率'] = (df['CT差異'] / df['標準CT'] * 100).round(1)
        
        return df, None
    except Exception as e:
        return None, str(e)

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
        
        3. 輸出選項：
           - 可以下載處理後的 CSV 檔案
           - 可以下載完整的 PDF 分析報告
           - PDF 報告包含所有分析數據和圖表
        
        ### 💡 小提示：
        - 系統會自動處理各種編碼格式
        - 可以使用篩選功能查看特定效率區間的數據
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

    # 文件上傳
    uploaded_file = st.file_uploader("選擇CSV檔案", type="csv")
    
    if uploaded_file is not None:
        try:
            # 讀取文件內容
            content = uploaded_file.read()
            
            # 嘗試不同的編碼方式
            encodings = ['utf-8', 'big5', 'gbk']
            df = None
            
            for encoding in encodings:
                try:
                    content_io = io.BytesIO(content)
                    df = pd.read_csv(content_io, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if df is None:
                st.error("無法讀取文件，請確保文件編碼為 UTF-8、Big5 或 GBK")
                return
            
            # 驗證必要的列是否存在
            required_columns = ['工站', '姓名', '效率', '標準CT', '實際CT']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                st.error(f"缺少必要的列：{', '.join(missing_columns)}")
                return
            
            # 處理數據框
            df, error = process_dataframe(df)
            if error:
                st.error(f"數據處理錯誤：{error}")
                return
            
            # 添加下載選項到頂部
            st.header("💾 下載選項")
            col1, col2 = st.columns(2)
            
            # 計算所有需要的數據
            try:
                # 1. 工站效率
                station_metrics = df.groupby('工站').agg({
                    '效率': 'mean',  # 使用基本的mean函數
                    '姓名': 'count'
                }).reset_index()
                
                # 轉換效率為百分比
                station_metrics['效率'] = pd.to_numeric(station_metrics['效率'], errors='coerce') * 100
                
                # 2. 效率異常分析
                too_low = 0.8    # 80%
                too_high = 1.05  # 105%
                low_efficiency = df[df['效率'] < too_low].copy()
                high_efficiency = df[df['效率'] > too_high].copy()
                normal_efficiency = df[(df['效率'] >= too_low) & (df['效率'] <= too_high)].copy()
                
                # 3. CT時間異常分析
                ct_abnormal = df[abs(df['CT差異率']) > 20].copy()
                ct_abnormal = ct_abnormal[['工站', '姓名', '標準CT', '實際CT', 'CT差異', 'CT差異率']].copy()
                
                # 4. 計算個人效率排名
                top_performers = df.sort_values('效率', ascending=False).head(10).copy()

                with col1:
                    # CSV下載按鈕
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📊 下載處理後的CSV",
                        data=csv,
                        file_name="processed_data.csv",
                        mime="text/csv"
                    )
                
                with col2:
                    # PDF報告下載按鈕
                    try:
                        pdf = generate_pdf_report(
                            df, 
                            station_metrics, 
                            top_performers, 
                            low_efficiency, 
                            high_efficiency, 
                            ct_abnormal
                        )
                        st.download_button(
                            label="📑 下載PDF分析報告",
                            data=pdf,
                            file_name="工廠生產效率分析報告.pdf",
                            mime="application/pdf"
                        )
                    except Exception as e:
                        st.error(f"生成PDF報告時發生錯誤：{str(e)}")
                        st.info("提示：請確保系統已安裝 wkhtmltopdf")
                
                # 報告概述
                st.header("📊 生產效率分析報告")
                
                # 1. 整體效率指標
                st.subheader("1. 整體效率指標")
                metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
                
                with metrics_col1:
                    avg_efficiency = df['效率'].mean() * 100
                    st.metric(
                        label="平均生產效率",
                        value=f"{avg_efficiency:.1f}%",
                        delta=f"{(avg_efficiency - 100):.1f}%" if avg_efficiency != 100 else None
                    )
                
                with metrics_col2:
                    qualified_rate = (df['效率'] >= 0.8).mean() * 100
                    st.metric(
                        label="達標率（≥80%）",
                        value=f"{qualified_rate:.1f}%"
                    )
                
                with metrics_col3:
                    best_station = df.groupby('工站')['效率'].mean().idxmax()
                    best_efficiency = df.groupby('工站')['效率'].mean().max() * 100
                    st.metric(
                        label="最佳工站",
                        value=f"{best_station}",
                        delta=f"{best_efficiency:.1f}%"
                    )
                
                # 2. 詳細分析圖表
                st.subheader("2. 詳細分析圖表")
                
                # 2.1 效率分布概況
                st.markdown("#### 2.1 效率分布概況")
                
                # 使用 plotly 繪製效率分布圖
                efficiency_dist_fig = plot_efficiency_distribution(df)
                st.plotly_chart(efficiency_dist_fig, use_container_width=True)
                
                # 添加效率分布分析說明
                st.markdown("""
                💡 **效率分布分析**：
                - 紅線（80%）以下的區域表示需要改善的人員
                - 橙線（105%）以上的區域表示工時標準可能過鬆
                - 分布越集中在80-105%之間表示生產越穩定
                """)
                
                # 2.2 工站效率分析
                st.markdown("#### 2.2 工站效率分析")
                
                # 工站效率熱力圖
                efficiency_heatmap = plot_efficiency_heatmap(df)
                st.plotly_chart(efficiency_heatmap, use_container_width=True)
                
                # 添加熱力圖分析說明
                st.markdown("""
                💡 **熱力圖分析**：
                - 紅色區域：效率低於80%，需要重點改善
                - 黃色區域：效率在80-105%之間，屬於正常範圍
                - 綠色區域：效率高於105%，需要重新評估工時
                """)
                
                # 工站效率箱型圖
                station_box_fig = plot_station_boxplot(df)
                st.plotly_chart(station_box_fig, use_container_width=True)
                
                # 添加箱型圖分析說明
                st.markdown("""
                💡 **箱型圖分析**：
                - 箱子的上下邊界表示25%和75%分位數
                - 箱子中的線表示中位數
                - 離群點表示異常值，需要特別關注
                - 箱子高度反映效率的波動程度
                """)
                
                # 2.3 CT時間分析
                st.markdown("#### 2.3 CT時間分析")
                
                # CT時間散點圖
                ct_scatter_fig = plot_ct_scatter(df)
                st.plotly_chart(ct_scatter_fig, use_container_width=True)
                
                # 添加CT時間分析說明
                st.markdown("""
                💡 **CT時間分析**：
                - 虛線表示理想狀態（標準CT = 實際CT）
                - 點位在虛線上方：實際CT高於標準CT，需要改善
                - 點位在虛線下方：實際CT低於標準CT，可能影響品質
                - 點位越偏離虛線，差異越大，越需要關注
                """)
                
                # 2.4 個人效率排名
                st.markdown("#### 2.4 個人效率排名")
                
                # 創建個人效率排名圖表
                top_performers_fig = px.bar(
                    top_performers,
                    x='姓名',
                    y='效率',
                    color='工站',
                    title='個人效率排名（前10名）',
                    labels={'效率': '效率值', '姓名': '姓名', '工站': '工站'}
                )
                
                # 更新布局
                top_performers_fig.update_layout(
                    title_x=0.5,
                    title_font_size=20,
                    xaxis_title="姓名",
                    yaxis_title="效率值"
                )
                
                # 添加參考線
                top_performers_fig.add_hline(y=0.8, line_dash="dash", line_color="red", annotation_text="最低要求(80%)")
                top_performers_fig.add_hline(y=1.05, line_dash="dash", line_color="orange", annotation_text="過高警告(105%)")
                
                # 顯示圖表
                st.plotly_chart(top_performers_fig, use_container_width=True)
                
                # 添加效率排名分析說明
                st.markdown("""
                💡 **效率排名分析**：
                - 不同顏色代表不同工站
                - 紅線（80%）為最低效率要求
                - 橙線（105%）為效率過高警告線
                - 建議分析高效率人員的作業方法，作為標準化參考
                """)
                
                # 3. 異常數據分析
                st.subheader("3. 異常數據分析")
                
                # 效率異常分析
                st.markdown("#### 3.1 效率異常分析")
                
                # 顯示效率分布
                st.markdown("##### 效率分布概況")
                dist_col1, dist_col2, dist_col3 = st.columns(3)
                
                with dist_col1:
                    low_count = len(low_efficiency)
                    low_percent = (low_count/len(df)*100)
                    st.metric(
                        label="效率偏低 (<80%)",
                        value=f"{low_count}人",
                        delta=f"{low_percent:.1f}%",
                        delta_color="inverse"
                    )
                    if low_count > 0:
                        st.markdown("⚠️ **需要製程改善和人員效率提升**")
                
                with dist_col2:
                    normal_count = len(normal_efficiency)
                    normal_percent = (normal_count/len(df)*100)
                    st.metric(
                        label="效率正常 (80-105%)",
                        value=f"{normal_count}人",
                        delta=f"{normal_percent:.1f}%"
                    )
                
                with dist_col3:
                    high_count = len(high_efficiency)
                    high_percent = (high_count/len(df)*100)
                    st.metric(
                        label="效率偏高 (>105%)",
                        value=f"{high_count}人",
                        delta=f"{high_percent:.1f}%",
                        delta_color="off"
                    )
                    if high_count > 0:
                        st.markdown("⚠️ **標準工時定義過鬆**")
                
                # 顯示異常數據詳情
                if len(low_efficiency) > 0:
                    st.markdown("##### 效率偏低人員名單（前10名最需要改善）")
                    # 按效率升序排序，取最低的10名
                    low_eff_df = low_efficiency.sort_values('效率', ascending=True).head(10)[['工站', '姓名', '效率']].copy()
                    low_eff_df['效率'] = (low_eff_df['效率'] * 100).map('{:.1f}%'.format)
                    low_eff_df['建議優先順序'] = range(1, len(low_eff_df) + 1)
                    st.table(low_eff_df.set_index('建議優先順序'))
                    st.info("💡 請特別關注效率差異較大的案例")
                
                if len(high_efficiency) > 0:
                    st.markdown("##### 效率偏高人員名單（前10名最需要重新評估）")
                    # 按效率降序排序，取最高的10名
                    high_eff_df = high_efficiency.sort_values('效率', ascending=False).head(10)[['工站', '姓名', '效率']].copy()
                    high_eff_df['效率'] = (high_eff_df['效率'] * 100).map('{:.1f}%'.format)
                    high_eff_df['重評順序'] = range(1, len(high_eff_df) + 1)
                    st.table(high_eff_df.set_index('重評順序'))
                    st.info("💡 建議重新評估這些工站的標準工時設定")
                
                # 3.2 CT時間異常分析
                st.markdown("#### 3.2 CT時間異常分析")
                
                # 顯示CT時間異常數據
                if len(ct_abnormal) > 0:
                    st.markdown("##### CT時間差異最顯著的案例（前10名）")
                    
                    # 按CT差異率的絕對值排序
                    ct_display = ct_abnormal.copy()
                    ct_display['CT差異率絕對值'] = abs(ct_display['CT差異率'])
                    ct_display = ct_display.sort_values('CT差異率絕對值', ascending=False).head(10)
                    ct_display = ct_display.drop('CT差異率絕對值', axis=1)
                    
                    # 格式化所有數值列
                    for col in ['標準CT', '實際CT', 'CT差異']:
                        ct_display[col] = ct_display[col].map('{:.1f}'.format)
                    ct_display['CT差異率'] = ct_display['CT差異率'].map('{:.1f}%'.format)
                    ct_display['異常程度'] = range(1, len(ct_display) + 1)
                    st.table(ct_display.set_index('異常程度'))
                    
                    # 添加分析說明
                    st.info("""
                    💡 CT時間異常分析說明：
                    1. 正值表示實際CT高於標準CT（需要改善）
                    2. 負值表示實際CT低於標準CT（可能影響品質）
                    3. 差異率越大表示越需要關注
                    """)
                else:
                    st.success("沒有發現顯著的CT時間異常")
                
            except Exception as e:
                st.error(f"數據分析錯誤：{str(e)}")
                st.error("請檢查數據格式是否正確，特別是效率值和CT時間的格式")
                import traceback
                st.error(f"詳細錯誤：{traceback.format_exc()}")
                return
                
            # 添加專業改善建議區塊
            st.markdown("---")
            st.header("💡 專業改善建議")
            
            with st.expander("點擊查看詳細改善建議"):
                # 工站效率異常分析
                high_stations = df[df['效率'] > too_high]['工站'].unique()
                low_stations = df[df['效率'] < too_low]['工站'].unique()
                
                if len(high_stations) > 0:
                    st.warning(f"""
                    ### ⚠️ 標準工時定義過鬆的工站（{len(high_stations)}個）：
                    
                    #### 影響工站：
                    {', '.join(high_stations)}
                    
                    #### 建議措施：
                    1. **重新評估標準工時的合理性**
                       - 進行詳細的時間研究
                       - 考慮工序難度和品質要求
                       - 評估工具和設備的影響
                    
                    2. **分析高效率人員的作業方法**
                       - 記錄並分析作業流程
                       - 找出效率提升的關鍵因素
                       - 優化標準作業程序
                    
                    3. **工時平衡與人力配置**
                       - 重新評估人力需求
                       - 考慮工作負荷平衡
                       - 適當調整作業分配
                    """)
                
                if len(low_stations) > 0:
                    st.error(f"""
                    ### 🔧 需要製程改善的工站（{len(low_stations)}個）：
                    
                    #### 影響工站：
                    {', '.join(low_stations)}
                    
                    #### 改善方向：
                    1. **製程分析與改善**
                       - 進行詳細的製程分析
                       - 識別效率瓶頸點
                       - 消除非增值活動
                    
                    2. **工具與設備改善**
                       - 評估現有設備狀態
                       - 改善工具配置
                       - 考慮自動化可能性
                    
                    3. **作業環境優化**
                       - 檢查工作環境條件
                       - 改善人機工程設計
                       - 優化物料動線
                    
                    4. **標準作業優化**
                       - 重新設計作業流程
                       - 制定標準作業指導書
                       - 建立品質檢查點
                    """)
                
                # 人員效率改善建議
                if len(low_efficiency) > 0:
                    st.info(f"""
                    ### 👥 人員效率改善建議（{len(low_efficiency)}人）：
                    
                    #### 1. 技能提升計劃
                    - **專業培訓**
                      * 安排專人一對一技能輔導
                      * 提供標準作業流程培訓
                      * 建立技能認證制度
                    
                    - **經驗分享**
                      * 組織優秀員工經驗分享會
                      * 建立師徒制培訓機制
                      * 定期技能評估與回饋
                    
                    #### 2. 工作支援系統
                    - **工具支援**
                      * 提供必要的工具和輔具
                      * 改善工作指導文件
                      * 建立問題諮詢管道
                    
                    - **環境支援**
                      * 優化工作站配置
                      * 改善作業環境
                      * 提供人體工學支援
                    
                    #### 3. 改善追蹤機制
                    - **目標管理**
                      * 設定階段性改善目標
                      * 建立每週進度追蹤
                      * 定期檢討改善成效
                    
                    - **激勵機制**
                      * 建立改善獎勵制度
                      * 表揚進步顯著人員
                      * 提供職涯發展機會
                    """)
                
                # 添加執行時程規劃
                st.markdown("""
                ### 📅 改善執行時程規劃
                
                #### 短期改善計劃（1-2週）
                1. ✅ 重新評估標準工時
                   - 進行時間研究
                   - 分析作業方法
                   - 制定新標準
                
                2. ✅ 更新作業指導文件
                   - 修訂標準作業程序
                   - 製作圖文作業指導書
                   - 進行人員培訓
                
                3. ✅ 實施基礎技能培訓
                   - 組織集中培訓
                   - 建立技能評估表
                   - 追蹤培訓效果
                
                #### 中期改善計劃（1-2月）
                1. 🔄 工作站布局優化
                   - 分析現有布局問題
                   - 設計改善方案
                   - 實施並驗證效果
                
                2. 🔄 自動化改善評估
                   - 識別自動化機會
                   - 評估投資效益
                   - 制定導入計劃
                
                3. 🔄 建立效率管理系統
                   - 開發監控儀表板
                   - 建立異常預警機制
                   - 優化數據收集流程
                
                #### 長期改善計劃（3-6月）
                1. 📈 導入智能分析系統
                   - 建立預測模型
                   - 開發決策支援功能
                   - 實現自動報表生成
                
                2. 📈 推動全面自動化
                   - 實施自動化項目
                   - 培訓操作人員
                   - 優化維護體系
                
                3. 📈 建立持續改善文化
                   - 推動改善提案制度
                   - 建立知識管理平台
                   - 發展學習型組織
                """)
                
                # 添加執行要點
                st.markdown("""
                ### 🎯 執行要點
                
                #### 1. 組織與人員
                - 👥 **專案團隊組建**
                  * 指定專案負責人
                  * 組建跨部門團隊
                  * 明確職責分工
                
                - 📋 **資源配置**
                  * 評估所需資源
                  * 分配預算與人力
                  * 建立支援機制
                
                #### 2. 管理與追蹤
                - 📊 **進度管理**
                  * 制定詳細時程表
                  * 建立里程碑檢核點
                  * 定期檢討會議
                
                - 📈 **效果確認**
                  * 設定改善目標
                  * 追蹤改善成效
                  * 及時調整方案
                
                #### 3. 溝通與協調
                - 🤝 **跨部門合作**
                  * 建立溝通機制
                  * 協調資源調度
                  * 解決衝突問題
                
                - 📢 **資訊共享**
                  * 建立資訊平台
                  * 定期進度報告
                  * 分享成功案例
                """)
            
            st.markdown("---")
            st.caption("© 2024 工廠生產效率分析系統 v1.0")
                
        except Exception as e:
            st.error(f"處理數據時發生錯誤：{str(e)}")
            st.error("請確保數據格式正確，並且包含所有必要的列")

if __name__ == "__main__":
    main() 