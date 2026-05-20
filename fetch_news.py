"""
汽车智能座舱新闻摘要 - GitHub Actions 版本
支持 60 天历史归档 + 月度报告永久保留 + 动态标签提取 + SPA框架页面
"""
import os
import json
import urllib.request
import urllib.error
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from html import escape

# ==================== 全局配置 ====================
BJ_TZ = timezone(timedelta(hours=8))

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
HISTORY_FILE = "docs/history_data.json"
TAG_STATS_FILE = "docs/tag_stats.json"
MAX_DAYS = 60

# Buttondown & SMTP 配置
BUTTONDOWN_API_KEY = os.environ.get("BUTTONDOWN_API_KEY") or ""
SMTP_HOST = os.environ.get("SMTP_HOST") or ""
SMTP_PORT = int(os.environ.get("SMTP_PORT") or "465")
SMTP_USER = os.environ.get("SMTP_USER") or ""
SMTP_PASS = os.environ.get("SMTP_PASS") or ""
PRIVATE_EMAILS = os.environ.get("PRIVATE_EMAILS") or ""


# ==================== 历史数据管理 ====================
def load_history_data():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"    加载历史数据失败: {e}")
    return {"records": []}

def save_history_data(history_data):
    history_data["records"].sort(key=lambda x: x.get("date", ""), reverse=True)
    if len(history_data["records"]) > MAX_DAYS:
        removed = len(history_data["records"]) - MAX_DAYS
        history_data["records"] = history_data["records"][:MAX_DAYS]
        print(f"    已清理 {removed} 条超过 {MAX_DAYS} 天的旧记录")
    
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)

def add_today_record(history_data, news_items):
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    today_display = datetime.now(BJ_TZ).strftime("%m月%d日")
    
    existing_dates = [r.get("date") for r in history_data["records"]]
    if today in existing_dates:
        for record in history_data["records"]:
            if record.get("date") == today:
                record["news"] = news_items
                record["updated_at"] = datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
                return history_data
    else:
        new_record = {
            "date": today,
            "date_display": today_display,
            "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now(BJ_TZ).weekday()],
            "news_count": len(news_items),
            "news": news_items,
            "created_at": datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M:%S")
        }
        history_data["records"].insert(0, new_record)
    return history_data


# ==================== 格式化工具 ====================
def safe_url(url):
    if not url: return "#"
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"): return url
    return "#"

def format_summary_for_email(summary, is_html=True):
    if not summary: return ""
    if is_html:
        formatted = escape(summary).replace("\n", "<br>")
        formatted = re.sub(r'([【\[].*?[】\]])', r'<br><div class="section-title" style="color:#667eea; font-weight:600; margin:12px 0 4px;">\1</div>', formatted)
        formatted = re.sub(r'(<br>\s*){3,}', '<br><br>', formatted)
        if formatted.startswith('<br>'): formatted = formatted[4:]
        return formatted
    return summary


