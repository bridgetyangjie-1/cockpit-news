"""
汽车智能座舱新闻摘要 - GitHub Actions 版本
使用 DeepSeek API 筛选和整理新闻内容
"""
import os
import re
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
def search_news(topic, max_results=10):
    """DuckDuckGo 免费搜索"""
    try:
        from ddgs import DDGS
        all_results = []
        seen_urls = set()
        
        # 多关键词搜索
        queries = [
            f"{topic} 智能座舱",
            f"{topic} 座舱 新车",
            f"智能座舱 技术 2025"
        ]
        
        with DDGS() as ddgs:
            for query in queries[:2]:
                for r in ddgs.text(query, max_results=max_results // 2):
                    title = (r.get("title") or "").strip()
                    url = (r.get("href") or "").strip()
                    body = (r.get("body") or "").strip()
                    
                    if not title or not url:
                        continue
                    if url in seen_urls:
                        continue
                    
                    seen_urls.add(url)
                    
                    try:
                        domain = urlparse(url).netloc
                        site_name = domain.replace("www.", "").split(".")[0].title()
                    except:
                        site_name = ""
                    
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
        print(f"DeepSeek 调用失败: {e.code} - {e.reason}")
        if body:
            print(f"详情: {body[:200]}")
        return None
    except Exception as e:
        print(f"DeepSeek 调用失败: {e}")
        return None


def filter_news(news_list):
    """DeepSeek 筛选新闻"""
    if not news_list:
        return []
    
    news_data = "\n".join([
        f"[{i+1}] 标题: {item.get('title', '')}\n来源: {item.get('site_name', '')}\n摘要: {item.get('snippet', '')}\n链接: {item.get('url', '')}"
        for i, item in enumerate(news_list)
    ])
    
    sp = """你是汽车行业内容审核专家。请从以下新闻中筛选出高质量、与智能座舱相关的内容，排除广告和低质量文章。
返回 JSON 数组格式，每项包含 title、url、site_name、snippet 四个字段，最多保留 5 条。"""
    
    up = f"请筛选以下{len(news_list)}条新闻，保留最好的5条：\n\n{news_data}"
    
    response = call_deepseek(sp, up)
    if not response:
        return news_list[:5]
    
    try:
        content = response.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        filtered = json.loads(content.strip())
        return filtered if isinstance(filtered, list) else news_list[:5]
    except:
        return news_list[:5]


def format_report(news_list):
    """DeepSeek 整理日报"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    if not news_list:
        return f"📰 【智能座舱日报】{today}\n\n今日暂无相关新闻。"
    
    news_data = "\n\n".join([
        f"【新闻{i+1}】\n标题: {item.get('title', '')}\n来源: {item.get('site_name', '')}\n摘要: {item.get('snippet', '')}\n链接: {item.get('url', '')}"
        for i, item in enumerate(news_list)
    ])
    
    sp = f"""你是汽车智能座舱领域的专业编辑，今天是{today}。
将筛选后的新闻整理成日报格式，每条新闻包含：
1. 标题
2. 来源
3. 200字左右的深度总结（要有核心信息、背景分析、行业意义）
4. 原文链接
输出风格简洁专业，便于快速阅读。"""
    
    up = f"请将以下新闻整理成{today}的日报：\n\n{news_data}"
    
    response = call_deepseek(sp, up)
    if response:
        return f"📰 【智能座舱日报】{today}\n\n{response}"
    else:
        # 降级：纯文本展示
        lines = [f"📰 【智能座舱日报】{today}"]
        for i, item in enumerate(news_list, 1):
            lines.append(f"\n【{i}】{item.get('title', '')}")
            lines.append(f"来源：{item.get('site_name', '')}")
            lines.append(f"摘要：{item.get('snippet', '')}")
            lines.append(f"链接：{item.get('url', '')}")
        return "\n".join(lines)


# ==================== HTML 生成 ====================
def text_to_html(text):
    """将纯文本报告转换为安全的 HTML"""
    # 先转义 HTML 特殊字符
    safe = escape(text)
    # 将链接转为可点击的链接
    safe = re.sub(
        r'https?://[^\s\n\)\]<>"]+',
        lambda m: f'<a href="{m.group(0)}" target="_blank" rel="noopener">{m.group(0)}</a>',
        safe
    )
    # 换行转 <br>
    safe = safe.replace('\n', '<br>')
    return safe


def generate_html(report_text, output_path):
    """生成漂亮的 HTML 页面"""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    content_html = text_to_html(report_text)
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚗 智能座舱日报 {today}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, 
                      "PingFang SC", "Microsoft YaHei", sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; padding: 20px;
        }}
        .container {{ max-width: 860px; margin: 0 auto; }}
        .card {{ 
            background: #fff; border-radius: 20px; overflow: hidden;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
        }}
        .card-header {{ 
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            color: #fff; padding: 40px 30px; text-align: center;
        }}
        .card-header h1 {{ font-size: 26px; margin-bottom: 8px; }}
        .card-header .date {{ font-size: 13px; opacity: 0.7; }}
        .card-body {{ 
            padding: 30px; 
            font-size: 15px; line-height: 1.8; 
            color: #333;
        }}
        .card-body a {{ 
            color: #667eea; text-decoration: none;
            word-break: break-all;
        }}
        .card-body a:hover {{ text-decoration: underline; }}
        .card-footer {{ 
            text-align: center; padding: 20px; 
            color: #999; font-size: 12px; 
            border-top: 1px solid #f0f0f0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="card-header">
                <h1>🚗 智能座舱日报</h1>
                <p class="date">更新时间：{today} · 由 GitHub Actions 自动生成</p>
            </div>
            <div class="card-body">
                {content_html}
            </div>
            <div class="card-footer">
                每日自动更新 · 数据由 DeepSeek AI 整理
            </div>
        </div>
    </div>
</body>
</html>"""
    
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ HTML 已生成: {output_path}")


# ==================== 主函数 ====================
def main():
    print("🚀 开始获取智能座舱新闻...")
    
    # 1. 搜索新闻
    print("🔍 搜索新闻...")
    news = search_news("汽车智能座舱", max_results=15)
    print(f"    搜索到 {len(news)} 条新闻")
    
    if not news:
        print("❌ 搜索失败")
        return False
    
    # 2. 筛选
    print("🏆 筛选高质量内容...")
    filtered = filter_news(news)
    print(f"    筛选出 {len(filtered)} 条")
    
    # 3. 整理日报
    print("📝 整理日报...")
    report = format_report(filtered)
    
    # 4. 生成 HTML
    output_path = "docs/index.html"
    generate_html(report, output_path)
    
    print("✅ 完成!")
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
