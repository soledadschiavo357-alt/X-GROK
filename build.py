import os
import re
import json
import datetime
import random
import shutil
import textwrap
from bs4 import BeautifulSoup

# 1. 基础配置
SITE_URL = "https://x-grok.top"
SITE_DOMAIN = "x-grok.top"
TEMPLATES_DIR = "templates"
SOURCE_DIR = "blog"
DEST_DIR = "blog"
OUTPUT_DIR = "." # Root directory
VERSION = str(int(datetime.datetime.now().timestamp()))

# Template paths
LAYOUT_TEMPLATE = os.path.join(TEMPLATES_DIR, "layout.html")
HOME_BODY_TEMPLATE = os.path.join(TEMPLATES_DIR, "home_body.html")
BLOG_INDEX_BODY_TEMPLATE = os.path.join(TEMPLATES_DIR, "blog_index_body.html")
ABOUT_BODY_TEMPLATE = os.path.join(TEMPLATES_DIR, "about_body.html")
SITEMAP_BODY_TEMPLATE = os.path.join(TEMPLATES_DIR, "sitemap_body.html")
POLICIES_BODY_TEMPLATE = os.path.join(TEMPLATES_DIR, "policies_body.html")
SIDEBAR_CARD_TEMPLATE = os.path.join(TEMPLATES_DIR, "sidebar_card.html")
RELATED_POSTS_TEMPLATE = os.path.join(TEMPLATES_DIR, "related_posts.html")
SITEMAP_TEMPLATE_FILE = os.path.join(TEMPLATES_DIR, "sitemap_template.html")

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    if path.endswith(".html"):
        try:
            # Use BeautifulSoup to prettify HTML for consistent formatting
            soup = BeautifulSoup(content, "html.parser")
            
            # Auto-add rel attributes for SEO and security
            for a in soup.find_all('a', href=True):
                href = a['href']
                
                # 1. Soft Routing / Sales Links (Strict protection with 'sponsored')
                if href.startswith('/go/'):
                    a['rel'] = "nofollow sponsored noopener noreferrer"
                
                # 2. General External Links (Standard protection)
                elif href.startswith('http') and SITE_DOMAIN not in href:
                    a['rel'] = "nofollow noopener noreferrer"
            
            content = soup.prettify()
        except Exception as e:
            print(f"Warning: Could not prettify {path}: {e}")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def inject_layout_vars(html, assets_path):
    """Injects assets_path and version into the layout."""
    html = html.replace("{{ assets_path }}", assets_path)
    html = html.replace("{{ version }}", VERSION)
    return html

# 2. 文章元数据提取
def extract_metadata(filename):
    path = os.path.join(SOURCE_DIR, filename)
    content = read_file(path)
    
    # Title
    # Try to find H1 first for the rich title (with HTML tags)
    h1_match = re.search(r'<h1.*?>(.*?)</h1>', content, re.DOTALL)
    title_match = re.search(r'<title>(.*?)</title>', content, re.DOTALL)
    
    if h1_match:
        raw_title = h1_match.group(1).strip()
    elif title_match:
        raw_title = title_match.group(1).split('|')[0].strip()
    else:
        raw_title = "Untitled"
        
    # Clean title for meta tags and <title> element
    clean_title = re.sub(r'<[^>]+>', '', raw_title).strip()
    clean_title = re.sub(r'\s+', ' ', clean_title) # Normalize whitespace
    
    # Description
    # Handle both orders and potential newlines
    desc_match = re.search(r'<meta\s+(?:name="description"\s+content="([^"]*)"|content="([^"]*)"\s+name="description")', content, re.DOTALL)
    if desc_match:
        description = desc_match.group(1) if desc_match.group(1) else desc_match.group(2)
    else:
        description = ""
    
    # Date
    date_match = re.search(r'<time datetime="(.*?)">', content)
    if date_match:
        date_str = date_match.group(1)
    else:
        # Try to find date in text like 2026年1月5日
        date_text_match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)', content)
        if date_text_match:
            date_str = date_text_match.group(1)
        else:
            # Try to find date in text like 📅 2026-01-12
            date_icon_match = re.search(r'📅\s*(\d{4}-\d{2}-\d{2})', content)
            if date_icon_match:
                date_str = date_icon_match.group(1)
            else:
                date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    # URL
    url = f"/blog/{filename.replace('.html', '')}"
    
    # Extract Article Content
    article_match = re.search(r'(<article.*?>.*?</article>)', content, re.DOTALL)
    article_content = article_match.group(1) if article_match else ""
    
    # Remove existing "Related Reading" section (duplicate fix)
    split_markers = [
        '<div class="mt-12 p-8 rounded-2xl bg-white/5 border border-white/10">',
        '<div class="mt-12 pt-8 border-t border-white/10">'
    ]
    
    for marker in split_markers:
        if marker in article_content:
            parts = article_content.split(marker)
            if "相关阅读" in parts[-1]:
                print(f"Removed 'Related Reading' section from {filename}")
                article_content = marker.join(parts[:-1])
                break
    
    if not article_content.strip().endswith("</article>"):
        article_content += "\n</article>"

    # Try to find image for OG tags (first image in article or default)
    image_match = re.search(r'<img.*?src="(.*?)".*?>', article_content)
    image_url = image_match.group(1) if image_match else "/assets/og-cover.png"
    if not image_url.startswith("http"):
        if image_url.startswith("../"):
            image_url = image_url.replace("../", "/")
        elif not image_url.startswith("/"):
            image_url = "/" + image_url
        image_url = SITE_URL + image_url

    # Process Content
    # Simply use the article content as is, assuming it's already well-formatted
    processed_content = article_content

    return {
        "title": raw_title,
        "clean_title": clean_title,
        "description": description,
        "date": date_str,
        "url": url,
        "filename": filename,
        "content": processed_content,
        "full_html": content, 
        "image_url": image_url
    }

