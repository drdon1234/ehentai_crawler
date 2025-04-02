import os
import glob
import time
import asyncio
import aiohttp
from pathlib import Path

# 导入自定义模块
from ehentai_downloader.config import load_config
from ehentai_downloader.utils.helpers import (
    parse_background_position,
    calculate_rating,
    extract_author_and_title,
    build_search_url,
    get_safe_filename
)
from ehentai_downloader.scraper.parser import (
    parse_gallery_from_html,
    get_next_page_url,
    extract_image_url_from_page,
    extract_gallery_info,
    extract_subpage_urls
)
from ehentai_downloader.downloader.async_downloader import AsyncDownloader
from ehentai_downloader.pdf_generator.generator import PDFGenerator
from ehentai_downloader.ui.interface import UserInterface


class Helpers:
    """帮助类，包含所有工具函数"""

    @staticmethod
    def parse_background_position(style):
        return parse_background_position(style)

    @staticmethod
    def calculate_rating(x, y):
        return calculate_rating(x, y)

    @staticmethod
    def extract_author_and_title(raw_title):
        return extract_author_and_title(raw_title)

    @staticmethod
    def build_search_url(base_url, params):
        return build_search_url(base_url, params)

    @staticmethod
    def get_safe_filename(title):
        return get_safe_filename(title)


class Parser:
    """解析类，包含所有解析函数"""

    @staticmethod
    def parse_gallery_from_html(html_content, helpers):
        return parse_gallery_from_html(html_content, helpers)

    @staticmethod
    def get_next_page_url(html_content):
        return get_next_page_url(html_content)

    @staticmethod
    def extract_image_url_from_page(html_content):
        return extract_image_url_from_page(html_content)

    @staticmethod
    def extract_gallery_info(html_content):
        return extract_gallery_info(html_content)

    @staticmethod
    def extract_subpage_urls(html_content):
        return extract_subpage_urls(html_content)


async def main():
    # 加载配置
    config = load_config()

    # 创建工具类实例
    helpers = Helpers()
    parser = Parser()

    # 初始化下载器
    downloader = AsyncDownloader(config, parser, helpers)

    # 初始化PDF生成器
    pdf_generator = PDFGenerator(config, helpers)

    # 初始化用户界面
    ui = UserInterface()

    # 清空图片文件夹
    for f in glob.glob(str(Path(config['output']['image_folder']) / "*.*")):
        os.remove(f)

    # 获取用户输入的搜索参数
    params = ui.get_search_parameters()

    # 开始搜索
    search_results = await downloader.crawl_ehentai(
        params["search_term"],
        params["min_rating"],
        params["min_pages"],
        params["target_page"]
    )

    if not search_results:
        print("未找到匹配结果")
        return

    # 显示搜索结果
    max_idx = ui.display_search_results(search_results)

    # 获取用户选择
    selected_idx = ui.get_user_selection(max_idx)
    selected_gallery = search_results[selected_idx - 1]

    # 设置画廊标题
    downloader.gallery_title = f"{selected_gallery['author']} - {selected_gallery['title']}" if selected_gallery[
                                                                                                    'author'] != "Unknown" else \
    selected_gallery['title']

    print(f"\n开始下载: {downloader.gallery_title}")
    print(f"JPEG质量: {config['output']['jpeg_quality']}%")
    print(f"PDF分页限制: {config['output']['max_pages_per_pdf'] or '无限制'}")

    # 记录开始时间
    stime = time.time()

    try:
        # 创建会话
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            # 下载画廊
            await downloader.process_pagination(session, selected_gallery["gallery_url"])

            # 生成PDF
            pdf_generator.merge_images_to_pdf(downloader.gallery_title)

            # 显示失败的任务
            if downloader.failed_tasks:
                print("\n失败任务列表:")
                for task in downloader.failed_tasks:
                    print(task)

    except Exception as e:
        print(f"运行错误: {str(e)}")

    finally:
        # 清空图片文件夹
        for f in glob.glob(str(Path(config['output']['image_folder']) / "*.*")):
            os.remove(f)

        # 显示用时
        etime = time.time() - stime
        print(f"用时 {etime:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