# ==================== 标签统计 ====================
def load_tag_stats():
    if os.path.exists(TAG_STATS_FILE):
        try:
            with open(TAG_STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception: pass
    return {"tags": {}, "monthly": {}, "yearly": {}}

def update_tag_stats(news_items):
    today = datetime.now(BJ_TZ)
    month_key = today.strftime("%Y-%m")
    year_key = today.strftime("%Y")
    stats = load_tag_stats()
    
    if "monthly" not in stats: stats["monthly"] = {}
    if "yearly" not in stats: stats["yearly"] = {}
    if "tags" not in stats: stats["tags"] = {}
    
    if month_key not in stats["monthly"]: stats["monthly"][month_key] = {}
    if year_key not in stats["yearly"]: stats["yearly"][year_key] = {}
    
    for item in news_items:
        for tag in item.get("tags", []):
            if not tag: continue
            stats["tags"][tag] = stats["tags"].get(tag, 0) + 1
            stats["monthly"][month_key][tag] = stats["monthly"][month_key].get(tag, 0) + 1
            stats["yearly"][year_key][tag] = stats["yearly"][year_key].get(tag, 0) + 1
            
    os.makedirs(os.path.dirname(TAG_STATS_FILE), exist_ok=True)
    with open(TAG_STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    return stats


# ==================== DeepSeek API ====================
def call_deepseek(system_prompt, user_prompt):
    if not DEEPSEEK_API_KEY: return None
    url = "https://api.deepseek.com/v1/chat/completions"
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1, "max_tokens": 8192
    }
    req = urllib.request.Request(
        url, data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {DEEPSEEK_API_KEY}'},
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode('utf-8'))['choices'][0]['message']['content']
    except Exception as e:
        print(f"DeepSeek 调用失败: {e}")
        return None


# ==================== 业务逻辑 ====================
def generate_search_keywords(topic="汽车智能座舱"):
    system_prompt = f"""你是深耕中国新能源汽车市场的资深用户研究与体验分析师。请围绕"{topic}"，生成15个精准且多样化的中文搜索关键词。
涵盖维度：
1. 数字娱乐生态：如 "车机 第三方 App", "座舱游戏 生态", "手车互联"
2. OTA更新：如 "新势力 OTA 升级 体验", "座舱 大模型"
3. 交互触点：如 "多模态交互 评测", "零层级 交互"
4. 品牌动态：如 "蔚来 Banyan", "小鹏 天玑", "澎湃OS"
注意：聚焦大陆市场，不含台湾、香港、澳门。仅返回JSON格式：{{"keywords": ["词1", "词2"]}}"""

    response = call_deepseek(system_prompt, f"请为'{topic}'生成关键词")
    if response:
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match: return json.loads(match.group(0)).get("keywords", ["智能座舱 OTA", "车机系统 体验", "车载交互 UI"])
        except Exception: pass
    return ["智能座舱 OTA", "车机系统 体验", "车载交互 UI"]

def search_news(keywords, max_results=40):
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

                    if not title or not url or url in seen_urls: continue
                    seen_urls.add(url)
                    
                    domain = urlparse(url).netloc.replace("www.", "")
                    site_name = domain.split(".")[0].title() if domain else ""
                    
                    if any(k in url.lower() for k in ["ad", "sponsored", "推广", "广告", "track"]): continue
                    if any(k in (title + body).lower() for k in ["台湾", "台灣", "taiwan", "香港", "hong kong", "澳门", "macau"]): continue

                    all_results.append({"title": title, "url": url, "snippet": body[:400], "site_name": site_name, "publish_date": publish_date})
        return all_results
    except Exception as e:
        print(f"搜索失败: {e}")
        return []

def filter_and_format(news_list):
    if not news_list: return []
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d")
    news_data = "\n\n".join([f"新闻{i+1}:\n标题: {item['title']}\n来源: {item['site_name']}\n日期: {item.get('publish_date', '')}\n摘要: {item['snippet']}\n链接: {item['url']}" for i, item in enumerate(news_list)])

    # 修复了字数总计的逻辑矛盾 (400 -> 500)
    system_prompt = f"""你是资深汽车体验分析专家。今天是{today}。
请以严苛标准，筛选出对国内汽车软件生态和交互设计最具价值的 5 条新闻。
必须聚焦纯软件功能创新、数字生态服务、OTA、交互逻辑(UI/UX)。排除纯硬件和敏感地区。

【结构与字数要求】：
每篇总结必须包含以下三个模块（必须使用这些标题），中文总计约 500 字：
【事件概述】（约 300 字）：详细描述核心软件事件及创新点。
【体验价值】（约 100 字）：从 UX 视角剖析该功能的正向体验价值。
【潜在槽点】（约 80 字）：【强制要求】以批判性视角指出该功能可能面临的用户学习成本、隐私风险、交互冗余或实际落地难度等挑战。

请返回JSON格式：
{{
  "news": [
    {{
      "title": "原标题", "url": "原链接", "site_name": "媒体", "publish_date": "发布日期",
      "tags": ["小米", "澎湃OS", "OTA"], 
      "summary": "【事件概述】... \\n\\n【体验价值】... \\n\\n【潜在槽点】...",
      "summary_en": "【Event Overview】... \\n\\n【Experience Value】... \\n\\n【Potential Friction】..."
    }}
  ]
}}
* tags 提取4个维度：品牌、OS、技术特征、场景生态。控制在5-8个词，使用简短的标准术语。
* 【重要】标签禁止包含"智能座舱"、"智能汽车"、"车机"等过于宽泛的词，因为整个看板都是关于智能座舱的。"""

    response = call_deepseek(system_prompt, f"请分析以下新闻：\n\n{news_data}")
    if response:
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group(0)).get("news", [])
        except Exception as e:
            print(f"    ❌ 解析失败: {e}")
    return []

def generate_monthly_report(history_data):
    today = datetime.now(BJ_TZ)
    if today.day != 1: return False
        
    last_month_year = today.year - 1 if today.month == 1 else today.year
    last_month = 12 if today.month == 1 else today.month - 1
    last_month_str = f"{last_month_year}-{last_month:02d}"
    
    compiled_data = ""
    for record in history_data.get("records", []):
        record_date = record.get("date", "")
        if record_date.startswith(last_month_str):
            compiled_data += f"\n日期: {record_date}\n"
            for news in record.get("news", []):
                compiled_data += f"标签: [{', '.join(news.get('tags', []))}]\n概要: {news.get('summary', '')}\n"
    
    if not compiled_data: return False

    system_prompt = """你是一位顶级的汽车行业首席分析师。
请你基于这些数据，撰写一篇《智能座舱软件体验月度风向标》报告。
要求：
1. 提取出本月最核心的 3 个行业大趋势。
2. 分析头部玩家在本月的核心角力点。
3. 必须输出为 Markdown 格式，层级分明，字数约 1000 字。"""

    report_md = call_deepseek(system_prompt, f"请分析以下 {last_month_year}年{last_month}月 的数据：\n\n{compiled_data}")
    if report_md:
        report_path = f"docs/monthly_report_{last_month_year}_{last_month:02d}.md"
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_md)
        return True
    return False