def get_all_posts():
    posts = []
    if not os.path.exists(SOURCE_DIR):
        return posts
        
    for filename in os.listdir(SOURCE_DIR):
        if filename.endswith(".html") and filename != "index.html":
            try:
                post = extract_metadata(filename)
                posts.append(post)
            except Exception as e:
                print(f"Error extracting metadata from {filename}: {e}")
    
    def parse_date(d):
        if not d:
            return datetime.datetime.min
        try:
            return datetime.datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            try:
                return datetime.datetime.strptime(d, "%Y年%m月%d日")
            except ValueError:
                # Try handling single digit month/day just in case
                try:
                    return datetime.datetime.strptime(d, "%Y年%-m月%-d日")
                except ValueError:
                    print(f"Warning: Could not parse date '{d}', using min date.")
                    return datetime.datetime.min
    
    posts.sort(key=lambda x: parse_date(x['date']), reverse=True)
    return posts

# 3. 首页构建
def build_home(posts):
    print("Building Home...")
    layout = read_file(LAYOUT_TEMPLATE)
    home_body = read_file(HOME_BODY_TEMPLATE)
    
    blog_posts_html = ""
    for post in posts[:6]:
        tag = "教程"
        tag_color = "slate"
        if "评测" in post['title']:
            tag = "深度评测"
            tag_color = "purple"
        elif "指南" in post['title'] or "怎么" in post['title']:
            tag = "使用指南"
            tag_color = "blue"
        elif "支付" in post['title'] or "购买" in post['title'] or "充值" in post['title']:
            tag = "支付方案"
            tag_color = "gold"
        elif "对比" in post['title'] or "vs" in post['title'].lower():
            tag = "差异对比"
            tag_color = "indigo"
        
        colors = {
            "purple": "bg-purple-500/10 text-purple-400 border border-purple-500/20",
            "blue": "bg-blue-500/10 text-blue-400 border border-blue-500/20",
            "gold": "bg-gold/10 text-gold border border-gold/20",
            "indigo": "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20",
            "slate": "bg-white/10 text-slate-300 border border-white/10"
        }
        badge_class = colors.get(tag_color, colors["slate"])

        blog_posts_html += f'''
        <article class="group relative flex flex-col p-8 rounded-3xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.06] backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_0_30px_-10px_rgba(212,175,55,0.15)] overflow-hidden">
          <div class="absolute top-0 right-0 p-6 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
            <svg class="w-6 h-6 text-gold -rotate-45 group-hover:rotate-0 transition-transform duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
          </div>
          <div class="flex items-center gap-3 mb-4">
            <span class="px-3 py-1 rounded-full text-xs font-medium {badge_class}">{tag}</span>
            <span class="text-xs text-slate-500">{post['date']}</span>
          </div>
          <h3 class="text-xl font-bold text-white mb-3 leading-snug group-hover:text-gold transition-colors">{post['title']}</h3>
          <p class="text-slate-400 text-sm leading-relaxed mb-6 flex-grow line-clamp-3">{post['description']}</p>
          <a href="{post['url']}" class="absolute inset-0 z-10" aria-label="Read article"></a>
        </article>
        '''
    
    home_content = home_body.replace("{{ blog_posts }}", blog_posts_html)
    full_html = layout.replace("{{ content }}", home_content)
    
    # Inject Layout Vars (Root)
    full_html = inject_layout_vars(full_html, "assets/")
    
    home_title = "Grok会员购买与代充平台 - Grok账号开通/共享/独享成品号 | X-Grok.top"
    home_desc = "专业Grok会员代充与账号购买平台。提供Grok 4.1会员独享成品号、Grok会员共享账号(低至¥70/月)、X Premium蓝标认证代开服务。完美解决国内用户Grok会员怎么买、Visa/Mastercard信用卡支付失败等问题，支持支付宝/微信支付，24小时自动发货，安全稳定。"
    home_url = SITE_URL + "/"
    home_image = SITE_URL + "/assets/og-cover.png"
    
    full_html = full_html.replace("{{ title }}", home_title)
    full_html = full_html.replace("{{ description }}", home_desc)
    full_html = full_html.replace("{{ canonical }}", home_url)
    
    home_head_meta = textwrap.dedent(f'''
    <meta name="baidu-site-verification" content="codeva-KQlVH1DEtT" />
    <meta name="keywords" content="Grok会员, Grok会员购买, Grok会员代充, Grok会员价格, Grok会员共享, Grok账号, Grok会员开通, X Premium 蓝标认证, Grok会员升级, Grok会员有什么用">
    <meta name="robots" content="index, follow">
    <meta name="theme-color" content="#000000">
    <meta property="og:type" content="website">
    <meta property="og:title" content="Grok 4.1 超人级 AI | SuperGrok 成品号与升级">
    <meta property="og:description" content="{home_desc}">
    <meta property="og:url" content="{home_url}">
    <meta property="og:image" content="{home_image}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Grok 4.1 超人级 AI | SuperGrok 成品号与升级">
    <meta name="twitter:description" content="{home_desc}">
    <meta name="twitter:image" content="{home_image}">
    ''').strip()
    full_html = full_html.replace("{{ head_meta }}", home_head_meta)
    
    home_schema = {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "WebSite",
          "url": "https://x-grok.top/",
          "name": "X-Grok.top",
          "description": "Grok会员购买与代充平台 - Grok账号开通/共享/独享成品号",
          "potentialAction": {
            "@type": "SearchAction",
            "target": "https://x-grok.top/?q={search_term_string}",
            "query-input": "required name=search_term_string"
          }
        },
        {
          "@type": "Organization",
          "name": "X-Grok.top",
          "url": "https://x-grok.top",
          "logo": "https://x-grok.top/assets/logo.png",
          "description": "专业Grok会员代充与账号购买平台，提供安全稳定的AI工具服务。",
          "areaServed": "World"
        },
        {
          "@type": "Product",
          "name": "Grok 4.1 独享成品号",
          "image": "https://x-grok.top/assets/og-cover.png",
          "description": "Grok 4.1 独享账号，包含 X Premium 蓝标认证。",
          "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.9",
            "reviewCount": "128"
          },
          "review": {
            "@type": "Review",
            "reviewRating": {
              "@type": "Rating",
              "ratingValue": "5"
            },
            "author": {
              "@type": "Person",
              "name": "Liang C."
            },
            "reviewBody": "作为开发者，Grok 4 的代码解释能力真的强。代充速度很快。"
          },
          "offers": {
            "@type": "Offer",
            "price": "250.00",
            "priceCurrency": "CNY",
            "availability": "https://schema.org/InStock",
            "priceValidUntil": "2026-12-31",
            "shippingDetails": {
              "@type": "OfferShippingDetails",
              "shippingRate": {
                "@type": "MonetaryAmount",
                "value": "0",
                "currency": "CNY"
              },
              "shippingDestination": {
                "@type": "DefinedRegion",
                "addressCountry": "CN"
              },
              "deliveryTime": {
                "@type": "ShippingDeliveryTime",
                "handlingTime": {
                  "@type": "QuantitativeValue",
                  "minValue": 0,
                  "maxValue": 0,
                  "unitCode": "DAY"
                },
                "transitTime": {
                  "@type": "QuantitativeValue",
                  "minValue": 0,
                  "maxValue": 0,
                  "unitCode": "DAY"
                }
              }
            },
            "hasMerchantReturnPolicy": {
              "@type": "MerchantReturnPolicy",
              "applicableCountry": "CN",
              "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
              "merchantReturnDays": 7,
              "returnMethod": "https://schema.org/ReturnByMail",
              "returnFees": "https://schema.org/FreeReturn"
            }
          }
        }
      ]
    }
    home_schema_json = json.dumps(home_schema, ensure_ascii=False, indent=2)
    home_schema_script = f'<script type="application/ld+json">\n{home_schema_json}\n</script>'
    full_html = full_html.replace("{{ schema }}", home_schema_script)
    
    # Path Fixes for content
    # 最终方案：使用根相对路径 (Root-Relative)
    full_html = full_html.replace('src="assets/', 'src="/assets/')
    full_html = full_html.replace('href="assets/', 'href="/assets/')
    
    full_html = full_html.replace('href="/"', 'href="/"')
    full_html = full_html.replace('href="/#', 'href="/#')
    full_html = full_html.replace('href="/blog/"', 'href="/blog/"')
    full_html = full_html.replace('href="/blog/', 'href="/blog/')
    full_html = full_html.replace('src="/assets/', 'src="/assets/')
    
    write_file("index.html", full_html)
    print("index.html built.")
    return 1

