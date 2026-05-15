"""
汽车智能座舱新闻摘要 - GitHub Actions 版本
支持 30 天历史归档 + 左侧边栏布局 + 动态交互
"""
import os
import json
import urllib.request
import urllib.error
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
    # 按日期排序（最新在前）
    history_data["records"].sort(
        key=lambda x: x.get("date", ""), 
        reverse=True
    )
    
    # 只保留最近 MAX_DAYS 天
    if len(history_data["records"]) > MAX_DAYS:
        removed = len(history_data["records"]) - MAX_DAYS
        history_data["records"] = history_data["records"][:MAX_DAYS]
        print(f"    已清理 {removed} 条超过 {MAX_DAYS} 天的旧记录")
    
    # 确保目录存在
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)
    print(f"    历史数据已保存: {len(history_data['records'])} 条记录")


def add_today_record(history_data, news_items):
    """添加今天的新闻记录"""
    today = datetime.now().strftime("%Y-%m-%d")
    today_display = datetime.now().strftime("%m月%d日")
    
    # 检查今天是否已有记录（避免重复）
    existing_dates = [r.get("date") for r in history_data["records"]]
    if today in existing_dates:
        # 更新今天的记录
        for record in history_data["records"]:
            if record.get("date") == today:
                record["news"] = news_items
                record["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"    已更新今天的记录: {today}")
                return history_data
    else:
        # 添加新记录
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


# ==================== 邮件发送（Buttondown API）====================
def send_daily_email(news_items, date_str):
    """通过 Buttondown API 发送邮件给所有订阅者"""
    
    if not BUTTONDOWN_API_KEY:
        print("    ⚠️ 未配置 BUTTONDOWN_API_KEY，跳过发送")
        return False
    
    # 构建邮件主题和内容
    subject = f"🚗 智能座舱日报 | {date_str}"
    
    # HTML 邮件正文
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', sans-serif; background: #f5f5f5; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; }}
            .header h1 {{ color: #fff; margin: 0; font-size: 24px; }}
            .header p {{ color: rgba(255,255,255,0.8); margin: 10px 0 0; font-size: 14px; }}
            .content {{ padding: 30px; }}
            .news-item {{ padding: 24px 0; border-bottom: 1px solid #eee; }}
            .news-item:last-child {{ border-bottom: none; }}
            .news-number {{ display: inline-block; width: 28px; height: 28px; background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; border-radius: 50%; text-align: center; line-height: 28px; font-size: 14px; font-weight: bold; margin-right: 10px; }}
            .news-title {{ font-size: 16px; font-weight: 600; color: #333; margin: 10px 0; }}
            .news-meta {{ font-size: 12px; color: #888; margin-bottom: 12px; }}
            .news-summary {{ font-size: 14px; color: #666; line-height: 1.8; white-space: pre-line; }}
            .news-link {{ display: inline-block; margin-top: 12px; padding: 6px 12px; background: #f0f0ff; color: #667eea; text-decoration: none; border-radius: 4px; font-size: 12px; }}
            .section-title {{ color: #667eea; font-weight: 600; margin: 12px 0 4px; }}
            .footer {{ background: #f9f9f9; padding: 20px; text-align: center; font-size: 12px; color: #999; }}
            .footer a {{ color: #667eea; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚗 智能座舱日报</h1>
                <p>{date_str} | 今日 {len(news_items)} 条精选资讯</p>
            </div>
            <div class="content">
    """
    
    for i, item in enumerate(news_items, 1):
        title = item.get("title", "")
        summary = item.get("summary", "")  # 显示完整内容
        url = item.get("url", "")
        site = item.get("site_name", "")
        pub_date = item.get("publish_date", "")
        
        # 格式化 summary，确保换行正确显示
        formatted_summary = summary.replace("【事件概述】", "<div class='section-title'>【事件概述】</div>")
        formatted_summary = formatted_summary.replace("【体验价值】", "<div class='section-title'>【体验价值】</div>")
        formatted_summary = formatted_summary.replace("【商业影响】", "<div class='section-title'>【商业影响】</div>")
        
        html_content += f"""
                <div class="news-item">
                    <span class="news-number">{i}</span>
                    <div class="news-title">{title}</div>
                    <div class="news-meta">📰 {site}{" | 📅 " + pub_date if pub_date else ""}</div>
                    <div class="news-summary">{formatted_summary}</div>
                    <a href="{url}" class="news-link">🔗 阅读原文</a>
                </div>
        """
    
    html_content += f"""
            </div>
            <div class="footer">
                <p>🌐 在线阅读: <a href="https://bridgetyangjie-1.github.io/cockpit-news/">bridgetyangjie-1.github.io/cockpit-news</a></p>
                <p style="margin-top: 10px;">本邮件由系统自动发送</p>
                <p style="margin-top: 5px;">© 2026 Bridget Yang</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # 调用 Buttondown API 发送邮件
    try:
        import urllib.parse
        
        # Buttondown API 要求：设置 publish_date 为当前时间，邮件才会立即发送
        from datetime import datetime, timezone
        # Buttondown API 要求时区信息，使用 UTC 时间
        publish_date = datetime.now(timezone.utc).isoformat()
        
        url = "https://api.buttondown.email/v1/emails"
        data = {
            "subject": subject,
            "body": html_content,
            "publish_date": publish_date  # 设置发布时间，邮件会立即发送
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
            result = json.loads(response.read().decode('utf-8'))
            print(f"    ✅ 邮件已通过 Buttondown 发送给所有订阅者")
            return True
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"    ❌ Buttondown API 错误: {e.code}")
        print(f"    详情: {error_body[:200]}")
        return False
    except Exception as e:
        print(f"    ❌ 邮件发送失败: {e}")
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
    
    # 构建邮件内容
    news_count = len(news_items)
    news_html = ""
    for i, item in enumerate(news_items, 1):
        # 格式化 summary，确保换行正确显示
        summary = item.get('summary', '')
        formatted_summary = summary.replace("【事件概述】", "<br><strong style='color:#00d4ff'>【事件概述】</strong><br>")
        formatted_summary = formatted_summary.replace("【体验价值】", "<br><strong style='color:#00d4ff'>【体验价值】</strong><br>")
        formatted_summary = formatted_summary.replace("【商业影响】", "<br><strong style='color:#00d4ff'>【商业影响】</strong><br>")
        
        news_html += f"""
        <div style="margin-bottom: 24px; padding: 16px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #00d4ff;">
            <h3 style="margin: 0 0 8px 0; color: #1a1a2e; font-size: 16px;">
                {i}. {item.get('title', '未知标题')}
            </h3>
            <p style="margin: 4px 0; color: #666; font-size: 13px;">
                📅 {item.get('publish_date', '')} | 📰 {item.get('site_name', '未知来源')}
            </p>
            <p style="margin: 12px 0 0 0; color: #333; font-size: 14px; line-height: 1.6;">
                {formatted_summary}
            </p>
            <a href="{item.get('url', '#')}" style="color: #00d4ff; font-size: 13px;">阅读原文 →</a>
        </div>
        """
    
    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
        </style>
    </head>
    <body>
        <div style="text-align: center; margin-bottom: 32px; padding: 24px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 12px;">
            <h1 style="color: #00d4ff; margin: 0; font-size: 24px;">🚗 智能座舱日报</h1>
            <p style="color: #fff; margin: 8px 0 0 0;">{date_str} | 今日 {news_count} 条精选资讯</p>
        </div>
        {news_html}
        <div style="text-align: center; margin-top: 32px; padding: 16px; color: #888; font-size: 12px; border-top: 1px solid #eee;">
            <p>本邮件由系统自动发送</p>
            <p>© 2026 Bridget Yang</p>
        </div>
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
                print(f"    ✅ 私人邮件已发送至: {recipient}")
            
            return True
            
    except Exception as e:
        print(f"    ❌ SMTP 发送失败: {e}")
        return False


# ==================== 搜索 ====================
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
- 关键词要能搜出科技媒体的深度解析、产品经理的复盘或硬核的用户评测。
- **【地理限制】必须聚焦中国大陆市场，关注大陆品牌（蔚小理、华米、比亚迪等）。不要包含台湾、香港、澳门相关字眼。**
- 必须返回严格的JSON格式，不要加任何其他文字：
{{"keywords": ["关键词1", "关键词2", ..., "关键词15"]}}"""

    user_prompt = f"请为'{topic}'生成多样化的搜索关键词"
    response = call_deepseek(system_prompt, user_prompt)
    if not response:
        print("    关键词生成失败，使用默认关键词")
        return ["车机 OTA 升级 体验", "智能座舱 交互设计", "车载语音助手 评测", "手车互联 生态"]
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
        return ["车机 OTA 升级 体验", "智能座舱 交互设计", "车载语音助手 评测", "手车互联 生态"]


def search_news(keywords, max_results=40):
    """用多个关键词搜索 DuckDuckGo，不做死板的词汇拦截，交给后续的大模型去语义判断"""
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

                    if not title or not url:
                        continue
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    domain = urlparse(url).netloc.replace("www.", "")
                    site_name = domain.split(".")[0].title() if domain else ""

                    # 仅保留最基础的去广告过滤
                    ad_keywords = ["ad", "sponsored", "推广", "广告", "track"]
                    if any(k in url.lower() for k in ad_keywords):
                        continue
                    
                    # 过滤敏感地区内容（严格遵守一个中国原则）
                    sensitive_keywords = ["台湾", "台灣", "taiwan", "taiwanese", "香港", "hong kong", "hongkong", "澳门", "macau"]
                    title_body = (title + body).lower()
                    if any(k in title_body for k in sensitive_keywords):
                        continue

                    all_results.append({
                        "title": title,
                        "url": url,
                        "snippet": body[:400],
                        "site_name": site_name,
                        "publish_date": publish_date
                    })

        print(f"    初筛获取共 {len(all_results)} 条新闻内容，准备提交给 AI 深度甄别")
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
        "max_tokens": 8192  # 增加到 8192，确保生成完整内容
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
        with urllib.request.urlopen(req, timeout=120) as response:  # 增加超时到 120 秒
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
        f"新闻{i+1}:\n标题: {item['title']}\n来源: {item['site_name']}\n发布日期: {item.get('publish_date', '未知')}\n摘要: {item['snippet']}\n链接: {item['url']}"
        for i, item in enumerate(news_list)
    ])

    system_prompt = f"""你是拥有十几年丰富经验的资深汽车用户研究与体验分析专家。今天是{today}。

我将提供一批通过搜索引擎抓取的行业新闻。请以极为严苛的标准，筛选出对国内汽车软件生态和交互设计最具研究价值的 5 条新闻。

【核心聚焦方向 - 软件与体验】：
绝对聚焦于中国"造车新势力"与科技大厂在智能座舱内的**纯软件功能创新、数字生态服务（如座舱内生活服务接入）、OTA 更新细节、以及底层交互逻辑 (UI/UX) 的演进**。

【过滤死线 - 绝对不要】：
1. 纯硬件发布（芯片、屏幕材质）、销量战报、无技术细节的软文。
2. 偏离座舱内数字体验的边缘新闻。
3. **【重要】任何涉及台湾、香港、澳门地区的内容，严格遵守一个中国原则，只聚焦中国大陆市场。**

请为选出的新闻撰写精炼总结，并翻译成英文。

【字数要求】：
- 每篇总结严格控制在 **280-320字**（中文）
- 英文版本相应精简

【结构要求】：
1. **事件概述（120字）**：提炼核心软件事件，如某品牌推送了包含特定功能的OTA，或发布了新的交互框架，详细说明功能内容。
2. **体验价值（80字）**：从用户研究视角剖析该功能的体验价值，分析其解决了什么用户痛点。
3. **商业影响（80字）**：研判其对提升用户粘性、软件订阅率或行业竞争壁垒的影响。

【格式要求】：
- 每个模块之间必须**换行**
- 使用"【事件概述】"、"【体验价值】"、"【商业影响】"作为标题
- 每个模块内容独立成段，不要挤在一起

必须返回严格的JSON格式，不要加任何其他文字：
{{
  "news": [
    {{
      "title": "原标题（中文）",
      "title_en": "English Title",
      "url": "原链接",
      "site_name": "来源媒体",
      "publish_date": "发布日期（如2025-01-14，若未知则填写"近日"）",
      "summary": "280-320字中文深度洞察，每个模块必须换行，格式如下：\n【事件概述】xxx\n\n【体验价值】xxx\n\n【商业影响】xxx",
      "summary_en": "对应格式的英文专业分析，同样换行：\n【Event Overview】xxx\n\n【Experience Value】xxx\n\n【Business Impact】xxx"
    }}
  ]
}}"""

    user_prompt = f"请分析以下{len(news_list)}条新闻，返回中英双语JSON格式：\n\n{news_data}"

    response = call_deepseek(system_prompt, user_prompt)
    if not response:
        return []

    try:
        content = response.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())
        items = data.get("news", data if isinstance(data, list) else [])
        
        # 验证每条新闻内容完整性
        if isinstance(items, list):
            for i, item in enumerate(items):
                if isinstance(item, dict):
                    summary = item.get("summary", "")
                    # 检查是否包含完整的三个部分
                    required_parts = ["【事件概述】", "【体验价值】", "【商业影响】"]
                    missing_parts = [p for p in required_parts if p not in summary]
                    if missing_parts:
                        print(f"    ⚠️ 新闻{i+1} 内容不完整，缺少: {', '.join(missing_parts)}")
        
        return items if isinstance(items, list) else []
    except Exception as e:
        print(f"    ❌ 解析 DeepSeek 响应失败: {e}")
        return []


# ==================== HTML 生成（Tailwind CSS + Material Design） ====================
def generate_html(output_path, lang='zh'):
    """生成使用 Tailwind CSS 框架的专业仪表盘页面"""
    
    is_zh = lang == 'zh'
    html_lang = "zh-CN" if is_zh else "en"
    
    # 页面文本
    texts = {
        'zh': {
            'title': '智能座舱日报',
            'subtitle': 'Daily Intelligence',
            'description': '聚焦中国新能源车软件生态与座舱交互体验，每日自动抓取OTA动态、功能创新与用户研究洞察。',
            'author': 'Bridget Yang',
            'author_email': 'mailto:bridgetyangjie@gmail.com',
            'nav_today': '今日',
            'nav_archives': '历史归档',
            'sidebar_archive': '历史归档',
            'loading': '加载中...',
            'no_news': '该日期暂无新闻数据',
            'read_original': '阅读原文',
            'footer': '数据来源：DuckDuckGo · DeepSeek AI',
            'switch_lang': 'English',
            'briefs': '条精选情报',
            'by_author': '作者',
            'published': '发布于',
            'disclaimer': '本看板内容基于公开信息自动抓取，由AI分析生成，仅供参考研究使用，不代表作者立场。',
            'copyright': '© 2026 Bridget Yang',
            'subscribe': '订阅日报',
            'email_placeholder': '输入邮箱地址',
            'subscribe_btn': '立即订阅'
        },
        'en': {
            'title': 'Smart Cockpit',
            'subtitle': 'Daily Intelligence',
            'description': 'Focusing on China\'s NEV software ecosystem and cockpit interaction experience. Daily auto-capture of OTA updates, feature innovations, and UX research insights.',
            'author': 'Bridget Yang',
            'author_email': 'mailto:bridgetyangjie@gmail.com',
            'nav_today': 'Today',
            'nav_archives': 'Archives',
            'sidebar_archive': 'ARCHIVE',
            'loading': 'Loading...',
            'no_news': 'No news available for this date',
            'read_original': 'Read Original',
            'footer': 'Source: DuckDuckGo · DeepSeek AI',
            'switch_lang': '中文',
            'briefs': 'Intelligence Briefs',
            'by_author': 'By',
            'published': 'Published',
            'disclaimer': 'Content is auto-curated from public sources and AI-analyzed for research purposes only. Does not represent the author\'s views.',
            'copyright': '© 2026 Bridget Yang',
            'subscribe': 'Subscribe',
            'email_placeholder': 'Enter your email',
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
                        "surface-container-low": "#1a1c1f",
                        "surface-container-high": "#282a2d",
                        "surface-container-highest": "#333538",
                        primary: "#00F2FF",
                        "on-surface": "#e2e2e6",
                        "on-surface-variant": "#b9cacb",
                        "outline-variant": "#3a494b",
                        outline: "#849495"
                    }},
                    fontFamily: {{
                        sans: ["Inter", "sans-serif"],
                        mono: ["JetBrains Mono", "monospace"]
                    }}
                }}
            }}
        }}
    </script>
    <style>
        .material-symbols-outlined {{ font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }}
        body {{ background-color: #0D0F12; }}
        .sidebar-blur {{ backdrop-filter: blur(20px); background-color: rgba(17, 19, 23, 0.8); }}
        ::-webkit-scrollbar {{ width: 4px; }}
        ::-webkit-scrollbar-track {{ background: #0D0F12; }}
        ::-webkit-scrollbar-thumb {{ background: #333538; border-radius: 10px; }}
        .news-card-bg {{ position: absolute; top: 8px; left: 16px; pointer-events: none; }}
        .news-card-bg span {{ font-size: 120px; color: #00F2FF; opacity: 0.05; line-height: 1; }}
        .news-card:hover .news-card-bg span {{ opacity: 0.1; }}
        .glow-hover {{ transition: all 0.3s ease; }}
        .glow-hover:hover {{ box-shadow: 0 12px 40px -12px rgba(0, 242, 255, 0.25); border-color: rgba(0, 242, 255, 0.5); }}
        .date-item-active {{ border-left: 4px solid #00F2FF; background: rgba(0, 242, 255, 0.1); color: #00F2FF; font-weight: 600; }}
    </style>
</head>
<body class="bg-background text-on-surface font-sans overflow-x-hidden">
    <!-- 移动端顶部栏 -->
    <header class="md:hidden fixed top-0 left-0 right-0 h-16 bg-surface-container/95 backdrop-blur-lg z-50 flex items-center justify-between px-4 border-b border-outline-variant">
        <h1 class="text-lg font-semibold">🚗 {t['title']}</h1>
        <button onclick="toggleSidebar()" class="p-2 hover:bg-surface-container-high rounded-lg">
            <span class="material-symbols-outlined">menu</span>
        </button>
    </header>
    
    <!-- 遮罩层 -->
    <div id="overlay" class="fixed inset-0 bg-black/50 z-40 hidden" onclick="toggleSidebar()"></div>
    
    <!-- 左侧边栏 -->
    <aside id="sidebar" class="fixed left-0 top-0 h-screen w-64 bg-surface-container border-r border-outline-variant sidebar-blur flex-col z-50 hidden md:flex">
        <!-- Logo & 标题 -->
        <div class="p-6 border-b border-outline-variant">
            <h1 class="text-xl font-bold text-on-surface tracking-tight">🚗 {t['title']}</h1>
            <p class="text-sm text-on-surface-variant mt-1">{t['subtitle']}</p>
            <p class="text-xs text-on-surface-variant/70 mt-3 leading-relaxed">{t['description']}</p>
            <p class="text-xs text-on-surface-variant/50 mt-2">{t['by_author']}: <a href="{t['author_email']}" class="text-primary hover:underline">{t['author']}</a></p>
        </div>
        
        <!-- 导航菜单 -->
        <nav class="flex-1 overflow-y-auto mt-4">
            <div id="navToday" onclick="selectToday()" class="flex items-center gap-3 px-5 py-3 cursor-pointer transition-colors hover:bg-surface-container-high">
                <span class="material-symbols-outlined text-xl">today</span>
                <span>{t['nav_today']}</span>
            </div>
            <div class="px-6 py-2 mt-4">
                <span class="text-[10px] uppercase tracking-widest text-on-surface-variant/50">{t['sidebar_archive']}</span>
            </div>
            <!-- 日期列表 -->
            <div id="dateList" class="space-y-1"></div>
        </nav>
        
        <!-- 底部操作 -->
        <div class="p-4 border-t border-outline-variant space-y-3">
            <a href="{lang_switch_url}" class="flex items-center gap-2 text-on-surface-variant hover:text-primary transition-colors cursor-pointer">
                <span class="material-symbols-outlined text-lg">language</span>
                <span class="text-sm">{t['switch_lang']}</span>
            </a>
            <!-- 订阅表单 -->
            <div class="pt-3 border-t border-outline-variant/50">
                <p class="text-xs text-on-surface-variant mb-2">📬 {t['subscribe']}</p>
                <form action="https://buttondown.com/api/emails/embed-subscribe/Cockpit_News_by_BridgetYang" method="post" class="space-y-2">
                    <input type="email" name="email" placeholder="{t['email_placeholder']}" required
                           class="w-full px-3 py-2 bg-surface-container-high border border-outline-variant rounded-lg text-sm text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:border-primary" />
                    <button type="submit" class="w-full py-2 bg-primary/20 hover:bg-primary/30 text-primary rounded-lg text-sm font-medium transition-colors">
                        {t['subscribe_btn']}
                    </button>
                </form>
            </div>
            <!-- 作者声明 -->
            <div class="pt-3 mt-3 border-t border-outline-variant/50">
                <p class="text-[10px] text-on-surface-variant/60 leading-relaxed">{t['disclaimer']}</p>
                <p class="text-[10px] text-on-surface-variant/40 mt-2">{t['copyright']}</p>
            </div>
        </div>
    </aside>
    
    <!-- 主内容区 -->
    <main class="md:ml-64 min-h-screen px-4 md:px-10 py-6 md:py-8 max-w-5xl mx-auto pt-20 md:pt-8">
        <!-- 顶部标题栏 -->
        <header class="flex flex-col md:flex-row md:justify-between md:items-end mb-8 border-b border-outline-variant pb-4">
            <div>
                <div class="flex items-baseline gap-3">
                    <h2 id="contentDate" class="text-3xl md:text-4xl font-bold tracking-tight">{t['loading']}</h2>
                    <span id="contentWeekday" class="text-xl text-primary/80 font-medium"></span>
                </div>
                <div class="flex items-center gap-2 text-on-surface-variant mt-2">
                    <span class="material-symbols-outlined text-sm">auto_awesome</span>
                    <span id="briefCount" class="text-sm font-mono">{t['loading']}</span>
                </div>
            </div>
        </header>
        
        <!-- 新闻列表 -->
        <section id="newsContainer" class="space-y-6">
            <div class="flex items-center justify-center py-20">
                <div class="w-10 h-10 border-2 border-primary border-t-transparent rounded-full animate-spin"></div>
            </div>
        </section>
        
        <!-- 页脚 -->
        <footer class="mt-12 pt-6 border-t border-outline-variant text-center text-sm text-on-surface-variant/50">
            {t['footer']}
        </footer>
    </main>

    <script>
        let historyData = {{records: []}};
        let currentLang = '{lang}';
        
        async function loadData() {{
            try {{
                const res = await fetch('{json_path}');
                if (!res.ok) throw new Error('Failed');
                historyData = await res.json();
                renderDateList();
                if (historyData.records.length > 0) {{
                    selectDate(historyData.records[0].date);
                }} else {{
                    showEmpty();
                }}
            }} catch (e) {{
                showError();
            }}
        }}
        
        function renderDateList() {{
            const container = document.getElementById('dateList');
            if (!historyData.records || historyData.records.length === 0) {{
                container.innerHTML = '<p class="px-5 py-2 text-on-surface-variant/50 text-sm">暂无数据</p>';
                return;
            }}
            container.innerHTML = historyData.records.map((r, i) => `
                <div class="date-item flex items-center justify-between px-5 py-2 cursor-pointer transition-colors hover:bg-surface-container-high ${{i === 0 ? 'date-item-active' : ''}}" 
                     data-date="${{r.date}}" onclick="selectDate('${{r.date}}')">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-base opacity-50">calendar_today</span>
                        <span class="text-sm">${{r.date_display || r.date}}</span>
                    </div>
                    <span class="text-xs font-mono text-on-surface-variant/70">${{r.news_count || (r.news ? r.news.length : 0)}}</span>
                </div>
            `).join('');
        }}
        
        function selectDate(date) {{
            // 更新侧边栏高亮
            document.querySelectorAll('.date-item').forEach(el => {{
                el.classList.toggle('date-item-active', el.dataset.date === date);
            }});
            
            const record = historyData.records.find(r => r.date === date);
            if (record) {{
                renderNews(record);
            }} else {{
                showEmpty();
            }}
            
            // 移动端关闭侧边栏
            if (window.innerWidth < 768) closeSidebar();
        }}
        
        function selectToday() {{
            if (historyData.records.length > 0) {{
                selectDate(historyData.records[0].date);
            }}
        }}
        
        function renderNews(record) {{
            const isZh = currentLang === 'zh';
            
            // 更新标题
            document.getElementById('contentDate').textContent = record.date_display || record.date;
            document.getElementById('contentWeekday').textContent = record.weekday || '';
            document.getElementById('briefCount').textContent = `${{record.news_count || (record.news ? record.news.length : 0)}} ${{isZh ? '条精选情报' : 'Intelligence Briefs'}}`;
            
            const container = document.getElementById('newsContainer');
            
            if (!record.news || record.news.length === 0) {{
                container.innerHTML = `
                    <div class="text-center py-20 text-on-surface-variant/50">
                        <span class="material-symbols-outlined text-5xl mb-4 opacity-30">article</span>
                        <p>${{isZh ? '该日期暂无新闻数据' : 'No news available for this date'}}</p>
                    </div>
                `;
                return;
            }}
            
            container.innerHTML = record.news.map((item, index) => `
                <article class="news-card relative bg-surface-container-low border border-outline-variant rounded-xl p-6 md:p-8 glow-hover cursor-pointer group">
                    <div class="news-card-bg">
                        <span class="font-bold font-mono">${{String(index + 1).padStart(2, '0')}}</span>
                    </div>
                    <div class="relative z-10">
                        <div class="flex flex-wrap items-center gap-3 mb-3">
                            <div class="flex items-center gap-2">
                                <span class="material-symbols-outlined text-primary text-lg">article</span>
                                <span class="text-xs text-on-surface-variant font-mono">${{escapeHtml(item.site_name || '')}}</span>
                            </div>
                            <div class="flex items-center gap-1 text-xs text-on-surface-variant/60">
                                <span class="material-symbols-outlined text-sm">schedule</span>
                                <span>${{escapeHtml(item.publish_date || record.date || '')}}</span>
                            </div>
                        </div>
                        <h3 class="text-lg md:text-xl font-semibold text-on-surface mb-3 group-hover:text-primary transition-colors leading-snug">
                            ${{escapeHtml(isZh ? item.title : (item.title_en || item.title))}}
                        </h3>
                        <p class="text-sm md:text-base text-on-surface-variant/80 leading-relaxed mb-4 max-w-3xl">
                            ${{escapeHtml(isZh ? item.summary : (item.summary_en || item.summary))}}
                        </p>
                        <a href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener" 
                           class="inline-flex items-center gap-1 text-sm text-primary hover:underline font-medium">
                            <span class="material-symbols-outlined text-base">open_in_new</span>
                            ${{isZh ? '阅读原文' : 'Read Original'}}
                        </a>
                    </div>
                </article>
            `).join('');
        }}
        
        function showEmpty() {{
            const isZh = currentLang === 'zh';
            document.getElementById('contentDate').textContent = isZh ? '暂无数据' : 'No Data';
            document.getElementById('contentWeekday').textContent = '';
            document.getElementById('briefCount').textContent = isZh ? '暂无情报' : 'No Intelligence';
            document.getElementById('newsContainer').innerHTML = `
                <div class="text-center py-20 text-on-surface-variant/50">
                    <span class="material-symbols-outlined text-5xl mb-4 opacity-30">article</span>
                    <p>${{isZh ? '暂无新闻数据' : 'No news available'}}</p>
                </div>
            `;
        }}
        
        function showError() {{
            const isZh = currentLang === 'zh';
            document.getElementById('contentDate').textContent = isZh ? '加载失败' : 'Error';
            document.getElementById('newsContainer').innerHTML = `
                <div class="text-center py-20 text-on-surface-variant/50">
                    <span class="material-symbols-outlined text-5xl mb-4 opacity-30">error</span>
                    <p>${{isZh ? '无法加载数据' : 'Failed to load data'}}</p>
                </div>
            `;
        }}
        
        function escapeHtml(str) {{
            if (!str) return '';
            return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }}
        
        function toggleSidebar() {{
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('overlay');
            sidebar.classList.toggle('hidden');
            sidebar.classList.toggle('flex');
            overlay.classList.toggle('hidden');
        }}
        
        function closeSidebar() {{
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('overlay');
            sidebar.classList.add('hidden');
            sidebar.classList.remove('flex');
            overlay.classList.add('hidden');
        }}
        
        document.addEventListener('DOMContentLoaded', loadData);
    </script>
</body>
</html>"""

    # 确保目录存在
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ {'中文' if is_zh else '英文'}页面已生成: {output_path}")


# ==================== 主函数 ====================
def main():
    print("🚀 开始获取智能座舱新闻...")

    # 1. 生成多样化搜索关键词
    print("🧠 生成多样化搜索关键词...")
    keywords = generate_search_keywords("汽车智能座舱")
    print(f"    关键词列表: {keywords}")

    # 2. 多关键词搜索
    print("🔍 多关键词搜索中...")
    news = search_news(keywords, max_results=40)
    print(f"    共搜索到 {len(news)} 条新闻")

    # 3. 加载历史数据
    print("📂 加载历史数据...")
    history_data = load_history_data()
    print(f"    已有 {len(history_data['records'])} 条历史记录")

    # 4. DeepSeek 分析（如果有新搜索结果）
    if news:
        print("🤖 DeepSeek 分析中...")
        items = filter_and_format(news)

        if items:
            print(f"    生成 {len(items)} 条深度分析")
        else:
            print("    DeepSeek 未返回数据，使用原始结果")
            items = [
                {"title": n["title"], "title_en": n["title"], "url": n["url"], 
                 "site_name": n["site_name"], "summary": n["snippet"], "summary_en": n["snippet"]}
                for n in news[:5]
            ]
        
        # 5. 添加今天的记录
        print("📝 更新历史数据...")
        history_data = add_today_record(history_data, items)
    else:
        print("❌ 搜索失败，跳过今日数据更新")

    # 6. 保存历史数据（自动清理超过30天的）
    save_history_data(history_data)

    # 7. 生成 HTML 页面（中英文）
    print("🌐 生成页面...")
    generate_html("docs/index.html", lang='zh')
    generate_html("docs/en/index.html", lang='en')

    # 8. 发送邮件（双通道）
    if items:
        print("📧 发送日报邮件...")
        today_str = datetime.now().strftime("%Y年%m月%d日")
        
        # 方式1: Buttondown 发给订阅者
        print("  📬 Buttondown 发送给订阅者...")
        send_daily_email(items, today_str)
        
        # 方式2: SMTP 发给私人邮箱
        print("  📨 SMTP 发送给私人邮箱...")
        send_private_email(items, today_str)

    print("✅ 完成！30天历史归档已更新")
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
