"""
汽车智能座舱新闻摘要 - GitHub Actions 版本
DeepSeek 返回 JSON 数据，Python 构建 HTML
"""
import os
import json
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from html import escape


# ==================== 配置 ====================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


# ==================== 搜索 ====================
def search_news(topic, max_results=25):
    """DuckDuckGo 免费搜索，限定近一周热点"""
    try:
        from ddgs import DDGS
        all_results = []
        seen_urls = set()
        year = datetime.now().strftime("%Y")

        # 多角度搜索，确保覆盖热点
        queries = [
            f"{topic} 智能座舱 热点",
            f"{topic} 最新技术 发布",
            f"{year} 智能座舱 新车 首发",
            f"智能座舱 AI 座舱系统 {year}"
        ]

        with DDGS() as ddgs:
            for query in queries:
                # timelimit='w' 限定过去一周的结果
                for r in ddgs.text(query, max_results=max_results // 2, timelimit='w'):
                    title = (r.get("title") or "").strip()
                    url = (r.get("href") or "").strip()
                    body = (r.get("body") or "").strip()

                    if not title or not url:
                        continue
                    if url in seen_urls:
                        continue

                    seen_urls.add(url)

                    domain = urlparse(url).netloc.replace("www.", "")
                    site_name = domain.split(".")[0].title() if domain else ""

                    # 过滤广告
                    ad_keywords = ["ad", "sponsored", "推广", "广告", "track"]
                    if any(k in url.lower() for k in ad_keywords):
                        continue

                    all_results.append({
                        "title": title,
                        "url": url,
                        "snippet": body[:400],
                        "site_name": site_name
                    })

        print(f"    去重后共 {len(all_results)} 条不同新闻")
        return all_results
    except ImportError:
        print("请先安装依赖: pip install ddgs")
        return []
    except Exception as e:
        print(f"搜索失败: {e}")
        return []


# ==================== DeepSeek API ====================
def call_deepseek(system_prompt, user_prompt):
    """调用 DeepSeek API"""
    if not DEEPSEEK_API_KEY:
        print("未设置 DEEPSEEK_API_KEY")
        return None

    url = "https://api.deepseek.com/v1/chat/completions"
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 4096
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}'
        },
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print(f"DeepSeek 调用失败: {e.code}")
        if body:
            print(f"详情: {body[:200]}")
        return None
    except Exception as e:
        print(f"DeepSeek 调用失败: {e}")
        return None


def filter_and_format(news_list):
    """DeepSeek 一次性完成筛选和整理，返回JSON格式（中英双语）"""
    if not news_list:
        return []

    today = datetime.now().strftime("%Y-%m-%d")

    news_data = "\n\n".join([
        f"新闻{i+1}:\n标题: {item['title']}\n来源: {item['site_name']}\n摘要: {item['snippet']}\n链接: {item['url']}"
        for i, item in enumerate(news_list)
    ])

    system_prompt = f"""你是汽车智能座舱专业编辑，今天是{today}。

请从以下新闻中筛选出最有价值的5条，为每条撰写200字中文深度总结，并将其翻译成英文。

必须返回严格的JSON格式，不要加任何其他文字：
{{
  "news": [
    {{
      "title": "原标题（中文）",
      "title_en": "English Title",
      "url": "原链接",
      "site_name": "来源名",
      "summary": "200字中文深度总结，包含核心信息、背景分析和行业意义",
      "summary_en": "200-word English deep summary, containing key information, background analysis and industry significance"
    }}
  ]
}}

要求：
1. 排除广告和低质量内容
2. 中文总结要有深度，不只是重复摘要
3. 英文翻译要专业、准确、自然
4. 返回标准JSON，不要用markdown"""

    user_prompt = f"请分析以下{len(news_list)}条新闻，返回中英双语JSON格式：\n\n{news_data}"

    response = call_deepseek(system_prompt, user_prompt)
    if not response:
        return []

    # 提取JSON
    try:
        content = response.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())
        items = data.get("news", data if isinstance(data, list) else [])
        return items if isinstance(items, list) else []
    except:
        return []


