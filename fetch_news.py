"""
汽车智能座舱新闻摘要 - GitHub Actions 版本
"""
import os
import json
import re
from datetime import datetime
from pathlib import Path


# ==================== 搜索 ====================
def search_news(topic, max_results=15):
    """DuckDuckGo 免费搜索（新版包名 ddgs）"""
    try:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(topic, max_results=max_results):
                title = r.get("title", "") or r.get("headline", "")
                url = r.get("href", "") or r.get("link", "")
                snippet = r.get("body", "") or r.get("description", "")
                if title and url:
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "site_name": extract_site_name(url)
                    })
        return results
    except ImportError:
        print("请安装 ddgs: pip install ddgs")
        return []
    except Exception as e:
        print(f"搜索失败: {e}")
        return []


def extract_site_name(url):
    from urllib.parse import urlparse
    try:
        domain = urlparse(url).netloc
        return domain.replace("www.", "").split(".")[0].title()
    except:
        return ""


# ==================== 大模型 ====================
def call_deepseek(system_prompt, user_prompt):
    """调用 DeepSeek API"""
    import urllib.request
    import urllib.error
    
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("❌ 未设置 DEEPSEEK_API_KEY")
        return None
    
    url = "https://api.deepseek.com/v1/chat/completions"
    data = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 4096
    }).encode('utf-8')
    
    req = urllib.request.Request(
        url, data=data,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        },
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"DeepSeek 调用失败: {e}")
        return None


def filter_news(news_list):
    """筛选高质量新闻"""
    if not news_list:
        return []
    
    news_data = "\n".join([
        f"[{i+1}] {item.get('title', '')}\n来源: {item.get('site_name', '')}\n摘要: {item.get('snippet', '')}\n链接: {item.get('url', '')}"
        for i, item in enumerate(news_list)
    ])
    
    resp = call_deepseek(
        "你是汽车行业新闻质量评估专家。筛选高质量新闻，排除广告软文和标题党。直接返回JSON数组，每项包含title、url、site_name、snippet，最多5条。",
        f"请筛选以下{len(news_list)}条新闻：\n\n{news_data}"
    )
    
    if not resp:
        return news_list[:5]
    
    try:
        content = resp.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        filtered = json.loads(content.strip())
        return filtered if isinstance(filtered, list) else news_list[:5]
    except:
        return news_list[:5]


def format_report(news_list, date):
    """整理日报"""
    if not news_list:
        return "今日暂无智能座舱相关新闻"
    
    news_data = "\n\n".join([
        f"【{i+1}】标题: {item.get('title', '')}\n来源: {item.get('site_name', '')}\n摘要: {item.get('snippet', '')}\n链接: {item.get('url', '')}"
        for i, item in enumerate(news_list)
    ])
    
    resp = call_deepseek(
        f"你是专业的汽车资讯编辑。日期：{date}\n将新闻整理成日报格式：\n- 每条含标题、来源、200字深度总结、链接\n- 优先3-5条\n- 总结要有深度",
        f"请整理以下新闻：\n\n{news_data}"
    )
    
    if not resp:
        return f"📰 【智能座舱日报】{date} 📰\n\n[日报整理功能暂时不可用]"
    return f"📰 【智能座舱日报】{date} 📰\n\n{resp}"


# ==================== HTML 生成 ====================
def generate_html(report, output_path):
    today = datetime.now().strftime("%Y-%m-%d")
    content = report.replace('\n', '<br>')
    
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
        h1 {{ text-align: center; color: #333; margin-bottom: 20px; }}
        .content {{ font-size: 15px; line-height: 1.8; color: #333; }}
        .footer {{ text-align: center; margin-top: 30px; color: #999; font-size: 12px; }}
        .update-time {{ text-align: center; color: #888; margin-bottom: 20px; font-size: 12px; }}
        a {{ color: #667eea; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <h1>🚗 智能座舱日报</h1>
            <p class="update-time">🔄 自动更新于 GitHub Actions</p>
            <div class="content">{content}</div>
            <div class="footer">由 GitHub Actions 自动生成</div>
        </div>
    </div>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ HTML 已生成: {output_path}")


# ==================== 主函数 ====================
def main():
    print("🚀 开始获取智能座舱新闻...")
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. 搜索 - 用多个关键词提高命中率
    print("📡 搜索新闻...")
    
    # 多组关键词搜索
    keywords = [
        "智能座舱 最新",
        "智能座舱 新车 发布",
        "智能座舱 技术 创新",
        "汽车智能座舱 评测 体验"
    ]
    
    all_news = []
    seen_urls = set()
    
    for kw in keywords:
        results = search_news(kw, max_results=8)
        for item in results:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_news.append(item)
    
    print(f"   搜索到 {len(all_news)} 条新闻")
    
    if not all_news:
        # 尝试更宽泛的关键词
        print("   第一次搜索未获取结果，尝试更宽泛的关键词...")
        results = search_news("汽车 智能座舱 2025", max_results=20)
        all_news = results
        print(f"   搜索到 {len(all_news)} 条新闻")
    
    if not all_news:
        print("❌ 搜索失败，无法获取任何新闻")
        # 生成空的日报页面
        output_dir = Path("docs")
        output_dir.mkdir(exist_ok=True)
        generate_html("📰 【智能座舱日报】\n\n今日暂无相关新闻数据，请稍后再试。", output_dir / "index.html")
        return True  # 返回成功，避免action报错
    
    # 2. 筛选
    print("🏆 筛选高质量内容...")
    filtered = filter_news(all_news)
    print(f"   筛选出 {len(filtered)} 条")
    
    # 3. 整理日报
    print("📝 整理日报...")
    report = format_report(filtered, today)
    
    # 4. 生成 HTML
    output_dir = Path("docs")
    output_dir.mkdir(exist_ok=True)
    generate_html(report, output_dir / "index.html")
    
    print("✅ 完成！")
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