# 3.5 博客索引页构建 (Blog Index)
def build_blog_index(posts):
    print("Building Blog Index...")
    layout = read_file(LAYOUT_TEMPLATE)
    blog_index_body = read_file(BLOG_INDEX_BODY_TEMPLATE)
    
    blog_grid_html = ""
    for post in posts:
        tag = "教程"
        tag_color = "slate"
        if "评测" in post['title']:
            tag = "深度评测"
            tag_color = "purple"
        elif "指南" in post['title'] or "怎么" in post['title']:
            tag = "使用指南"
            tag_color = "blue"
        elif "支付" in post['title'] or "购买" in post['title'] or "充值" in post['title']:
            tag = "支付方案"
            tag_color = "gold"
        elif "对比" in post['title'] or "vs" in post['title'].lower():
            tag = "差异对比"
            tag_color = "indigo"
        
        colors = {
            "purple": "bg-purple-500/10 text-purple-400 border border-purple-500/20",
            "blue": "bg-blue-500/10 text-blue-400 border border-blue-500/20",
            "gold": "bg-gold/10 text-gold border border-gold/20",
            "indigo": "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20",
            "slate": "bg-white/10 text-slate-300 border border-white/10"
        }
        badge_class = colors.get(tag_color, colors["slate"])
        
        blog_grid_html += f'''
      <article class="group relative flex flex-col p-8 rounded-3xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.06] backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_0_30px_-10px_rgba(212,175,55,0.15)] overflow-hidden" data-category="{tag}">
        <div class="absolute top-0 right-0 p-6 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
          <svg class="w-6 h-6 text-gold -rotate-45 group-hover:rotate-0 transition-transform duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
          </svg>
        </div>
        <div class="flex items-center gap-3 mb-4">
          <span class="px-3 py-1 rounded-full text-xs font-medium {badge_class}">{tag}</span>
          <span class="text-xs text-slate-500">{post['date']}</span>
        </div>
        <h2 class="text-xl font-bold text-white mb-3 leading-snug group-hover:text-gold transition-colors">{post['title']}</h2>
        <p class="text-slate-400 text-sm leading-relaxed mb-6 flex-grow line-clamp-3">{post['description']}</p>
        <a href="{post['url']}" class="absolute inset-0 z-10" aria-label="Read article"></a>
      </article>
        '''

    page_content = blog_index_body.replace("{{ blog_grid }}", blog_grid_html)
    full_html = layout.replace("{{ content }}", page_content)
    
    # Inject Layout Vars (Subdirectory)
    # blog/index.html is inside blog/ folder, so needs ../assets/
    full_html = inject_layout_vars(full_html, "../assets/")
    
    page_title = "Grok 教程导航 | Grok 4.0 使用指南、API 价格与购买评测大全"
    page_desc = "最全的 Grok AI 使用教程合集：涵盖 Grok 4.0/3.0 功能评测、X Premium 账号购买、API 价格对比、DeepSearch 深度搜索技巧及无过滤对话指南。助您快速掌握 xAI 生态。"
    page_url = SITE_URL + "/blog/"
    
    full_html = full_html.replace("{{ title }}", page_title)
    full_html = full_html.replace("{{ description }}", page_desc)
    full_html = full_html.replace("{{ canonical }}", page_url)
    
    head_meta = textwrap.dedent(f'''
    <meta name="keywords" content="Grok教程, Grok 4.0, Grok API价格, Grok账号购买, X Premium代充, DeepSearch技巧, Grok使用指南, xAI评测">
    <meta name="robots" content="index, follow">
    <meta property="og:title" content="{page_title}">
    <meta property="og:description" content="{page_desc}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{page_url}">
    <meta property="og:image" content="{SITE_URL}/assets/og-cover.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:image" content="{SITE_URL}/assets/og-cover.png">
    ''').strip()
    full_html = full_html.replace("{{ head_meta }}", head_meta)
    
    item_list_elements = []
    for i, post in enumerate(posts, 1):
        item_list_elements.append({
            "@type": "ListItem",
            "position": i,
            "url": SITE_URL + post['url'],
            "name": post['title']
        })

    collection_schema = {
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      "name": "Grok 教程导航",
      "url": page_url,
      "mainEntity": {
        "@type": "ItemList",
        "itemListElement": item_list_elements
      }
    }
    
    breadcrumb_schema = {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        { "@type": "ListItem", "position": 1, "name": "首页", "item": SITE_URL + "/" },
        { "@type": "ListItem", "position": 2, "name": "教程导航", "item": page_url }
      ]
    }
    
    schema_json = json.dumps([collection_schema, breadcrumb_schema], ensure_ascii=False, indent=2)
    full_html = full_html.replace("{{ schema }}", f'<script type="application/ld+json">\n{schema_json}\n</script>')
    
    # Path Fixes for /blog/index.html (one level deep)
    # Note: assets/ replacement is handled by inject_layout_vars now for the CSS
    # But for other assets in content, we still need this:
    # 最终方案：使用根相对路径 (Root-Relative)
    full_html = full_html.replace('src="assets/', 'src="/assets/')
    full_html = full_html.replace('href="assets/', 'href="/assets/')
    full_html = full_html.replace('href="/"', 'href="/"')
    full_html = full_html.replace('href="/#', 'href="/#')
    full_html = full_html.replace('href="/blog/"', 'href="/blog/"')
    full_html = full_html.replace('href="/blog/', 'href="/blog/')
    # 特殊修复：确保没有 ../ 或 ./ 残留
    full_html = full_html.replace('href="../', 'href="/')
    full_html = full_html.replace('href="./', 'href="/blog/')
    
    if not os.path.exists(DEST_DIR):
        os.makedirs(DEST_DIR)
    write_file(os.path.join(DEST_DIR, "index.html"), full_html)
    print("blog/index.html built.")
    return 1

