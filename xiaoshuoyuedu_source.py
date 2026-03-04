"""小说阅读网源实现"""
import requests
from bs4 import BeautifulSoup
from typing import List, Tuple, Optional
from novel_base import NovelSourceBase
import re


class XiaoshuoyueduSource(NovelSourceBase):
    """小说阅读网源实现"""

    def __init__(self):
        super().__init__()
        self.source_name = "小说阅读网"
        self.supported_domains = ["xiaoshuoyuedu.com", "www.xiaoshuoyuedu.com"]
        self.base_url = "https://www.xiaoshuoyuedu.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.xiaoshuoyuedu.com/',
            'Origin': 'https://www.xiaoshuoyuedu.com',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        })

    def is_supported(self, url: str) -> bool:
        """检查是否支持该URL"""
        return any(domain in url for domain in self.supported_domains)

    def _get_page_content(self, url: str, retries: int = 3) -> Optional[str]:
        """获取网页内容"""
        print(f"[XiaoshuoyueduSource] 请求URL: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Cache-Control': 'max-age=0',
            'Cookie': '__51uvsct__KlbLV9rWt7neFgxP=1; __51vcke__KlbLV9rWt7neFgxP=8e0c16ed-f8ef-55b6-9b0c-b35d971c43e7; __51vuft__KlbLV9rWt7neFgxP=1770894977410; Hm_lvt_abeb97d62bae1479d29dda44f2d0573b=1770894978; HMACCOUNT=A0FAE083D872A80F; articlevisited=1; Hm_lpvt_abeb97d62bae1479d29dda44f2d0573b=1770898040; __vtins__KlbLV9rWt7neFgxP=%7B%22sid%22%3A%20%22c188e36e-4e35-5577-bbef-10fc2a763b1d%22%2C%20%22vd%22%3A%2030%2C%20%22stt%22%3A%203062589%2C%20%22dr%22%3A%2028019%2C%20%22expires%22%3A%201770899839996%2C%20%22ct%22%3A%201770898039996%7D',
            'Sec-Ch-Ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
        for attempt in range(retries):
            try:
                response = self.session.get(url, headers=headers, timeout=15)
                print(f"[XiaoshuoyueduSource] 响应状态码: {response.status_code}")
                response.encoding = 'utf-8'
                return response.text
            except Exception as e:
                print(f"[XiaoshuoyueduSource] 请求失败 (尝试 {attempt+1}/{retries}): {e}")
                if attempt == retries - 1:
                    return None
        return None

    def extract_novel_info(self, url: str) -> Tuple[str, List[Tuple[str, str]]]:
        """提取小说信息（标题和章节列表）"""
        print(f"[XiaoshuoyueduSource] extract_novel_info: {url}")
        try:
            html_content = self._get_page_content(url)
            if not html_content:
                print(f"[XiaoshuoyueduSource] 获取页面失败")
                self.error.emit("获取页面失败")
                return "未知小说", []

            soup = BeautifulSoup(html_content, 'html.parser')

            novel_title = ""
            title_selectors = ['h1', '.book-title', '.novel-title', 'h2.title']
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    novel_title = title_elem.get_text(strip=True)
                    if novel_title:
                        break

            print(f"[XiaoshuoyueduSource] 找到标题: {novel_title}")

            chapters = []
            info_chapters_divs = soup.select('.info-chapters')
            
            if len(info_chapters_divs) >= 2:
                print(f"[XiaoshuoyueduSource] 找到 {len(info_chapters_divs)} 个 .info-chapters div，使用第二个（正文）")
                chapter_elements = info_chapters_divs[1].select('a')
            else:
                chapter_elements = soup.select('.info-chapters a')
            
            if chapter_elements:
                print(f"[XiaoshuoyueduSource] 找到 {len(chapter_elements)} 个章节")
                for elem in chapter_elements:
                    chapter_url = elem.get('href', '')
                    chapter_title = elem.get_text(strip=True)
                    
                    if not chapter_url or not chapter_title:
                        continue
                    
                    if not chapter_url.startswith('http'):
                        if chapter_url.startswith('/'):
                            chapter_url = f"{self.base_url}{chapter_url}"
                        else:
                            chapter_url = f"{url.rsplit('/', 1)[0]}/{chapter_url}"
                    
                    chapters.append((chapter_title, chapter_url))
            else:
                chapter_selectors = [
                    '.chapter-list a',
                    '.list-chapters a',
                    '#chapters a',
                    '.chapterlist a',
                    '.book-list a',
                    '.novel-list a',
                    'ul.list a',
                    '.content-list a',
                    '#list a',
                    '.section-list a',
                ]

                for selector in chapter_selectors:
                    chapter_elements = soup.select(selector)
                    if chapter_elements:
                        print(f"[XiaoshuoyueduSource] 使用选择器 '{selector}' 找到 {len(chapter_elements)} 个章节")
                        for elem in chapter_elements:
                            chapter_url = elem.get('href', '')
                            chapter_title = elem.get_text(strip=True)
                            
                            if not chapter_url or not chapter_title:
                                continue
                            
                            if any(kw in chapter_title for kw in ['下一页', '上一页', '首页', '末页', '返回']):
                                continue
                            
                            if not chapter_url.startswith('http'):
                                if chapter_url.startswith('/'):
                                    chapter_url = f"{self.base_url}{chapter_url}"
                                else:
                                    chapter_url = f"{url.rsplit('/', 1)[0]}/{chapter_url}"
                            
                            chapters.append((chapter_title, chapter_url))
                        
                        if chapters:
                            break

            print(f"[XiaoshuoyueduSource] 提取完成，共 {len(chapters)} 个章节")
            self.finished.emit(url, novel_title, chapters)
            return novel_title, chapters

        except Exception as e:
            print(f"[XiaoshuoyueduSource] extract_novel_info异常: {e}")
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))
            return "未知小说", []

    def extract_chapter_content(self, chapter_url: str) -> Optional[str]:
        """获取章节内容"""
        print(f"[XiaoshuoyueduSource] extract_chapter_content: {chapter_url}")
        try:
            html_content = self._get_page_content(chapter_url)
            if not html_content:
                print(f"[XiaoshuoyueduSource] 获取页面失败")
                return None

            soup = BeautifulSoup(html_content, 'html.parser')

            content_selectors = [
                '#content',
                '.chapter-content',
                '.novel-content',
                '.text-content',
                '.read-content',
                'article',
                '.content',
                '#chaptercontent',
                '.book-content',
            ]

            content_element = None
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    print(f"[XiaoshuoyueduSource] 使用选择器 '{selector}' 找到内容")
                    break

            if not content_element:
                all_divs = soup.find_all('div')
                max_text_len = 0
                for div in all_divs:
                    text = div.get_text(strip=True)
                    if len(text) > max_text_len and len(text) > 200:
                        max_text_len = len(text)
                        content_element = div

            if not content_element:
                print(f"[XiaoshuoyueduSource] 未找到内容元素")
                return None

            for unwanted in content_element.select('script, style, .ad, .adsbygoogle, .navigation, iframe'):
                unwanted.decompose()

            paragraphs = content_element.find_all('p')
            if paragraphs and len(paragraphs) > 3:
                text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            else:
                text = content_element.get_text(separator='\n', strip=True)

            if not text or len(text) < 50:
                print(f"[XiaoshuoyueduSource] 内容太短: {len(text)}")
                return None

            ad_patterns = [
                r'.*?天才一秒记住.*?',
                r'.*?笔趣阁.*?最新章节.*?',
                r'.*?www\..*?\.com.*?',
                r'.*?请记住本站域名.*?',
                r'.*?手机用户请.*?',
                r'.*?最新网址.*?',
                r'.*?永久地址.*?',
                r'.*?章节错误.*?',
            ]

            for pattern in ad_patterns:
                text = re.sub(pattern, '', text, flags=re.MULTILINE)

            text = re.sub(r'\n{3,}', '\n\n', text)
            
            lines = text.split('\n')
            lines = [line.strip() for line in lines if line.strip()]
            
            filtered_lines = []
            for line in lines:
                if len(line) < 10:
                    nav_keywords = ['上一章', '下一章', '目录', '书架', '投票', '推荐']
                    if any(kw in line for kw in nav_keywords):
                        continue
                filtered_lines.append(line)

            final_text = '\n\n'.join(filtered_lines)
            print(f"[XiaoshuoyueduSource] 提取内容长度: {len(final_text)}")
            return final_text.strip() if final_text else None

        except Exception as e:
            print(f"[XiaoshuoyueduSource] extract_chapter_content异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def search_novel(self, keyword: str) -> List[dict]:
        """搜索小说"""
        try:
            from urllib.parse import quote
            encoded_keyword = quote(keyword)
            search_url = f"{self.base_url}/search?searchkey={encoded_keyword}"
            print(f"[XiaoshuoyueduSource] 搜索URL: {search_url}")
            print(f"[XiaoshuoyueduSource] 搜索关键词: {keyword}")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Cache-Control': 'max-age=0',
                'Cookie': '__51uvsct__KlbLV9rWt7neFgxP=1; __51vcke__KlbLV9rWt7neFgxP=8e0c16ed-f8ef-55b6-9b0c-b35d971c43e7; __51vuft__KlbLV9rWt7neFgxP=1770894977410; Hm_lvt_abeb97d62bae1479d29dda44f2d0573b=1770894978; HMACCOUNT=A0FAE083D872A80F; articlevisited=1; Hm_lpvt_abeb97d62bae1479d29dda44f2d0573b=1770898040; __vtins__KlbLV9rWt7neFgxP=%7B%22sid%22%3A%20%22c188e36e-4e35-5577-bbef-10fc2a763b1d%22%2C%20%22vd%22%3A%2030%2C%20%22stt%22%3A%203062589%2C%20%22dr%22%3A%2028019%2C%20%22expires%22%3A%201770899839996%2C%20%22ct%22%3A%201770898039996%7D',
                'Sec-Ch-Ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
            }

            response = self.session.get(search_url, headers=headers, timeout=15)
            print(f"[XiaoshuoyueduSource] 响应状态码: {response.status_code}")
            print(f"[XiaoshuoyueduSource] 响应URL: {response.url}")
            
            response.encoding = 'utf-8'
            html_content = response.text

            if not html_content:
                print(f"[XiaoshuoyueduSource] 获取搜索页面失败")
                return []

            print(f"[XiaoshuoyueduSource] 获取到页面内容，长度: {len(html_content)}")
            
            if 'Firewall' in html_content or len(html_content) < 2000:
                print(f"[XiaoshuoyueduSource] 可能被拦截，内容预览: {html_content[:500]}")

            soup = BeautifulSoup(html_content, 'html.parser')
            results = []

            category_divs = soup.select('.category-div')
            print(f"[XiaoshuoyueduSource] 找到 {len(category_divs)} 个搜索结果")

            for div in category_divs:
                try:
                    title_elem = div.select_one('.commend-title a h3')
                    link_elem = div.select_one('.commend-title a')
                    author_elem = div.select_one('.commend-title span')
                    intro_elem = div.select_one('.intro')
                    
                    if title_elem and link_elem:
                        title = title_elem.get_text(strip=True)
                        link = link_elem.get('href', '')
                        author = author_elem.get_text(strip=True) if author_elem else '未知作者'
                        intro = intro_elem.get_text(strip=True) if intro_elem else ''
                        
                        if link and not link.startswith('http'):
                            if link.startswith('/'):
                                link = f"{self.base_url}{link}"
                            else:
                                link = f"{self.base_url}/{link}"
                        
                        if title and link:
                            results.append({
                                'title': title,
                                'author': author,
                                'description': intro,
                                'url': link,
                                'cover': '',
                                'source': self.source_name
                            })
                            print(f"[XiaoshuoyueduSource] 找到小说: {title} - {author} - {link}")
                except Exception as e:
                    print(f"[XiaoshuoyueduSource] 解析单个结果失败: {e}")
                    continue

            print(f"[XiaoshuoyueduSource] 搜索完成，共 {len(results)} 个结果")
            return results

        except Exception as e:
            print(f"[XiaoshuoyueduSource] 搜索异常: {e}")
            import traceback
            traceback.print_exc()
            return []