# ==================== 页面生成 (趋势页子页面) ====================
def generate_trends_page(lang='zh'):
    is_zh = lang == 'zh'
    stats = load_tag_stats()
    texts = {
        'zh': {'title': '标签趋势分析', 'desc': '持续追踪行业热点', 'monthly': '按月查看', 'yearly': '按年查看', 'top_tags': '热门标签排行', 'trend_chart': '趋势变化图', 'no_data': '暂无数据'},
        'en': {'title': 'Tag Trends', 'desc': 'Track industry trends', 'monthly': 'Monthly', 'yearly': 'Yearly', 'top_tags': 'Top Tags', 'trend_chart': 'Trend Chart', 'no_data': 'No data'}
    }
    t = texts[lang]
    
    monthly_data = stats.get("monthly", {})
    yearly_data = stats.get("yearly", {})
    total_tags = stats.get("tags", {})
    
    sorted_total = sorted(total_tags.items(), key=lambda x: x[1], reverse=True)[:10]
    tags_html = ""
    if sorted_total:
        max_count = sorted_total[0][1] if sorted_total else 1
        for i, (tag, count) in enumerate(sorted_total, 1):
            width_percent = max(10, int(count / max_count * 100))
            tags_html += f"""
            <div class="flex items-center gap-4 mb-3">
                <span class="text-sm font-mono text-primary w-8">{i}.</span>
                <span class="text-sm font-mono text-on-surface w-24 truncate">{tag}</span>
                <div class="flex-1 h-6 bg-surface-container-high rounded overflow-hidden">
                    <div class="h-full bg-gradient-to-r from-primary/50 to-primary transition-all duration-300" style="width: {width_percent}%"></div>
                </div>
                <span class="text-sm text-on-surface-variant w-12 text-right">{count}</span>
            </div>
            """
    else: tags_html = f'<p class="text-on-surface-variant">{t["no_data"]}</p>'
    
    sorted_months = sorted(monthly_data.keys())
    monthly_labels = sorted_months[-12:] if len(sorted_months) > 12 else sorted_months
    top_5_tags = [tag for tag, _ in sorted_total[:5]]
    
    colors = ['#00F2FF', '#FF6B6B', '#4ECDC4', '#FFE66D', '#95E1D3']
    datasets = []
    for i, tag in enumerate(top_5_tags):
        datasets.append({
            'label': tag,
            'data': [monthly_data.get(m, {}).get(tag, 0) for m in monthly_labels],
            'borderColor': colors[i % len(colors)], 'backgroundColor': colors[i % len(colors)] + '20',
            'tension': 0.4, 'fill': False
        })
        
    yearly_labels = sorted(yearly_data.keys())
    yearly_datasets = []
    for i, tag in enumerate(top_5_tags):
        yearly_datasets.append({
            'label': tag,
            'data': [yearly_data.get(y, {}).get(tag, 0) for y in yearly_labels],
            'borderColor': colors[i % len(colors)], 'backgroundColor': colors[i % len(colors)] + '20',
            'tension': 0.4, 'fill': False
        })

    content_html = f"""<!DOCTYPE html>
<html lang="{'zh-CN' if is_zh else 'en'}" class="dark">
<head>
    <meta charset="UTF-8">
    <title>{t['title']}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>tailwind.config = {{ darkMode: "class", theme: {{ extend: {{ colors: {{ background: "#0D0F12", surface: "#111317", "surface-container": "#1e2023", "surface-container-low": "#1a1c1f", primary: "#00F2FF", "on-surface": "#e2e2e6", "on-surface-variant": "#b9cacb" }} }} }} }}</script>
    <style>body {{ background-color: #0D0F12; }}</style>
</head>
<body class="bg-background text-on-surface font-sans p-6 pb-20">
    <h1 class="text-3xl font-bold mb-2 tracking-tight">📊 {t['title']}</h1>
    <p class="text-sm text-on-surface-variant mb-6">{t['desc']}</p>
    <div class="flex gap-2 mb-6">
        <button id="btn-monthly" onclick="showMonthly()" class="px-4 py-2 rounded-lg text-sm font-medium bg-primary/20 text-primary border border-primary/30">{t['monthly']}</button>
        <button id="btn-yearly" onclick="showYearly()" class="px-4 py-2 rounded-lg text-sm font-medium bg-surface-container-high text-on-surface-variant hover:bg-surface-container-high/80">{t['yearly']}</button>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div class="bg-surface-container-low border border-outline-variant rounded-2xl p-6">
            <h2 class="text-lg font-semibold mb-4">🏷️ {t['top_tags']}</h2>
            <div class="space-y-3">{tags_html}</div>
        </div>
        <div class="bg-surface-container-low border border-outline-variant rounded-2xl p-6">
            <h2 class="text-lg font-semibold mb-4">📈 {t['trend_chart']}</h2>
            <div class="h-64"><canvas id="trendChart"></canvas></div>
        </div>
    </div>
    <script>
        const monthlyLabels = {json.dumps(monthly_labels)};
        const monthlyDatasets = {json.dumps(datasets)};
        const yearlyLabels = {json.dumps(yearly_labels)};
        const yearlyDatasets = {json.dumps(yearly_datasets)};
        const ctx = document.getElementById('trendChart').getContext('2d');
        const trendChart = new Chart(ctx, {{
            type: 'line',
            data: {{ labels: monthlyLabels, datasets: monthlyDatasets }},
            options: {{
                responsive: true, maintainAspectRatio: false,
                plugins: {{ legend: {{ labels: {{ color: '#b9cacb' }} }} }},
                scales: {{
                    x: {{ ticks: {{ color: '#b9cacb' }}, grid: {{ color: '#3a494b30' }} }},
                    y: {{ ticks: {{ color: '#b9cacb' }}, grid: {{ color: '#3a494b30' }} }}
                }}
            }}
        }});
        function showMonthly() {{
            trendChart.data.labels = monthlyLabels; trendChart.data.datasets = monthlyDatasets; trendChart.update();
            document.getElementById('btn-monthly').className = 'px-4 py-2 rounded-lg text-sm font-medium bg-primary/20 text-primary border border-primary/30';
            document.getElementById('btn-yearly').className = 'px-4 py-2 rounded-lg text-sm font-medium bg-surface-container-high text-on-surface-variant hover:bg-surface-container-high/80';
        }}
        function showYearly() {{
            trendChart.data.labels = yearlyLabels; trendChart.data.datasets = yearlyDatasets; trendChart.update();
            document.getElementById('btn-yearly').className = 'px-4 py-2 rounded-lg text-sm font-medium bg-primary/20 text-primary border border-primary/30';
            document.getElementById('btn-monthly').className = 'px-4 py-2 rounded-lg text-sm font-medium bg-surface-container-high text-on-surface-variant hover:bg-surface-container-high/80';
        }}
    </script>
</body>
</html>"""
    content_path = f"docs/{'trends_content.html' if is_zh else 'en/trends_content.html'}"
    os.makedirs(os.path.dirname(content_path), exist_ok=True)
    with open(content_path, 'w', encoding='utf-8') as f: f.write(content_html)