# 3.6 关于页构建
def build_about():
    print("Building About Page...")
    layout = read_file(LAYOUT_TEMPLATE)
    about_body = read_file(ABOUT_BODY_TEMPLATE)
    
    full_html = layout.replace("{{ content }}", about_body)
    
    # Inject Layout Vars (Root)
    full_html = inject_layout_vars(full_html, "assets/")
    
    page_title = "关于我们 - X-Grok.top | 专业的 AI 服务提供商"
    page_desc = "X-Grok.top 是一家专业的 AI 服务提供商，致力于消除国内用户使用 Grok AI 的门槛。我们提供安全、稳定、合规的 Grok 4.1 会员账号购买、代充与 X Premium 蓝标认证服务。通过本地化支付方式（支付宝/微信），让您轻松解锁马斯克旗下最强 AI 的全部潜力。"
    page_url = SITE_URL + "/about"
    
    full_html = full_html.replace("{{ title }}", page_title)
    full_html = full_html.replace("{{ description }}", page_desc)
    full_html = full_html.replace("{{ canonical }}", page_url)
    
    full_html = full_html.replace("{{ head_meta }}", "") 
    full_html = full_html.replace("{{ schema }}", "")
    
    write_file(os.path.join(OUTPUT_DIR, "about.html"), full_html)
    print("about.html built.")
    return 1

