"""
汽车智能座舱新闻摘要 - GitHub Actions 版本
支持 30 天历史归档 + 左侧边栏布局 + 动态交互 + 正则防弹解析
"""
import os
import json
import urllib.request
import urllib.error
import re
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from html import escape

# ==================== 配置 ====================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
HISTORY_FILE = "docs/history_data.json"
MAX_DAYS = 30  # 保留最近 30 天

# Buttondown 邮件订阅配置（发给订阅者）
BUTTONDOWN_API_KEY = os.environ.get("BUTTONDOWN_API_KEY") or ""

# SMTP 邮件配置（发给私人邮箱）
SMTP_HOST = os.environ.get("SMTP_HOST") or ""
SMTP_PORT = int(os.environ.get("SMTP_PORT") or "465")
SMTP_USER = os.environ.get("SMTP_USER") or ""
SMTP_PASS = os.environ.get("SMTP_PASS") or ""
PRIVATE_EMAILS = os.environ.get("PRIVATE_EMAILS") or ""  # 逗号分隔


# ==================== 历史数据管理 ====================
def load_history_data():
    """加载历史数据文件"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"    加载历史数据失败: {e}")
    return {"records": []}


def save_history_data(history_data):
    """保存历史数据，自动清理超过30天的记录"""
    history_data["records"].sort(key=lambda x: x.get("date", ""), reverse=True)
    
    if len(history_data["records"]) > MAX_DAYS:
        removed = len(history_data["records"]) - MAX_DAYS
        history_data["records"] = history_data["records"][:MAX_DAYS]
        print(f"    已清理 {removed} 条超过 {MAX_DAYS} 天的旧记录")
    
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)
    print(f"    历史数据已保存: {len(history_data['records'])} 条记录")


def add_today_record(history_data, news_items):
    """添加今天的新闻记录"""
    today = datetime.now().strftime("%Y-%m-%d")
    today_display = datetime.now().strftime("%m月%d日")
    
    existing_dates = [r.get("date") for r in history_data["records"]]
    if today in existing_dates:
        for record in history_data["records"]:
            if record.get("date") == today:
                record["news"] = news_items
                record["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"    已更新今天的记录: {today}")
                return history_data
    else:
        new_record = {
            "date": today,
            "date_display": today_display,
            "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now().weekday()],
            "news_count": len(news_items),
            "news": news_items,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        history_data["records"].insert(0, new_record)
        print(f"    已添加新记录: {today}")
    return history_data


# ==================== 邮件格式化工具 ====================
def format_summary_for_email(summary, is_html=True):
    """使用正则表达式，鲁棒地处理大模型输出的段落标题"""
    if not summary:
        return ""
    
    # 替换所有的 \n 为 <br>
    formatted = summary.replace("\n", "<br>")
    
    # 使用正则匹配 【任意文字】 或 [任意文字] 并替换为高亮样式
    # 这样即使大模型输出 【 事件 概述 】，也能正确高亮
    if is_html:
        pattern = r'([【\[].*?[】\]])'
        replacement = r'<br><div class="section-title" style="color:#667eea; font-weight:600; margin:12px 0 4px;">\1</div>'
        formatted = re.sub(pattern, replacement, formatted)
    
    # 清理连续多余的换行
    formatted = re.sub(r'(<br>\s*){3,}', '<br><br>', formatted)
    
    # 去掉最开头的多余换行
    if formatted.startswith('<br>'):
        formatted = formatted[4:]
        
    return formatted


# ==================== 邮件发送（Buttondown & SMTP）====================
def send_daily_email(news_items, date_str):
    """通过 Buttondown API 发送邮件给所有订阅者"""
    if not BUTTONDOWN_API_KEY:
        print("    ⚠️ 未配置 BUTTONDOWN_API_KEY，跳过发送")
        return False
    
    subject = f"🚗 智能座舱日报 | {date_str}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', sans-serif; background: #f5f5f5; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #111317 0%, #1e2023 100%); padding: 30px; text-align: center; border-bottom: 2px solid #00F2FF; }}
            .header h1 {{ color: #00F2FF; margin: 0; font-size: 24px; letter-spacing: 1px; }}
            .header p {{ color: rgba(255,255,255,0.8); margin: 10px 0 0; font-size: 14px; }}
            .content {{ padding: 30px; }}
            .news-item {{ padding: 24px 0; border-bottom: 1px solid #eee; }}
            .news-item:last-child {{ border-bottom: none; }}
            .news-number {{ display: inline-block; width: 28px; height: 28px; background: #00F2FF; color: #111317; border-radius: 50%; text-align: center; line-height: 28px; font-size: 14px; font-weight: bold; margin-right: 10px; }}
            .news-title {{ font-size: 18px; font-weight: 600; color: #333; margin: 10px 0; line-height: 1.4; }}
            .news-meta {{ font-size: 12px; color: #888; margin-bottom: 12px; }}
            .news-summary {{ font-size: 15px; color: #444; line-height: 1.8; }}
            .news-link {{ display: inline-block; margin-top: 12px; padding: 8px 16px; background: #f0f0ff; color: #667eea; text-decoration: none; border-radius: 6px; font-size: 13px; font-weight: 500; }}
            .footer {{ background: #f9f9f9; padding: 20px; text-align: center; font-size: 12px; color: #999; }}
            .footer a {{ color: #667eea; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>SMART COCKPIT DAILY</h1>
                <p>{date_str} | 今日 {len(news_items)} 条精选资讯</p>
            </div>
            <div class="content">
    """
    
    for i, item in enumerate(news_items, 1):
        formatted_summary = format_summary_for_email(item.get("summary", ""), is_html=True)
        
        html_content += f"""
                <div class="news-item">
                    <span class="news-number">{i}</span>
                    <div class="news-title">{item.get('title', '')}</div>
                    <div class="news-meta">📰 {item.get('site_name', '')} | 📅 {item.get('publish_date', '')}</div>
                    <div class="news-summary">{formatted_summary}</div>
                    <a href="{item.get('url', '')}" class="news-link">🔗 阅读原文</a>
                </div>
        """
    
    html_content += """
            </div>
            <div class="footer">
                <p>🌐 在线阅读: <a href="https://bridgetyangjie-1.github.io/cockpit-news/">访问智能座舱日报看板</a></p>
                <p style="margin-top: 10px;">本邮件由系统自动发送</p>
                <p style="margin-top: 5px;">© 2026 Bridget Yang</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        url = "https://api.buttondown.email/v1/emails"
        data = {
            "subject": subject,
            "body": html_content,
            "email_type": "public"  # 规范用法，发送给所有订阅者并归档
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={
                'Authorization': f'Token {BUTTONDOWN_API_KEY}',
                'Content-Type': 'application/json'
            },
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"    ✅ 邮件已通过 Buttondown 发送给所有订阅者")
            return True
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"    ❌ Buttondown API 错误: {e.code}")
        print(f"    详情: {error_body[:200]}")
        return False
    except Exception as e:
        print(f"    ❌ Buttondown 发送失败: {e}")
        return False


def send_private_email(news_items, date_str):
    """通过 SMTP 发送邮件给私人邮箱"""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, PRIVATE_EMAILS]):
        print("    ⚠️ SMTP 配置不完整，跳过私人邮件发送")
        return False
    
    recipients = [e.strip() for e in PRIVATE_EMAILS.split(",") if e.strip()]
    if not recipients:
        print("    ⚠️ 未配置私人邮箱，跳过发送")
        return False
    
    subject = f"🚗 智能座舱日报 | {date_str}"
    news_html = ""
    for i, item in enumerate(news_items, 1):
        formatted_summary = format_summary_for_email(item.get('summary', ''), is_html=True)
        # 将 section-title 颜色替换为适应私人邮件的蓝色
        formatted_summary = formatted_summary.replace('color:#667eea', 'color:#00d4ff')
        
        news_html += f"""
        <div style="margin-bottom: 24px; padding: 16px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #00d4ff;">
            <h3 style="margin: 0 0 8px 0; color: #1a1a2e; font-size: 16px;">
                {i}. {item.get('title', '')}
            </h3>
            <p style="margin: 4px 0; color: #666; font-size: 13px;">
                📅 {item.get('publish_date', '')} | 📰 {item.get('site_name', '')}
            </p>
            <p style="margin: 12px 0 0 0; color: #333; font-size: 14px; line-height: 1.6;">
                {formatted_summary}
            </p>
            <a href="{item.get('url', '#')}" style="color: #00d4ff; font-size: 13px;">阅读原文 →</a>
        </div>
        """
    
    html_content = f"""
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 32px; padding: 24px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 12px;">
            <h1 style="color: #00d4ff; margin: 0; font-size: 24px;">SMART COCKPIT DAILY</h1>
            <p style="color: #fff; margin: 8px 0 0 0;">{date_str} | 今日 {len(news_items)} 条精选资讯</p>
        </div>
        {news_html}
    </body>
    </html>
    """
    
    try:
        import ssl
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SMTP_USER, SMTP_PASS)
            for recipient in recipients:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = SMTP_USER
                msg['To'] = recipient
                msg.attach(MIMEText(html_content, 'html', 'utf-8'))
                server.sendmail(SMTP_USER, recipient, msg.as_string())
            print(f"    ✅ 私人邮件已发送至 {len(recipients)} 个联系人")
            return True
    except Exception as e:
        print(f"    ❌ SMTP 发送失败: {e}")
        return False


# ==================== 搜索与AI逻辑 ====================
def generate_search_keywords(topic="汽车智能座舱"):
    """DeepSeek 生成精准的软件生态与数字体验搜索关键词"""
    system_prompt = f"""你是深耕中国新能源汽车市场的资深用户研究与体验分析师。请围绕"{topic}"，生成15个精准且多样化的中文搜索关键词。