# ==================== 页面生成 (月报子页面) ====================
def generate_report_list_page(lang='zh'):
    is_zh = lang == 'zh'
    texts = {
        'zh': {'title': '月度宏观报告', 'desc': '每月1号自动生成上个月行业深度分析', 'select_prompt': '👈 请在左侧选择一份报告', 'no_report': '暂无月度报告'},
        'en': {'title': 'Monthly Report', 'desc': 'Auto-generated on the 1st of each month', 'select_prompt': '👈 Select a report', 'no_report': 'No reports yet'}
    }
    t = texts[lang]
    prefix = "" if is_zh else "../"
    
    import glob
    report_files = glob.glob("docs/monthly_report_*.md")
    report_files.sort(reverse=True)
    
    reports_html = ""
    if report_files:
        for rf in report_files:
            match = re.search(r'(\d{4})_(\d{2})', rf)
            if match:
                year, month = match.groups()
                report_name = f"{year}年{month}月研判" if is_zh else f"{year}/{month} Report"
                file_path = f"{prefix}{rf.replace('docs/', '')}"
                reports_html += f"""
                <button onclick="loadReport('{file_path}')" class="w-full text-left p-4 bg-surface-container-low border border-outline-variant rounded-xl hover:border-primary transition-all mb-4 group">
                    <div class="flex items-center justify-between">
                        <span class="text-base font-semibold group-hover:text-primary transition-colors">📑 {report_name}</span>
                        <span class="text-primary text-sm">阅读 →</span>
                    </div>
                </button>"""
    else: reports_html = f'<p class="text-on-surface-variant text-sm py-4">{t["no_report"]}</p>'

    content_html = f"""<!DOCTYPE html>
<html lang="{'zh-CN' if is_zh else 'en'}" class="dark">
<head>
    <meta charset="UTF-8">
    <title>{t['title']}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script>tailwind.config = {{ darkMode: "class", theme: {{ extend: {{ colors: {{ background: "#0D0F12", surface: "#111317", "surface-container": "#1e2023", "surface-container-low": "#1a1c1f", primary: "#00F2FF", "on-surface": "#e2e2e6", "on-surface-variant": "#b9cacb" }} }} }} }}</script>
    <style>
        body {{ background-color: #0D0F12; }}
        .markdown-body h1 {{ font-size: 1.5rem; font-weight: 700; color: #00F2FF; margin-bottom: 1.5rem; }}
        .markdown-body h2 {{ font-size: 1.25rem; font-weight: 600; color: #e2e2e6; margin-top: 1.5rem; margin-bottom: 1rem; border-bottom: 1px solid #3a494b; padding-bottom: 0.5rem; }}
        .markdown-body h3 {{ font-size: 1.1rem; font-weight: 600; color: #b9cacb; margin-top: 1rem; margin-bottom: 0.5rem; }}
        .markdown-body p {{ margin-bottom: 1rem; line-height: 1.7; color: #b9cacb; font-size: 14px; }}
        .markdown-body ul {{ list-style-type: disc; padding-left: 1.5rem; margin-bottom: 1rem; color: #b9cacb; font-size: 14px; }}
        .markdown-body strong {{ color: #e2e2e6; }}
    </style>
</head>
<body class="bg-background text-on-surface font-sans p-6 pb-20">
    <div class="flex flex-col md:flex-row gap-8">
        <div class="w-full md:w-1/3 flex-shrink-0">
            <h1 class="text-3xl font-bold mb-2 tracking-tight">📑 {t['title']}</h1>
            <p class="text-sm text-on-surface-variant mb-6">{t['desc']}</p>
            <section>{reports_html}</section>
        </div>
        <div class="w-full md:w-2/3 bg-surface-container-low border border-outline-variant rounded-2xl p-6 md:p-10 min-h-[500px]">
            <div id="reader-empty" class="h-full flex flex-col items-center justify-center text-on-surface-variant/40">
                <span class="text-5xl mb-4">📖</span><p class="text-sm">{t['select_prompt']}</p>
            </div>
            <div id="report-content" class="markdown-body hidden"></div>
        </div>
    </div>
    <script>
        async function loadReport(path) {{
            try {{
                const res = await fetch(path);
                if (!res.ok) throw new Error('File not found');
                const htmlContent = marked.parse(await res.text());
                document.getElementById('reader-empty').classList.add('hidden');
                const reader = document.getElementById('report-content');
                reader.innerHTML = htmlContent;
                reader.classList.remove('hidden');
                
                // 移动端点击后自动平滑滚动到阅读区
                if (window.innerWidth < 768) {{
                    reader.scrollIntoView({{ behavior: 'smooth' }});
                }}
            }} catch (e) {{ alert("报告加载失败"); }}
        }}
    </script>
</body>
</html>"""
    content_path = f"docs/{'report_content.html' if is_zh else 'en/report_content.html'}"
    os.makedirs(os.path.dirname(content_path), exist_ok=True)
    with open(content_path, 'w', encoding='utf-8') as f: f.write(content_html)

