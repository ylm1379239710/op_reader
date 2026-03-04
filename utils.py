"""工具函数"""
import os
import json
import re
from typing import Optional, Any

def ensure_dir(directory: str) -> None:
    """确保目录存在"""
    if not os.path.exists(directory):
        os.makedirs(directory)

def clean_text(text: str) -> str:
    """清理文本"""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9，。！？、；：""''《》（）\[\]…—\s]', '', text)
    return text.strip()

def format_time(seconds: float) -> str:
    """格式化时间为 MM:SS"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"

def format_time_ms(ms: int) -> str:
    """格式化毫秒时间为 MM:SS"""
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

def load_json(filepath: str, default: Any = None) -> Any:
    """加载JSON文件"""
    if not os.path.exists(filepath):
        return default if default is not None else {}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default if default is not None else {}

def save_json(filepath: str, data: Any) -> bool:
    """保存JSON文件"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def is_valid_url(url: str) -> bool:
    """验证URL是否有效"""
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None

def sanitize_filename(filename: str) -> str:
    """清理文件名,移除不合法字符"""
    invalid_chars = r'[<>:"/\\|?*]'
    filename = re.sub(invalid_chars, '', filename)
    if len(filename) > 200:
        filename = filename[:200]
    return filename.strip()

def parse_chapter_number(chapter_title: str) -> Optional[int]:
    """从章节标题中解析章节号"""
    patterns = [
        r'第(\d+)[章节]',
        r'第([一二三四五六七八九十百千]+)[章节]',
        r'[Cc]hapter\s*(\d+)',
        r'^(\d+)[\.、\s]',
        r'^\[(\d+)\]',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, chapter_title)
        if match:
            num_str = match.group(1)
            if not num_str.isdigit():
                num_str = chinese_to_arabic(num_str)
            try:
                return int(num_str)
            except ValueError:
                continue
    
    return None

def chinese_to_arabic(chinese_num: str) -> str:
    """将中文数字转换为阿拉伯数字"""
    chinese_digits = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, 
                     '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
    chinese_units = {'十': 10, '百': 100, '千': 1000}
    
    result = 0
    temp = 0
    
    for char in chinese_num:
        if char in chinese_digits:
            temp = chinese_digits[char]
        elif char in chinese_units:
            if temp == 0:
                temp = 1
            result += temp * chinese_units[char]
            temp = 0
    
    result += temp
    return str(result)

class RateLimiter:
    """简单的速率限制器"""
    def __init__(self, max_requests: int, time_window: float):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def can_request(self) -> bool:
        """检查是否可以发起新请求"""
        import time
        current_time = time.time()
        
        self.requests = [t for t in self.requests if current_time - t < self.time_window]
        
        return len(self.requests) < self.max_requests
    
    def add_request(self) -> None:
        """添加新请求"""
        import time
        self.requests.append(time.time())
