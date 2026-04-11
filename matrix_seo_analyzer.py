import pandas as pd
import jieba
from collections import Counter
import re
import datetime
import os
import glob
import json
from urllib.parse import urlparse

# ==========================================
# 1. 智能数据加载与清洗 
# ==========================================
def clean_metric(x):
    if pd.isna(x): return 0
    x_str = str(x).strip()
    has_percent = '%' in x_str
    x_clean = x_str.replace('%', '').replace(',', '')
    try:
        val = float(x_clean)
        if not has_percent and val <= 1.0 and '.' in x_str:
            return val * 100
        return val
    except:
        return 0

def load_gsc_data():
    data = {}
    query_files = glob.glob("*查询数*.csv")
    page_files = glob.glob("*网页*.csv")
    date_files = glob.glob("*图表*.csv") 
    
    if query_files and page_files and date_files:
        try:
            data['queries'] = pd.read_csv(query_files[0])
            data['pages'] = pd.read_csv(page_files[0])
            data['dates'] = pd.read_csv(date_files[0])
            return data
        except Exception as e:
            print(f"❌ 读取 CSV 失败: {e}")
            return None
    print("❌ 找不到完整的 GSC 数据文件！")
    return None

# ==========================================
# 2. 通用型意图分类与词频引擎
# ==========================================
def classify_intent(keyword):
    keyword = str(keyword).lower()
    transactional = ['下载', 'apk', '购买', '钱', '价格', '充值', '会员', '升级', '订阅', '账号', '共享', 'api', '多少钱', '哪买', '买', '代购', '费用']
    informational = ['教程', '怎么', '解决', '指南', '报错', '为什么', '什么', '代码', '对比', '区别', '如何', '技巧', '评测', '介绍']
    navigational = ['官网', '入口', '网页版', '登录', '网址', 'app', '官方']

    if any(p in keyword for p in transactional): return "💰 转化意图"
    elif any(p in keyword for p in informational): return "🚦 信息意图"
    elif any(p in keyword for p in navigational): return "🧭 导航意图"
    else: return "🔍 泛需求探索"

def get_top_words(queries, domain_name):
    stop_words = {'怎么', '的', '是', '在', '了', '如何', '个', '包', '版', '安装', '使用', '什么', '国内', '苹果', '安卓', '怎么用'}
    brand_parts = re.split(r'[-.]', domain_name.lower())
    stop_words.update(brand_parts)
    words = []
    for kw in queries.dropna():
        words.extend([w for w in jieba.lcut(str(kw).lower()) if len(w) > 1 and w not in stop_words and not re.search(r'\d', w)])
    return dict(Counter(words).most_common(12))

# ==========================================
# 3. 深度专业诊断引擎
# ==========================================
def query_action_engine(row):
    imp, pos, ctr = row['展示'], row['排名'], row['点击率']
    if pos <= 10 and ctr < 3.0 and imp > 50: 
        return "<span class='badge bg-danger'>🔴 漏水紧急</span>", "重写标题/描述"
    elif 11 <= pos <= 20 and imp > 30: 
        return "<span class='badge bg-warning text-dark'>🟡 临门一脚</span>", "加权重内链"
    elif pos > 20 and imp > 50: 
        return "<span class='badge bg-info text-dark'>🔵 内容缺口</span>", "新建独立文章"
    elif pos <= 10 and ctr >= 3.0: 
        return "<span class='badge bg-success'>🟢 核心健康</span>", "保持观察"
    return "<span class='badge bg-secondary'>⚪ 常规词</span>", "自然沉淀"

