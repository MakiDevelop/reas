#!/usr/bin/env python3
"""
ETtoday 爬蟲診斷腳本
用於檢查網站結構變化並輸出實際的 HTML 以便修正選擇器
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

def setup_driver():
    """設置 Chrome Driver"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')

    # 根據你的環境調整路徑
    chrome_binary_location = "/usr/bin/chromium"
    chrome_options.binary_location = chrome_binary_location

    chromedriver_path = "/usr/bin/chromedriver"
    service = Service(executable_path=chromedriver_path)

    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30)

    return driver

def diagnose_ettoday():
    """診斷 ETtoday 網站結構"""
    print("=" * 80)
    print("ETtoday 房產雲網站結構診斷")
    print("=" * 80)

    driver = None
    try:
        driver = setup_driver()
        url = "https://house.ettoday.net/"

        print(f"\n正在訪問: {url}")
        driver.get(url)
        time.sleep(5)  # 等待頁面完全載入

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        print("\n" + "=" * 80)
        print("1. 檢查舊的選擇器")
        print("=" * 80)

        # 檢查舊的選擇器
        old_selectors = {
            '焦點文章區塊': '.block_1 .gallery_3 .piece',
            '最新文章區塊': '.part_txt_1',
            '區塊標題': '.block_title_3',
            '文章標題連結': 'h3 a'
        }

        for name, selector in old_selectors.items():
            elements = soup.select(selector)
            print(f"\n{name} ({selector}): 找到 {len(elements)} 個元素")
            if elements:
                print(f"  ✅ 選擇器有效")
                # 顯示前3個元素的內容
                for i, elem in enumerate(elements[:3], 1):
                    if elem.name == 'a':
                        print(f"  - 元素 {i}: {elem.get('title', elem.text.strip()[:50])}")
                    else:
                        print(f"  - 元素 {i}: {elem.get('class', [])} {elem.name}")
            else:
                print(f"  ❌ 選擇器失效")

        print("\n" + "=" * 80)
        print("2. 尋找可能的新選擇器")
        print("=" * 80)

        # 尋找所有可能包含文章的元素
        print("\n查找包含 'href' 的 <a> 標籤 (包含 '/news/')...")
        news_links = soup.select('a[href*="/news/"]')
        print(f"找到 {len(news_links)} 個新聞連結")

        if news_links:
            print("\n前 10 個新聞連結的結構:")
            for i, link in enumerate(news_links[:10], 1):
                title = link.get('title', link.text.strip())
                href = link.get('href', '')
                parent_classes = link.parent.get('class', []) if link.parent else []
                print(f"\n  {i}. 標題: {title[:60]}")
                print(f"     URL: {href}")
                print(f"     父元素: {link.parent.name if link.parent else 'None'}")
                print(f"     父元素 class: {' '.join(parent_classes)}")
                print(f"     連結 class: {' '.join(link.get('class', []))}")

        print("\n" + "=" * 80)
        print("3. 查找主要區塊結構")
        print("=" * 80)

        # 尋找可能的區塊容器
        potential_containers = [
            ('div[class*="block"]', 'div 含 block 的 class'),
            ('div[class*="section"]', 'div 含 section 的 class'),
            ('div[class*="article"]', 'div 含 article 的 class'),
            ('div[class*="list"]', 'div 含 list 的 class'),
            ('section', 'section 標籤'),
            ('article', 'article 標籤'),
        ]

        for selector, name in potential_containers:
            elements = soup.select(selector)
            if elements:
                print(f"\n{name} ({selector}): 找到 {len(elements)} 個")
                for i, elem in enumerate(elements[:3], 1):
                    classes = ' '.join(elem.get('class', []))
                    children_with_links = elem.select('a[href*="/news/"]')
                    print(f"  {i}. class='{classes}' (包含 {len(children_with_links)} 個新聞連結)")

        print("\n" + "=" * 80)
        print("4. 保存完整 HTML 用於詳細分析")
        print("=" * 80)

        # 保存完整的 HTML 到文件
        output_file = "/app/debug_ettoday_output.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"\n完整 HTML 已保存到: {output_file}")
        print("你可以用瀏覽器或文字編輯器打開查看完整結構")

        print("\n" + "=" * 80)
        print("5. 測試單篇文章頁面")
        print("=" * 80)

        # 如果找到新聞連結，測試第一篇文章頁面
        if news_links:
            article_url = news_links[0].get('href', '')
            if not article_url.startswith('http'):
                article_url = 'https://house.ettoday.net' + article_url

            print(f"\n正在訪問文章頁面: {article_url}")
            driver.get(article_url)
            time.sleep(3)

            article_soup = BeautifulSoup(driver.page_source, 'html.parser')

            # 檢查舊的文章內容選擇器
            article_selectors = {
                '內容區塊 .story': article_soup.select_one('.story'),
                '內容區塊 .story-content': article_soup.select_one('.story-content'),
                '內容區塊 article': article_soup.select_one('article'),
                '時間元素 time.date': article_soup.select_one('time.date'),
                '時間元素 .date': article_soup.select_one('.date'),
                '時間元素 .news-time': article_soup.select_one('.news-time'),
            }

            for name, element in article_selectors.items():
                if element:
                    print(f"  ✅ {name}: 找到")
                    if element.name == 'time' or 'date' in name.lower():
                        print(f"     內容: {element.text.strip()}")
                else:
                    print(f"  ❌ {name}: 未找到")

            # 尋找新的可能選擇器
            print("\n  尋找可能的新選擇器:")
            print(f"    - 所有 <time> 標籤: {len(article_soup.select('time'))} 個")
            print(f"    - 所有 <article> 標籤: {len(article_soup.select('article'))} 個")
            content_selector = 'div[class*="content"]'
            story_selector = 'div[class*="story"]'
            print(f"    - class 含 'content' 的 div: {len(article_soup.select(content_selector))} 個")
            print(f"    - class 含 'story' 的 div: {len(article_soup.select(story_selector))} 個")

            # 保存文章頁面的 HTML
            article_output = "/app/debug_ettoday_article.html"
            with open(article_output, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print(f"\n  文章頁面 HTML 已保存到: {article_output}")

        print("\n" + "=" * 80)
        print("診斷完成！")
        print("=" * 80)
        print("\n建議:")
        print("1. 檢查上面標記為 ❌ 的選擇器")
        print("2. 查看保存的 HTML 文件以找出新的選擇器")
        print("3. 使用找到的新選擇器更新爬蟲代碼")

    except Exception as e:
        print(f"\n❌ 發生錯誤: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            driver.quit()
            print("\n瀏覽器已關閉")

if __name__ == "__main__":
    diagnose_ettoday()
