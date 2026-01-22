import os
import sys
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections import defaultdict

# Colors
class Colors:
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_error(msg):
    print(f"{Colors.RED}{msg}{Colors.RESET}")

def print_warning(msg):
    print(f"{Colors.YELLOW}{msg}{Colors.RESET}")

# Check dependencies
try:
    from bs4 import BeautifulSoup
except ImportError:
    print_error("❌ 错误: 环境中未找到 beautifulsoup4 库。")
    print_error("请运行以下命令安装:")
    print(f"{Colors.BOLD}pip install beautifulsoup4{Colors.RESET}")
    sys.exit(1)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Configuration
ROOT_DIR = "."
SITE_DOMAIN = "x-grok.top"
SITE_URL = f"https://{SITE_DOMAIN}"
CONVERSION_KEYWORDS = ["Grok 4.1 独享成品号", "sidebar_card", "sidebar-card"]
IGNORE_PREFIXES = ["/go/", "/legal"] # Ignore these paths for 404 checks
SKIP_FILES = ["404.html", "googlea685aa8ff3686b48.html"]

# Data structures
all_html_files = set()
linked_pages = set()
inbound_links = defaultdict(list) # target_page -> [source_pages]
external_links_map = defaultdict(list) # external_url -> [source_pages]
unsafe_external_links = defaultdict(set) # external_url -> {source_pages_with_issues}
soft_routing_map = defaultdict(list) # soft_route -> [source_pages]
clean_url_issues = []
redirect_issues = [] # (source_page, link_url, status_code, final_url)
sitemap_xml_urls = set()
sitemap_html_urls = set()
errors = []
warnings = []
sitemap_warnings = []
stats = {
    "pages_scanned": 0,
    "internal_links": 0,
    "external_links": 0,
}
# Cache for redirect checks to avoid repeated requests
link_status_cache = {} 

def get_html_files(root_dir):
    files = []
    # Explicitly check root files
    with os.scandir(root_dir) as entries:
        for entry in entries:
            if entry.is_file() and entry.name.endswith('.html'):
                files.append(entry.name)
    
    # Check blog directory
    blog_dir = os.path.join(root_dir, 'blog')
    if os.path.exists(blog_dir):
        for entry in os.scandir(blog_dir):
            if entry.is_file() and entry.name.endswith('.html'):
                files.append(os.path.join('blog', entry.name))
                
    return files

def normalize_path(path):
    return path.replace("\\", "/")

def resolve_link(source_file, link):
    if link.startswith("http") or link.startswith("//"):
        return None
    
    if link.startswith("#") or link.startswith("mailto:") or link.startswith("tel:") or link.startswith("javascript:"):
        return "IGNORED"

    # Remove query string and fragment
    link = link.split("?")[0].split("#")[0]
    
    if not link:
        return None
        
    # Check ignore prefixes
    for prefix in IGNORE_PREFIXES:
        if link.startswith(prefix):
            return "IGNORED"

    if link.startswith("/"):
        target_path = link[1:]
    else:
        source_dir = os.path.dirname(source_file)
        target_path = os.path.join(source_dir, link)
    
    target_path = os.path.normpath(target_path)
    return normalize_path(target_path)

def inspect_link(url):
    """
    Check the status code of a link. Returns (status_code, final_url).
    """
    if not HAS_REQUESTS:
        return (None, None)
        
    if url in link_status_cache:
        return link_status_cache[url]
        
    try:
        # We use allow_redirects=False first to catch the redirect code
        # But requests.head might follow if we don't set it.
        # Actually, to check 'efficiency', we want to know if it redirects.
        response = requests.head(url, allow_redirects=False, timeout=5)
        status = response.status_code
        
        # If it is a redirect, get the target
        location = None
        if status in [301, 302, 307, 308]:
             location = response.headers.get('Location')
             # If relative redirect, make it absolute for display? (requests handles this usually if following)
             
        link_status_cache[url] = (status, location)
        return (status, location)
    except Exception as e:
        # print(f"Request failed for {url}: {e}")
        return (None, None)

def check_redirect(url):
    # Backward compatibility wrapper if needed, but we will use inspect_link directly
    s, l = inspect_link(url)
    if s == 302: return True
    return False