def page_action_engine(row):
    imp, pos, ctr = row['展示'], row['排名'], row['点击率']
    if pos <= 10 and ctr < 2.0 and imp > 100: 
        return "<span class='badge bg-danger'>🔴 CTR 严重不达标</span>", "<b>专业建议：</b>Title 缺乏诱惑力，尝试加入数字、年份[2026]或痛点词；检查 Description 是否匹配需求。"
    elif 11 <= pos <= 20 and imp > 50: 
        return "<span class='badge bg-warning text-dark'>🟡 第二页潜力股</span>", "<b>专业建议：</b>在全站流量 Top3 的老文章中，增加指向该页面的锚文本内链。"
    elif pos > 20 and imp > 100:
        return "<span class='badge bg-info text-dark'>🔵 排名低迷</span>", "<b>专业建议：</b>页面内容可能过薄（Thin Content）。建议扩充字数至 1500 字以上，或增加图片/视频。"
    elif pos <= 10 and ctr >= 5.0:
        return "<span class='badge bg-success'>🟢 高效提款机</span>", "<b>专业建议：</b>流量极佳。请重点检查该页面的“转化漏斗”，确保购买/下载/注册按钮非常显眼。"
    return "<span class='badge bg-secondary'>⚪ 表现平稳</span>", "流量正常，按原计划持续观察数据变化即可。"

