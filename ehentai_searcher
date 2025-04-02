import re
import requests
from bs4 import BeautifulSoup
import json
import time
import os
import random
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse


def parse_background_position(style):
    """解析background-position的坐标值"""
    match = re.search(r'background-position:\s*(-?\d+)px\s+(-?\d+)px', style)
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


def calculate_rating(x, y):
    """根据坐标计算评分"""
    full_stars = 5 - abs(x) // 16  # 每偏移 -16px 减去一颗星
    half_star = 0.5 if y == -21 else 0  # -21px 表示扣 0.5 分
    return full_stars - half_star


def extract_author_and_title(raw_title):
    """从标题中分离作者和作品名称"""
    match = re.match(r'^\[(.*?)\]\s*(.*)', raw_title)
    return (match.groups() if match else (None, raw_title))


def parse_timestamp_from_cell(cell):
    """从单元格中提取时间戳"""
    match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', cell.get_text(strip=True))
    return match.group(1) if match else time.strftime("%Y-%m-%d %H:%M")


def extract_cover_url(cell):
    """提取封面URL"""
    try:
        img_tag = cell.find('img')
        if img_tag:
            url = img_tag.get('data-src') or img_tag.get('src', '')
            return url.replace('/t/', '/i/').split('?')[0]
    except Exception as e:
        print(f"封面解析失败: {e}")
    return ""


def build_search_url(base_url, params):
    """构建包含高级搜索参数的URL"""
    parsed_url = urlparse(base_url)
    query = parse_qs(parsed_url.query)
    query.update(params)
    new_query = urlencode(query, doseq=True)
    return urlunparse(parsed_url._replace(query=new_query))


def crawl_ehentai(search_term, min_rating=0, min_pages=0, max_pages=1):
    """爬取E-Hentai画廊数据，支持高级搜索选项和分页"""
    base_url = "https://e-hentai.org/"
    search_params = {
        'f_search': search_term,
        'f_srdd': min_rating,
        'f_spf': min_pages
    }

    search_url = build_search_url(base_url, search_params)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Referer": "https://e-hentai.org/"
    }

    proxies = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}

    results = []
    current_page = 1

    while search_url and current_page <= max_pages:
        try:
            print(f"正在爬取第 {current_page} 页: {search_url}")
            response = requests.get(search_url, headers=headers, proxies=proxies, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', class_='itg')

            if not table:
                print("未找到结果表格")
                break

            for row in table.find_all('tr')[1:]:  # 跳过表头
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue

                try:
                    # 提取基础信息
                    category = cells[0].get_text(strip=True)
                    gallery_url = cells[2].find('a')['href']

                    # 提取封面URL和时间戳
                    cover_url = extract_cover_url(cells[1])
                    timestamp = parse_timestamp_from_cell(cells[1])

                    # 提取标题和作者
                    title_element = cells[2].find('a')
                    raw_title = title_element.find('div', class_='glink').get_text(strip=True)
                    author, title = extract_author_and_title(raw_title)

                    # 提取评分
                    rating_div = cells[1].find('div', class_='ir')  # 确定评分元素在封面单元格中
                    rating = 0.0
                    if rating_div:
                        style = rating_div.get('style', '')
                        x, y = parse_background_position(style)
                        rating = calculate_rating(x, y)

                    results.append({
                        "title": title.strip(),
                        "author": author.strip() if author else "Unknown",
                        "category": category,
                        "gallery_url": gallery_url,
                        "cover_url": cover_url,
                        "timestamp": timestamp,
                        "rating": round(rating, 1)  # 保留1位小数
                    })

                except Exception as e:
                    print(f"数据解析异常: {e}")

            # 查找下一页链接并保留搜索参数
            next_link = soup.find('a', id='unext')
            if next_link:
                parsed_next_link = urlparse(next_link['href'])
                next_query_params = parse_qs(parsed_next_link.query)
                search_params.update(next_query_params)
                search_url = build_search_url(base_url, search_params)
            else:
                search_url = None

            current_page += 1
            time.sleep(random.uniform(1.5, 3.5))

        except Exception as e:
            print(f"爬取过程异常: {e}")
            break

    return results


def save_to_json(data, search_term):
    """保存结构化数据到JSON文件"""
    output_dir = "ehentai_archives"
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{output_dir}/{search_term}_{int(time.time())}.json"

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(
                obj={
                    "metadata": {
                        "domain": "e-hentai.org",
                        "search_term": search_term,
                        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
                        "result_count": len(data)
                    },
                    "results": data
                },
                fp=f,
                ensure_ascii=False,
                indent=2,
                sort_keys=False  # 保持字段顺序
            )
        print(f"成功保存 {len(data)} 条数据至 {filename}")
    except Exception as e:
        print(f"JSON保存失败: {e}")


def main():
    print("=" * 40)
    print("E-Hentai 高级搜索爬虫")
    print("=" * 40)

    search_term = input("请输入搜索关键词: ").strip()
    min_rating = int(input("设置最低评分（0-5，默认4）: ") or 4)
    min_pages = int(input("设置最少页数（默认1）: ") or 1)
    max_pages = int(input("最大爬取页数（默认1）: ") or 1)

    all_results = crawl_ehentai(
        search_term=search_term,
        min_rating=min_rating,
        min_pages=min_pages,
        max_pages=max_pages
    )

    if all_results:
        save_to_json(all_results, search_term)
    else:
        print("\n未找到任何匹配结果")


if __name__ == "__main__":
    main()