# 3.7 政策页构建
def build_policies():
    print("Building Policies Page...")
    layout = read_file(LAYOUT_TEMPLATE)
    policies_body = read_file(POLICIES_BODY_TEMPLATE)
    
    full_html = layout.replace("{{ content }}", policies_body)
    
    # Inject Layout Vars (Root)
    full_html = inject_layout_vars(full_html, "assets/")
    
    page_title = "服务条款与隐私政策 | X-Grok.top"
    page_desc = "X-Grok.top 的服务条款、隐私政策及退款说明。我们承诺保障您的账号安全与个人隐私，提供透明的服务流程与售后保障。了解我们的退款政策、账号使用规范及数据保护措施，确保您在购买 Grok 会员服务时享有完整的权益保障与安心体验。"
    page_url = SITE_URL + "/policies"
    
    full_html = full_html.replace("{{ title }}", page_title)
    full_html = full_html.replace("{{ description }}", page_desc)
    full_html = full_html.replace("{{ canonical }}", page_url)
    
    head_meta = '<meta name="robots" content="noindex,follow">'
    full_html = full_html.replace("{{ head_meta }}", head_meta)
    full_html = full_html.replace("{{ schema }}", "")
    
    write_file(os.path.join(OUTPUT_DIR, "policies.html"), full_html)
    print("policies.html built.")
    return 1

