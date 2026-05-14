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
def generate_search_keywords(topic="汽车智能座舱"):
    """DeepSeek 生成多样化搜索关键词，覆盖全球视野"""
    system_prompt = f"""你是全球汽车智能座舱领域的资深行业分析师。请围绕"{topic}"，生成15个极具前瞻性和多样性的搜索关键词。

为了打破信息茧房，捕捉最深度的行业动态，关键词必须包含中文和英文（比例约1:1），并覆盖以下维度：
1. 全球科技巨头与底层生态：如 "Android Automotive update", "Apple CarPlay 2.0 UX", "车载大模型 AI Agent"
2. 北美与全球前沿新势力：如 "Rivian software update", "Tesla V12 UI", "Waymo interior design"
3. 顶级供应商与硬件架构：如 "Qualcomm Snapdragon Digital Chassis", "舱驾一体 电子电气架构", "Bosch smart cockpit"
4. 交互体验与用户研究：如 "Multimodal interaction in-car", "人机交互 HCI 座舱", "智能座舱 情感计算"
5. 商业化与行业趋势：如 "Software defined vehicle monetization", "车企 软件订阅 服务"

要求：
- 拒绝水文词汇，关键词要有针对性，能搜出B2B行业报告、科技媒体深度文章或极客评测。
- 关键词中尽量不要包含普遍的"汽车智能座舱"这几个中文字，以免搜到重复度极高的公关稿。
- 必须返回严格的JSON格式，不要加任何其他文字：
{{"keywords": ["keyword1", "keyword2", ..., "keyword15"]}}"""

    user_prompt = f"请为'{topic}'生成多样化的搜索关键词"
    response = call_deepseek(system_prompt, user_prompt)
    if not response:
        print("    关键词生成失败，使用默认关键词")
        return ["汽车智能座舱 热点", "新车 智能体验 2025", "车载大模型 AI", "智能车机 系统"]
    try:
        content = response.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        data = json.loads(content.strip())
        keywords = data.get("keywords", [])
        print(f"    生成 {len(keywords)} 个搜索关键词")
        return keywords
    except Exception as e:
        print(f"    关键词解析失败: {e}")
        return ["汽车智能座舱 热点", "新车 智能体验 2025", "车载大模型 AI", "智能车机 系统"]


