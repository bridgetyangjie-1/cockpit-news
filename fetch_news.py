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


# ==================== 搜索 ====================
def generate_search_keywords(topic="汽车智能座舱"):
    """DeepSeek 生成精准的软件生态与数字体验搜索关键词"""
    system_prompt = f"""你是深耕中国新能源汽车市场的资深用户研究与体验分析师。请围绕"{topic}"，生成15个精准且多样化的中文搜索关键词。

为了精准捕捉行业内的软件创新与数字体验动态，关键词必须覆盖以下维度：
1. 核心软件功能与生态：如 "车机 生态 接入", "智能座舱 第三方 App", "手车互联 无缝流转", "座舱 场景引擎"
2. OTA与用户活跃度：如 "新势力 OTA 升级 体验", "车机系统 RSU 推送", "座舱 软件订阅 服务"
3. 关键交互触点 (UX/UI)：如 "座舱 零层级 交互", "车载语音 多指令", "多模态交互 评测", "车内屏幕 交互逻辑"
4. 头部玩家的软件动作：如 "蔚来 Banyan 智能应用", "小鹏 天玑 AI 代驾", "小米 澎湃OS 座舱互联", "理想 任务大师"

要求：
- 绝对不要外观、底盘、硬件参数相关的词汇。只聚焦"软件"、"交互"和"服务"。
- 关键词要能搜出科技媒体的深度解析、产品经理的复盘或硬核的用户评测。
- 关键词中尽量不要包含"汽车智能座舱"这几个字，以免搜到千篇一律的公关稿。
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

    system_prompt = f"""你是拥有十几年丰富经验的资深汽车用户研究与体验分析专家。今天是{today}。

我将提供一批通过搜索引擎抓取的行业新闻。请以极为严苛的标准，筛选出对国内汽车软件生态和交互设计最具研究价值的 5 条新闻。

【核心聚焦方向 - 软件与体验】：
绝对聚焦于中国"造车新势力"与科技大厂在智能座舱内的**纯软件功能创新、数字生态服务（如座舱内生活服务接入）、OTA 更新细节、以及底层交互逻辑 (UI/UX) 的演进**。

【过滤死线 - 绝对不要】：
1. 纯硬件发布（芯片、屏幕材质）、销量战报、无技术细节的软文。
2. 偏离座舱内数字体验的边缘新闻。

请为选出的新闻撰写深度总结，并翻译成英文。
总结必须是结构化的，包含极具洞察力的三句话：
第一句：提炼核心软件事件（如某品牌推送了包含特定功能的 OTA，或发布了新的交互框架）。
第二句：从用户研究视角剖析该功能的体验价值（分析其解决了什么用户痛点，或创造了何种使用场景）。
第三句：研判其对提升用户粘性、软件订阅率或行业竞争壁垒的商业影响。

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