def get_relative_url(full_url):
    if not full_url.startswith(SITE_URL):
        return None
    
    rel = full_url[len(SITE_URL):]
    if rel == "" or rel == "/":
        return "index.html"
    
    rel = rel.lstrip("/")
    
    # Check if it maps to an existing file
    candidates = [
        rel,
        rel + ".html",
        os.path.join(rel, "index.html")
    ]
    
    for c in candidates:
        if os.path.exists(c):
            return normalize_path(c)
            
    return None

def check_sitemaps():
    print(f"\n{Colors.BOLD}🗺️  Sitemap 一致性检查...{Colors.RESET}")
    
    # 1. XML Sitemap
    xml_path = "sitemap.xml"
    if os.path.exists(xml_path):
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            # Handle namespace
            ns = {'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            for url in root.findall('sitemap:url', ns):
                loc = url.find('sitemap:loc', ns)
                if loc is not None:
                    sitemap_xml_urls.add(loc.text.strip())
            print(f"  - sitemap.xml: 发现 {len(sitemap_xml_urls)} 个 URL")
        except Exception as e:
            sitemap_warnings.append(f"[sitemap.xml] 解析失败: {e}")

    # 2. HTML Sitemap
    html_path = "sitemap.html"
    if os.path.exists(html_path):
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), "html.parser")
                # Look for links in sitemap-item list or generally
                # Assuming sitemap structure, but general crawl is safer
                links = soup.find_all("a")
                for a in links:
                    href = a.get("href")
                    if href:
                        if href.startswith("/"):
                            full_url = SITE_URL + href
                            sitemap_html_urls.add(full_url)
                        elif href.startswith(SITE_URL):
                            sitemap_html_urls.add(href)
            print(f"  - sitemap.html: 发现 {len(sitemap_html_urls)} 个 URL")
        except Exception as e:
            sitemap_warnings.append(f"[sitemap.html] 解析失败: {e}")

    # 3. Cross Check
    # Check XML -> File
    for url in sitemap_xml_urls:
        if "/#" in url: continue # Skip anchor links
        file_path = get_relative_url(url)
        if not file_path:
             sitemap_warnings.append(f"[SITEMAP WARNING] XML 中存在死链或外部链接: {url}")

    # Check File -> XML
    for f in all_html_files:
        if f in ["google_verification.html", "baidu_verification.html", "sitemap_template.html", "preview_card.html", "policies.html"] or f in SKIP_FILES: continue
        
        # Construct expected URL
        if f == "index.html":
            expected_url = SITE_URL
        elif f.endswith("/index.html"):
            expected_url = SITE_URL + "/" + os.path.dirname(f)
        else:
            expected_url = SITE_URL + "/" + f.replace(".html", "")
            
        # Try to find a match (allowing for slight variations like trailing slash)
        found = False
        for xml_url in sitemap_xml_urls:
            # Check both with and without trailing slash, and exact match
            check_urls = [
                expected_url,
                expected_url.rstrip("/"),
                expected_url + "/"
            ]
            if any(xml_url.rstrip("/") == u.rstrip("/") for u in check_urls):
                found = True
                break
        
        if not found:
             sitemap_warnings.append(f"[SITEMAP WARNING] 页面未被 sitemap.xml 收录: {f}")

