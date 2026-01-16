import requests
import xml.etree.ElementTree as ET
import os
import json

# 配置信息
SITE_HOST = "x-grok.top"
SITE_URL = f"https://{SITE_HOST}"
API_KEY = "88944569503442658120658421865954"
KEY_LOCATION = f"{SITE_URL}/{API_KEY}.txt"
API_URL = "https://api.indexnow.org/indexnow"
SITEMAP_FILE = "sitemap.xml"

def get_urls_from_sitemap(sitemap_path):
    """从 sitemap.xml 提取所有 URL"""
    urls = []
    if not os.path.exists(sitemap_path):
        print(f"错误: 找不到文件 {sitemap_path}")
        return urls
    
    try:
        tree = ET.parse(sitemap_path)
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
            print("推送成功！IndexNow 已接收 URL 列表。")
        elif response.status_code == 202:
            print("推送成功！请求已被接受但尚未处理。")
        else:
            print(f"推送失败: {response.text}")
            
        print("-" * 30)
        
    except Exception as e:
        print(f"推送请求失败: {e}")

if __name__ == "__main__":
    print("开始执行 IndexNow 主动推送...")
    print(f"Host: {SITE_HOST}")
    print(f"Key Location: {KEY_LOCATION}")
    
    target_urls = get_urls_from_sitemap(SITEMAP_FILE)
    
    # 过滤掉非本站域名的 URL (以防万一)
    target_urls = [url for url in target_urls if SITE_HOST in url]
    
    push_to_indexnow(target_urls)
