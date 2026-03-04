"""得取小说源实现"""
import requests
from bs4 import BeautifulSoup
from typing import List, Tuple, Optional
from novel_base import NovelSourceBase
import re


class DeqixsSource(NovelSourceBase):
    """得取小说源实现"""

    def __init__(self):
        super().__init__()
        self.source_name = "得取小说"
        self.supported_domains = ["deqixs.co", "www.deqixs.co"]
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })

    def is_supported(self, url: str) -> bool:
        """检查是否支持该URL"""
        return any(domain in url for domain in self.supported_domains)

    def extract_novel_info(self, url: str) -> Tuple[str, List[Tuple[str, str]]]:
        """提取小说信息（标题和章节列表）"""
        print(f"[DeqixsSource] extract_novel_info: {url}")
        try:
            novel_title = ""
            if not novel_title:
                html_content = self._get_page_content(url)
                if html_content:
                    soup = BeautifulSoup(html_content, 'html.parser')
                    title_element = soup.find('h1')
                    if title_element:
                        novel_title = title_element.text.strip()
                        print(f"[DeqixsSource] 找到标题: {novel_title}")

            chapters = []
            current_url = url
            page_count = 1
            
            print(f"[DeqixsSource] 开始提取章节列表...")
            
            while True:
                print(f"[DeqixsSource] 正在处理第 {page_count} 页: {current_url}")
                html_content = self._get_page_content(current_url)
                if not html_content:
                    print(f"[DeqixsSource] 获取页面失败")
                    break

                soup = BeautifulSoup(html_content, 'html.parser')

                chapter_selectors = [
                    '#list-chapterAll a',
                    '.chapter-list a',
                    '.listmain a',
                    '.chapter a',
                    'a[href*="chapter"]',
                    '#list a',
                    '.section-list a',
                    '.content-list a',
                    '.chapterlist a',
                    '.booklist a',
                    '#chapter-list a',
                    '.volume a',
                    '.list a'
                ]

                page_chapters = []
                found_selector = None
                for selector in chapter_selectors:
                    chapter_elements = soup.select(selector)
                    if chapter_elements:
                        found_selector = selector
                        print(f"[DeqixsSource] 使用选择器 '{selector}' 找到 {len(chapter_elements)} 个章节")
                        for element in chapter_elements:
                            chapter_url = element.get('href')
                            chapter_title = element.text.strip()
                            if chapter_url and chapter_title:
                                if any(keyword in chapter_title for keyword in ['下一页', '上一页', '首页', '末页']):
                                    continue
                                if chapter_title.strip() in ['>', '>>', '<', '<<']:
                                    continue
                                if 'page=' in chapter_url:
                                    continue
                                if chapter_title.strip().isdigit():
                                    continue
                                if chapter_title and len(chapter_title) < 2:
                                    continue
                                if not chapter_url.startswith('http'):
                                    if chapter_url.startswith('/'):
                                        chapter_url = f"https://www.deqixs.co{chapter_url}"
                                    else:
                                        chapter_url = f"{url.rsplit('/', 1)[0]}/{chapter_url}"
                                page_chapters.append((chapter_title, chapter_url))
                        break

                if page_chapters:
                    chapters.extend(page_chapters)
                    print(f"[DeqixsSource] 本页添加 {len(page_chapters)} 个章节")
                else:
                    print(f"[DeqixsSource] 本页未找到章节")

                next_page = None

                next_page_elements = soup.find_all('a', string=lambda text: text and '下一页' in text)
                if next_page_elements:
                    next_page = next_page_elements[0]
                    print(f"[DeqixsSource] 找到下一页链接")

                if not next_page:
                    next_page_elements = soup.select('.next, .nextpage, .pagenext')
                    if next_page_elements:
                        next_page = next_page_elements[0]

                if not next_page:
                    page_links = soup.find_all('a', href=lambda href: href and 'page=' in href)
                    for link in page_links:
                        try:
                            page_num = int(re.search(r'page=(\d+)', link.get('href')).group(1))
                            if page_num == page_count + 1:
                                next_page = link
                                break
                        except:
                            continue

                if next_page:
                    next_page_url = next_page.get('href')
                    if not next_page_url.startswith('http'):
                        if next_page_url.startswith('/'):
                            next_page_url = f"https://www.deqixs.co{next_page_url}"
                        else:
                            next_page_url = f"{url.rsplit('/', 1)[0]}/{next_page_url}"
                    current_url = next_page_url
                    page_count += 1
                else:
                    print(f"[DeqixsSource] 没有下一页，结束")
                    break

            print(f"[DeqixsSource] 提取完成，共 {len(chapters)} 个章节")
            self.finished.emit(url, novel_title, chapters)
            return novel_title, chapters

        except Exception as e:
            print(f"[DeqixsSource] extract_novel_info异常: {e}")
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))
            return "未知小说", []

    def extract_chapter_content(self, chapter_url: str) -> Optional[str]:
        """获取章节内容"""
        print(f"[extract_chapter_content] 开始获取: {chapter_url}")
        try:
            html_content = self._get_page_content(chapter_url)

            if not html_content:
                print(f"[extract_chapter_content] 获取HTML失败")
                return None

            print(f"[extract_chapter_content] HTML长度: {len(html_content)}")

            soup = BeautifulSoup(html_content, 'html.parser')

            url_match = re.search(r'/books/(\d+)/(\d+)\.html', chapter_url)
            aid = url_match.group(1) if url_match else ""
            cid = url_match.group(2) if url_match else ""
            
            print(f"[extract_chapter_content] aid={aid}, cid={cid}")

            script_match = re.search(
                r'chapterToken\s*=\s*["\']([^"\']+)["\'].*?timestamp\s*=\s*(\d+).*?nonce\s*=\s*["\']([^"\']+)["\']',
                html_content, re.DOTALL
            )
            token = script_match.group(1) if script_match else ""
            timestamp = script_match.group(2) if script_match else ""
            nonce = script_match.group(3) if script_match else ""
            
            print(f"[extract_chapter_content] token={token[:20] if token else 'None'}..., timestamp={timestamp}, nonce={nonce}")

            if aid and cid and token and timestamp and nonce:
                print(f"[extract_chapter_content] 参数完整，调用AJAX接口...")
                content = self._fetch_ajax_content(aid, cid, token, timestamp, nonce, chapter_url)
                if content:
                    print(f"[extract_chapter_content] AJAX获取成功，内容长度: {len(content)}")
                    return content
                else:
                    print(f"[extract_chapter_content] AJAX返回空内容，尝试解析HTML...")

            content_selectors = [
                '#content',
                '#chaptercontent',
                'div#content',
                'div.content',
                '.chapter-content',
                '.read-content',
                '.novel-content',
                '.text-content',
                '.txt',
                '#txt',
                'article',
                '.article-content',
                '#bookcontent',
                '.book-content',
                'div[id*="content"]',
                'div[class*="content"]',
            ]

            content_element = None
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
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
                return None

            for unwanted in content_element.select(
                '.ad, .adsbygoogle, script, style, .navigation, '
                '.chapter-nav, .page-nav, .recommend, .related, '
                'iframe, .footer, .header, .comment'
            ):
                unwanted.decompose()

            paragraphs = content_element.find_all('p')
            if paragraphs and len(paragraphs) > 3:
                text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            else:
                text = content_element.get_text(separator='\n', strip=True)

            if not text or len(text) < 50:
                return None

            text = re.sub(r'\n{3,}', '\n\n', text)

            ad_patterns = [
                r'.*?天才一秒记住.*?',
                r'.*?笔趣阁.*?最新章节.*?',
                r'.*?www\..*?\.com.*?',
                r'.*?请记住本站域名.*?',
                r'.*?手机用户请.*?',
                r'.*?请使用.*?访问.*?',
                r'.*?最新网址.*?',
                r'.*?永久地址.*?',
                r'.*?本章未完.*?点击下一页继续阅读.*?',
                r'.*?↑返回.*?↑.*?',
                r'.*?章节错误.*?点此报送.*?',
                r'.*?加入书签.*?',
                r'.*?推荐阅读.*?',
            ]

            for pattern in ad_patterns:
                text = re.sub(pattern, '', text, flags=re.MULTILINE)

            lines = text.split('\n')
            lines = [line for line in lines if line.strip()]

            filtered_lines = []
            for line in lines:
                line = line.strip()
                if len(line) < 10:
                    nav_keywords = ['上一章', '下一章', '目录', '书架', '投票', '推荐']
                    if any(kw in line for kw in nav_keywords):
                        continue
                filtered_lines.append(line)

            final_text = '\n\n'.join(filtered_lines)

            return final_text.strip() if final_text else None

        except Exception:
            return None

    def _get_page_content(self, url: str, retries: int = 3) -> Optional[str]:
        """获取网页内容"""
        print(f"[DeqixsSource] 请求URL: {url}")
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=10)
                print(f"[DeqixsSource] 响应状态码: {response.status_code}")
                response.encoding = 'utf-8'
                return response.text
            except Exception as e:
                print(f"[DeqixsSource] 请求失败 (尝试 {attempt+1}/{retries}): {e}")
                if attempt == retries - 1:
                    return None
        return None

    def _fetch_ajax_content(self, aid: str, cid: str, token: str, timestamp: str, nonce: str, referer: str) -> Optional[str]:
        """使用AJAX获取章节内容"""
        try:
            ajax_url = (
                f"https://www.deqixs.co/modules/article/ajax2.php?"
                f"aid={aid}&cid={cid}&token={token}&timestamp={timestamp}&nonce={nonce}"
            )

            ajax_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': referer,
                'Origin': 'https://www.deqixs.co',
                'X-Requested-With': 'XMLHttpRequest',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            }

            ajax_response = self.session.get(ajax_url, headers=ajax_headers, timeout=10)
            ajax_response.encoding = 'utf-8'
            ajax_data = ajax_response.json()

            if isinstance(ajax_data, dict) and ajax_data.get('status') == 1:
                data = ajax_data.get('data')
                if isinstance(data, dict) and 'content' in data:
                    content = data['content']
                    content = content.replace('<br />', '\n')
                    content = re.sub(r'<[^>]+>', '', content)
                    return content.strip()

            return None

        except Exception as e:
            print(f"[DeqixsSource] _fetch_ajax_content异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def search_novel(self, keyword: str) -> List[dict]:
        """搜索小说"""
        from urllib.parse import quote
        try:
            encoded_keyword = quote(keyword)
            search_url = f"https://www.deqixs.co/modules/article/search.php?searchkey={encoded_keyword}&action=login&searchtype=all&submit="
            print(f"[DeqixsSource] 搜索URL: {search_url}")

            html_content = self._get_page_content(search_url)
            if not html_content:
                print(f"[DeqixsSource] 获取搜索页面失败")
                return []

            print(f"[DeqixsSource] 获取到页面内容，长度: {len(html_content)}")
            
            soup = BeautifulSoup(html_content, 'html.parser')
            results = []

            selectors = [
                '.bookbox .bookname a',
                '.bookbox a',
                '.result-list a',
                '.search-result a',
                '.novel-list a',
                '.book-list a',
                'table a',
                'a[href*="/\\d+/"]'
            ]

            found_by_selector = None
            for selector in selectors:
                items = soup.select(selector)
                if items:
                    found_by_selector = selector
                    print(f"[DeqixsSource] 使用选择器 '{selector}' 找到 {len(items)} 个元素")
                    break

            if found_by_selector:
                items = soup.select(found_by_selector)
                for item in items:
                    if found_by_selector in ['.bookbox .bookname a', '.bookbox a']:
                        title_elem = item
                        link_elem = item
                    else:
                        title_elem = item.select_one('a, .title, .book-title, .name')
                        link_elem = item.select_one('a[href*="book"]')

                    if title_elem and link_elem:
                        title = title_elem.get_text(strip=True) if hasattr(title_elem, 'get_text') else str(title_elem)
                        link = link_elem.get('href', '') if hasattr(link_elem, 'get') else ''
                        if not link:
                            link = link_elem.get('href', '') if hasattr(link_elem, 'get') else ''
                        if link and not link.startswith('http'):
                            if link.startswith('/'):
                                link = f"https://www.deqixs.co{link}"
                            else:
                                link = f"https://www.deqixs.co/{link}"

                        if title and link:
                            results.append({
                                'title': title,
                                'author': '未知作者',
                                'description': '',
                                'url': link,
                                'cover': '',
                                'source': self.source_name
                            })
                            print(f"[DeqixsSource] 找到小说: {title} - {link}")

            if not results:
                print(f"[DeqixsSource] 未找到搜索结果，尝试查找其他元素...")
                all_links = soup.find_all('a', href=True)
                print(f"[DeqixsSource] 页面中所有链接数量: {len(all_links)}")
                for link in all_links[:20]:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    if 'book' in href or len(text) > 5:
                        print(f"  链接: {text[:30]}... -> {href[:50]}")

            print(f"[DeqixsSource] 搜索完成，共 {len(results)} 个结果")
            return results

        except Exception as e:
            print(f"[DeqixsSource] 搜索异常: {e}")
            import traceback
            traceback.print_exc()
            return []