# 3.8 智能推荐算法
def get_post_category(post):
    """统一的分类逻辑"""
    title = post['title'].lower()
    if "评测" in title:
        return "深度评测"
    elif "指南" in title or "怎么" in title or "教程" in title:
        return "使用指南"
    elif "支付" in title or "购买" in title or "充值" in title:
        return "支付方案"
    elif "对比" in title or "vs" in title:
        return "差异对比"
    return "教程"

PILLAR_POSTS = []

def recommend_posts(current_post, all_posts, ref_counts):
        """
        智能推荐算法 (Smart Recommendation)
        优先级逻辑：
        1. Tags Overlap (Tags匹配度) - 最高优先级
        2. Incoming Link Count (引用次数) - 均衡调节
        3. Date (发布时间) - 新鲜度
        """
        candidates = []
        current_cat = get_post_category(current_post)
        current_keywords = set(re.findall(r'\w+', current_post['title'].lower()))
        
        # 预处理：计算当前文章的时间戳
        def get_timestamp(date_str):
            try:
                return datetime.datetime.strptime(date_str, "%Y-%m-%d").timestamp()
            except:
                return 0
        
        for p in all_posts:
            if p['filename'] == current_post['filename']:
                continue
                
            # --- 1. 相关性得分 (Base Score) ---
            relevance_score = 0
            
            # 分类匹配 (Tag Overlap - Category)
            if get_post_category(p) == current_cat:
                relevance_score += 10
                
            # 关键词匹配 (Tag Overlap - Keywords)
            p_keywords = set(re.findall(r'\w+', p['clean_title'].lower()))
            common_words = current_keywords.intersection(p_keywords)
            common_words = {w for w in common_words if w not in ['grok', 'ai', '使用', '指南', '教程', '怎么', '是什么']}
            relevance_score += len(common_words) * 5  # 提高关键词权重
            
            # --- 2. 引用均衡得分 (Balancing Score) ---
            # 引用次数越少，得分越高。非线性惩罚，避免初期波动太大
            current_refs = ref_counts.get(p['filename'], 0)
            balance_score = - (current_refs * 3) 
            
            # --- 3. 时间新鲜度得分 (Freshness Score) ---
            # 归一化时间戳，让其影响在 0-2 分之间
            try:
                ts = get_timestamp(p['date'])
                # 假设最近一年的文章
                freshness_score = (ts / 1700000000) * 2 
            except:
                freshness_score = 0
                
            # --- 最终总分 ---
            # 权重：相关性 > 均衡性 > 新鲜度
            final_score = relevance_score + balance_score + freshness_score + random.random() * 0.5
            
            candidates.append((final_score, p))
        
        # 按总分降序排序
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        # 返回前4篇
        return [c[1] for c in candidates[:4]]