def search_news(keywords, max_results=40):
    """用多个关键词搜索 DuckDuckGo，限定近一周"""
    try:
        from ddgs import DDGS
        all_results = []
        seen_urls = set()
        results_per_query = max(3, max_results // len(keywords))

        with DDGS() as ddgs:
            for query in keywords:
                for r in ddgs.text(query, max_results=results_per_query, timelimit='w'):
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
    """DeepSeek 严苛筛选+深度分析，返回双语JSON"""
    if not news_list:
        return []

    today = datetime.now().strftime("%Y-%m-%d")

    news_data = "\n\n".join([
        f"新闻{i+1}:\n标题: {item['title']}\n来源: {item['site_name']}\n摘要: {item['snippet']}\n链接: {item['url']}"
        for i, item in enumerate(news_list)
    ])

    system_prompt = f"""你是拥有十几年经验的资深汽车行业分析师与用户体验专家。今天是{today}。

我将提供一批通过全球搜索引擎抓取的行业新闻。请以极为严苛的标准，筛选出最具战略价值和前沿洞察的 5 条新闻。

【过滤死线 - 绝对不要】：
1. 纯粹的销量战报、车企公关通稿、毫无技术细节的软文。
2. 缺乏商业或技术影响力的边缘新闻。

【筛选优先级 - 优先保留】：
1. 颠覆性的交互设计 (UI/UX) 与用户体验研究成果。
2. 底层软硬件架构的重大突破 (如全新的 OS、算力芯片迭代)。
3. 全球头部企业 (如 Apple, Google, Tesla 及顶级 Tier 1) 的战略动向。

请为选出的新闻撰写深度总结，并翻译成英文。
总结必须是结构化的，包含三句话：
第一句写明核心事件；第二句分析技术/体验亮点；第三句指出其对行业的长期影响或潜在隐患。

必须返回严格的JSON格式，不要加任何其他文字：
{{
  "news": [
    {{
      "title": "原标题（中文）",
      "title_en": "English Title",
      "url": "原链接",
      "site_name": "来源媒体",
      "summary": "200字中文深度洞察，严格按照要求的三句话逻辑撰写。",
      "summary_en": "200-word English professional analysis corresponding to the Chinese text."
    }}
  ]
}}"""

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
    """生成单语言 HTML 页面，带语言切换按钮"""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")

    is_zh = lang == 'zh'
    page_title = "智能座舱日报" if is_zh else "Smart Cockpit Daily"
    page_desc = "由 GitHub Actions 自动更新" if is_zh else "Auto-updated by GitHub Actions"

    if is_zh:
        switch_btn = '<a href="en/index.html" class="lang-switch">🌐 EN</a>'
        switch_label = "切换到英文版"
    else:
        switch_btn = '<a href="../index.html" class="lang-switch">🌐 中文</a>'
        switch_label = "Switch to Chinese"

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
        news_cards = f'<div class="no-news"><p>{no_news_msg}</p></div>'

    footer_text = "数据来源：DuckDuckGo 搜索 · 内容整理：DeepSeek AI" if is_zh else "Source: DuckDuckGo Search · Analysis: DeepSeek AI"
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
            display: inline-block; margin-top: 12px; padding: 8px 20px;
            border-radius: 20px; background: rgba(255,255,255,0.15);
            color: #fff; text-decoration: none; font-size: 14px; font-weight: 500;
            transition: background 0.3s;
        }}
        .lang-switch:hover {{ background: rgba(255,255,255,0.3); }}
        .card {{ background: #fff; border-radius: 16px; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }}
        .card-body {{ padding: 30px; }}
        .news-item {{ display: flex; gap: 16px; padding: 20px 0; border-bottom: 1px solid #f0f0f0; }}
        .news-item:last-child {{ border-bottom: none; }}
        .news-number {{
            width: 36px; height: 36px; border-radius: 50%;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: #fff; display: flex; align-items: center;
            justify-content: center; font-weight: bold; font-size: 16px; flex-shrink: 0;
        }}
        .news-body {{ flex: 1; }}
        .news-title {{ font-size: 18px; font-weight: 600; color: #1a1a2e; margin-bottom: 6px; line-height: 1.4; }}
        .news-source {{ font-size: 13px; color: #888; margin-bottom: 10px; }}
        .news-summary {{ font-size: 14.5px; line-height: 1.8; color: #444; margin-bottom: 12px; }}
        .news-link {{ display: inline-block; font-size: 13px; color: #667eea; text-decoration: none; padding: 4px 12px; border-radius: 4px; background: #f0f0ff; }}
        .news-link:hover {{ background: #e0e0ff; text-decoration: underline; }}
        .footer {{ text-align: center; padding: 18px; color: #999; font-size: 12px; border-top: 1px solid #f0f0f0; }}
        .no-news {{ text-align: center; padding: 40px; color: #999; }}
        @media (max-width: 600px) {{ .card-body {{ padding: 16px; }} .news-title {{ font-size: 16px; }} .news-summary {{ font-size: 14px; }} }}
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
            <div class="card-body">{news_cards}</div>
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

    # 0. 生成多样化搜索关键词
    print("🧠 生成多样化搜索关键词...")
    keywords = generate_search_keywords("汽车智能座舱")
    print(f"    关键词列表: {keywords}")

    # 1. 用多个关键词搜索
    print("🔍 多关键词搜索中...")
    news = search_news(keywords, max_results=40)
    print(f"    共搜索到 {len(news)} 条新闻")

    if not news:
        print("❌ 搜索失败，生成空页面")
        generate_html([], "docs/index.html", lang='zh')
        generate_html([], "docs/en/index.html", lang='en')
        return False

    # 2. DeepSeek 筛选 + 整理
    print("🤖 DeepSeek 分析中...")
    items = filter_and_format(news)

    if items:
        print(f"    生成 {len(items)} 条深度分析")
    else:
        print("    DeepSeek 未返回数据，使用原始结果")
        items = [
            {"title": n["title"], "title_en": n["title"], "url": n["url"], "site_name": n["site_name"], "summary": n["snippet"], "summary_en": n["snippet"]}
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
