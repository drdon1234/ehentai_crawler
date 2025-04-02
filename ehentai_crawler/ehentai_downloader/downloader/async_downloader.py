import asyncio
import aiohttp
import aiofiles
import random
from pathlib import Path
from PIL import Image


class AsyncDownloader:
    def __init__(self, config, parser, helpers):
        self.config = config
        self.parser = parser
        self.helpers = helpers
        self.semaphore = asyncio.Semaphore(self.config['request']['concurrency'])
        self.failed_tasks = []
        self.image_index = 1
        self.gallery_title = "output"

        # 初始化目录
        Path(self.config['output']['image_folder']).mkdir(parents=True, exist_ok=True)
        Path(self.config['output']['pdf_folder']).mkdir(parents=True, exist_ok=True)

    async def fetch_with_retry(self, session, url):
        """带重试机制的页面请求"""
        proxy_conf = self.config['request'].get('proxy', {})

        for attempt in range(self.config['request']['max_retries']):
            try:
                async with self.semaphore:
                    async with session.get(
                            url,
                            headers=self.config['request']['headers'],
                            proxy=proxy_conf.get('url'),
                            proxy_auth=proxy_conf.get('auth'),
                            timeout=aiohttp.ClientTimeout(total=self.config['request']['timeout']),
                            ssl=False
                    ) as response:
                        response.raise_for_status()
                        return await response.text()
            except Exception as e:
                print(f"尝试 {attempt + 1}/{self.config['request']['max_retries']} 失败: {url} - {str(e)}")
                await asyncio.sleep(2 ** attempt)

        print(f"请求失败，放弃: {url}")
        return None

    async def download_image(self, session, img_url):
        """下载并转换图片为JPEG格式"""
        proxy_conf = self.config['request'].get('proxy', {})

        for attempt in range(self.config['request']['max_retries']):
            try:
                async with self.semaphore:
                    async with session.get(
                            img_url,
                            headers=self.config['request']['headers'],
                            proxy=proxy_conf.get('url'),
                            proxy_auth=proxy_conf.get('auth'),
                            timeout=aiohttp.ClientTimeout(total=self.config['request']['timeout']),
                            ssl=False
                    ) as response:
                        response.raise_for_status()
                        content = await response.read()

                        if len(content) < 1024:
                            raise ValueError("无效的图片内容")

                        image_path = Path(self.config['output']['image_folder']) / f"{self.image_index}.jpg"

                        async with aiofiles.open(image_path, "wb") as file:
                            await file.write(content)

                        with Image.open(image_path) as img:
                            if img.format != 'JPEG':
                                if img.mode in ('RGBA', 'LA'):
                                    background = Image.new('RGB', img.size, (255, 255, 255))
                                    background.paste(img, mask=img.split()[-1])
                                    background.save(image_path, 'JPEG', quality=self.config['output']['jpeg_quality'])
                                else:
                                    img = img.convert('RGB')
                                    img.save(image_path, 'JPEG', quality=self.config['output']['jpeg_quality'])

                        self.image_index += 1
                        return True
            except Exception as e:
                print(f"图片下载尝试 {attempt + 1} 失败: {img_url} - {str(e)}")
                await asyncio.sleep(2 ** attempt)

        self.failed_tasks.append(img_url)
        return False

    async def process_subpage(self, session, subpage_url):
        """处理子页面并下载图片"""
        html_content = await self.fetch_with_retry(session, subpage_url)
        if not html_content:
            return

        img_url = self.parser.extract_image_url_from_page(html_content)
        if img_url:
            await self.download_image(session, img_url)

    async def process_pagination(self, session, gallery_url):
        """处理分页"""
        main_html = await self.fetch_with_retry(session, gallery_url)
        if not main_html:
            raise ValueError("无法获取主页面内容")

        self.gallery_title, last_page_number = self.parser.extract_gallery_info(main_html)

        page_urls = [f"{gallery_url}?p={page}" for page in range(last_page_number)]

        for page_url in page_urls:
            html_content = await self.fetch_with_retry(session, page_url)
            if html_content:
                subpage_urls = self.parser.extract_subpage_urls(html_content)
                await asyncio.gather(*[self.process_subpage(session, url) for url in subpage_urls])

    async def crawl_ehentai(self, search_term, min_rating=0, min_pages=0, target_page=1):
        """爬取画廊数据"""
        base_url = "https://e-hentai.org/"
        search_params = {'f_search': search_term, 'f_srdd': min_rating, 'f_spf': min_pages}
        search_url = self.helpers.build_search_url(base_url, search_params)

        results = []
        current_page = 1

        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            while search_url and current_page <= target_page:
                html = await self.fetch_with_retry(session, search_url)
                if not html:
                    break

                if current_page == target_page:
                    results = self.parser.parse_gallery_from_html(html, self.helpers)
                    break

                search_url = self.parser.get_next_page_url(html)
                current_page += 1
                await asyncio.sleep(random.uniform(1.5, 3.5))

        return results