# ==========================================
# 4. 生成完美大盘
# ==========================================
def generate_dashboard():
    print("⏳ 正在进行全量数据计算与 AI 洞察分析...")
    raw_data = load_gsc_data()
    if not raw_data: return

    q_df, p_df, d_df = raw_data['queries'], raw_data['pages'], raw_data['dates']
    sample_url = p_df['排名靠前的网页'].dropna().iloc[0] if '排名靠前的网页' in p_df.columns else ""
    site_domain = urlparse(str(sample_url)).netloc if "http" in str(sample_url) else "MySite"

    for df in [q_df, p_df, d_df]:
        df['展示'] = df['展示'].apply(clean_metric).astype(int)
        df['点击次数'] = df['点击次数'].apply(clean_metric).astype(int)
        df['点击率'] = df['点击率'].apply(clean_metric)
        if '排名' in df.columns: df['排名'] = df['排名'].apply(clean_metric)

    true_impressions = d_df['展示'].sum()
    true_clicks = d_df['点击次数'].sum()
    true_ctr = (true_clicks / true_impressions * 100) if true_impressions > 0 else 0
    dates_trend = d_df.sort_values('日期').tail(14)
    
    q_df['意图'] = q_df['热门查询'].apply(classify_intent)
    intent_counts = q_df['意图'].value_counts().to_dict()
    word_freq = get_top_words(q_df['热门查询'], site_domain)

    q_df[['状态', '核心动作']] = q_df.apply(lambda row: pd.Series(query_action_engine(row)), axis=1)
    p_df[['状态', '执行建议']] = p_df.apply(lambda row: pd.Series(page_action_engine(row)), axis=1)

    # 🚀 挖掘机数据
    valid_seeds_df = q_df[q_df['意图'] != '🧭 导航意图'].sort_values('展示', ascending=False).head(100)
    seeds_list = valid_seeds_df['热门查询'].tolist()
    seeds_text = "\n".join(seeds_list) if seeds_list else "⚠️ 暂无数据"
    seeds_count = len(seeds_list)
    seed_intent_counts = valid_seeds_df['意图'].value_counts().to_dict() if seeds_list else {}
    top_10_seeds = valid_seeds_df.head(10).to_dict('records') if seeds_list else []

    top10_html = ""
    for idx, item in enumerate(top_10_seeds):
        badge_color = "bg-danger" if idx < 3 else "bg-secondary"
        top10_html += f'<li class="list-group-item bg-transparent px-0 d-flex justify-content-between align-items-center border-bottom border-light"><div class="text-truncate" style="max-width: 70%;"><span class="badge {badge_color} rounded-circle me-2">{idx+1}</span><span class="fw-bold">{item["热门查询"]}</span></div><span class="text-muted small">曝光: {item["展示"]}</span></li>'

    # ==========================================
    # 🤖 AI 智能总结与交叉匹配提取真实 URL
    # ==========================================
    page1_count = len(q_df[q_df['排名'] <= 10])
    page2_count = len(q_df[(q_df['排名'] > 10) & (q_df['排名'] <= 20)])
    overall_health = "健康" if true_ctr >= 3.0 else ("亚健康" if true_ctr >= 1.0 else "漏水严重")
    health_color = "success" if true_ctr >= 3.0 else ("warning" if true_ctr >= 1.0 else "danger")
    
    action_counts = q_df['核心动作'].value_counts()
    need_title_fix = action_counts.get('重写标题/描述', 0)
    need_links = action_counts.get('加权重内链', 0)
    need_new_content = action_counts.get('新建独立文章', 0)

    # 💡 核心升级：从 p_df 中提取真实的 URL 放入总结框！
    bad_title_urls = []
    for _, row in p_df[p_df['状态'].str.contains('🔴')].sort_values('展示', ascending=False).head(3).iterrows():
        path = urlparse(str(row['排名靠前的网页'])).path
        path = path if path and path != "/" else "首页(/)"
        bad_title_urls.append(f"<a href='{row['排名靠前的网页']}' target='_blank' class='fw-bold text-danger text-decoration-none'>{path}</a>")
    bad_title_str = "、".join(bad_title_urls) if bad_title_urls else "暂无"

    need_link_urls = []
    for _, row in p_df[p_df['状态'].str.contains('🟡')].sort_values('展示', ascending=False).head(3).iterrows():
        path = urlparse(str(row['排名靠前的网页'])).path
        path = path if path and path != "/" else "首页(/)"
        need_link_urls.append(f"<a href='{row['排名靠前的网页']}' target='_blank' class='fw-bold text-warning text-dark text-decoration-none'>{path}</a>")
    need_link_str = "、".join(need_link_urls) if need_link_urls else "暂无"

    # ==========================================
    # 组装 HTML 表格
    # ==========================================
    actionable_queries = q_df[q_df['核心动作'] != '自然沉淀'].sort_values('展示', ascending=False)
    query_html = ""
    for _, row in actionable_queries.iterrows():
        kw = row["热门查询"]
        search_link = f"https://www.google.com/search?q=site:{site_domain}+{kw}"
        query_html += f'<tr><td class="fw-bold">{kw}</td><td>{row["展示"]}</td><td>#{row["排名"]:.1f}</td><td class="text-secondary">{row["点击率"]:.2f}%</td><td>{row["状态"]}</td><td class="fw-bold text-primary">{row["核心动作"]}</td><td><a href="{search_link}" target="_blank" class="btn btn-sm btn-outline-secondary">🔍 查对应网页</a></td></tr>'

    # ✨ 核心升级：将这里改为输出 p_df 的【所有】数据，实现全量网页诊断！
    all_diagnosed_pages = p_df.sort_values('展示', ascending=False)
    page_html = ""
    for _, row in all_diagnosed_pages.iterrows():
        raw_url = str(row["排名靠前的网页"])
        parsed_url = urlparse(raw_url)
        url_display = parsed_url.path if parsed_url.path and parsed_url.path != "/" else "首页 (/)"
        page_html += f'<tr><td style="max-width:250px; word-wrap:break-word;"><a href="{raw_url}" target="_blank" class="text-decoration-none fw-bold text-primary">{url_display}</a></td><td>{row["展示"]}</td><td>#{row["排名"]:.1f}</td><td class="fw-bold text-secondary">{row["点击率"]:.2f}%</td><td>{row["状态"]}</td><td class="text-dark small">{row["执行建议"]}</td></tr>'

    deep_dive_html = ""
    for _, row in q_df.sort_values('展示', ascending=False).iterrows():
        kw = row["热门查询"]
        search_link = f"https://www.google.com/search?q=site:{site_domain}+{kw}"
        deep_dive_html += f'<tr><td>{kw}</td><td class="text-primary fw-bold">{row["展示"]}</td><td>{row["点击次数"]}</td><td>#{row["排名"]:.1f}</td><td>{row["点击率"]:.2f}%</td><td>{row["意图"]}</td><td><a href="{search_link}" target="_blank" class="text-decoration-none">🔍 查网页</a></td></tr>'

    # 渲染最终 HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <title>{site_domain} - 矩阵流量分析台</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <link href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #f4f6f9; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
            .card {{ border: none; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.04); margin-bottom: 24px; }}
            .kpi-card {{ position: relative; overflow: hidden; padding: 20px; transition: transform 0.2s; }}
            .kpi-icon {{ position: absolute; right: -10px; bottom: -15px; font-size: 5rem; opacity: 0.1; }}
            .chart-container {{ position: relative; height: 250px; width: 100%; }}
            .nav-tabs .nav-link.active {{ font-weight: bold; border-bottom: 3px solid #0d6efd; color: #0d6efd !important; }}
            .seed-box {{ background-color: #2b3035; color: #20c997; font-family: monospace; padding: 15px; border-radius: 8px; height: 320px; overflow-y: auto; white-space: pre-wrap; }}
            .custom-scrollbar::-webkit-scrollbar {{ width: 6px; }}
            .custom-scrollbar::-webkit-scrollbar-track {{ background: transparent; }}
            .custom-scrollbar::-webkit-scrollbar-thumb {{ background-color: #dee2e6; border-radius: 10px; }}
            .ai-summary-box {{ border-left: 5px solid #0d6efd; background: linear-gradient(90deg, #f8f9fa 0%, #ffffff 100%); }}
        </style>
    </head>
    <body class="pb-5">
        <nav class="navbar navbar-dark bg-dark mb-4 shadow">
            <div class="container-fluid px-4"><a class="navbar-brand fw-bold" href="#"><i class="fa-solid fa-server text-success me-2"></i>{site_domain} - 自动化 SEO 增长中台</a></div>
        </nav>

        <div class="container-fluid px-4">
            
            <div class="row mb-2">
                <div class="col-md-3"><div class="card kpi-card bg-primary text-white"><i class="fa-solid fa-hand-pointer kpi-icon"></i><h6 class="opacity-75">总点击次数</h6><h2 class="mb-0 fw-bold">{true_clicks:,}</h2></div></div>
                <div class="col-md-3"><div class="card kpi-card bg-info text-white"><i class="fa-solid fa-eye kpi-icon"></i><h6 class="opacity-75">总需求曝光</h6><h2 class="mb-0 fw-bold">{true_impressions:,}</h2></div></div>
                <div class="col-md-3"><div class="card kpi-card bg-{health_color} text-white"><i class="fa-solid fa-bullseye kpi-icon"></i><h6 class="opacity-75">全局平均 CTR ({overall_health})</h6><h2 class="mb-0 fw-bold">{true_ctr:.2f}%</h2></div></div>
                <div class="col-md-3"><div class="card kpi-card bg-dark text-white"><i class="fa-solid fa-rocket kpi-icon"></i><h6 class="opacity-75">全站收录总词数</h6><h2 class="mb-0 fw-bold text-warning">{len(q_df)} 个</h2></div></div>
            </div>

            <div class="card p-3 mb-4 ai-summary-box">
                <h5 class="fw-bold text-dark mb-2"><i class="fa-solid fa-robot text-primary"></i> AI 首席诊断官报告 (Executive Summary)</h5>
                <p class="mb-0 text-secondary" style="font-size: 1.05em; line-height: 1.6;">
                    经过系统扫描，您的网站目前共有 <strong class="text-success">{page1_count} 个</strong> 关键词稳居谷歌首页（前10名）。
                    同时，有 <strong class="text-warning">{page2_count} 个</strong> 关键词正处于第二页（11-20名）的冲刺期，这是本期<b>性价比最高的流量增长点</b>。
                    整体来看，网站 CTR 表现评级为 <span class="badge bg-{health_color}">{overall_health}</span>。
                </p>
            </div>

            <div class="row">
                <div class="col-md-5"><div class="card p-3"><h6 class="text-secondary mb-3"><i class="fa-solid fa-chart-line"></i> 最近 14 天曝光趋势</h6><div class="chart-container"><canvas id="trendChart"></canvas></div></div></div>
                <div class="col-md-3"><div class="card p-3"><h6 class="text-secondary mb-3"><i class="fa-solid fa-chart-pie"></i> 搜索意图分布</h6><div class="chart-container"><canvas id="intentChart"></canvas></div></div></div>
                <div class="col-md-4"><div class="card p-3"><h6 class="text-secondary mb-3"><i class="fa-solid fa-brain"></i> 核心需求词云</h6><div class="chart-container"><canvas id="wordChart"></canvas></div></div></div>
            </div>

            <div class="card p-4 mt-2">
                <ul class="nav nav-tabs mb-4" id="dataTabs" role="tablist">
                    <li class="nav-item"><button class="nav-link active text-secondary" data-bs-toggle="tab" data-bs-target="#query-audit"><i class="fa-solid fa-fire me-1"></i>急需优化词</button></li>
                    <li class="nav-item"><button class="nav-link text-secondary" data-bs-toggle="tab" data-bs-target="#page-audit"><i class="fa-solid fa-stethoscope me-1"></i>网页深度诊断 (全量)</button></li>
                    <li class="nav-item"><button class="nav-link text-primary fw-bold" data-bs-toggle="tab" data-bs-target="#seeds-export" onclick="setTimeout(()=>window.dispatchEvent(new Event('resize')), 100);"><i class="fa-solid fa-code-branch me-1"></i>🚀 挖掘机对接</button></li>
                    <li class="nav-item"><button class="nav-link text-success fw-bold" data-bs-toggle="tab" data-bs-target="#deep-dive"><i class="fa-solid fa-database me-1"></i>🗄️ 全量词库</button></li>
                </ul>
                <div class="tab-content">
                    
                    <div class="tab-pane fade show active" id="query-audit">
                        <div class="alert alert-primary bg-opacity-10 border-primary mb-4">
                            <h6 class="fw-bold"><i class="fa-solid fa-calendar-check text-primary"></i> 🎯 本周核心行动清单与直达链接：</h6>
                            <ul class="mb-0 small" style="line-height: 2;">
                                <li>发现 <b class="text-danger">{need_title_fix} 个</b> 在首页但无人点击的词。👉 <b>优先修改网页标题：</b> [{bad_title_str}] </li>
                                <li>发现 <b class="text-warning">{need_links} 个</b> 排在第二页的潜力词。👉 <b>优先增加站内链接：</b> [{need_link_str}] </li>
                                <li>发现 <b class="text-info">{need_new_content} 个</b> 高热度市场缺口词。👉 <b>去“🚀 挖掘机对接”页提取种子，新建文章。</b></li>
                            </ul>
                        </div>
                        <table id="tableQueryAudit" class="table table-hover align-middle w-100 table-striped">
                            <thead class="table-dark"><tr><th>用户搜索词</th><th>曝光量</th><th>排名</th><th>点击率</th><th>状态</th><th>👉 优化指令</th><th>长尾验证(找网页)</th></tr></thead>
                            <tbody>{query_html}</tbody>
                        </table>
                    </div>
                    
                    <div class="tab-pane fade" id="page-audit">
                        <div class="alert alert-secondary border-secondary mb-3">
                            <i class="fa-solid fa-circle-info"></i> <b>全站资产体检单：</b> 此处已列出 GSC 抓取到的<b>全量 {len(p_df)} 个</b> 网页。AI 已经对每一个页面出具了诊断报告。
                        </div>
                        <table id="tablePageAudit" class="table table-hover align-middle w-100 table-striped">
                            <thead class="table-light"><tr><th>网页相对路径</th><th>曝光量</th><th>平均排名</th><th>点击率</th><th>状态</th><th>🔧 SEO 专业修补建议</th></tr></thead>
                            <tbody>{page_html}</tbody>
                        </table>
                    </div>

                    <div class="tab-pane fade" id="seeds-export">
                        <div class="row">
                            <div class="col-md-7">
                                <h5 class="fw-bold"><i class="fa-solid fa-seedling text-success"></i> 挖掘机高潜力种子词 ({seeds_count}个)</h5>
                                <div class="seed-box custom-scrollbar" id="seedText">{seeds_text}</div>
                                <button class="btn btn-primary mt-3" onclick="copySeeds()"><i class="fa-solid fa-copy"></i> 一键全部复制</button>
                            </div>
                            <div class="col-md-5">
                                <div class="card bg-light border-0 p-3 mb-3">
                                    <h6 class="fw-bold text-dark mb-2"><i class="fa-solid fa-chart-pie text-primary"></i> 种子词属性分布</h6>
                                    <div class="chart-container" style="height: 120px;"><canvas id="seedIntentChart"></canvas></div>
                                </div>
                                <div class="card bg-light border-0 p-3">
                                    <h6 class="fw-bold text-danger mb-2"><i class="fa-solid fa-fire text-danger"></i> Top 10 绝对金矿词 (滑动查看)</h6>
                                    <ul class="list-group list-group-flush bg-transparent custom-scrollbar" style="max-height: 180px; overflow-y: auto; padding-right: 5px;">
                                        {top10_html}
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="tab-pane fade" id="deep-dive">
                        <table id="tableDeepDive" class="table table-hover align-middle w-100 table-striped">
                            <thead class="table-dark"><tr><th>完整搜索词</th><th>曝光量</th><th>点击次数</th><th>当前排名</th><th>点击率</th><th>分析意图</th><th>定位网页</th></tr></thead>
                            <tbody>{deep_dive_html}</tbody>
                        </table>
                    </div>

                </div>
            </div>
        </div>

        <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <script>
            $(document).ready(function() {{
                $('#tableQueryAudit').DataTable({{ "order": [[ 1, "desc" ]], "pageLength": 10 }});
                // 网页审计表现在是全量数据了，调整默认行数
                $('#tablePageAudit').DataTable({{ "order": [[ 1, "desc" ]], "pageLength": 15, "language": {{ "search": "🔎 搜索网页:" }} }});
                $('#tableDeepDive').DataTable({{ "order": [[ 1, "desc" ]], "pageLength": 20, "language": {{ "search": "🔎 词库搜索:" }} }});
            }});

            function copySeeds() {{
                var text = document.getElementById("seedText").innerText;
                navigator.clipboard.writeText(text).then(function() {{ alert("✅ 种子词复制成功！"); }});
            }}

            new Chart(document.getElementById('trendChart'), {{ type: 'line', data: {{ labels: {json.dumps(dates_trend['日期'].tolist())}, datasets: [{{ label: '展示次数', data: {json.dumps(dates_trend['展示'].tolist())}, borderColor: '#20c997', backgroundColor: 'rgba(32, 201, 151, 0.1)', tension: 0.3, fill: true }}] }}, options: {{ maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }} }} }});
            new Chart(document.getElementById('intentChart'), {{ type: 'doughnut', data: {{ labels: {json.dumps(list(intent_counts.keys()))}, datasets: [{{ data: {json.dumps(list(intent_counts.values()))}, backgroundColor: ['#fd7e14', '#198754', '#6c757d', '#0dcaf0'] }}] }}, options: {{ maintainAspectRatio: false, cutout: '60%', plugins: {{ legend: {{ position: 'right' }} }} }} }});
            new Chart(document.getElementById('wordChart'), {{ type: 'bar', data: {{ labels: {json.dumps(list(word_freq.keys()))}, datasets: [{{ label: '词频', data: {json.dumps(list(word_freq.values()))}, backgroundColor: '#6f42c1', borderRadius: 4 }}] }}, options: {{ maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ grid: {{ display: false }} }} }} }} }});
            new Chart(document.getElementById('seedIntentChart'), {{ type: 'pie', data: {{ labels: {json.dumps(list(seed_intent_counts.keys()))}, datasets: [{{ data: {json.dumps(list(seed_intent_counts.values()))}, backgroundColor: ['#0d6efd', '#ffc107', '#198754'] }}] }}, options: {{ maintainAspectRatio: false, plugins: {{ legend: {{ position: 'right' }} }} }} }});
        </script>
    </body>
    </html>
    """
    
    safe_domain_name = site_domain.replace(".", "_")
    output_file = f"SEO_终极控制台_{safe_domain_name}.html"
    with open(output_file, "w", encoding="utf-8") as f: f.write(html)
    print(f"✅ 满配大屏幕已经生成：{output_file}")

if __name__ == "__main__":
    generate_dashboard()