为了精准捕捉行业内的软件创新与数字体验动态，关键词必须覆盖以下维度：
1. 核心软件与数字娱乐生态：如 "车机 第三方 App 接入", "座舱 影音娱乐 体验", "车载游戏 生态", "手车互联 无缝流转"
2. OTA与核心功能演进：如 "新势力 OTA 升级 体验", "座舱 AI大模型 落地", "座舱 软件订阅 服务"
3. 关键交互触点 (UX/UI)：如 "座舱 零层级 交互", "车载语音 多指令", "多模态交互 评测", "车机屏幕 交互逻辑"
4. 头部玩家的具体动作：如 "蔚来 Banyan 智能应用", "小鹏 天玑 系统体验", "小米 澎湃OS 座舱", "理想 空间交互"

要求：
- 绝对不要外观、底盘、硬件参数相关的词汇。只聚焦"软件"、"交互"、"生态应用（含娱乐/音频）"。
- 【地理限制】必须聚焦中国大陆市场，关注大陆品牌。不要包含台湾、香港、澳门相关字眼。
- 必须返回严格的JSON格式：
{{"keywords": ["关键词1", "关键词2", ..., "关键词15"]}}"""

    response = call_deepseek(system_prompt, f"请为'{topic}'生成多样化的搜索关键词")
    if not response:
        return ["车机 OTA 升级 体验", "智能座舱 交互设计", "车载语音助手 评测", "手车互联 生态"]
        
    try:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            keywords = data.get("keywords", [])
            print(f"    生成 {len(keywords)} 个搜索关键词")
            return keywords
    except Exception as e:
        print(f"    关键词解析失败: {e}")
    return ["智能座舱 OTA", "车机系统 体验", "车载交互 UI"]


def search_news(keywords, max_results=40):
    """用多个关键词搜索 DuckDuckGo"""
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
                    publish_date = (r.get("date") or "").strip()

                    if not title or not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    domain = urlparse(url).netloc.replace("www.", "")
                    site_name = domain.split(".")[0].title() if domain else ""

                    # 仅保留最基础的去广告过滤
                    ad_keywords = ["ad", "sponsored", "推广", "广告", "track"]
                    if any(k in url.lower() for k in ad_keywords):
                        continue
                    
                    # 过滤敏感地区内容
                    sensitive_keywords = ["台湾", "台灣", "taiwan", "香港", "hong kong", "澳门", "macau"]
                    if any(k in (title + body).lower() for k in sensitive_keywords):
                        continue

                    all_results.append({
                        "title": title,
                        "url": url,
                        "snippet": body[:400],
                        "site_name": site_name,
                        "publish_date": publish_date
                    })

        print(f"    初筛获取共 {len(all_results)} 条新闻内容")
        return all_results
    except ImportError:
        print("请先安装依赖: pip install ddgs")
        return []
    except Exception as e:
        print(f"搜索失败: {e}")
        return []


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
        "max_tokens": 8192
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
        with urllib.request.urlopen(req, timeout=120) as response:
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
        f"新闻{i+1}:\n标题: {item['title']}\n来源: {item['site_name']}\n日期: {item.get('publish_date', '')}\n摘要: {item['snippet']}\n链接: {item['url']}"
        for i, item in enumerate(news_list)
    ])

    system_prompt = f"""你是拥有十几年丰富经验的资深汽车用户研究与体验分析专家。今天是{today}。

