class UserInterface:
    @staticmethod
    def display_search_results(results):
        """显示搜索结果"""
        print("\n搜索结果:")
        print("=" * 80)

        for idx, result in enumerate(results, 1):
            print(f"[{idx}] {result['title']}")
            print(
                f" 作者: {result['author']} | 分类: {result['category']} | 页数: {result['pages']} | 评分: {result['rating']} | 时间: {result['timestamp']}")
            print(f" 封面: {result['cover_url']}")
            print("-" * 80)

        return len(results)

    @staticmethod
    def get_user_selection(max_idx):
        """获取用户选择"""
        while True:
            try:
                selection = int(input(f"\n请输入要下载的画廊编号 (1-{max_idx}): "))
                if 1 <= selection <= max_idx:
                    return selection
                print(f"请输入1-{max_idx}之间的数字")
            except ValueError:
                print("请输入有效的数字")

    @staticmethod
    def get_search_parameters():
        """获取搜索参数"""
        print("=" * 40)
        print("E-Hentai 爬虫")
        print("=" * 40)

        search_term = input("请输入搜索关键词: ").strip()
        min_rating = int(input("过滤最低评分（2-5，默认2）: ") or 2)
        min_pages = int(input("过滤最少页数（默认1）: ") or 1)
        target_page = int(input("获取第几页的画廊列表（默认1）: ") or 1)

        return {
            "search_term": search_term,
            "min_rating": min_rating,
            "min_pages": min_pages,
            "target_page": target_page
        }
