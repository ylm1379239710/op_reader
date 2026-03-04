# 小说语音阅读器

一个功能丰富的小说阅读与语音朗读应用，支持多小说源搜索、章节内容获取、文本转语音等功能。

## 功能特点

### 多小说源支持
- **得奇小说网** (deqixs.co) - 支持搜索和章节获取
- **小说阅读网** (xiaoshuoyuedu.com) - 支持搜索和章节获取
- 可扩展架构，方便添加更多小说源

### 语音朗读
- 使用 Edge-TTS 高质量语音合成
- 多种中文语音选择（晓晓、云希等）
- 可调节语速（0.5x - 2.0x）
- 音频文件自动缓存，避免重复生成

### 阅读功能
- 章节列表导航
- 自动播放下一章
- 播放进度控制
- 暂停/继续播放
- 上一章/下一章切换

### 书架管理
- 自动保存已加载的小说
- 记住上次阅读位置
- 快速访问历史小说

## 文件结构

```
op_reader/
├── config.py              # 配置文件（语音映射、目录设置等）
├── utils.py               # 工具函数
├── novel_base.py          # 小说源抽象基类
├── deqixs_source.py       # 得奇小说网源实现
├── xiaoshuoyuedu_source.py # 小说阅读网源实现
├── source_manager.py      # 小说源管理器
├── tts_engine.py          # TTS引擎模块
├── reader_optimized.py    # 主程序
├── novel/                 # 小说文件存储目录
├── mp3/                   # 音频文件缓存目录
└── dist/                  # 打包后的可执行文件
```

## 安装依赖

```bash
pip install -r requirements.txt
```

依赖包：
- PySide6 >= 6.5.0 (GUI框架)
- pygame >= 2.5.0 (音频播放)
- edge-tts >= 6.1.0 (语音合成)
- requests >= 2.31.0 (网络请求)
- beautifulsoup4 >= 4.12.0 (HTML解析)
- mutagen >= 1.47.0 (音频元数据)

## 使用方法

### 运行程序
```bash
python reader_optimized.py
```

### 或使用打包版本
直接运行 `dist/小说阅读器.exe`

### 加载小说
1. **在线搜索**: 切换到"小说获取"标签页，选择小说源，输入关键词搜索
2. **本地文件**: 通过书架或直接打开已保存的小说文件

### 播放朗读
1. 在章节列表中选择章节
2. 点击"开始"按钮
3. 首次播放会自动生成音频文件

### 设置
- 选择语音类型
- 调节语速
- 开启/关闭自动播放下一章

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| 空格 | 播放/暂停 |
| Ctrl + → | 下一章 |
| Ctrl + ← | 上一章 |

## 扩展小说源

要添加新的小说源，需要：

1. 创建新的源文件（如 `new_source.py`）
2. 继承 `NovelSourceBase` 基类
3. 实现以下方法：
   - `search_novel(keyword)` - 搜索小说
   - `extract_novel_info(url)` - 提取小说信息
   - `extract_chapter_content(url)` - 获取章节内容
4. 在 `source_manager.py` 中注册新源

示例：
```python
from novel_base import NovelSourceBase

class NewSource(NovelSourceBase):
    def __init__(self):
        super().__init__()
        self.source_name = "新小说源"
        self.base_url = "https://example.com"
    
    def search_novel(self, keyword: str) -> List[dict]:
        # 实现搜索逻辑
        pass
    
    def extract_novel_info(self, url: str) -> Tuple[str, List]:
        # 实现小说信息提取
        pass
    
    def extract_chapter_content(self, chapter_url: str) -> Optional[str]:
        # 实现章节内容获取
        pass
```

## 打包为可执行文件

```bash
pyinstaller --onefile --windowed --name "小说阅读器" reader_optimized.py
```

## 注意事项

- 首次生成音频需要网络连接
- 音频文件会缓存到 `mp3/` 目录
- 不同源的同名小说会分别存储
- 建议在网络良好时预加载章节

## 许可证

本项目仅供学习交流使用。