我将提供一批通过搜索引擎抓取的行业新闻。请以极为严苛的标准，筛选出对国内汽车软件生态和交互设计最具研究价值的 5 条新闻。

【核心聚焦方向 - 软件与体验】：
聚焦于中国"造车新势力"与科技大厂在智能座舱内的纯软件功能创新、数字生态服务（如影音娱乐/游戏/生活服务接入）、OTA更新细节、以及底层交互逻辑(UI/UX)演进。

【过滤死线 - 绝对不要】：
1. 纯硬件发布（芯片、屏幕材质）、销量战报。
2. 涉及台湾、香港、澳门地区的内容。

请为选出的新闻撰写精炼总结，并翻译成英文。

【结构与字数要求】：
每篇总结必须包含以下三个模块（必须使用这些标题），中文总计约 300 字：
【事件概述】提炼核心软件事件，详细说明功能内容。
【体验价值】从UX视角剖析该功能的体验价值，解决了什么痛点。
【商业影响】研判其对提升用户粘性、软件订阅率的影响。

【语言要求】：
summary 字段仅纯中文；summary_en 字段仅纯英文。

必须返回严格的JSON格式：
{{
  "news": [
    {{
      "title": "原标题", "title_en": "English Title", "url": "链接", "site_name": "来源", "publish_date": "发布日期",
      "summary": "【事件概述】... \\n\\n【体验价值】... \\n\\n【商业影响】...",
      "summary_en": "【Event Overview】... \\n\\n【Experience Value】... \\n\\n【Business Impact】..."
    }}
  ]
}}"""

    response = call_deepseek(system_prompt, f"请分析以下新闻：\n\n{news_data}")
    if not response:
        return []

    try:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            items = data.get("news", [])
            print(f"    ✅ AI 筛选出 {len(items)} 条高质量新闻")
            return items
    except Exception as e:
        print(f"    ❌ 解析 DeepSeek 响应失败: {e}")
    return []


# ==================== HTML 生成 ====================
def generate_html(output_path, lang='zh'):
    """生成使用 Tailwind CSS 框架的专业仪表盘页面"""
    is_zh = lang == 'zh'
    html_lang = "zh-CN" if is_zh else "en"
    
    texts = {
        'zh': {
            'title': '智能座舱日报',
            'subtitle': 'Daily Intelligence',
            'description': '聚焦中国新能源车软件生态与座舱交互体验，每日自动抓取OTA动态、功能创新与用户研究洞察。',
            'nav_today': '今日',
            'sidebar_archive': '历史归档',
            'loading': '加载中...',
            'no_news': '该日期暂无新闻数据',
            'read_original': '阅读原文',
            'footer': '数据来源：DuckDuckGo · DeepSeek AI',
            'switch_lang': 'English',
            'subscribe': '订阅日报',
            'subscribe_btn': '立即订阅'
        },
        'en': {
            'title': 'Smart Cockpit',
            'subtitle': 'Daily Intelligence',
            'description': 'Focusing on China NEV software ecosystem and cockpit interaction experience. Daily insights on OTA and UX.',
            'nav_today': 'Today',
            'sidebar_archive': 'ARCHIVE',
            'loading': 'Loading...',
            'no_news': 'No news available',
            'read_original': 'Read Original',
            'footer': 'Source: DuckDuckGo · DeepSeek AI',
            'switch_lang': '中文',
            'subscribe': 'Subscribe',
            'subscribe_btn': 'Subscribe'
        }
    }
    t = texts[lang]
    json_path = "history_data.json" if is_zh else "../history_data.json"
    lang_switch_url = "en/index.html" if is_zh else "../index.html"

    html = f"""<!DOCTYPE html>