# ==================== HTML 生成（侧边栏+动态交互） ====================
def generate_html(output_path, lang='zh'):
    """生成带有侧边栏和动态交互的 HTML 页面"""
    
    is_zh = lang == 'zh'
    html_lang = "zh-CN" if is_zh else "en"
    
    # 页面文本
    texts = {
        'zh': {
            'title': '智能座舱日报',
            'subtitle': '30天历史归档',
            'sidebar_title': '📅 历史归档',
            'loading': '加载中...',
            'no_news': '该日期暂无新闻数据',
            'read_original': '🔗 阅读原文',
            'footer': '数据来源：DuckDuckGo 搜索 · 内容整理：DeepSeek AI',
            'switch_lang': '🌐 EN',
            'switch_label': '切换到英文版',
            'menu_btn': '☰ 菜单',
            'select_date': '选择日期'
        },
        'en': {
            'title': 'Smart Cockpit Daily',
            'subtitle': '30-Day Archive',
            'sidebar_title': '📅 Archive',
            'loading': 'Loading...',
            'no_news': 'No news available for this date',
            'read_original': '🔗 Read Original',
            'footer': 'Source: DuckDuckGo Search · Analysis: DeepSeek AI',
            'switch_lang': '🌐 中文',
            'switch_label': 'Switch to Chinese',
            'menu_btn': '☰ Menu',
            'select_date': 'Select Date'
        }
    }
    
    t = texts[lang]
    json_path = "history_data.json" if is_zh else "../history_data.json"
    lang_switch_url = "en/index.html" if is_zh else "../index.html"

    html = f"""<!DOCTYPE html>
<html lang="{html_lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚗 {t['title']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                      "PingFang SC", "Microsoft YaHei", sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            min-height: 100vh;
            display: flex;
        }}
        
        /* 主容器 */
        .app-container {{
            display: flex;
            width: 100%;
            min-height: 100vh;
        }}
        
        /* 移动端顶部栏 */
        .mobile-header {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 60px;
            background: rgba(15, 12, 41, 0.95);
            backdrop-filter: blur(10px);
            z-index: 1000;
            padding: 0 15px;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        
        .mobile-header h1 {{
            color: #fff;
            font-size: 18px;
        }}
        
        .menu-toggle {{
            background: rgba(255,255,255,0.1);
            border: none;
            color: #fff;
            padding: 8px 12px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
        }}
        
        /* 左侧边栏 */
        .sidebar {{
            width: 280px;
            min-width: 280px;
            background: rgba(255, 255, 255, 0.03);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            flex-direction: column;
            height: 100vh;
            position: sticky;
            top: 0;
        }}
        
        .sidebar-header {{
            padding: 25px 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .sidebar-header h1 {{
            color: #fff;
            font-size: 22px;
            margin-bottom: 5px;
        }}
        
        .sidebar-header .subtitle {{
            color: rgba(255, 255, 255, 0.6);
            font-size: 13px;
        }}
        
        .sidebar-title {{
            padding: 15px 20px;
            color: rgba(255, 255, 255, 0.5);
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .date-list {{
            flex: 1;
            overflow-y: auto;
            padding: 10px;
        }}
        
        .date-item {{
            display: flex;
            align-items: center;
            padding: 12px 15px;
            margin-bottom: 5px;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s;
            color: rgba(255, 255, 255, 0.7);
        }}
        
        .date-item:hover {{
            background: rgba(255, 255, 255, 0.08);
            color: #fff;
        }}
        
        .date-item.active {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: #fff;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }}
        
        .date-item .date-text {{
            flex: 1;
        }}
        
        .date-item .date-main {{
            font-size: 15px;
            font-weight: 500;
        }}
        
        .date-item .date-weekday {{
            font-size: 12px;
            opacity: 0.7;
            margin-top: 2px;
        }}
        
        .date-item .news-count {{
            background: rgba(255, 255, 255, 0.15);
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 600;
        }}
        
        .sidebar-footer {{
            padding: 15px 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .lang-switch {{
            display: block;
            text-align: center;
            padding: 10px;
            background: rgba(255, 255, 255, 0.1);
            color: #fff;
            text-decoration: none;
            border-radius: 8px;
            font-size: 14px;
            transition: background 0.2s;
        }}
        
        .lang-switch:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}
        
        /* 右侧主内容区 */
        .main-content {{
            flex: 1;
            padding: 30px;
            overflow-y: auto;
            height: 100vh;
        }}
        
        .content-header {{
            text-align: center;
            margin-bottom: 30px;
            color: #fff;
        }}
        
        .content-header h2 {{
            font-size: 26px;
            margin-bottom: 8px;
        }}
        
        .content-header .date-info {{
            font-size: 14px;
            opacity: 0.7;
        }}
        
        /* 新闻卡片容器 */
        .news-container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        
        .news-card {{
            background: #fff;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }}
        
        .news-card-body {{
            padding: 30px;
        }}
        
        .news-item {{
            display: flex;
            gap: 16px;
            padding: 20px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        
        .news-item:last-child {{
            border-bottom: none;
        }}
        
        .news-number {{
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 16px;
            flex-shrink: 0;
        }}
        
        .news-body {{
            flex: 1;
        }}
        
        .news-title {{
            font-size: 18px;
            font-weight: 600;
            color: #1a1a2e;
            margin-bottom: 6px;
            line-height: 1.4;
        }}
        
        .news-source {{
            font-size: 13px;
            color: #888;
            margin-bottom: 10px;
        }}
        
        .news-summary {{
            font-size: 14.5px;
            line-height: 1.8;
            color: #444;
            margin-bottom: 12px;
        }}
        
        .news-link {{
            display: inline-block;
            font-size: 13px;
            color: #667eea;
            text-decoration: none;
            padding: 4px 12px;
            border-radius: 4px;
            background: #f0f0ff;
            transition: all 0.2s;
        }}
        
        .news-link:hover {{
            background: #e0e0ff;
            text-decoration: underline;
        }}
        
        .card-footer {{
            text-align: center;
            padding: 18px;
            color: #999;
            font-size: 12px;
            border-top: 1px solid #f0f0f0;
        }}
        
        /* 加载状态 */
        .loading-state {{
            text-align: center;
            padding: 60px 20px;
            color: rgba(255, 255, 255, 0.6);
        }}
        
        .loading-spinner {{
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: rgba(255, 255, 255, 0.5);
        }}
        
        /* 移动端适配 */
        @media (max-width: 768px) {{
            .mobile-header {{
                display: flex;
            }}
            
            .sidebar {{
                position: fixed;
                left: -280px;
                top: 60px;
                height: calc(100vh - 60px);
                z-index: 999;
                transition: left 0.3s ease;
                background: rgba(15, 12, 41, 0.98);
            }}
            
            .sidebar.open {{
                left: 0;
            }}
            
            .main-content {{
                margin-top: 60px;
                height: calc(100vh - 60px);
                padding: 20px 15px;
            }}
            
            .content-header h2 {{
                font-size: 22px;
            }}
            
            .news-card-body {{
                padding: 20px 15px;
            }}
            
            .news-title {{
                font-size: 16px;
            }}
            
            .news-summary {{
                font-size: 14px;
            }}
            
            /* 遮罩层 */
            .overlay {{
                display: none;
                position: fixed;
                top: 60px;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                z-index: 998;
            }}
            
            .overlay.show {{
                display: block;
            }}
        }}
    </style>
</head>
<body>
    <!-- 移动端顶部栏 -->
    <div class="mobile-header">
        <h1>🚗 {t['title']}</h1>
        <button class="menu-toggle" onclick="toggleSidebar()">{t['menu_btn']}</button>
    </div>
    
    <!-- 遮罩层（移动端） -->
    <div class="overlay" id="overlay" onclick="toggleSidebar()"></div>
    
    <div class="app-container">
        <!-- 左侧边栏 -->
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <h1>🚗 {t['title']}</h1>
                <p class="subtitle">{t['subtitle']}</p>
            </div>
            
            <div class="sidebar-title">{t['sidebar_title']}</div>
            
            <div class="date-list" id="dateList">
                <!-- 动态加载日期列表 -->
            </div>
            
            <div class="sidebar-footer">
                <a href="{lang_switch_url}" class="lang-switch">{t['switch_lang']}</a>
            </div>
        </aside>
        
        <!-- 右侧主内容区 -->
        <main class="main-content">
            <div class="content-header">
                <h2 id="contentTitle">{t['loading']}</h2>
                <p class="date-info" id="dateInfo"></p>
            </div>
            
            <div class="news-container">
                <div class="news-card">
                    <div class="news-card-body" id="newsBody">
                        <div class="loading-state">
                            <div class="loading-spinner"></div>
                            <p>{t['loading']}</p>
                        </div>
                    </div>
                    <div class="card-footer">{t['footer']}</div>
                </div>
            </div>
        </main>
    </div>
    
    <script>
        // 全局数据
        let historyData = {{ records: [] }};
        let currentLang = '{lang}';
        
        // 加载历史数据
        async function loadData() {{
            try {{
                const response = await fetch('{json_path}');
                if (!response.ok) throw new Error('Failed to load data');
                historyData = await response.json();
                renderDateList();
                if (historyData.records.length > 0) {{
                    selectDate(historyData.records[0].date);
                }} else {{
                    showEmpty();
                }}
            }} catch (error) {{
                console.error('Load error:', error);
                showError();
            }}
        }}
        
        // 渲染日期列表
        function renderDateList() {{
            const container = document.getElementById('dateList');
            if (!historyData.records || historyData.records.length === 0) {{
                container.innerHTML = '<div class="empty-state"><p>暂无历史数据</p></div>';
                return;
            }}
            
            container.innerHTML = historyData.records.map(record => `
                <div class="date-item" data-date="${{record.date}}" onclick="selectDate('${{record.date}}')">
                    <div class="date-text">
                        <div class="date-main">${{record.date_display || record.date}}</div>
                        <div class="date-weekday">${{record.weekday || ''}}</div>
                    </div>
                    <div class="news-count">${{record.news_count || (record.news ? record.news.length : 0)}}条</div>
                </div>
            `).join('');
        }}
        
        // 选择日期
        function selectDate(date) {{
            // 更新高亮
            document.querySelectorAll('.date-item').forEach(el => {{
                el.classList.toggle('active', el.dataset.date === date);
            }});
            
            // 查找对应记录
            const record = historyData.records.find(r => r.date === date);
            if (record) {{
                renderNews(record);
            }} else {{
                showEmpty();
            }}
            
            // 移动端关闭侧边栏
            if (window.innerWidth <= 768) {{
                closeSidebar();
            }}
        }}
        
        // 渲染新闻内容
        function renderNews(record) {{
            const titleEl = document.getElementById('contentTitle');
            const infoEl = document.getElementById('dateInfo');
            const bodyEl = document.getElementById('newsBody');
            
            titleEl.textContent = record.date_display || record.date;
            infoEl.textContent = record.weekday ? `${{record.weekday}} · ${{record.news_count || record.news.length}}条新闻` : '';
            
            const isZh = currentLang === 'zh';
            const readText = isZh ? '🔗 阅读原文' : '🔗 Read Original';
            
            if (!record.news || record.news.length === 0) {{
                bodyEl.innerHTML = `<div class="empty-state"><p>${{isZh ? '该日期暂无新闻数据' : 'No news available'}}</p></div>`;
                return;
            }}
            
            bodyEl.innerHTML = record.news.map((item, i) => `
                <div class="news-item">
                    <div class="news-number">${{i + 1}}</div>
                    <div class="news-body">
                        <h3 class="news-title">${{escapeHtml(isZh ? item.title : (item.title_en || item.title))}}</h3>
                        <div class="news-source">📰 ${{escapeHtml(item.site_name || '')}}</div>
                        <div class="news-summary">${{escapeHtml(isZh ? item.summary : (item.summary_en || item.summary))}}</div>
                        <a href="${{escapeHtml(item.url)}}" class="news-link" target="_blank" rel="noopener">${{readText}}</a>
                    </div>
                </div>
            `).join('');
        }}
        
        // 显示空状态
        function showEmpty() {{
            const isZh = currentLang === 'zh';
            document.getElementById('contentTitle').textContent = isZh ? '暂无数据' : 'No Data';
            document.getElementById('newsBody').innerHTML = `<div class="empty-state"><p>${{isZh ? '暂无新闻数据' : 'No news available'}}</p></div>`;
        }}
        
        // 显示错误
        function showError() {{
            const isZh = currentLang === 'zh';
            document.getElementById('contentTitle').textContent = isZh ? '加载失败' : 'Load Failed';
            document.getElementById('newsBody').innerHTML = `<div class="empty-state"><p>${{isZh ? '无法加载数据，请稍后重试' : 'Failed to load data'}}</p></div>`;
        }}
        
        // HTML转义
        function escapeHtml(str) {{
            if (!str) return '';
            return str.replace(/&/g, '&amp;')
                      .replace(/</g, '&lt;')
                      .replace(/>/g, '&gt;')
                      .replace(/"/g, '&quot;')
                      .replace(/'/g, '&#039;');
        }}
        
        // 移动端菜单切换
        function toggleSidebar() {{
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('overlay');
            sidebar.classList.toggle('open');
            overlay.classList.toggle('show');
        }}
        
        function closeSidebar() {{
            document.getElementById('sidebar').classList.remove('open');
            document.getElementById('overlay').classList.remove('show');
        }}
        
        // 页面加载完成后初始化
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

    print("✅ 完成！30天历史归档已更新")
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
