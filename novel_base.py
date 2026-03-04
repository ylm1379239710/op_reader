"""小说源抽象基类 - 定义小说源的统一接口"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from PySide6.QtCore import QObject, Signal


class NovelSourceBase(QObject):
    """小说源抽象基类"""

    finished = Signal(str, str, list)
    error = Signal(str)
    progress = Signal(int, str)
    search_finished = Signal(list)

    def __init__(self):
        super().__init__()
        self.source_name = ""
        self.supported_domains = []

    @abstractmethod
    def is_supported(self, url: str) -> bool:
        """检查是否支持该URL"""
        pass

    @abstractmethod
    def extract_novel_info(self, url: str) -> Tuple[str, List[Tuple[str, str]]]:
        """提取小说信息（标题和章节列表）"""
        pass

    @abstractmethod
    def extract_chapter_content(self, chapter_url: str) -> Optional[str]:
        """获取章节内容"""
        pass

    @abstractmethod
    def search_novel(self, keyword: str) -> List[dict]:
        """搜索小说"""
        pass
