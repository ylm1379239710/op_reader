"""小说源管理器 - 管理和调度各小说源"""
from typing import List, Optional, Dict
from novel_base import NovelSourceBase
from deqixs_source import DeqixsSource
from xiaoshuoyuedu_source import XiaoshuoyueduSource


class NovelSourceManager:
    """小说源管理器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._sources = {}
            cls._instance._register_default_sources()
        return cls._instance

    def _register_default_sources(self):
        """注册默认小说源"""
        self.register_source(DeqixsSource())
        self.register_source(XiaoshuoyueduSource())

    def register_source(self, source: NovelSourceBase):
        """注册小说源"""
        self._sources[source.source_name] = source

    def get_source(self, url: str) -> Optional[NovelSourceBase]:
        """根据URL获取对应的小说源"""
        for source in self._sources.values():
            if source.is_supported(url):
                return source
        return None

    def get_source_by_name(self, name: str) -> Optional[NovelSourceBase]:
        """根据名称获取小说源"""
        return self._sources.get(name)

    def get_all_sources(self) -> List[NovelSourceBase]:
        """获取所有已注册的小说源"""
        return list(self._sources.values())

    def get_supported_domains(self) -> Dict[str, List[str]]:
        """获取所有支持的域名"""
        return {source.source_name: source.supported_domains
                for source in self._sources.values()}

    def search_all_sources(self, keyword: str) -> Dict[str, List[dict]]:
        """在所有小说源中搜索"""
        results = {}
        for name, source in self._sources.items():
            search_results = source.search_novel(keyword)
            if search_results:
                results[name] = search_results
        return results