def audit_file(file_path):
    stats["pages_scanned"] += 1
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        errors.append(f"[{file_path}] 无法读取文件: {str(e)}")
        return

    soup = BeautifulSoup(content, "html.parser")
    
    # --- Meta Check ---
    title = soup.find("title")
    if not title or not title.string or len(title.string.strip()) <= 5:
        warnings.append(f"[{file_path}] [SEO WARNING] Thin Content: Title 缺失或过短 (<=5 chars)")
        
    desc = soup.find("meta", attrs={"name": "description"})
    if not desc or not desc.get("content") or len(desc.get("content").strip()) <= 50:
         warnings.append(f"[{file_path}] [SEO WARNING] Thin Content: Description 缺失或过短 (<=50 chars)")

    # --- Canonical Check ---
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical:
        c_href = canonical.get("href")
        if c_href:
            # Expected Clean URL
            if file_path == "index.html":
                expected_path = "" # root
            elif file_path.endswith("/index.html"):
                # Directory index should ideally have a trailing slash
                expected_path = "/" + os.path.dirname(file_path) + "/"
            else:
                expected_path = "/" + file_path.replace(".html", "")
            
            expected_path = expected_path.replace("\\", "/")
            
            if not c_href.endswith(expected_path) and not (expected_path == "" and c_href == SITE_URL):
                 warnings.append(f"[{file_path}] [SEO WARNING] Canonical Mismatch: {c_href} (应指向 {expected_path})")
            
            if c_href.endswith(".html"):
                 warnings.append(f"[{file_path}] [SEO WARNING] Canonical 包含 .html 后缀: {c_href}")

    # 2. Deep Crawl
    links = soup.find_all("a")
    for a in links:
        href = a.get("href")
        
        # Check Empty Links
        if href is None or (href.strip() == "" and href != "#"):
            if href is None or href.strip() == "":
                 warnings.append(f"[{file_path}] 空链接: href 为空")
                 continue
        
        if href == "#":
            warnings.append(f"[{file_path}] 空链接: href=\"#\"")
            continue

        href = href.strip()

        # Check Soft Routing / Sales Links
        if href.startswith('/go/'):
            soft_routing_map[href].append(file_path)
            
            rel = a.get("rel", [])
            if isinstance(rel, str):
                rel = rel.split()
            
            # Strict check for sales links
            required_rel = {"nofollow", "sponsored", "noopener", "noreferrer"}
            if not required_rel.issubset(set(rel)):
                warnings.append(f"[{file_path}] 软路由/销售链接警告: {href} (缺少 rel=\"nofollow sponsored noopener noreferrer\")")

        # Check Protocol
        if "http://x-grok.top" in href:
             warnings.append(f"[{file_path}] 不安全协议: {href} (应使用 https)")
        
        # Internal vs External
        is_internal = False
        if not href.startswith("http") and not href.startswith("//"):
            is_internal = True
        elif SITE_DOMAIN in href:
            is_internal = True
        
        if is_internal:
            stats["internal_links"] += 1
            
            # Check Clean URL
            href_clean = href.split('#')[0].split('?')[0]
            if href_clean.endswith(".html") or "/index.html" in href:
                 clean_url_issues.append(f"[{file_path}] 非 Clean URL: {href} (建议去除 .html)")
                 # warnings.append(f"[{file_path}] 非 Clean URL: {href} (建议去除 .html)") # Clean URL issues moved to separate report
            
            # 404 Check & Inbound Link Tracking
            target_file = resolve_link(file_path, href)
            
            if target_file == "IGNORED":
                continue
                
            if target_file:
                # Handle directory resolution
                check_path = target_file
                
                # If path exists as file
                found = False
                if os.path.exists(check_path) and os.path.isfile(check_path):
                    found = True
                # If path exists as dir, look for index.html
                elif os.path.exists(check_path) and os.path.isdir(check_path):
                    if os.path.exists(os.path.join(check_path, "index.html")):
                        check_path = os.path.join(check_path, "index.html")
                        found = True
                # If path doesn't exist, maybe it's a clean URL (e.g. /about -> /about.html)
                elif not check_path.endswith(".html"):
                    if os.path.exists(check_path + ".html"):
                        check_path = check_path + ".html"
                        found = True
                
                if found:
                    # 修复：先标准化路径，去掉多余的 ./ 前缀
                    check_path = os.path.normpath(check_path)
                    check_path = normalize_path(check_path)
                    
                    if check_path in all_html_files:
                        linked_pages.add(check_path)
                        # Record inbound link
                        inbound_links[check_path].append(file_path)
                else:
                    errors.append(f"[{file_path}] 404 死链: {href} (目标不存在)")
                    
            # Redirect & Link Efficiency Check
            # Only perform network check if it's an absolute internal URL
            if HAS_REQUESTS and href.startswith("http"):
                 status, loc = inspect_link(href)
                 if status in [301, 308]:
                     redirect_issues.append(f"[{file_path}] 301 永久重定向: {href} -> {loc} (建议直接链接到目标)")
                 elif status in [302, 307]:
                     redirect_issues.append(f"[{file_path}] 302 临时重定向: {href} -> {loc} (可能造成权重流失)")
                 elif status == 404:
                     # Already caught by static check usually, but good to confirm
                     pass

        else:
            stats["external_links"] += 1
            # Record external link
            external_links_map[href].append(file_path)
            
            # Check rel attribute for external links
            rel = a.get("rel", [])
            if isinstance(rel, str):
                rel = rel.split()
            
            required_rel = {"nofollow", "noopener", "noreferrer"}
            if not required_rel.issubset(set(rel)):
                warnings.append(f"[{file_path}] 外链安全警告: {href} (缺少 rel=\"nofollow noopener noreferrer\")")
                unsafe_external_links[href].add(file_path)

    # 4. Conversion Check (blog posts only)
    if file_path.startswith("blog/") and file_path != "blog/index.html":
        found_conversion = False
        for kw in CONVERSION_KEYWORDS:
            if kw in content:
                found_conversion = True
                break
        
        if not found_conversion:
             errors.append(f"[{file_path}] 组件丢失: 未发现侧边栏推广卡片")

