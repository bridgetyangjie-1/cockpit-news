"""
汽车智能座舱新闻摘要 - GitHub Actions 版本
直接调用 Coze Coding 平台 API 获取新闻
"""
import os
import json
from datetime import datetime
from pathlib import Path

API_BASE_URL = "https://x5ygy49c7k.coze.site"
TOKEN = "eyJhbGciOiJSUzI1NiIsImtpZCI6ImFmMDQyOWY0LWY4YTItNDAxZi05N2UwLTg3M2M2ODcxZTUyZiJ9.eyJpc3MiOiJodHRwczovL2FwaS5jb3plLmNuIiwiYXVkIjpbInF5MlgwQlEyY212Zk94c0ptNmZMU1Z4Y0t2UzFNWGIzIl0sImV4cCI6ODIxMDI2Njg3Njc5OSwiaWF0IjoxNzc4NTgwNzcxLCJzdWIiOiJzcGlmZmU6Ly9hcGkuY296ZS5jbi93b3JrbG9hZF9pZGVudGl0eS9pZDo3NjM4ODMxOTMwMjI1NDU5MjM4Iiwic3JjIjoiaW5ib3VuZF9hdXRoX2FjY2Vzc190b2tlbl9pZDo3NjM4OTQ2MjQ1MTg4MjU1Nzk4In0.FnICbcku72HRS_334qq9OVTBU2u7XfpfiE0Hi2BXxMT5mNbCWrAAk--abwhFAdJaDRRQ-zYC80XXu-S6B8B4aopaaXtUmLXdVW24bb8fcPh4pd3V6IOjvdT4abxp6OZD0t8Gt4ngIISUNcB78MqSyxsE33mwnxugu7NOWODvPSzx2hI_TU2dYACJw8QKLrqa-kxGYbl2kIjf_Im1ViKWt6_hJpHP4Qys8_Us5i-kqgVMsbYyUGr96Ru95JqKZGpGJITEFdLH95ejWmq9GbzhKHZvrCUFDa679X5lzWE2dE_aoj7QMPW6qwOmlVWhfcUYuKrZxVXrA8rppDItzFPOzw"

def fetch_news():
    import urllib.request
    import urllib.error
    
    url = f"{API_BASE_URL}/api/workflow/run"
    data = {
        "workflow_name": "cockpit_news_workflow",
        "parameters": {
            "search_topic": "汽车智能座舱",
            "max_news_count": 20,
            "time_range": "1d"
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {TOKEN}'
        },
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result
    except Exception as e:
        print(f"Error: {e}")
        return None

def generate_html_report(news_data, output_path):
    today = datetime.now().strftime("%Y-%m-%d")
    
    import re
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚗 智能座舱日报 {today}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; padding: 20px;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .card {{ 
            background: white; border-radius: 20px; padding: 40px; 
            box-shadow: 0 20px 60px rgba(0,0,0,0.2);
        }}
        h1 {{ text-align: center; color: #333; margin-bottom: 10px; }}
        .date {{ text-align: center; color: #666; margin-bottom: 30px; }}
        .news-item {{ 
            background: #f8f9fa; border-radius: 12px; padding: 20px; 
            margin-bottom: 20px; border-left: 4px solid #667eea;
        }}
        .news-content {{ font-size: 15px; line-height: 1.8; }}
        .news-content a {{ color: #667eea; text-decoration: none; }}
        .footer {{ text-align: center; margin-top: 30px; color: #999; font-size: 12px; }}
        .update-time {{ text-align: center; color: #888; margin-bottom: 20px; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🚗 智能座舱日报</h1>
            <p class="date">{today}</p>
            <p class="update-time">🔄 自动更新于 GitHub Actions</p>
            <div class="news-content">
                {format_news_content(news_data)}
            </div>
            <div class="footer">由 GitHub Actions 自动生成</div>
        </div>
    </div>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ HTML 报告已生成: {output_path}")

def format_news_content(news_data):
    if not news_data:
        return "<p>暂无新闻数据</p>"
    
    content = ""
    if isinstance(news_data, dict):
        if news_data.get('data'):
            content = str(news_data['data'])
        elif news_data.get('output'):
            output = news_data['output']
            if isinstance(output, dict) and output.get('daily_report'):
                content = output['daily_report']
            else:
                content = str(output)
        else:
            content = str(news_data)
    elif isinstance(news_data, str):
        content = news_data
    else:
        content = json.dumps(news_data, ensure_ascii=False)
    
    import re
    content = content.replace('\n', '<br>')
    
    html_parts = []
    blocks = re.split(r'【\d+】', content)
    for block in blocks:
        if block.strip():
            block_links = re.findall(r'https?://[^\s<>\)]+', block)
            link_html = f'<br><a href="{block_links[0]}" target="_blank">🔗 查看原文</a>' if block_links else ""
            html_parts.append(f'<div class="news-item"><div>{block.strip()}{link_html}</div></div>')
    
    return '\n'.join(html_parts) if html_parts else f'<div class="news-item"><div>{content}</div></div>'

def main():
    print("🚀 开始获取智能座舱新闻...")
    result = fetch_news()
    
    if result:
        print("✅ 新闻获取成功！")
        output_dir = Path("docs")
        output_dir.mkdir(exist_ok=True)
        
        html_path = output_dir / "index.html"
        generate_html_report(result, html_path)
        
        data_path = output_dir / "news.json"
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return True
    else:
        print("❌ 新闻获取失败")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
