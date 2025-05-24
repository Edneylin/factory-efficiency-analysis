import os
import smtplib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime
from jinja2 import Template
from dotenv import load_dotenv
import pandas as pd
import plotly.graph_objects as go
import io
import matplotlib.pyplot as plt
import seaborn as sns

load_dotenv()

def fig_to_base64(fig):
    """將 matplotlib 圖形轉換為 base64 字符串"""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', dpi=300)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode()
    plt.close(fig)
    return img_base64

def create_charts(df):
    """創建圖表並返回base64編碼的圖片"""
    # 深度複製數據框以避免修改原始數據
    df = df.copy()
    
    # 確保效率是數值類型
    df['效率'] = df['效率'].astype(str).str.rstrip('%').astype(float) / 100
    
    charts = {}
    
    # 工站效率圖
    plt.figure(figsize=(12, 6))
    station_metrics = df.groupby('工站').agg({
        '效率': 'mean',
        '姓名': 'count'
    }).reset_index()
    station_metrics['效率'] *= 100  # 轉換為百分比顯示
    
    ax = sns.barplot(data=station_metrics, x='工站', y='效率')
    plt.axhline(y=100, color='r', linestyle='--', label='標準線')
    
    # 添加數值標籤
    for i, v in enumerate(station_metrics['效率']):
        ax.text(i, v, f'{v:.1f}%', ha='center', va='bottom')
    
    plt.title('各工站平均效率')
    plt.xlabel('工站')
    plt.ylabel('效率 (%)')
    plt.legend()
    charts['station_chart'] = fig_to_base64(plt.gcf())
    
    # 個人效率排名圖（前10名）
    plt.figure(figsize=(12, 6))
    person_metrics = df.sort_values('效率', ascending=False).head(10)
    ax = sns.barplot(data=person_metrics, x='姓名', y='效率', hue='工站')
    
    # 添加數值標籤
    for i, v in enumerate(person_metrics['效率']):
        ax.text(i, v, f'{v*100:.1f}%', ha='center', va='bottom')
    
    plt.axhline(y=1, color='r', linestyle='--', label='標準線')
    plt.title('個人效率排名（前10名）')
    plt.xlabel('姓名')
    plt.ylabel('效率')
    plt.legend(title='工站', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    charts['personal_chart'] = fig_to_base64(plt.gcf())
    
    # CT時間分析圖
    plt.figure(figsize=(12, 6))
    # 確保CT時間為數值類型
    df['標準CT'] = pd.to_numeric(df['標準CT'], errors='coerce')
    df['實際CT'] = pd.to_numeric(df['實際CT'], errors='coerce')
    
    ct_data = df.groupby('工站').agg({
        '標準CT': 'mean',
        '實際CT': 'mean'
    }).reset_index()
    
    x = range(len(ct_data['工站']))
    width = 0.35
    
    plt.bar([i - width/2 for i in x], ct_data['標準CT'], width, label='標準CT')
    plt.bar([i + width/2 for i in x], ct_data['實際CT'], width, label='實際CT')
    
    plt.xlabel('工站')
    plt.ylabel('時間')
    plt.title('標準CT vs 實際CT對比')
    plt.xticks(x, ct_data['工站'])
    plt.legend()
    
    # 添加數值標籤
    for i, (std, real) in enumerate(zip(ct_data['標準CT'], ct_data['實際CT'])):
        plt.text(i - width/2, std, f'{std:.2f}', ha='center', va='bottom')
        plt.text(i + width/2, real, f'{real:.2f}', ha='center', va='bottom')
    
    plt.tight_layout()
    charts['ct_chart'] = fig_to_base64(plt.gcf())
    
    return charts

def generate_report_data(df):
    """生成報告數據"""
    try:
        # 深度複製數據框以避免修改原始數據
        df = df.copy()
        
        # 確保效率是數值類型，移除任何百分比符號
        df['效率'] = df['效率'].astype(str).str.rstrip('%').astype(float) / 100
        
        # 計算平均效率
        avg_efficiency = df['效率'].mean() * 100
        above_standard = (df['效率'] >= 1).sum()
        total_workers = len(df)
        
        # 計算最佳工站
        station_efficiency = df.groupby('工站')['效率'].mean()
        best_station = station_efficiency.idxmax()
        best_efficiency = station_efficiency.max() * 100
        
        # 生成異常效率人員表格
        abnormal_df = df[
            (df['效率'] < 0.8) | (df['效率'] > 1.2)
        ].copy()
        
        abnormal_df['效率'] = (abnormal_df['效率'] * 100).round(1).astype(str) + '%'
        abnormal_table = abnormal_df[['工站', '姓名', '效率']].to_html(
            index=False,
            classes='table table-striped'
        )
        
        return {
            'report_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'avg_efficiency': f"{avg_efficiency:.1f}",
            'efficiency_delta': f"{(avg_efficiency - 100):.1f}",
            'above_standard_ratio': f"{(above_standard/total_workers*100):.1f}",
            'above_standard': above_standard,
            'total_workers': total_workers,
            'best_station': best_station,
            'best_efficiency': f"{best_efficiency:.1f}",
            'abnormal_table': abnormal_table
        }
    except Exception as e:
        print(f"生成報告數據時發生錯誤：{str(e)}")
        raise

def send_report_email(df, recipients):
    """發送報告郵件"""
    try:
        # 深度複製數據框以避免修改原始數據
        df = df.copy()
        
        # 預處理數據
        # 確保效率列為數值類型
        if '效率' in df.columns:
            df['效率'] = df['效率'].astype(str).str.rstrip('%').astype(float) / 100
        
        # 確保CT時間為數值類型
        if '標準CT' in df.columns:
            df['標準CT'] = pd.to_numeric(df['標準CT'], errors='coerce')
        if '實際CT' in df.columns:
            df['實際CT'] = pd.to_numeric(df['實際CT'], errors='coerce')
        
        # 讀取郵件模板
        with open('email_template.html', 'r', encoding='utf-8') as f:
            template = Template(f.read())
        
        # 生成報告數據
        report_data = generate_report_data(df)
        charts = create_charts(df)
        report_data.update(charts)
        
        # 生成HTML內容
        html_content = template.render(**report_data)
        
        # 創建郵件
        msg = MIMEMultipart()
        msg['Subject'] = f'工廠生產效率分析報告 - {datetime.now().strftime("%Y-%m-%d")}'
        msg['From'] = os.getenv('SMTP_USERNAME')
        msg['To'] = ', '.join(recipients)
        
        msg.attach(MIMEText(html_content, 'html'))
        
        # 發送郵件
        with smtplib.SMTP(os.getenv('SMTP_SERVER'), int(os.getenv('SMTP_PORT'))) as server:
            server.starttls()
            server.login(os.getenv('SMTP_USERNAME'), os.getenv('SMTP_PASSWORD'))
            server.send_message(msg)
        
        return True, "郵件發送成功！"
    
    except Exception as e:
        error_msg = f"發送郵件時發生錯誤：{str(e)}"
        print(error_msg)
        # 如果是數據處理相關的錯誤，提供更詳細的錯誤信息
        if "'>=' not supported" in str(e):
            error_msg += "\n可能是數據格式問題，請確保：\n1. 效率數據為數值類型\n2. 沒有無效的百分比值\n3. 所有必要的列都存在"
        return False, error_msg