# ==================== HTML 生成 ====================
def generate_html(news_items, output_path, lang='zh'):
    """生成单语言 HTML 页面，带语言切换按钮
    
    lang='zh' -> 中文版（docs/index.html），显示 "EN" 按钮
    lang='en' -> 英文版（docs/en/index.html），显示 "中文" 按钮
    """
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    is_zh = lang == 'zh'
    page_title = "智能座舱日报" if is_zh else "Smart Cockpit Daily"
    page_desc = "由 GitHub Actions 自动更新" if is_zh else "Auto-updated by GitHub Actions"

    # 语言切换按钮
    if is_zh:
        switch_btn = '<a href="en/index.html" class="lang-switch">🌐 EN</a>'
        switch_label = "切换到英文版"
    else:
        switch_btn = '<a href="../index.html" class="lang-switch">🌐 中文</a>'
        switch_label = "Switch to Chinese"

    # 构建新闻卡片
    news_cards = ""
    if news_items:
        for i, item in enumerate(news_items, 1):
            if is_zh:
                title = escape(item.get("title", ""))
                summary = escape(item.get("summary", item.get("summary_en", "")))
            else:
                title = escape(item.get("title_en", item.get("title", "")))
                summary = escape(item.get("summary_en", item.get("summary", "")))

            site = escape(item.get("site_name", ""))
            url = escape(item.get("url", ""))

            news_cards += f"""
            <div class="news-item">
                <div class="news-number">{i}</div>
                <div class="news-body">
                    <h2 class="news-title">{title}</h2>
                    <div class="news-source">📰 {site}</div>
                    <div class="news-summary">{summary}</div>
                    <a href="{url}" class="news-link" target="_blank" rel="noopener">{'🔗 阅读原文' if is_zh else '🔗 Read Original'}</a>
                </div>
            </div>"""
    else:
        no_news_msg = "😔 今日暂无智能座舱相关新闻" if is_zh else "😔 No smart cockpit news today"
        news_cards = f"""
        <div class="no-news">
            <p>{no_news_msg}</p>
        </div>"""

    footer_text = "数据来源：DuckDuckGo 搜索 · 内容整理：DeepSeek AI" if is_zh \
        else "Source: DuckDuckGo Search · Analysis: DeepSeek AI"

    html_lang = "zh-CN" if is_zh else "en"

    html = f"""<!DOCTYPE html>
<html lang="{html_lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚗 {page_title} {today}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                      "PingFang SC", "Microsoft YaHei", sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            min-height: 100vh; padding: 30px 15px;
        }}
        .container {{ max-width: 860px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 30px; color: #fff; position: relative; }}
        .header h1 {{ font-size: 28px; margin-bottom: 8px; }}
        .header .sub {{ font-size: 13px; opacity: 0.7; }}
        .lang-switch {{
            display: inline-block; margin-top: 12px;
            padding: 8px 20px; border-radius: 20px;
            background: rgba(255,255,255,0.15);
            color: #fff; text-decoration: none;
            font-size: 14px; font-weight: 500;
            transition: background 0.3s;
        }}
        .lang-switch:hover {{ background: rgba(255,255,255,0.3); }}
        .card {{
            background: #fff; border-radius: 16px; overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }}
        .card-body {{ padding: 30px; }}
        .news-item {{
            display: flex; gap: 16px; padding: 20px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .news-item:last-child {{ border-bottom: none; }}
        .news-number {{
            width: 36px; height: 36px; border-radius: 50%;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: #fff; display: flex; align-items: center;
            justify-content: center; font-weight: bold; font-size: 16px;
            flex-shrink: 0;
        }}
        .news-body {{ flex: 1; }}
        .news-title {{
            font-size: 18px; font-weight: 600; color: #1a1a2e;
            margin-bottom: 6px; line-height: 1.4;
        }}
        .news-source {{
            font-size: 13px; color: #888; margin-bottom: 10px;
        }}
        .news-summary {{
            font-size: 14.5px; line-height: 1.8; color: #444;
            margin-bottom: 12px;
        }}
        .news-link {{
            display: inline-block; font-size: 13px;
            color: #667eea; text-decoration: none;
            padding: 4px 12px; border-radius: 4px;
            background: #f0f0ff;
        }}
        .news-link:hover {{ background: #e0e0ff; text-decoration: underline; }}
        .footer {{
            text-align: center; padding: 18px;
            color: #999; font-size: 12px;
            border-top: 1px solid #f0f0f0;
        }}
        .no-news {{ text-align: center; padding: 40px; color: #999; }}
        @media (max-width: 600px) {{
            .card-body {{ padding: 16px; }}
            .news-title {{ font-size: 16px; }}
            .news-summary {{ font-size: 14px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚗 {page_title}</h1>
            <p class="sub">{today} · {page_desc}</p>
            <p>{switch_btn}<br><span style="font-size:12px;opacity:0.6">{switch_label}</span></p>
        </div>
        <div class="card">
            <div class="card-body">
                {news_cards}
            </div>
            <div class="footer">{footer_text}</div>
        </div>
    </div>
</body>
</html>"""

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ {'中文' if is_zh else '英文'}页面已生成: {output_path}")


# ==================== 主函数 ====================
def main():
    print("🚀 开始获取智能座舱新闻...")

    # 1. 搜索新闻
    print("🔍 搜索新闻...")
    news = search_news("汽车智能座舱", max_results=15)
    print(f"    搜索到 {len(news)} 条新闻")

    if not news:
        print("❌ 搜索失败，生成空页面")
        generate_html([], "docs/index.html", lang='zh')
        generate_html([], "docs/en/index.html", lang='en')
        return False

    # 2. DeepSeek 筛选 + 整理（返回双语JSON）
    print("🤖 DeepSeek 分析中...")
    items = filter_and_format(news)

    if items:
        print(f"    生成 {len(items)} 条深度分析")
    else:
        print("    DeepSeek 未返回数据，使用原始结果")
        items = [
            {
                "title": n["title"],
                "title_en": n["title"],
                "url": n["url"],
                "site_name": n["site_name"],
                "summary": n["snippet"],
                "summary_en": n["snippet"]
            }
            for n in news[:5]
        ]

    # 3. 生成中英文两个 HTML 页面
    print("📝 生成页面...")
    generate_html(items, "docs/index.html", lang='zh')
    generate_html(items, "docs/en/index.html", lang='en')

    print("✅ 完成！中英双语日报已同步生成")
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