# ==================== HTML SPA主框架生成 ====================
def generate_html(output_path, lang='zh'):
    is_zh = lang == 'zh'
    html_lang = "zh-CN" if is_zh else "en"
    
    texts = {
        'zh': {
            'title': '智能座舱日报', 'description': '聚焦新能源车软件生态与座舱交互，每日自动提纯OTA动态与行业风向。',
            'nav_today': '今日情报', 'nav_trends': '标签趋势', 'nav_report': '月度报告',
            'sidebar_archive': '历史归档', 'loading': '加载中...', 'subscribe': '订阅日报', 'subscribe_btn': '立即订阅', 'switch_lang': 'English'
        },
        'en': {
            'title': 'Smart Cockpit', 'description': 'Focusing on China NEV software ecosystem. Daily insights on OTA and UX.',
            'nav_today': 'Today', 'nav_trends': 'Tag Trends', 'nav_report': 'Monthly Report',
            'sidebar_archive': 'ARCHIVE', 'loading': 'Loading...', 'subscribe': 'Subscribe', 'subscribe_btn': 'Subscribe', 'switch_lang': '中文'
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
        tailwind.config = {{ darkMode: "class", theme: {{ extend: {{ colors: {{ background: "#0D0F12", surface: "#111317", "surface-container": "#1e2023", "surface-container-high": "#282a2d", primary: "#00F2FF", "on-surface": "#e2e2e6", "on-surface-variant": "#b9cacb", "outline-variant": "#3a494b" }} }} }} }}
    </script>
    <style>
        .material-symbols-outlined {{ font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }}
        body {{ background-color: #0D0F12; }}
        .news-card-bg {{ position: absolute; top: 8px; left: 16px; pointer-events: none; }}
        .news-card-bg span {{ font-size: 120px; color: #00F2FF; opacity: 0.05; line-height: 1; }}
        .glow-hover:hover {{ box-shadow: 0 12px 40px -12px rgba(0, 242, 255, 0.25); border-color: rgba(0, 242, 255, 0.5); }}
        .date-item-active {{ border-left: 4px solid #00F2FF; background: rgba(0, 242, 255, 0.1); color: #00F2FF; font-weight: 600; }}
        .section-title {{ color: #00F2FF; font-weight: 600; margin-top: 12px; margin-bottom: 4px; font-size: 14px; }}
        /* 自定义滚动条，使 iframe 内部滚动与外部一致 */
        ::-webkit-scrollbar {{ width: 6px; }}
        ::-webkit-scrollbar-track {{ background: #0D0F12; }}
        ::-webkit-scrollbar-thumb {{ background: #3a494b; border-radius: 10px; }}
    </style>
</head>
<body class="bg-background text-on-surface font-sans overflow-x-hidden">
    
    <header class="md:hidden fixed top-0 left-0 right-0 h-16 bg-[#111317]/95 backdrop-blur-lg z-50 flex items-center justify-between px-4 border-b border-outline-variant">
        <h1 class="text-lg font-bold text-primary">🚗 SMART COCKPIT</h1>
        <button onclick="toggleSidebar()" class="p-2 text-on-surface hover:text-primary">
            <span class="material-symbols-outlined">menu</span>
        </button>
    </header>

    <div id="overlay" class="fixed inset-0 bg-black/60 z-40 hidden backdrop-blur-sm transition-opacity" onclick="closeSidebar()"></div>

    <aside id="sidebar" class="fixed left-0 top-0 h-screen w-64 bg-surface-container border-r border-outline-variant flex flex-col z-50 transform -translate-x-full md:translate-x-0 transition-transform duration-300">
        <div class="p-6 border-b border-outline-variant text-center">
            <h1 class="text-xl font-bold text-primary tracking-tight uppercase">SMART COCKPIT</h1>
            <p class="text-xs text-on-surface-variant/70 mt-3 leading-relaxed">{t['description']}</p>
        </div>
        <nav class="flex-1 overflow-y-auto mt-4">
            <div id="nav-today" onclick="showView('today')" class="nav-item flex items-center gap-3 px-5 py-3 cursor-pointer hover:bg-surface-container-high transition-colors bg-primary/10 text-primary border-l-4 border-primary">
                <span class="material-symbols-outlined text-xl">today</span><span class="font-medium">{t['nav_today']}</span>
            </div>
            <div id="nav-trends" onclick="showView('trends')" class="nav-item flex items-center gap-3 px-5 py-3 cursor-pointer hover:bg-surface-container-high transition-colors">
                <span class="material-symbols-outlined text-xl">trending_up</span><span>{t['nav_trends']}</span>
            </div>
            <div id="nav-report" onclick="showView('report')" class="nav-item flex items-center gap-3 px-5 py-3 cursor-pointer hover:bg-surface-container-high transition-colors">
                <span class="material-symbols-outlined text-xl">summarize</span><span>{t['nav_report']}</span>
            </div>
            <div class="px-6 py-2 mt-4"><span class="text-[10px] uppercase tracking-widest text-on-surface-variant/50">{t['sidebar_archive']}</span></div>
            <div id="dateList" class="space-y-1"></div>
        </nav>
        <div class="p-4 border-t border-outline-variant space-y-3">
            <a href="{lang_switch_url}" class="flex items-center gap-2 text-on-surface-variant hover:text-primary transition-colors cursor-pointer">
                <span class="material-symbols-outlined text-lg">language</span><span class="text-sm">{t['switch_lang']}</span>
            </a>
            <div class="pt-3 border-t border-outline-variant/50">
                <form action="https://buttondown.com/api/emails/embed-subscribe/Cockpit_News_by_BridgetYang" method="post" class="space-y-2">
                    <input type="email" name="email" required class="w-full px-3 py-2 bg-[#1a1c1f] border border-outline-variant rounded-lg text-sm focus:border-primary" placeholder="email@example.com" />
                    <button type="submit" class="w-full py-2 bg-primary/20 hover:bg-primary/30 text-primary rounded-lg text-sm">{t['subscribe_btn']}</button>
                </form>
            </div>
        </div>
    </aside>
    
    <main class="md:ml-64 min-h-screen pt-16 md:pt-0">
        <div id="view-today" class="px-4 md:px-10 py-6 max-w-5xl mx-auto md:pt-8">
            <header class="mb-8 border-b border-outline-variant pb-4">
                <div class="flex items-baseline gap-3">
                    <h2 id="contentDate" class="text-3xl font-bold">{t['loading']}</h2>
                    <span id="contentWeekday" class="text-xl text-primary/80"></span>
                </div>
            </header>
            <section id="newsContainer" class="space-y-6"></section>
        </div>
        
        <iframe id="contentFrame" class="hidden w-full border-0" style="height: calc(100vh - 64px); md:height: 100vh;"></iframe>
    </main>

    <script>
        let historyData = {{records: []}};
        let currentLang = '{lang}';
        
        // 移动端菜单控制
        function toggleSidebar() {{
            document.getElementById('sidebar').classList.toggle('-translate-x-full');
            document.getElementById('overlay').classList.toggle('hidden');
        }}
        function closeSidebar() {{
            document.getElementById('sidebar').classList.add('-translate-x-full');
            document.getElementById('overlay').classList.add('hidden');
        }}

        async function loadData() {{
            try {{
                const res = await fetch('{json_path}');
                historyData = await res.json();
                renderDateList();
                if(historyData.records.length > 0) selectDate(historyData.records[0].date, false);
            }} catch (e) {{ console.error('Failed to load data:', e); }}
        }}
        
        function renderDateList() {{
            document.getElementById('dateList').innerHTML = historyData.records.map((r, i) => `
                <div class="date-item flex items-center justify-between px-5 py-2 cursor-pointer hover:bg-surface-container-high ${{i===0?'date-item-active':''}}" data-date="${{r.date}}" onclick="selectDate('${{r.date}}', true)">
                    <div class="flex items-center gap-2"><span class="material-symbols-outlined text-base opacity-50">calendar_today</span><span class="text-sm">${{r.date_display || r.date}}</span></div>
                    <span class="text-xs font-mono text-on-surface-variant/70">${{r.news_count}}</span>
                </div>`).join('');
        }}
        
        function selectDate(date, userTriggered = false) {{
            showView('today');
            document.querySelectorAll('.date-item').forEach(el => el.classList.toggle('date-item-active', el.dataset.date === date));
            const record = historyData.records.find(r => r.date === date);
            if(record) renderNews(record);
            
            if (userTriggered && window.innerWidth < 768) closeSidebar();
        }}
        
        function showView(view) {{
            // 切换导航高亮
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('bg-primary/10', 'text-primary', 'border-l-4', 'border-primary'));
            const activeNav = document.getElementById('nav-' + view);
            if(activeNav) activeNav.classList.add('bg-primary/10', 'text-primary', 'border-l-4', 'border-primary');
            
            const viewToday = document.getElementById('view-today');
            const iframe = document.getElementById('contentFrame');
            
            if (view === 'today') {{
                viewToday.classList.remove('hidden');
                iframe.classList.add('hidden');
                iframe.src = ""; // 清空减少内存占用
            }} else {{
                viewToday.classList.add('hidden');
                iframe.classList.remove('hidden');
                iframe.src = view === 'trends' ? 'trends_content.html' : 'report_content.html';
            }}
            
            // 移动端点击后自动收起菜单
            if (window.innerWidth < 768) closeSidebar();
        }}
        
        function formatSummary(text) {{
            if(!text) return "";
            let html = text.replace(/\\n/g, '<br>');
            html = html.replace(/([【\\[].*?[】\\]])/g, '<br><div class="section-title">$1</div>');
            html = html.replace(/(<br>\\s*){{3,}}/g, '<br><br>');
            if(html.startsWith('<br>')) html = html.substring(4);
            return html;
        }}
        
        function renderNews(record) {{
            const isZh = currentLang === 'zh';
            document.getElementById('contentDate').textContent = record.date_display || record.date;
            document.getElementById('contentWeekday').textContent = record.weekday || '';
            
            document.getElementById('newsContainer').innerHTML = record.news.map((item, index) => {{
                let tagsHtml = '';
                if (item.tags && item.tags.length > 0) {{
                    tagsHtml = `<div class="flex flex-wrap gap-2 mt-3 mb-3">${{item.tags.map(tag => `<span class="px-2 py-1 text-[11px] font-medium bg-primary/10 text-primary border border-primary/20 rounded-md uppercase tracking-wider">${{tag}}</span>`).join('')}}</div>`;
                }}
                return `
                <article class="news-card relative bg-[#1a1c1f] border border-outline-variant rounded-xl p-6 glow-hover group">
                    <div class="news-card-bg"><span class="font-bold font-mono">${{String(index + 1).padStart(2, '0')}}</span></div>
                    <div class="relative z-10">
                        <div class="flex gap-3 mb-3 text-xs text-on-surface-variant/60">
                            <span class="font-mono text-primary/80">📰 ${{item.site_name||''}}</span>
                            <span>📅 ${{item.publish_date||record.date}}</span>
                        </div>
                        <h3 class="text-xl font-semibold text-on-surface mb-2 group-hover:text-primary transition-colors">${{isZh ? item.title : (item.title_en||item.title)}}</h3>
                        ${{tagsHtml}}
                        <div class="text-sm text-on-surface-variant/80 leading-relaxed mb-4 max-w-3xl">${{formatSummary(isZh ? item.summary : (item.summary_en||item.summary))}}</div>
                        <a href="${{item.url}}" target="_blank" class="text-primary hover:underline text-sm font-medium">🔗 ${{isZh?'阅读原文':'Read Original'}}</a>
                    </div>
                </article>`;
            }}).join('');
        }}
        
        document.addEventListener('DOMContentLoaded', loadData);
    </script>
</body>
</html>"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ {'中文' if is_zh else '英文'}SPA主框架页面已生成: {output_path}")


# ==================== 发送邮件包装 ====================
def send_daily_email(news_items, date_str):
    if not BUTTONDOWN_API_KEY: return False
    subject = f"🚗 智能座舱日报 | {date_str}"
    
    html_content = f"""
    <html>
    <head><style>
        body {{ font-family: sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #fff; border-radius: 16px; overflow: hidden; }}
        .header {{ background: #111317; padding: 30px; text-align: center; border-bottom: 2px solid #00F2FF; }}
        .news-item {{ padding: 24px; border-bottom: 1px solid #eee; }}
    </style></head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="color:#00F2FF; margin:0;">SMART COCKPIT DAILY</h1>
                <p style="color:#fff; margin-top:10px;">{date_str} | 今日 {len(news_items)} 条资讯</p>
            </div>
    """
    
    for i, item in enumerate(news_items, 1):
        title = escape(item.get('title', ''))
        site_name = escape(item.get('site_name', ''))
        pub_date = escape(item.get('publish_date', ''))
        url = safe_url(item.get('url', ''))
        formatted_summary = format_summary_for_email(item.get("summary", ""), is_html=True)
        formatted_summary = formatted_summary.replace('>【潜在槽点】<', 'style="color:#ff6b6b; border-bottom: 1px dashed #ff6b6b; padding-bottom: 2px;">【潜在槽点】<')
        
        tags = item.get('tags', [])
        tags_html = ' '.join([f'<span style="display:inline-block; padding:4px 10px; margin:2px; background:#e8f4f8; color:#0066cc; border-radius:12px; font-size:12px;">{escape(tag)}</span>' for tag in tags]) if tags else ''
        
        html_content += f"""
            <div class="news-item">
                <h3 style="margin: 0 0 10px 0;">{i}. {title}</h3>
                <p style="font-size: 12px; color: #888;">📰 {site_name} | 📅 {pub_date}</p>
                {f'<div style="margin: 12px 0;">{tags_html}</div>' if tags_html else ''}
                <div style="font-size: 14px; color: #444; line-height: 1.6;">{formatted_summary}</div>
                <a href="{url}" style="display:inline-block; margin-top:12px; color:#667eea;">🔗 阅读原文</a>
            </div>
        """
    
    html_content += """
            <div style="padding: 24px; text-align: center; background: #f9f9f9;">
                <p style="margin-bottom: 12px; color: #666; font-size: 14px;">📊 更多数据分析与往期内容</p>
                <p style="color: #999; font-size: 12px;">🌐 <a href="https://bridgetyangjie-1.github.io/cockpit-news/">访问在线 Dashboard 看板</a></p>
            </div>
        </div>
    </body></html>
    """
    
    try:
        url = "https://api.buttondown.email/v1/emails"
        publish_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        data = {
            "subject": subject, "body": html_content, 
            "publish_date": publish_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        req = urllib.request.Request(
            url, data=json.dumps(data).encode('utf-8'),
            headers={'Authorization': f'Token {BUTTONDOWN_API_KEY}', 'Content-Type': 'application/json'},
            method='POST'
        )
        urllib.request.urlopen(req, timeout=30)
        print("    ✅ 邮件已通过 Buttondown 发送")
        return True
    except Exception as e:
        print(f"    ❌ Buttondown 发送失败: {e}")
        return False

def send_private_email(news_items, date_str):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, PRIVATE_EMAILS]): return False
    recipients = [e.strip() for e in PRIVATE_EMAILS.split(",") if e.strip()]
    subject = f"🚗 智能座舱日报 | {date_str}"
    
    news_html = ""
    for i, item in enumerate(news_items, 1):
        title = escape(item.get('title', ''))
        site_name = escape(item.get('site_name', ''))
        pub_date = escape(item.get('publish_date', ''))
        url = safe_url(item.get('url', '#'))
        
        formatted_summary = format_summary_for_email(item.get('summary', ''), is_html=True)
        formatted_summary = formatted_summary.replace('color:#667eea', 'color:#00d4ff')
        formatted_summary = formatted_summary.replace('>【潜在槽点】<', 'style="color:#ff6b6b; border-bottom: 1px dashed #ff6b6b; padding-bottom: 2px;">【潜在槽点】<')
        
        tags = item.get('tags', [])
        tags_html = ' '.join([f'<span style="display:inline-block; padding:4px 10px; margin:2px; background:#e0f7fa; color:#0097a7; border-radius:12px; font-size:12px;">{escape(tag)}</span>' for tag in tags]) if tags else ''
        
        news_html += f"""
        <div style="margin-bottom: 24px; padding: 16px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #00d4ff;">
            <h3 style="margin: 0 0 8px 0; color: #1a1a2e; font-size: 16px;">{i}. {title}</h3>
            <p style="margin: 4px 0; color: #666; font-size: 13px;">📅 {pub_date} | 📰 {site_name}</p>
            {f'<div style="margin: 12px 0;">{tags_html}</div>' if tags_html else ''}
            <p style="margin: 12px 0 0 0; color: #333; font-size: 14px; line-height: 1.6;">{formatted_summary}</p>
            <a href="{url}" style="color: #00d4ff; font-size: 13px;">阅读原文 →</a>
        </div>
        """
        
    html_content = f"""
    <html><body>
        <div style="text-align:center; margin-bottom:32px; padding:24px; background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%); border-radius:12px;">
            <h1 style="color:#00d4ff; margin:0; font-size:24px;">SMART COCKPIT DAILY</h1>
            <p style="color:#fff; margin:8px 0 0 0;">{date_str} | 今日 {len(news_items)} 条精选资讯</p>
        </div>
        {news_html}
    </body></html>
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


# ==================== 主程序入口 ====================
def main():
    print("=" * 50)
    print("🚗 智能座舱日报 - 自动抓取系统启动")
    print("=" * 50)
    
    print("\n📌 步骤1: 生成搜索关键词...")
    keywords = generate_search_keywords()
    
    print("\n📌 步骤2: 搜索新闻...")
    news = search_news(keywords, max_results=40)
    
    history_data = load_history_data()

    if news:
        print("\n📌 步骤3: AI 深度分析与筛选...")
        items = filter_and_format(news)
        
        if items:
            print("\n📌 步骤4: 归档与生成网页...")
            history_data = add_today_record(history_data, items)
            save_history_data(history_data)
            
            # 更新标签统计
            update_tag_stats(items)
            
            # 生成各个模块的页面
            generate_trends_page(lang='zh')
            generate_trends_page(lang='en')
            generate_report_list_page(lang='zh')
            generate_report_list_page(lang='en')
            
            # 生成 SPA 核心框架
            generate_html("docs/index.html", lang='zh')
            generate_html("docs/en/index.html", lang='en')
            
            print("\n📌 步骤5: 推送服务...")
            today_str = datetime.now(BJ_TZ).strftime("%Y年%m月%d日")
            send_daily_email(items, today_str)
            send_private_email(items, today_str)
            
            print("\n📌 步骤6: 检查宏观研判触发条件...")
            generate_monthly_report(history_data)
            
            print("\n" + "=" * 50)
            print("✅ 任务圆满完成！")
            print("=" * 50)
        else:
            print("❌ AI 过滤后无结果。")
    else:
        print("❌ 未搜索到新闻。")

if __name__ == "__main__":
    main()
