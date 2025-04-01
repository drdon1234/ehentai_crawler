import os
import asyncio
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
import glob
from natsort import natsorted
import img2pdf
from PIL import Image

# 配置参数
BASE_URL = "https://e-hentai.org/g/3294676/721924eeb6/" # 暂时需要手动传入，正在制作ehentai_searcher
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}
PROXIES = "http://127.0.0.1:7897"  # 必须配置
CONCURRENCY = 5  # 并发限制
MAX_RETRIES = 10  # 最大重试次数
TIMEOUT = 30  # 请求超时时间

# 创建保存图片的文件夹
OUTPUT_FOLDER = "./images"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

class AsyncDownloader:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(CONCURRENCY)
        self.failed_tasks = []  # 用于记录失败的下载任务
        self.image_index = 1  # 图片文件名从1开始递增

    async def fetch_with_retry(self, session, url):
        """带重试机制的页面请求"""
        for attempt in range(MAX_RETRIES):
            try:
                async with self.semaphore:
                    async with session.get(
                            url,
                            headers=HEADERS,
                            proxy=PROXIES,
                            timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                    ) as response:
                        response.raise_for_status()
                        return await response.text()
            except Exception as e:
                print(f"尝试 {attempt + 1}/{MAX_RETRIES} 获取页面失败: {url} - {str(e)}")
                await asyncio.sleep(2 ** attempt)  # 指数退避策略

        print(f"页面获取失败，放弃: {url}")
        return None

    async def download_image(self, session, img_url):
        """下载图片并保存到本地"""
        for attempt in range(MAX_RETRIES):
            try:
                async with self.semaphore:
                    async with session.get(
                            img_url,
                            headers=HEADERS,
                            proxy=PROXIES,
                            timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                    ) as response:
                        response.raise_for_status()
                        content = await response.read()

                        # 检查图片内容是否有效（大于1KB）
                        if len(content) < 1024:
                            raise ValueError("无效的图片内容")

                        # 保存图片到本地，文件名为自然数递增
                        async with aiofiles.open(os.path.join(OUTPUT_FOLDER, f"{self.image_index}.jpg"), "wb") as file:
                            await file.write(content)

                        print(f"图片已保存: {self.image_index}.jpg")
                        self.image_index += 1  # 增加文件名计数器
                        return True

            except Exception as e:
                print(f"图片下载尝试 {attempt + 1}/{MAX_RETRIES} 失败: {img_url} - {str(e)}")
                await asyncio.sleep(2 ** attempt)  # 指数退避策略

        print(f"图片下载失败，放弃: {img_url}")
        self.failed_tasks.append(img_url)
        return False

    async def process_subpage(self, session, subpage_url):
        """处理子页面并下载图片"""
        html_content = await self.fetch_with_retry(session, subpage_url)
        if not html_content:
            return

        soup = BeautifulSoup(html_content, "html.parser")
        img_tag = soup.select_one("html > body > div:nth-of-type(1) > div:nth-of-type(2) > a > img")

        if img_tag and (img_url := img_tag.get("src")):
            await self.download_image(session, img_url)

    async def process_pagination(self, session):
        """获取所有分页链接并处理子页面"""
        main_html = await self.fetch_with_retry(session, BASE_URL)
        if not main_html:
            raise ValueError("无法获取主页面内容")

        soup = BeautifulSoup(main_html, "html.parser")
        pagination_row = soup.select_one("table.ptt > tr")

        last_page_element = pagination_row.find_all("td")[-2].find("a")
        last_page_number = int(last_page_element.text.strip())

        page_urls = [f"{BASE_URL}?p={page}" for page in range(last_page_number)]

        for page_url in page_urls:
            html_content = await self.fetch_with_retry(session, page_url)
            if not html_content:
                continue

            soup = BeautifulSoup(html_content, "html.parser")
            gdt_element = soup.find("div", id="gdt")

            if gdt_element:
                subpage_urls = [a["href"] for a in gdt_element.find_all("a", href=True)]
                tasks = [self.process_subpage(session, subpage_url) for subpage_url in subpage_urls]
                await asyncio.gather(*tasks)

    async def run(self):
        connector = aiohttp.TCPConnector(ssl=False)

        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                await self.process_pagination(session)

                if self.failed_tasks:
                    print("\n以下任务下载失败:")
                    for task in self.failed_tasks:
                        print(task)

                # 下载完成后合并图片为PDF
                await self.merge_images_to_pdf()

            except Exception as e:
                print(f"运行错误: {str(e)}")

    async def merge_images_to_pdf(self):
        """将下载好的图片合并为一个PDF文件"""
        image_files = natsorted(
            glob.glob(os.path.join(OUTPUT_FOLDER, "*.jpg")) +
            glob.glob(os.path.join(OUTPUT_FOLDER, "*.png"))
        )

        if not image_files:
            print("未找到可转换的图片文件")
            return

        # 移除透明通道
        for file in image_files:
            if file.endswith(".png"):
                img = Image.open(file)
                if img.mode in ("RGBA", "LA"):
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    background.save(file)

        for file in image_files:
            if file.endswith(".png"):
                img = Image.open(file).convert("RGB")
                img.save(file.replace(".png", ".jpg"))
                image_files = [f.replace(".png", ".jpg") if f.endswith(".png") else f for f in image_files]

        os.makedirs("./pdfs", exist_ok=True)
        output_pdf = "./pdfs/output.pdf"
        with open(output_pdf, "wb") as f:
            f.write(img2pdf.convert(image_files))

        print(f"图片已合并为PDF文件 → {os.path.abspath(output_pdf)}")


if __name__ == "__main__":
    downloader = AsyncDownloader()
    asyncio.run(downloader.run())
