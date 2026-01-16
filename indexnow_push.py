import requests
import xml.etree.ElementTree as ET
import os
import json

# 配置信息
SITE_HOST = "x-grok.top"
SITE_URL = f"https://{SITE_HOST}"
API_KEY = "d18753b123184422bd671c0d6263beff"
KEY_LOCATION = f"{SITE_URL}/{API_KEY}.txt"
API_URL = "https://api.indexnow.org/indexnow"
SITEMAP_URL = f"{SITE_URL}/sitemap.xml"

def get_urls_from_sitemap(sitemap_source):
    """从 sitemap.xml 提取所有 URL (支持本地路径或远程 URL)"""
    urls = []
    print(f"正在尝试从 {sitemap_source} 获取 Sitemap...")
    
    try:
        if sitemap_source.startswith("http"):
            response = requests.get(sitemap_source, timeout=10)
            if response.status_code != 200:
                print(f"远程获取失败: HTTP {response.status_code}")
                return []
            content = response.content
            # 解析 XML
            root = ET.fromstring(content)
        else:
            if not os.path.exists(sitemap_source):
                print(f"错误: 找不到文件 {sitemap_source}")
                return urls
            tree = ET.parse(sitemap_source)
            root = tree.getroot()

        # Sitemap namespace
        namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        
        for url in root.findall('ns:url', namespace):
            loc = url.find('ns:loc', namespace)
            if loc is not None and loc.text:
                urls.append(loc.text.strip())
                
        print(f"成功提取 {len(urls)} 个 URL")
        return urls
    except Exception as e:
        print(f"解析 Sitemap 出错: {e}")
        return []

def push_to_indexnow(urls):
    """推送 URL 到 IndexNow"""
    if not urls:
        print("没有 URL 需要推送")
        return

    payload = {
        "host": SITE_HOST,
        "key": API_KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls
    }

    headers = {
        'Content-Type': 'application/json; charset=utf-8'
    }

    try:
        response = requests.post(
            API_URL, 
            json=payload, 
            headers=headers,
            timeout=10
        )
        
        print("-" * 30)
        print("IndexNow 推送结果:")
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ 推送成功！IndexNow 已接收 URL 列表。")
        elif response.status_code == 202:
            print("✅ 推送成功！请求已被接受但尚未处理。")
        elif response.status_code == 403:
            print(f"❌ 推送失败 (403 Forbidden): {response.json().get('message', response.text)}")
            print("\n⚠️  可能的原因与解决方案:")
            print(f"1. 验证文件无法访问: 请确保 {KEY_LOCATION} 可以被公网访问。")
            print("2. CDN/防火墙拦截 (最常见):")
            print("   - 您的网站使用了 Cloudflare。IndexNow 的验证爬虫可能被 'Bot Fight Mode' 或 WAF 拦截。")
            print(f"   - 建议: 在 Cloudflare WAF 中添加一条规则，'URI Path' 包含 '{API_KEY}.txt' 时，操作选 'Skip' (跳过所有防护) 或 'Allow'。")
        else:
            print(f"❌ 推送失败: {response.status_code} - {response.text}")
            
        print("-" * 30)
        
    except Exception as e:
        print(f"推送请求失败: {e}")

if __name__ == "__main__":
    print("开始执行 IndexNow 主动推送...")
    print(f"Host: {SITE_HOST}")
    print(f"Key Location: {KEY_LOCATION}")
    
    # 优先尝试远程获取，失败则尝试本地
    target_urls = get_urls_from_sitemap(SITEMAP_URL)
    if not target_urls:
        print("远程获取失败或为空，尝试读取本地 sitemap.xml...")
        target_urls = get_urls_from_sitemap("sitemap.xml")
    
    # 过滤掉非本站域名的 URL (以防万一)
    target_urls = [url for url in target_urls if SITE_HOST in url]
    
    push_to_indexnow(target_urls)