# 4. 文章详情页构建
def build_posts_pages(posts):
    print("Building Post Pages...")
    layout = read_file(LAYOUT_TEMPLATE)
    sidebar_card = read_file(SIDEBAR_CARD_TEMPLATE)
    related_template = read_file(RELATED_POSTS_TEMPLATE)
    
    # 初始化引用计数器
    ref_counts = {p['filename']: 0 for p in posts}
    
    count = 0
    for post in posts:
        # 使用智能推荐算法替代随机采样
        related_sample = recommend_posts(post, posts, ref_counts)
        
        # 更新引用计数
        for rp in related_sample:
            ref_counts[rp['filename']] += 1
        
        related_items_html = ""
        for rp in related_sample:
            related_items_html += f'''
            <a href="{rp['url']}" class="group p-4 rounded-xl bg-white/5 border border-white/10 hover:border-gold/30 transition-all">
              <h4 class="text-gold font-bold mb-2 group-hover:text-white transition-colors">{rp['title']}</h4>
              <p class="text-xs text-slate-400 line-clamp-2">{rp['description']}</p>
            </a>
            '''
        
        related_html = related_template.replace("{{ related_items }}", related_items_html)
        
        page_content = f'''
        <div class="max-w-7xl mx-auto px-4 pt-32 pb-12 grid grid-cols-1 lg:grid-cols-3 gap-12">
            <main class="lg:col-span-2">
                <div class="article-card">
                    {post['content']}
                </div>
                
                {related_html}
            </main>
            <aside class="hidden lg:block lg:col-span-1">
                {sidebar_card}
            </aside>
        </div>
        '''
        
        full_html = layout.replace("{{ content }}", page_content)
        
        # Inject Layout Vars (Subdirectory)
        full_html = inject_layout_vars(full_html, "../assets/")
        
        post_title = f"{post['clean_title']} | X-Grok.Top"
        post_url = f"{SITE_URL}{post['url']}"
        full_html = full_html.replace("{{ title }}", post_title)
        full_html = full_html.replace("{{ description }}", post['description'])
        full_html = full_html.replace("{{ canonical }}", post_url)
        
        post_head_meta = textwrap.dedent(f'''
        <meta name="keywords" content="{post['clean_title']}, Grok教程, Grok会员, X-Grok">
        <meta name="robots" content="index, follow">
        <meta name="theme-color" content="#000000">
        <meta property="og:type" content="article">
        <meta property="og:title" content="{post['clean_title']}">
        <meta property="og:description" content="{post['description']}">
        <meta property="og:url" content="{post_url}">
        <meta property="og:image" content="{post['image_url']}">
        <meta name="twitter:card" content="summary_large_image">
        <meta name="twitter:title" content="{post['clean_title']}">
        <meta name="twitter:description" content="{post['description']}">
        <meta name="twitter:image" content="{post['image_url']}">
        ''').strip()
        full_html = full_html.replace("{{ head_meta }}", post_head_meta)
        
        article_schema = {
          "@context": "https://schema.org",
          "@type": "Article",
          "headline": post['clean_title'],
          "image": post['image_url'],
          "author": { "@type": "Organization", "name": "X-Grok Team" },
          "publisher": { "@type": "Organization", "name": "X-Grok.top" },
          "datePublished": post['date'],
          "description": post['description']
        }
        
        breadcrumb_schema = {
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          "itemListElement": [
            { "@type": "ListItem", "position": 1, "name": "首页", "item": SITE_URL + "/" },
            { "@type": "ListItem", "position": 2, "name": "教程导航", "item": SITE_URL + "/blog/" },
            { "@type": "ListItem", "position": 3, "name": post['title'], "item": post_url }
          ]
        }
        
        schema_json = json.dumps([article_schema, breadcrumb_schema], ensure_ascii=False, indent=2)
        schema_script = f'<script type="application/ld+json">\n{schema_json}\n</script>'
        full_html = full_html.replace("{{ schema }}", schema_script)
        
        # Path Fixes for content
        # 最终方案：使用根相对路径 (Root-Relative)
        full_html = full_html.replace('src="assets/', 'src="/assets/')
        full_html = full_html.replace('href="assets/', 'href="/assets/')
        
        full_html = full_html.replace('href="/"', 'href="/"')
        full_html = full_html.replace('href="/#', 'href="/#')
        full_html = full_html.replace('href="/blog/"', 'href="/blog/"')
        full_html = full_html.replace('href="/blog/', 'href="/blog/')
        full_html = full_html.replace('src="/assets/', 'src="/assets/')
        # 特殊修复：确保没有 ../ 或 ./ 残留
        full_html = full_html.replace('href="../', 'href="/')
        full_html = full_html.replace('href="./', 'href="/blog/')
        
        if not os.path.exists(DEST_DIR):
            os.makedirs(DEST_DIR)
        write_file(os.path.join(DEST_DIR, post['filename']), full_html)
        print(f"Built {post['filename']}")
        count += 1
    return count