<html lang="{html_lang}" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚗 {t['title']}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet"/>
    <script>
        tailwind.config = {{
            darkMode: "class",
            theme: {{
                extend: {{
                    colors: {{
                        background: "#0D0F12",
                        surface: "#111317",
                        "surface-container": "#1e2023",
                        "surface-container-high": "#282a2d",
                        primary: "#00F2FF",
                        "on-surface": "#e2e2e6",
                        "on-surface-variant": "#b9cacb",
                        "outline-variant": "#3a494b"
                    }}
                }}
            }}
        }}
    </script>
    <style>
        .material-symbols-outlined {{ font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }}
        body {{ background-color: #0D0F12; }}
        .news-card-bg {{ position: absolute; top: 8px; left: 16px; pointer-events: none; }}
        .news-card-bg span {{ font-size: 120px; color: #00F2FF; opacity: 0.05; line-height: 1; }}
        .glow-hover:hover {{ box-shadow: 0 12px 40px -12px rgba(0, 242, 255, 0.25); border-color: rgba(0, 242, 255, 0.5); }}
        .date-item-active {{ border-left: 4px solid #00F2FF; background: rgba(0, 242, 255, 0.1); color: #00F2FF; font-weight: 600; }}
        .section-title {{ color: #00F2FF; font-weight: 600; margin-top: 12px; margin-bottom: 4px; font-size: 14px; }}
    </style>
</head>
<body class="bg-background text-on-surface font-sans overflow-x-hidden">
    <aside id="sidebar" class="fixed left-0 top-0 h-screen w-64 bg-surface-container border-r border-outline-variant flex-col z-50 hidden md:flex">
        <div class="p-6 border-b border-outline-variant text-center">
            <h1 class="text-xl font-bold text-primary tracking-tight uppercase">SMART COCKPIT</h1>
            <p class="text-xs text-on-surface-variant/70 mt-3 leading-relaxed">{t['description']}</p>
        </div>
        
        <nav class="flex-1 overflow-y-auto mt-4">
            <div onclick="selectToday()" class="flex items-center gap-3 px-5 py-3 cursor-pointer transition-colors hover:bg-surface-container-high">
                <span class="material-symbols-outlined text-xl">today</span>
                <span>{t['nav_today']}</span>
            </div>
            <div class="px-6 py-2 mt-4">
                <span class="text-[10px] uppercase tracking-widest text-on-surface-variant/50">{t['sidebar_archive']}</span>
            </div>
            <div id="dateList" class="space-y-1"></div>
        </nav>
        
        <div class="p-4 border-t border-outline-variant space-y-3">
            <a href="{lang_switch_url}" class="flex items-center gap-2 text-on-surface-variant hover:text-primary transition-colors cursor-pointer">
                <span class="material-symbols-outlined text-lg">language</span>
                <span class="text-sm">{t['switch_lang']}</span>
            </a>
            <div class="pt-3 border-t border-outline-variant/50">
                <p class="text-xs text-on-surface-variant mb-2">📬 {t['subscribe']}</p>
                <form action="https://buttondown.com/api/emails/embed-subscribe/Cockpit_News_by_BridgetYang" method="post" class="space-y-2">
                    <input type="email" name="email" required class="w-full px-3 py-2 bg-[#1a1c1f] border border-outline-variant rounded-lg text-sm focus:border-primary" placeholder="email@example.com" />
                    <button type="submit" class="w-full py-2 bg-primary/20 hover:bg-primary/30 text-primary rounded-lg text-sm">{t['subscribe_btn']}</button>
                </form>
            </div>
        </div>
    </aside>
    
    <main class="md:ml-64 min-h-screen px-4 md:px-10 py-6 max-w-5xl mx-auto md:pt-8">
        <header class="mb-8 border-b border-outline-variant pb-4">
            <div class="flex items-baseline gap-3">
                <h2 id="contentDate" class="text-3xl font-bold">{t['loading']}</h2>
                <span id="contentWeekday" class="text-xl text-primary/80"></span>
            </div>
        </header>
        <section id="newsContainer" class="space-y-6"></section>
    </main>

    <script>
        let historyData = {{records: []}};
        let currentLang = '{lang}';
        
        async function loadData() {{
            try {{
                const res = await fetch('{json_path}');
                historyData = await res.json();
                renderDateList();
                if(historyData.records.length > 0) selectDate(historyData.records[0].date);
            }} catch (e) {{
                console.error('Failed to load data:', e);
            }}
        }}
        
        function renderDateList() {{
            document.getElementById('dateList').innerHTML = historyData.records.map((r, i) => `
                <div class="date-item flex items-center justify-between px-5 py-2 cursor-pointer hover:bg-surface-container-high ${{i===0?'date-item-active':''}}" data-date="${{r.date}}" onclick="selectDate('${{r.date}}')">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-base opacity-50">calendar_today</span>
                        <span class="text-sm">${{r.date_display || r.date}}</span>
                    </div>
                    <span class="text-xs font-mono text-on-surface-variant/70">${{r.news_count}}</span>
                </div>`).join('');
        }}
        
        function selectDate(date) {{
            document.querySelectorAll('.date-item').forEach(el => el.classList.toggle('date-item-active', el.dataset.date === date));
            const record = historyData.records.find(r => r.date === date);
            if(record) renderNews(record);
        }}
        
        function selectToday() {{
            if(historyData.records.length > 0) selectDate(historyData.records[0].date);
        }}
        
        function formatSummary(text) {{
            if(!text) return "";
            let html = text.replace(/\\n/g, '<br>');
            // 正则匹配括号标题并加上样式
            html = html.replace(/([【\\[].*?[】\\]])/g, '<br><div class="section-title">$1</div>');
            html = html.replace(/(<br>\\s*){{3,}}/g, '<br><br>');
            if(html.startsWith('<br>')) html = html.substring(4);
            return html;
        }}
        
        function renderNews(record) {{
            const isZh = currentLang === 'zh';
            document.getElementById('contentDate').textContent = record.date_display || record.date;
            document.getElementById('contentWeekday').textContent = record.weekday || '';
            
            document.getElementById('newsContainer').innerHTML = record.news.map((item, index) => `
                <article class="news-card relative bg-[#1a1c1f] border border-outline-variant rounded-xl p-6 glow-hover group">
                    <div class="news-card-bg"><span class="font-bold font-mono">${{String(index + 1).padStart(2, '0')}}</span></div>
                    <div class="relative z-10">
                        <div class="flex gap-3 mb-3 text-xs text-on-surface-variant/60">
                            <span class="font-mono text-primary/80">📰 ${{item.site_name||''}}</span>
                            <span>📅 ${{item.publish_date||record.date}}</span>
                        </div>
                        <h3 class="text-xl font-semibold text-on-surface mb-3 group-hover:text-primary transition-colors">${{isZh ? item.title : (item.title_en||item.title)}}</h3>
                        <div class="text-sm text-on-surface-variant/80 leading-relaxed mb-4 max-w-3xl">${{formatSummary(isZh ? item.summary : (item.summary_en||item.summary))}}</div>
                        <a href="${{item.url}}" target="_blank" class="text-primary hover:underline text-sm font-medium">🔗 ${{isZh?'阅读原文':'Read Original'}}</a>
                    </div>
                </article>`).join('');
        }}
        
        document.addEventListener('DOMContentLoaded', loadData);
    </script>
</body>
</html>"""
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ {'中文' if is_zh else '英文'}页面已生成: {output_path}")


# ==================== 主程序 ====================
def main():
    print("=" * 50)
    print("🚗 智能座舱日报 - 自动抓取系统启动")
    print("=" * 50)
    
    # 1. 生成搜索关键词
    print("\n📌 步骤1: 生成搜索关键词...")
    keywords = generate_search_keywords()
    
    # 2. 搜索新闻
    print("\n📌 步骤2: 搜索新闻...")
    news = search_news(keywords, max_results=40)
    
    # 3. 加载历史数据
    history_data = load_history_data()

    if news:
        # 4. AI 筛选和格式化
        print("\n📌 步骤3: AI 深度分析与筛选...")
        items = filter_and_format(news)
        
        if items:
            # 5. 保存历史记录
            history_data = add_today_record(history_data, items)
            save_history_data(history_data)
            
            # 6. 生成网页
            print("\n📌 步骤4: 生成网页...")
            generate_html("docs/index.html", lang='zh')
            generate_html("docs/en/index.html", lang='en')
            
            # 7. 发送邮件
            print("\n📌 步骤5: 发送邮件...")
            today_str = datetime.now().strftime("%Y年%m月%d日")
            send_daily_email(items, today_str)
            send_private_email(items, today_str)
            
            print("\n" + "=" * 50)
            print("✅ 任务圆满完成！")
            print("=" * 50)
        else:
            print("❌ AI 过滤后无结果。")
    else:
        print("❌ 未搜索到新闻。")


if __name__ == "__main__":
    main()