def main():
    print(f"{Colors.BOLD}🚀 开始全站 SEO 审计...{Colors.RESET}")
    print("-" * 30)

    # 1. Map Files
    files = get_html_files(ROOT_DIR)
    global all_html_files
    all_html_files = set([normalize_path(f) for f in files])
    
    print(f"📦 建立索引: 发现 {len(all_html_files)} 个 HTML 页面")
    
    # 2. Crawl & Analyze
    for f in all_html_files:
        if f in SKIP_FILES: continue
        audit_file(f)
        
    # 3. Weight Flow (Orphans)
    orphans = []
    for f in all_html_files:
        if f == "index.html": continue
        if f in SKIP_FILES: continue
        if f not in linked_pages:
            orphans.append(f)
            warnings.append(f"[{f}] 孤岛页面: 存在但从未被内部链接引用")
            
    # 4. Sitemap Check
    check_sitemaps()

    # Calculate Score
    base_score = 100
    deduction = (len(errors) * 5) + (len(warnings) * 1) + (len(sitemap_warnings) * 2) + (len(clean_url_issues) * 0.5) + (len(redirect_issues) * 2)
    final_score = max(0, base_score - deduction)
    
    # 5. Report
    print("\n" + "="*50)
    print(f"{Colors.BOLD}📊 审计报告{Colors.RESET}")
    print("="*50)
    
    if errors:
        print(f"\n{Colors.RED}🔴 严重错误 ({len(errors)}){Colors.RESET}")
        for e in errors:
            print(f"  - {e}")
    else:
        print(f"\n{Colors.GREEN}🔴 严重错误: 无{Colors.RESET}")

    if warnings:
        print(f"\n{Colors.YELLOW}🟡 SEO 警告 ({len(warnings)}){Colors.RESET}")
        for i, w in enumerate(warnings):
            if i < 20:
                print(f"  - {w}")
            else:
                print(f"  ... (还有 {len(warnings) - 20} 条警告)")
                break
    else:
        print(f"\n{Colors.GREEN}🟡 SEO 警告: 无{Colors.RESET}")

    if sitemap_warnings:
        print(f"\n{Colors.YELLOW}🗺️  Sitemap 警告 ({len(sitemap_warnings)}){Colors.RESET}")
        for w in sitemap_warnings:
            print(f"  - {w}")
    else:
        print(f"\n{Colors.GREEN}🗺️  Sitemap 状态: 完美{Colors.RESET}")

    # Redirect Report
    if redirect_issues:
        print(f"\n{Colors.PURPLE}🔄 重定向检测 (Link Efficiency){Colors.RESET}")
        for issue in redirect_issues:
            print(f"  - {issue}")
    else:
        print(f"\n{Colors.GREEN}🔄 重定向状态: 完美 (无内部跳转){Colors.RESET}")

    # Soft Routing Report
    print(f"\n{Colors.PURPLE}🛍️  软路由/销售链接分布{Colors.RESET}")
    if soft_routing_map:
        # Load _redirects to verify validity
        valid_redirects = set()
        if os.path.exists("_redirects"):
            try:
                with open("_redirects", "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
                        if parts and parts[0].startswith("/"):
                            valid_redirects.add(parts[0])
            except Exception as e:
                print(f"  {Colors.RED}[ERROR] 读取 _redirects 失败: {e}{Colors.RESET}")

        for url, sources in soft_routing_map.items():
            status = f"{Colors.GREEN}[VALID]{Colors.RESET}" if url in valid_redirects else f"{Colors.RED}[INVALID]{Colors.RESET}"
            print(f"  - {url} {status}")
            
            unique_sources = sorted(list(set(sources)))
            for src in unique_sources:
                # Rule Check: Only allowed on index.html (or explicitly allowed pages)
                # User Requirement: "Other page jump buttons must point to the homepage sales card"
                # Implication: Direct /go/ links should ideally only be on index.html
                
                is_home = (src == "index.html")
                policy_mark = f"{Colors.GREEN}[HOME]{Colors.RESET}" if is_home else f"{Colors.YELLOW}[OTHER PAGE - PLEASE VERIFY]{Colors.RESET}"
                
                print(f"      FROM: {src} {policy_mark}")
        
        print(f"\n{Colors.YELLOW}[政策提示] 非首页出现的销售链接建议指向首页销售卡片 (index.html#pricing) 而非直接跳转。{Colors.RESET}")
    else:
        print("  - 无软路由链接")

    # Clean URL Report
    if clean_url_issues:
        print(f"\n{Colors.PURPLE}🧹 Clean URL 审计 ({len(clean_url_issues)}){Colors.RESET}")
        for i, issue in enumerate(clean_url_issues):
            if i < 10:
                print(f"  - {issue}")
            else:
                print(f"  ... (还有 {len(clean_url_issues) - 10} 条非 Clean URL 链接)")
                break
    else:
        print(f"\n{Colors.GREEN}🧹 Clean URL 状态: 完美{Colors.RESET}")

    # External Links Report
    print(f"\n{Colors.CYAN}🌐 外链审计 (Top 50){Colors.RESET}")
    if external_links_map:
        sorted_ext = sorted(external_links_map.items(), key=lambda x: len(x[1]), reverse=True)
        for url, sources in sorted_ext[:50]:
            print(f"  - [{len(sources)}] {url}")
            
            # Show sources
            unique_sources = sorted(list(set(sources)))
            for src in unique_sources:
                # Check if this source has security issue for this URL
                is_unsafe = src in unsafe_external_links.get(url, set())
                status_mark = f"{Colors.RED}[UNSAFE]{Colors.RESET}" if is_unsafe else f"{Colors.GREEN}[OK]{Colors.RESET}"
                print(f"      FROM: {src} {status_mark}")
                
        if len(sorted_ext) > 50:
            print(f"  ... (共 {len(sorted_ext)} 个外部链接)")
            
        print(f"\n{Colors.YELLOW}[外链保护提示] {Colors.RED}[UNSAFE]{Colors.YELLOW} 标记表示缺少 rel=\"nofollow noopener noreferrer\" 属性。{Colors.RESET}")
    else:
        print("  - 无外部链接")

    # Inbound Links Report
    print(f"\n{Colors.BLUE}🔗 内链分布 (全部){Colors.RESET}")
    sorted_links = sorted(inbound_links.items(), key=lambda x: len(x[1]), reverse=True)
    
    for page, sources in sorted_links:
        print(f"  - [{len(sources)}] {page}")
    
    # Low internal links warning
    print(f"\n{Colors.YELLOW}📉 低权重页面 (入度 < 3){Colors.RESET}")
    low_weight_count = 0
    for f in all_html_files:
        if f == "index.html": continue
        if f in SKIP_FILES: continue
        count = len(inbound_links.get(f, []))
        if count < 3 and f not in orphans: # orphans already reported
            low_weight_count += 1
            if low_weight_count <= 10:
                print(f"  - [{count}] {f}")
    if low_weight_count > 10:
        print(f"  ... (共 {low_weight_count} 个页面入度不足)")

    print(f"\n{Colors.GREEN}🟢 健康状态{Colors.RESET}")
    print(f"  - 总页面数: {stats['pages_scanned']}")
    print(f"  - 内链总数: {stats['internal_links']}")
    print(f"  - 外链总数: {stats['external_links']}")
    print(f"  - 孤岛页面: {len(orphans)}")
    
    score_color = Colors.GREEN
    if final_score < 60: score_color = Colors.RED
    elif final_score < 80: score_color = Colors.YELLOW
    
    print(f"  - 健康度评分: {score_color}{final_score}/100{Colors.RESET}")

    if not HAS_REQUESTS:
        print(f"\n{Colors.YELLOW}[提示] 未检测到 requests 库，跳过 302 重定向检查。{Colors.RESET}")

if __name__ == "__main__":
    main()