# 5. Sitemap 构建
def build_sitemap(posts):
    print("Building Sitemap...")
    layout = read_file(LAYOUT_TEMPLATE)
    sitemap_body = read_file(SITEMAP_BODY_TEMPLATE)
    
    sitemap_list_html = ""
    for post in posts:
        sitemap_list_html += f'''
        <li class="sitemap-item">
            <a href="{post["url"]}">
                <span class="block truncate">{post["clean_title"]}</span>
                <span class="text-xs text-slate-500 mt-1 block">{post["date"]}</span>
            </a>
        </li>
        '''
    
    full_html = layout.replace("{{ content }}", sitemap_body)
    full_html = full_html.replace("{{ sitemap_list }}", sitemap_list_html)
    
    # Inject Layout Vars (Root)
    full_html = inject_layout_vars(full_html, "assets/")
    
    page_title = "网站地图 - X-Grok.top"
    page_url = SITE_URL + "/sitemap"
    
    full_html = full_html.replace("{{ title }}", page_title)
    full_html = full_html.replace("{{ description }}", "X-Grok.top 网站全站地图索引。一站式快速查找 Grok 4.1 会员购买渠道、账号代充服务、使用教程指南、API 深度评测、DeepSearch 技巧及常见问题解答等所有页面链接，助您高效浏览并获取所需信息。")
    full_html = full_html.replace("{{ canonical }}", page_url)
    full_html = full_html.replace("{{ head_meta }}", '<meta name="robots" content="index, follow">')
    full_html = full_html.replace("{{ schema }}", "")
    
    write_file(os.path.join(OUTPUT_DIR, "sitemap.html"), full_html)
    
    # XML Sitemap
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    # Define pages with specific frequencies and priorities
    static_pages_config = [
        {"loc": "", "freq": "weekly", "prio": "1.0"},
        {"loc": "about", "freq": "monthly", "prio": "0.8"},
        {"loc": "blog/", "freq": "weekly", "prio": "0.9"},
        {"loc": "sitemap", "freq": "weekly", "prio": "0.5"},
        {"loc": "policies", "freq": "monthly", "prio": "0.5"}
    ]
    
    for p_conf in static_pages_config:
        sitemap_xml += f"""  <url>
    <loc>{SITE_URL}/{p_conf['loc']}</loc>
    <changefreq>{p_conf['freq']}</changefreq>
    <priority>{p_conf['prio']}</priority>
  </url>\n"""

    for post in posts:
        clean_url = post['url'].replace('.html', '')
        sitemap_xml += f"""  <url>
    <loc>{SITE_URL}{clean_url}</loc>
    <lastmod>{post['date']}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>\n"""
        
    sitemap_xml += '</urlset>'
    write_file(os.path.join(OUTPUT_DIR, "sitemap.xml"), sitemap_xml)
    
    print("Sitemaps built.")
    return 2

def main():
    print("Starting Build Process...")
    posts = get_all_posts()
    print(f"Found {len(posts)} posts.")
    
    total_files = 0
    total_files += build_home(posts)
    total_files += build_about()
    total_files += build_policies()
    total_files += build_blog_index(posts)
    total_files += build_posts_pages(posts)
    total_files += build_sitemap(posts)
    
    print(f"Build Complete! Generated {total_files} files.")
    
    if os.path.exists("preview_card.html"):
        os.remove("preview_card.html")
        print("Removed preview_card.html (cleanup)")

if __name__ == "__main__":
    main()
