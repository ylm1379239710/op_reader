"""优化版小说语音阅读器 - 与reader.py功能兼容"""
import os
import pygame
import glob
import re
from urllib.parse import quote
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QListWidget, QMessageBox,
    QSlider, QComboBox, QGroupBox, QTextEdit, QDialog, QProgressBar, 
    QCheckBox, QListWidgetItem, QLineEdit, QStackedWidget ,QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl, QSettings
from PySide6.QtGui import QFont
from PySide6.QtWebEngineWidgets import QWebEngineView

from config import VOICE_MAP, WINDOW_TITLE, MP3_DIR, NOVEL_DIR, LAST_NOVEL_PATH, LAST_VOICE_INDEX, LAST_SPEED_VALUE, LAST_AUTO_PLAY
from utils import ensure_dir, format_time_ms
from tts_engine import TTSWorker
from source_manager import NovelSourceManager


class UniversalLoadingWorker(QThread):
    """通用章节加载工作线程 - 使用小说源管理器"""
    finished = Signal(str, str, list, str)
    error = Signal(str)

    def __init__(self, novel_url, novel_title=""):
        super().__init__()
        self.novel_url = novel_url
        self.novel_title = novel_title
        self.source_manager = NovelSourceManager()
        self.source_name = ""
        print(f"[UniversalLoadingWorker] 初始化: url={novel_url}")

    def run(self):
        print(f"[UniversalLoadingWorker] 开始运行...")
        try:
            source = self.source_manager.get_source(self.novel_url)
            if source:
                print(f"[UniversalLoadingWorker] 找到源: {source.source_name}")
                self.source_name = source.source_name
                source.finished.connect(self.on_source_finished)
                source.error.connect(self.on_source_error)
                source.extract_novel_info(self.novel_url)
            else:
                print(f"[UniversalLoadingWorker] 未找到支持的小说源")
                self.error.emit(f"不支持的网站: {self.novel_url}")

        except Exception as e:
            print(f"[UniversalLoadingWorker] 异常: {e}")
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))

    def on_source_finished(self, url, title, chapters):
        print(f"[UniversalLoadingWorker] 源完成: url={url}, title={title}, chapters={len(chapters)}")
        if url == self.novel_url:
            self.finished.emit(url, title, chapters, self.source_name)

    def on_source_error(self, error_msg):
        print(f"[UniversalLoadingWorker] 源错误: {error_msg}")
        self.error.emit(error_msg)


class ChapterContentWorker(QThread):
    """章节内容获取工作线程"""
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, chapter_url=""):
        super().__init__()
        self.chapter_url = chapter_url
        self.source_manager = NovelSourceManager()
        self.source = None
    
    def set_chapter_url(self, url):
        self.chapter_url = url

    def run(self):
        try:
            if self.source is None:
                self.source = self.source_manager.get_source(self.chapter_url)
                if self.source:
                    self.source.error.connect(self.on_source_error)
            
            if self.source:
                content = self.source.extract_chapter_content(self.chapter_url)
                if content:
                    self.finished.emit(content)
                else:
                    self.error.emit("获取章节内容失败")
            else:
                self.error.emit(f"不支持的网站")

        except Exception as e:
            self.error.emit(str(e))

    def on_source_error(self, error_msg):
        self.error.emit(error_msg)


class NovelSearchWorker(QThread):
    """小说搜索工作线程"""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, keyword, source_name=None):
        super().__init__()
        self.keyword = keyword
        self.source_name = source_name
        self.source_manager = NovelSourceManager()

    def run(self):
        try:
            print(f"[NovelSearchWorker] 开始搜索: {self.keyword}")
            results = []
            
            if self.source_name:
                source = self.source_manager.get_source_by_name(self.source_name)
                if source:
                    print(f"[NovelSearchWorker] 搜索指定源: {source.source_name}")
                    try:
                        source_results = source.search_novel(self.keyword)
                        print(f"[NovelSearchWorker] {source.source_name} 返回 {len(source_results)} 个结果")
                        if source_results:
                            results.extend(source_results)
                    except Exception as e:
                        print(f"[NovelSearchWorker] {source.source_name} 搜索出错: {e}")
            else:
                sources = self.source_manager.get_all_sources()
                print(f"[NovelSearchWorker] 已注册的小说源: {[s.source_name for s in sources]}")
                
                for source in sources:
                    print(f"[NovelSearchWorker] 正在搜索源: {source.source_name}")
                    try:
                        source_results = source.search_novel(self.keyword)
                        print(f"[NovelSearchWorker] {source.source_name} 返回 {len(source_results)} 个结果")
                        if source_results:
                            results.extend(source_results)
                    except Exception as e:
                        print(f"[NovelSearchWorker] {source.source_name} 搜索出错: {e}")
            
            print(f"[NovelSearchWorker] 搜索完成，共 {len(results)} 个结果")
            self.finished.emit(results)

        except Exception as e:
            print(f"[NovelSearchWorker] 搜索异常: {e}")
            self.error.emit(str(e))


class LoadingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("加载中")
        self.setMinimumWidth(300)
        self.setMinimumHeight(100)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setFixedSize(300, 100)
        self.setModal(False)
        
        layout = QVBoxLayout(self)
        
        self.label = QLabel("正在加载小说章节列表，请稍候...")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont("微软雅黑", 10))
        layout.addWidget(self.label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
    
    def closeEvent(self, event):
        event.ignore()


class TTSProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("语音生成任务")
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)
        self.setWindowModality(Qt.ApplicationModal)
        
        layout = QVBoxLayout(self)
        
        title_label = QLabel("语音生成进度")
        title_label.setFont(QFont("微软雅黑", 12, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        self.current_task_label = QLabel("正在准备...")
        self.current_task_label.setFont(QFont("微软雅黑", 10))
        self.current_task_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.current_task_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        layout.addWidget(self.progress_bar)
        
        task_list_label = QLabel("任务列表:")
        task_list_label.setFont(QFont("微软雅黑", 10))
        layout.addWidget(task_list_label)
        
        self.task_list = QListWidget()
        self.task_list.setFont(QFont("微软雅黑", 9))
        self.task_list.setMaximumHeight(150)
        layout.addWidget(self.task_list)
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        self.close_btn.setEnabled(False)
        layout.addWidget(self.close_btn)
    
    def update_progress(self, value, text):
        self.progress_bar.setValue(value)
        self.current_task_label.setText(text)
    
    def add_task(self, task_text):
        self.task_list.addItem(task_text)
        self.task_list.scrollToBottom()
    
    def update_task_status(self, index, status):
        if index < self.task_list.count():
            item = self.task_list.item(index)
            current_text = item.text()
            if " [等待中]" in current_text:
                item.setText(current_text.replace(" [等待中]", f" {status}"))
            elif " [生成中]" in current_text:
                item.setText(current_text.replace(" [生成中]", f" {status}"))
            elif " [已完成]" not in current_text and " [失败]" not in current_text:
                item.setText(current_text + f" {status}")
    
    def set_finished(self):
        self.progress_bar.setValue(100)
        self.current_task_label.setText("所有任务已完成")
        self.close_btn.setEnabled(True)
        QTimer.singleShot(1500, self.auto_close)
    
    def auto_close(self):
        self.accept()


class NovelReader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        
        window_width = int(screen_width * 0.7)
        window_height = int(screen_height * 0.9)
        
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.setGeometry(x, y, window_width, window_height)
        self.setMinimumSize(800, 600)
        
        ensure_dir(MP3_DIR)
        
        self.novel_path = ""
        self.content = ""
        self.novel_title = ""
        self.chapters = []
        self.current_chapter = -1
        self.is_playing = False
        self.is_paused = False
        self.is_preloading = False
        self.is_auto_switching = False
        self.current_audio_file = None
        self.tts_worker = None
        self.content_worker = None
        self.search_worker = None
        self.loading_worker = None
        self.preload_worker = None
        self.preload_content_worker = None
        self.audio_duration = 0
        self.playback_start_time = 0
        self.playback_start_pos = 0
        self.is_dragging_progress = False
        self.play_timer = None
        self.on_tts_finished_called = False
        self.tts_progress_dialog = None
        self.auto_play_enabled = False
        self.preload_next_chapter_num = None
        
        pygame.mixer.init()
        pygame.mixer.music.set_endevent(pygame.USEREVENT + 1)
        
        self.music_event_timer = QTimer()
        self.music_event_timer.setInterval(50)
        self.music_event_timer.timeout.connect(self.check_music_events)
        self.music_event_timer.start()
        
        font = QFont("微软雅黑", 10)
        QApplication.setFont(font)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        help_group = QGroupBox("📖 使用流程")
        help_group.setFont(QFont("微软雅黑", 10))
        help_layout = QHBoxLayout(help_group)
        help_layout.setSpacing(20)
        
        step1 = QLabel("① <b>小说获取</b> - 从网站搜索或浏览下载小说")
        step1.setFont(QFont("微软雅黑", 9))
        step2 = QLabel("② <b>我的书架</b> - 查看和管理已下载的小说")
        step2.setFont(QFont("微软雅黑", 9))
        step3 = QLabel("③ <b>语音阅读</b> - 选择章节，点击开始听书")
        step3.setFont(QFont("微软雅黑", 9))
        
        help_layout.addWidget(step1)
        help_layout.addWidget(step2)
        help_layout.addWidget(step3)
        
        precondition_group = QGroupBox("⚠️ 使用前提")
        precondition_group.setFont(QFont("微软雅黑", 10))
        precondition_layout = QVBoxLayout(precondition_group)
        precondition_layout.setSpacing(5)
        
        precondition_label = QLabel("📡 <b>需要连接网络</b> - 获取小说内容和生成语音都需要联网")
        precondition_label.setFont(QFont("微软雅黑", 9))
        precondition_label.setStyleSheet("color: #E65100;")
        precondition_layout.addWidget(precondition_label)
        
        top_row_layout = QHBoxLayout()
        top_row_layout.addWidget(help_group)
        top_row_layout.addWidget(precondition_group)
        
        main_layout.addLayout(top_row_layout)
        
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("微软雅黑", 11))
        main_layout.addWidget(self.tab_widget)
        
        self.web_tab = QWidget()
        self.tab_widget.addTab(self.web_tab, "小说获取")
        
        self.novel_shelf_tab = QWidget()
        self.tab_widget.addTab(self.novel_shelf_tab, "我的书架")
        
        self.main_tab = QWidget()
        self.tab_widget.addTab(self.main_tab, "语音阅读")
        
        self.init_web_tab()
        self.init_novel_shelf_tab()
        self.init_main_tab()
        self.update_voice_list()
        
        ensure_dir(NOVEL_DIR)
        
        QTimer.singleShot(1000, self.load_last_novel)
    
    def init_main_tab(self):
        layout = QHBoxLayout(self.main_tab)
        layout.setSpacing(15)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(10)
        
        self.current_novel_label = QLabel("未加载小说")
        self.current_novel_label.setFont(QFont("微软雅黑", 12, QFont.Bold))
        self.current_novel_label.setStyleSheet("color: #1976D2;")
        self.current_novel_label.setAlignment(Qt.AlignCenter)
        self.current_novel_label.setMinimumHeight(35)
        
        left_layout.addWidget(self.current_novel_label)
        
        tip_group = QGroupBox("📌 听书须知")
        tip_group.setFont(QFont("微软雅黑", 12))
        tip_layout = QVBoxLayout(tip_group)
        tip_layout.setSpacing(5)
        
        tip_label = QLabel("1️⃣ 系统会先将文字转为MP3音频文件\n2️⃣ 首次生成需要一些时间，时间由电脑性能决定\n3️⃣ 生成完成后自动开始播放\n4️⃣ 生成过的章节下次可直接播放\n5️⃣ 语音会占用磁盘空间，请及时清理音频")
        tip_label.setFont(QFont("微软雅黑", 12))
        tip_label.setStyleSheet("color: #FF0000;")
        tip_label.setWordWrap(True)
        tip_layout.addWidget(tip_label)
        
        self.clean_audio_btn = QPushButton("🗑️ 已有音频")
        self.clean_audio_btn.clicked.connect(self.clean_audio_files)
        self.clean_audio_btn.setMinimumWidth(140)
        self.clean_audio_btn.setMinimumHeight(35)
        self.clean_audio_btn.setFont(QFont("微软雅黑", 11))
        self.clean_audio_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
            QPushButton:pressed {
                background-color: #D84315;
            }
        """)
        tip_layout.addWidget(self.clean_audio_btn, alignment=Qt.AlignCenter)
        
        left_layout.addWidget(tip_group)
        
        chapter_group = QGroupBox("章节列表")
        chapter_group.setFont(QFont("微软雅黑", 11))
        chapter_layout = QVBoxLayout(chapter_group)
        
        self.chapter_list = QListWidget()
        self.chapter_list.setFont(QFont("微软雅黑", 10))
        self.chapter_list.setMinimumHeight(300)
        self.chapter_list.itemClicked.connect(self.on_chapter_clicked)
        
        chapter_layout.addWidget(self.chapter_list)
        
        left_layout.addWidget(chapter_group)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(15)
        
        content_group = QGroupBox("章节内容")
        content_group.setFont(QFont("微软雅黑", 11))
        content_layout = QVBoxLayout(content_group)
        
        self.chapter_content = QTextEdit()
        self.chapter_content.setFont(QFont("微软雅黑", 10))
        self.chapter_content.setMinimumHeight(200)
        self.chapter_content.setReadOnly(True)
        
        content_layout.addWidget(self.chapter_content)
        
        setting_tip = QLabel("💡 因为无法实时实现语速与语音的切换，所以开始前请先选择您喜欢的语速和语音类型。\n切换到没有生成过的语速和语音类型都会重新生成，不建议经常修改（推荐1.5x倍速男生云希）")
        setting_tip.setFont(QFont("微软雅黑", 14))
        setting_tip.setStyleSheet("color: #FF0000;")
        setting_tip.setAlignment(Qt.AlignCenter)
        setting_tip.setMinimumHeight(25)
        content_layout.addWidget(setting_tip)
        
        control_group = QGroupBox("阅读控制")
        control_group.setFont(QFont("微软雅黑", 11))
        control_layout = QVBoxLayout(control_group)
        
        button_row = QHBoxLayout()
        button_row.setSpacing(15)
        
        self.start_btn = QPushButton("开始")
        self.start_btn.clicked.connect(self.start_reading)
        self.start_btn.setMinimumWidth(100)
        self.start_btn.setFont(QFont("微软雅黑", 10, QFont.Bold))
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.clicked.connect(self.pause_reading)
        self.pause_btn.setMinimumWidth(80)
        self.pause_btn.setFont(QFont("微软雅黑", 10))
        self.pause_btn.setEnabled(False)
        self.pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0b7dda;
            }
            QPushButton:pressed {
                background-color: #0a6eb8;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self.stop_reading)
        self.stop_btn.setMinimumWidth(80)
        self.stop_btn.setFont(QFont("微软雅黑", 10))
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c41105;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        button_row.addWidget(self.start_btn)
        button_row.addWidget(self.pause_btn)
        button_row.addWidget(self.stop_btn)
        
        button_row.addSpacing(20)
        
        self.prev_chapter_btn = QPushButton("◀ 上一章")
        self.prev_chapter_btn.clicked.connect(self.prev_chapter)
        self.prev_chapter_btn.setMinimumWidth(100)
        self.prev_chapter_btn.setFont(QFont("微软雅黑", 10))
        self.prev_chapter_btn.setEnabled(False)
        self.prev_chapter_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:pressed {
                background-color: #6A1B9A;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        button_row.addWidget(self.prev_chapter_btn)
        
        self.next_chapter_btn = QPushButton("下一章 ▶")
        self.next_chapter_btn.clicked.connect(self.next_chapter)
        self.next_chapter_btn.setMinimumWidth(100)
        self.next_chapter_btn.setFont(QFont("微软雅黑", 10))
        self.next_chapter_btn.setEnabled(False)
        self.next_chapter_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:pressed {
                background-color: #6A1B9A;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        button_row.addWidget(self.next_chapter_btn)
        
        button_row.addStretch()
        
        speed_row = QHBoxLayout()
        speed_label = QLabel("语速:")
        speed_label.setMinimumWidth(50)
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(50)
        self.speed_slider.setMaximum(300)
        self.speed_slider.setValue(100)
        self.speed_slider.setSingleStep(10)
        self.speed_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 8px;
                background: #e0e0e0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #2196F3;
                width: 18px;
                height: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #0b7dda;
            }
            QSlider::sub-page:horizontal {
                background: #2196F3;
                border-radius: 4px;
            }
            QSlider:disabled {
                opacity: 0.5;
            }
            QSlider::groove:horizontal:disabled {
                background: #f0f0f0;
            }
            QSlider::handle:horizontal:disabled {
                background: #cccccc;
            }
            QSlider::sub-page:horizontal:disabled {
                background: #cccccc;
            }
        """)
        self.speed_value = QLabel("1.0x")
        self.speed_value.setMinimumWidth(50)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        speed_row.addWidget(speed_label)
        speed_row.addWidget(self.speed_slider)
        speed_row.addWidget(self.speed_value)
        
        voice_row = QHBoxLayout()
        voice_label = QLabel("语音:")
        voice_label.setMinimumWidth(50)
        self.voice_combo = QComboBox()
        self.voice_combo.setFont(QFont("微软雅黑", 10))
        self.voice_combo.setMinimumWidth(150)
        self.voice_combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                color: black;
                border: 1px solid #ccc;
                padding: 5px;
                border-radius: 3px;
            }
            QComboBox:hover {
                border: 1px solid #2196F3;
            }
            QComboBox:disabled {
                background-color: #f0f0f0;
                color: #999999;
                border: 1px solid #e0e0e0;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
        """)
        voice_row.addWidget(voice_label)
        voice_row.addWidget(self.voice_combo)
        
        progress_row = QHBoxLayout()
        progress_label = QLabel("进度:")
        progress_label.setMinimumWidth(50)
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setMinimum(0)
        self.progress_slider.setMaximum(100)
        self.progress_slider.setValue(0)
        self.progress_slider.sliderPressed.connect(self.on_progress_pressed)
        self.progress_slider.sliderReleased.connect(self.on_progress_released)
        self.progress_time = QLabel("00:00 / 00:00")
        self.progress_time.setMinimumWidth(100)
        self.progress_time.setAlignment(Qt.AlignCenter)
        progress_row.addWidget(progress_label)
        progress_row.addWidget(self.progress_slider)
        progress_row.addWidget(self.progress_time)
        
        status_row = QHBoxLayout()
        status_label = QLabel("状态:")
        status_label.setMinimumWidth(50)
        self.status_label = QLabel("就绪")
        self.status_label.setFont(QFont("微软雅黑", 10))
        status_row.addWidget(status_label)
        status_row.addWidget(self.status_label)
        
        auto_play_row = QHBoxLayout()
        self.auto_play_checkbox = QCheckBox("自动播放下一章（功能开启时会自动缓存下一章内容）")
        self.auto_play_checkbox.setChecked(False)
        self.auto_play_checkbox.toggled.connect(self.on_auto_play_toggled)
        auto_play_row.addWidget(self.auto_play_checkbox)
        
        control_layout.addLayout(button_row)
        control_layout.addLayout(speed_row)
        control_layout.addLayout(voice_row)
        control_layout.addLayout(progress_row)
        control_layout.addLayout(status_row)
        control_layout.addLayout(auto_play_row)
        
        right_layout.addWidget(content_group)
        right_layout.addWidget(control_group)
        
        left_widget.setMaximumWidth(350)
        layout.addWidget(left_widget)
        layout.addWidget(right_widget)
    
    def on_speed_changed(self, value):
        speed = value / 100.0
        self.speed_value.setText(f"{speed:.2f}x")
    
    def on_auto_play_toggled(self, checked):
        self.auto_play_enabled = checked
        
        if checked and self.is_playing:
            self.preload_next_chapter()
    
    def get_audio_filename(self, chapter_num, chapter_title, voice, rate):
        safe_novel_title = re.sub(r'[<>:"/\\|?*]', '', self.novel_title) if self.novel_title else "未知小说"
        safe_novel_title = safe_novel_title[:20]
        safe_title = re.sub(r'[<>:"/\\|?*]', '', chapter_title)
        safe_title = safe_title[:30]
        
        source_prefix = ""
        if hasattr(self, 'novel_source') and self.novel_source:
            safe_source = re.sub(r'[<>:"/\\|?*]', '', self.novel_source)[:10]
            source_prefix = f"[{safe_source}]_"
        
        return os.path.join(MP3_DIR, f"{source_prefix}{safe_novel_title}_{chapter_num}_{safe_title}_{voice}_{rate}.mp3")
    
    def preload_next_chapter(self):
        if self.current_chapter < 0:
            return
        
        if self.is_preloading:
            print(f"[预加载] 已在预加载中，跳过")
            return
        
        next_chapter = self.current_chapter + 1
        if next_chapter >= len(self.chapters):
            self.preload_next_chapter_num = None
            return
        
        self.preload_next_chapter_num = next_chapter
        self.is_preloading = True
        print(f"[预加载] 开始预加载第{next_chapter + 1}章")
        
        next_chapter_title, next_chapter_content = self.chapters[next_chapter]
        
        voice_name = self.voice_combo.currentText()
        voice = VOICE_MAP.get(voice_name, VOICE_MAP["中文-女声（晓晓）"])
        speed_value = self.speed_slider.value()
        rate_offset = (speed_value - 100)
        rate = f"{rate_offset:+d}%"
        
        audio_file = self.get_audio_filename(next_chapter + 1, next_chapter_title, voice, rate)
        
        if os.path.exists(audio_file):
            print(f"[预加载] 第{next_chapter + 1}章音频已存在")
            self.is_preloading = False
            return
        
        url_match = re.search(r'\[URL: (.*?)\]', next_chapter_content)
        if url_match and len(next_chapter_content) < 500:
            chapter_url = url_match.group(1)
            
            def on_content_fetched(content):
                if content and len(content) > 100 and not content.startswith('http'):
                    speed_value = self.speed_slider.value()
                    rate_offset = speed_value - 100
                    rate = f"{rate_offset:+d}%"
                    
                    novel_source = getattr(self, 'novel_source', '')
                    self.preload_worker = TTSWorker(content, voice, rate, next_chapter, next_chapter_title, self.novel_title, novel_source)
                    
                    def on_preload_finished():
                        print(f"[预加载] 第{next_chapter + 1}章TTS生成完成")
                        self.is_preloading = False
                    
                    def on_preload_error(error_msg):
                        print(f"[预加载] 第{next_chapter + 1}章生成失败: {error_msg}")
                        self.preload_next_chapter_num = None
                        self.is_preloading = False
                    
                    self.preload_worker.finished.connect(on_preload_finished)
                    self.preload_worker.error.connect(on_preload_error)
                    self.preload_worker.start()
                else:
                    print(f"[预加载] 内容无效或太短，跳过生成")
                    self.is_preloading = False
            
            def on_content_error(error_msg):
                print(f"[预加载] 获取章节内容失败: {error_msg}")
                self.preload_next_chapter_num = None
                self.is_preloading = False
            
            if self.preload_content_worker is None:
                self.preload_content_worker = ChapterContentWorker("")
            
            if self.preload_content_worker.isRunning():
                print(f"[预加载] 线程正在运行，跳过重复请求")
                self.is_preloading = False
                return
            
            self.preload_content_worker.set_chapter_url(chapter_url)
            try:
                self.preload_content_worker.finished.disconnect()
                self.preload_content_worker.error.disconnect()
            except:
                pass
            self.preload_content_worker.finished.connect(on_content_fetched)
            self.preload_content_worker.error.connect(on_content_error)
            
            self.preload_content_worker.start()
        elif len(next_chapter_content) > 200 and not next_chapter_content.startswith('[URL:'):
            novel_source = getattr(self, 'novel_source', '')
            self.preload_worker = TTSWorker(next_chapter_content, voice, rate, next_chapter, next_chapter_title, self.novel_title, novel_source)
            
            def on_preload_finished():
                print(f"[预加载] 第{next_chapter + 1}章TTS生成完成")
                self.is_preloading = False
            
            def on_preload_error(error_msg):
                print(f"[预加载] 第{next_chapter + 1}章生成失败: {error_msg}")
                self.preload_next_chapter_num = None
                self.is_preloading = False
            
            self.preload_worker.finished.connect(on_preload_finished)
            self.preload_worker.error.connect(on_preload_error)
            self.preload_worker.start()
        else:
            print(f"[预加载] 内容无效，跳过生成")
            self.is_preloading = False
        
        self.preload_next_chapter_num = None
    
    def load_novel(self, file_path=None, show_loading_dialog=True, callback=None):
        if file_path:
            self.novel_path = file_path
        else:
            self.novel_path = self.novel_path if hasattr(self, 'novel_path') and self.novel_path else ""
        
        if not self.novel_path:
            QMessageBox.critical(self, "错误", "未找到小说文件!")
            if callback:
                callback(False)
            return
        
        if not os.path.exists(self.novel_path):
            QMessageBox.critical(self, "错误", "小说文件不存在!")
            if callback:
                callback(False)
            return
        
        original_status = self.status_label.text()
        if show_loading_dialog:
            self.status_label.setText("⏳ 正在加载小说文件，请稍候...")
        
        def do_load():
            try:
                with open(self.novel_path, 'r', encoding='utf-8') as f:
                    self.content = f.read()
                
                self.novel_title, self.chapters = self.split_into_chapters(self.content)
                
                self.update_chapter_list()
                
                if self.novel_title:
                    self.current_novel_label.setText(f"📖 《{self.novel_title}》")
                else:
                    self.current_novel_label.setText("📖 未知小说")
                
                if show_loading_dialog:
                    self.status_label.setText(f"✅ 小说加载成功，共 {len(self.chapters)} 章")
                    QTimer.singleShot(3000, lambda: self.status_label.setText(original_status))
                
                if self.novel_title and os.path.exists(self.novel_path):
                    self.save_novel_to_shelf(self.novel_title, self.novel_path)
                
                if callback:
                    callback(True)
            except Exception as e:
                if show_loading_dialog:
                    self.status_label.setText(f"❌ 加载失败: {str(e)}")
                    QTimer.singleShot(5000, lambda: self.status_label.setText(original_status))
                if callback:
                    callback(False)
        
        QTimer.singleShot(50, do_load)
    
    def split_into_chapters(self, content):
        chapters = []
        lines = content.split('\n')
        current_chapter = []
        chapter_title = None
        novel_title = None
        novel_source = None
        
        for line in lines:
            if line.startswith('# ') and novel_title is None:
                novel_title = line.strip()[2:]
            elif line.startswith('[SOURCE:'):
                source_match = re.match(r'\[SOURCE: (.*?)\]', line)
                if source_match:
                    novel_source = source_match.group(1)
            elif line.startswith('## '):
                if current_chapter and chapter_title:
                    chapters.append((chapter_title, '\n'.join(current_chapter)))
                    current_chapter = []
                chapter_title = line.strip()[2:]
            elif line.startswith('第') and ('章' in line or '回' in line):
                if current_chapter and chapter_title:
                    chapters.append((chapter_title, '\n'.join(current_chapter)))
                    current_chapter = []
                chapter_title = line.strip()
            else:
                if chapter_title:
                    current_chapter.append(line)
        
        if current_chapter and chapter_title:
            chapters.append((chapter_title, '\n'.join(current_chapter)))
        
        self.novel_source = novel_source
        return novel_title, chapters
    
    def update_chapter_list(self):
        self.chapter_list.clear()
        for i, (title, _) in enumerate(self.chapters):
            self.chapter_list.addItem(f"{i+1}. {title}")
        self.update_chapter_buttons()
    
    def on_chapter_clicked(self, item):
        index = self.chapter_list.row(item)
        self.current_chapter = index
        chapter_title, chapter_content = self.chapters[index]
        
        url_match = re.search(r'\[URL: (.*?)\]', chapter_content)
        if url_match:
            chapter_url = url_match.group(1)
            
            self.status_label.setText("⏳ 正在加载章节内容...")
            
            def on_content_fetched(content):
                if content and len(content) > 100 and not content.startswith('http'):
                    self.chapter_content.setPlainText(content)
                    self.chapters[index] = (chapter_title, content)
                    self.status_label.setText("✅ 章节内容加载完成")
                    QTimer.singleShot(2000, lambda: self.status_label.setText("就绪"))
                    
                    if self.is_auto_switching:
                        print(f"[章节] 内容加载完成，自动开始播放")
                        self.is_auto_switching = False
                        QTimer.singleShot(100, self.start_reading)
                        QTimer.singleShot(200, self.update_chapter_buttons)
                        QTimer.singleShot(500, self.preload_next_chapter)
                else:
                    self.chapter_content.setPlainText("内容加载失败，请重试")
                    self.status_label.setText("❌ 内容无效，请重试")
                    if self.is_auto_switching:
                        print(f"[章节] 内容无效，停止自动播放")
                        self.is_auto_switching = False
            
            def on_content_error(error_msg):
                self.chapter_content.setPlainText(f"获取失败: {error_msg}")
                self.status_label.setText(f"❌ 加载失败: {error_msg}")
                if self.is_auto_switching:
                    print(f"[章节] 获取失败，停止自动播放")
                    self.is_auto_switching = False
            
            if self.content_worker is None:
                self.content_worker = ChapterContentWorker("")
            
            if self.content_worker.isRunning():
                print(f"[章节] 线程正在运行，跳过重复请求")
                return
            
            self.content_worker.set_chapter_url(chapter_url)
            try:
                self.content_worker.finished.disconnect()
                self.content_worker.error.disconnect()
            except:
                pass
            self.content_worker.finished.connect(on_content_fetched)
            self.content_worker.error.connect(on_content_error)
            
            self.content_worker.start()
            print(f"[章节] 开始加载章节内容: {chapter_url}")
        else:
            self.chapter_content.setPlainText(chapter_content)
    
    def update_voice_list(self):
        self.voice_combo.clear()
        for voice_name in VOICE_MAP.keys():
            self.voice_combo.addItem(voice_name)
        
        settings = QSettings("novel_reader.ini", QSettings.IniFormat)
        last_voice_index = settings.value(LAST_VOICE_INDEX, 0, type=int)
        last_speed_value = settings.value(LAST_SPEED_VALUE, 100, type=int)
        last_auto_play = settings.value(LAST_AUTO_PLAY, False, type=bool)
        
        if 0 <= last_voice_index < self.voice_combo.count():
            self.voice_combo.setCurrentIndex(last_voice_index)
        
        if self.speed_slider.minimum() <= last_speed_value <= self.speed_slider.maximum():
            self.speed_slider.setValue(last_speed_value)
            self.on_speed_changed(last_speed_value)
        
        self.auto_play_checkbox.setChecked(last_auto_play)
        self.auto_play_enabled = last_auto_play
    
    def check_music_events(self):
        if self.is_playing and self.pause_btn.text() == "暂停" and not pygame.mixer.music.get_busy():
            print(f"[播放] 检测到播放完成")
            QTimer.singleShot(50, self.on_playback_finished)
    
    def start_reading(self):
        if self.current_chapter == -1:
            QMessageBox.information(self, "提示", "请先选择章节!")
            return
        
        if self.is_playing:
            QMessageBox.information(self, "提示", "正在阅读中，请先停止当前阅读!")
            return
        
        voice_name = self.voice_combo.currentText()
        voice = VOICE_MAP.get(voice_name, VOICE_MAP["中文-女声（晓晓）"])
        speed_value = self.speed_slider.value()
        rate_offset = (speed_value - 100)
        rate = f"{rate_offset:+d}%"
        
        chapter_title, chapter_content = self.chapters[self.current_chapter]
        chapter_num = self.current_chapter + 1
        audio_file = self.get_audio_filename(chapter_num, chapter_title, voice, rate)
        
        if os.path.exists(audio_file):
            self.play_existing_audio(audio_file)
            return
        
        url_match = re.search(r'\[URL: (.*?)\]', chapter_content)
        if url_match and (not chapter_content or len(chapter_content.strip()) < 500):
            chapter_url = url_match.group(1)
            
            if self.content_worker is not None and self.content_worker.isRunning():
                QMessageBox.information(self, "提示", "正在获取章节内容，请稍后再试")
                return
            
            self.status_label.setText("⏳ 正在获取章节内容...")
            
            def on_content_fetched(content):
                if content and len(content) > 100 and not content.startswith('http'):
                    self.chapters[self.current_chapter] = (chapter_title, content)
                    self._do_start_reading(content, voice, voice_name, chapter_title, chapter_num)
                else:
                    QMessageBox.warning(self, "提示", "章节内容获取失败，请重试")
                    if self.is_auto_switching:
                        self.is_auto_switching = False
            
            def on_content_error(error_msg):
                QMessageBox.critical(self, "错误", f"获取章节内容失败: {error_msg}")
                if self.is_auto_switching:
                    self.is_auto_switching = False
            
            if self.content_worker is None:
                self.content_worker = ChapterContentWorker("")
            
            self.content_worker.set_chapter_url(chapter_url)
            try:
                self.content_worker.finished.disconnect()
                self.content_worker.error.disconnect()
            except:
                pass
            self.content_worker.finished.connect(on_content_fetched)
            self.content_worker.error.connect(on_content_error)
            self.content_worker.start()
            return
        
        if not chapter_content or len(chapter_content.strip()) < 100:
            QMessageBox.warning(self, "提示", "请先点击章节加载内容！")
            if self.is_auto_switching:
                self.is_auto_switching = False
            return
        
        self._do_start_reading(chapter_content, voice, voice_name, chapter_title, chapter_num)

    def _do_start_reading(self, chapter_content, voice, voice_name, chapter_title, chapter_num):
        if not chapter_content or len(chapter_content) < 200 or chapter_content.startswith('http') or chapter_content.startswith('[URL:'):
            QMessageBox.warning(self, "提示", "章节内容无效，请重新加载")
            if self.is_auto_switching:
                self.is_auto_switching = False
            return
        
        speed_value = self.speed_slider.value()
        rate_offset = (speed_value - 100)
        rate = f"{rate_offset:+d}%"
        
        audio_file = self.get_audio_filename(chapter_num, chapter_title, voice, rate)
        
        print(f"[播放] _do_start_reading called, voice={voice}, rate={rate}, audio_exists={os.path.exists(audio_file)}")
        
        if os.path.exists(audio_file):
            print(f"[播放] 音频文件已存在，直接播放: {audio_file}")
            self.play_existing_audio(audio_file)
            return
        
        self.on_tts_finished_called = False
        
        self.tts_progress_dialog = TTSProgressDialog(self)
        self.tts_progress_dialog.show()
        
        safe_novel_title = re.sub(r'[<>:"/\\|?*]', '', self.novel_title) if self.novel_title else "未知小说"
        safe_novel_title = safe_novel_title[:20]
        safe_title = re.sub(r'[<>:"/\\|?*]', '', chapter_title)
        safe_title = safe_title[:30]
        
        source_prefix = ""
        if hasattr(self, 'novel_source') and self.novel_source:
            safe_source = re.sub(r'[<>:"/\\|?*]', '', self.novel_source)[:10]
            source_prefix = f"[{safe_source}]_"
        
        task_text = f"{source_prefix}{safe_novel_title}_{chapter_num}_{safe_title} [等待中]"
        self.tts_progress_dialog.add_task(task_text)
        self.tts_progress_dialog.update_task_status(0, " [生成中]")
        
        self.status_label.setText(f"🔊 正在生成语音 - 章节 {self.current_chapter + 1} ({voice_name})...")
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        
        import time
        time.sleep(0.5)
        
        if self.tts_worker:
            try:
                self.tts_worker.finished.disconnect(self.on_tts_finished)
                self.tts_worker.error.disconnect(self.on_tts_error)
                self.tts_worker.progress.disconnect(self.on_tts_progress)
            except:
                pass
        
        novel_source = getattr(self, 'novel_source', '')
        self.tts_worker = TTSWorker(chapter_content, voice, rate, self.current_chapter, chapter_title, self.novel_title, novel_source)
        self.tts_worker.finished.connect(self.on_tts_finished)
        self.tts_worker.error.connect(self.on_tts_error)
        self.tts_worker.progress.connect(self.on_tts_progress)
        self.tts_worker.start()
    
    def on_tts_progress(self, progress, text):
        if self.tts_progress_dialog:
            self.tts_progress_dialog.update_progress(progress, text)
    
    def on_tts_finished(self):
        if self.on_tts_finished_called:
            return
        
        self.on_tts_finished_called = True
        
        if self.tts_progress_dialog:
            self.tts_progress_dialog.update_task_status(0, " [已完成]")
            self.tts_progress_dialog.set_finished()
        
        audio_file = self.tts_worker.output_file
        if os.path.exists(audio_file):
            try:
                chapter_index = self.tts_worker.chapter_index
                voice_name = self.voice_combo.currentText()
                
                pygame.mixer.music.load(audio_file)
                
                sound = pygame.mixer.Sound(audio_file)
                self.audio_duration = sound.get_length() * 1000
                
                self.status_label.setText(f"🔊 播放中 - 章节 {chapter_index + 1} ({voice_name})")
                self.pause_btn.setEnabled(True)
                self.stop_btn.setEnabled(True)
                
                self.speed_slider.setEnabled(False)
                self.voice_combo.setEnabled(False)
                
                total = format_time_ms(int(self.audio_duration))
                self.progress_time.setText(f"00:00 / {total}")
                
                pygame.mixer.music.play()
                
                self.is_playing = True
                
                import time
                self.playback_start_time = time.time() * 1000
                self.playback_start_pos = 0
                self.is_paused = False
                
                self.play_timer = QTimer()
                self.play_timer.setInterval(100)
                self.play_timer.timeout.connect(self.update_progress)
                self.play_timer.start()
                
                self.update_chapter_buttons()
                
                if self.auto_play_enabled:
                    self.preload_next_chapter()
            except Exception as e:
                self.on_tts_error(str(e))
        else:
            QMessageBox.warning(self, "警告", "语音文件生成失败")
            self.status_label.setText("语音生成失败")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
    
    def play_existing_audio(self, audio_file):
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        
        import time
        time.sleep(0.5)
        
        self.is_playing = True
        self.on_tts_finished_called = True
        
        try:
            match = re.search(r'(?:\[([^\]]+)\]_)?(.+?)_(\d+)_(.+)_([^_]+)_([^_]+)\.mp3', audio_file)
            if match:
                source_name = match.group(1)
                novel_name = match.group(2)
                chapter_num = match.group(3)
                chapter_title = match.group(4)
                voice_code = match.group(5)
                rate = match.group(6)
                voice_name = None
                for name, code in VOICE_MAP.items():
                    if code == voice_code:
                        voice_name = name
                        break
                if not voice_name:
                    voice_name = voice_code
            else:
                match = re.search(r'(.+)_(.+)\.mp3', audio_file)
                if match:
                    chapter_title = match.group(1)
                    voice_code = match.group(2)
                    voice_name = None
                    for name, code in VOICE_MAP.items():
                        if code == voice_code:
                            voice_name = name
                            break
                    if not voice_name:
                        voice_name = voice_code
                else:
                    chapter_title = os.path.basename(audio_file)
                    voice_name = "未知"
            
            self.current_audio_file = audio_file
            
            try:
                from mutagen.mp3 import MP3
                audio = MP3(audio_file)
                self.audio_duration = audio.info.length * 1000
            except Exception as mp3_error:
                try:
                    os.remove(audio_file)
                except:
                    pass
                
                self.is_playing = False
                self.on_tts_finished_called = False
                QMessageBox.warning(self, "文件损坏", "音频文件已损坏，将重新生成")
                self.start_reading()
                return
            
            speed_value = self.speed_slider.value()
            actual_speed = speed_value / 100.0
            
            pygame.mixer.music.load(audio_file)
            
            self.status_label.setText(f"🔊 播放中 - {chapter_title} ({voice_name})")
            
            self.stop_btn.setEnabled(True)
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText("暂停")
            
            self.speed_slider.setEnabled(False)
            self.voice_combo.setEnabled(False)
            
            total = format_time_ms(int(self.audio_duration))
            self.progress_time.setText(f"00:00 / {total}")
            
            pygame.mixer.music.play()
            
            self.is_playing = True
            
            self.playback_start_time = time.time() * 1000
            self.playback_start_pos = 0
            
            self.play_timer = QTimer()
            self.play_timer.setInterval(100)
            self.play_timer.timeout.connect(self.update_progress)
            self.play_timer.start()
            
            self.update_chapter_buttons()
            
            if self.auto_play_enabled:
                self.preload_next_chapter()
        except Exception as e:
            self.on_tts_error(str(e))
    
    def update_progress(self):
        if self.is_playing and not self.is_dragging_progress and not self.is_paused:
            try:
                if pygame.mixer.music.get_busy():
                    import time
                    elapsed_time = time.time() * 1000 - self.playback_start_time
                    current_pos_ms = self.playback_start_pos + elapsed_time
                    
                    if current_pos_ms < self.audio_duration:
                        progress = min(int(current_pos_ms / self.audio_duration * 100), 100)
                        self.progress_slider.setValue(progress)
                        
                        current = format_time_ms(int(current_pos_ms))
                        total = format_time_ms(int(self.audio_duration))
                        self.progress_time.setText(f"{current} / {total}")
                    else:
                        self.is_playing = False
                        QTimer.singleShot(1500, self.on_playback_finished)
            except:
                pass
    
    def on_playback_finished(self):
        print(f"[播放] on_playback_finished called, auto_play_enabled={self.auto_play_enabled}")
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception as e:
            print(f"[播放] pygame stop error: {e}")
        
        self.is_playing = False
        
        if self.auto_play_enabled:
            print(f"[播放] 自动播放已启用，准备切换下一章")
            next_chapter = self.current_chapter + 1
            print(f"[播放] 当前章节={self.current_chapter}, 下一章={next_chapter}, 总章节数={len(self.chapters)}")
            if next_chapter < len(self.chapters):
                chapter_title, chapter_content = self.chapters[next_chapter]
                
                self.current_chapter = next_chapter
                self.chapter_list.setCurrentRow(next_chapter)
                self.is_auto_switching = True
                
                print(f"[播放] 章节内容长度={len(chapter_content)}, 包含URL={('[URL:' in chapter_content)}")
                
                has_valid_content = len(chapter_content) > 200 and not chapter_content.startswith('[URL:')
                
                if has_valid_content:
                    self.chapter_content.setPlainText(chapter_content)
                    QTimer.singleShot(100, self.start_reading)
                else:
                    print(f"[播放] 内容无效，需要先获取章节内容")
                    self.on_chapter_clicked(self.chapter_list.item(next_chapter))
                
                QTimer.singleShot(500, self.preload_next_chapter)
                QTimer.singleShot(100, self.update_chapter_buttons)
                return
            else:
                print(f"[播放] 已经是最后一章")
        
        print(f"[播放] 手动停止或完成")
        self.is_playing = False
        self.status_label.setText("阅读完成")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.progress_slider.setValue(0)
        self.progress_time.setText("00:00 / 00:00")
        
        self.speed_slider.setEnabled(True)
        self.voice_combo.setEnabled(True)
        self.update_chapter_buttons()
    
    def prev_chapter(self):
        if self.current_chapter > 0:
            self.current_chapter -= 1
            chapter_title = self.chapters[self.current_chapter][0]
            self.status_label.setText(f"已切换到: {chapter_title}")
            
            self.chapter_list.setCurrentRow(self.current_chapter)
            
            chapter_title, chapter_content = self.chapters[self.current_chapter]
            
            was_playing = self.is_playing
            self.is_playing = False
            
            if '[URL:' not in chapter_content or len(chapter_content) > 200:
                self.chapter_content.setPlainText(chapter_content)
            else:
                item = self.chapter_list.item(self.current_chapter)
                if item:
                    self.on_chapter_clicked(item)
            
            if was_playing:
                QTimer.singleShot(100, self.start_reading)
            
            self.update_chapter_buttons()
    
    def next_chapter(self):
        if self.current_chapter < len(self.chapters) - 1:
            self.current_chapter += 1
            chapter_title = self.chapters[self.current_chapter][0]
            self.status_label.setText(f"已切换到: {chapter_title}")
            
            self.chapter_list.setCurrentRow(self.current_chapter)
            
            chapter_title, chapter_content = self.chapters[self.current_chapter]
            
            was_playing = self.is_playing
            self.is_playing = False
            
            if '[URL:' not in chapter_content or len(chapter_content) > 200:
                self.chapter_content.setPlainText(chapter_content)
            else:
                item = self.chapter_list.item(self.current_chapter)
                if item:
                    self.on_chapter_clicked(item)
            
            if was_playing:
                QTimer.singleShot(100, self.start_reading)
            
            self.update_chapter_buttons()
    
    def update_chapter_buttons(self):
        has_chapters = len(self.chapters) > 0
        
        self.prev_chapter_btn.setEnabled(has_chapters and self.current_chapter > 0)
        self.next_chapter_btn.setEnabled(has_chapters and self.current_chapter < len(self.chapters) - 1)
    
    def on_progress_pressed(self):
        self.is_dragging_progress = True
    
    def on_progress_released(self):
        if self.is_playing and self.audio_duration > 0:
            progress = self.progress_slider.value()
            new_pos_ms = progress / 100 * self.audio_duration
            new_pos_sec = new_pos_ms / 1000
            
            pygame.mixer.music.stop()
            pygame.mixer.music.play(start=new_pos_sec)
            
            import time
            self.playback_start_time = time.time() * 1000
            self.playback_start_pos = new_pos_ms
        
        self.is_dragging_progress = False
    
    def on_tts_error(self, error_msg):
        self.is_playing = False
        self.status_label.setText("语音生成失败")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        
        audio_file = getattr(self.tts_worker, 'output_file', os.path.join(MP3_DIR, "temp_audio.mp3"))
        if os.path.exists(audio_file):
            try:
                os.remove(audio_file)
            except:
                pass
        
        if self.tts_progress_dialog:
            self.tts_progress_dialog.update_task_status(0, " [失败]")
            self.tts_progress_dialog.set_finished()
        
        QMessageBox.critical(self, "错误", f"语音生成失败: {error_msg}")
    
    def pause_reading(self):
        if not self.is_playing:
            return
        
        import time
        
        if self.pause_btn.text() == "暂停":
            pygame.mixer.music.pause()
            self.is_paused = True
            
            elapsed = time.time() * 1000 - self.playback_start_time
            self.playback_start_pos = self.playback_start_pos + elapsed
            
            self.status_label.setText("⏸ 已暂停")
            self.pause_btn.setText("恢复")
            self.stop_btn.setEnabled(False)
        else:
            pygame.mixer.music.unpause()
            self.is_paused = False
            
            self.playback_start_time = time.time() * 1000
            
            self.status_label.setText("🔊 播放中...")
            self.pause_btn.setText("暂停")
            self.stop_btn.setEnabled(True)
    
    def stop_reading(self):
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        
        if self.play_timer and self.play_timer.isActive():
            self.play_timer.stop()
        
        self.is_playing = False
        self.is_auto_switching = False
        self.status_label.setText("已停止")
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("暂停")
        self.stop_btn.setEnabled(False)
        self.progress_slider.setValue(0)
        self.progress_time.setText("00:00 / 00:00")
        
        self.speed_slider.setEnabled(True)
        self.voice_combo.setEnabled(True)
    
    def clean_audio_files(self):
        audio_files = glob.glob(os.path.join(MP3_DIR, "*.mp3"))
        
        if not audio_files:
            QMessageBox.information(self, "提示", "没有找到音频文件")
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("已有音频文件")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)
        
        layout = QVBoxLayout(dialog)
        
        info_label = QLabel("请选择要播放或删除的音频文件：")
        info_label.setFont(QFont("微软雅黑", 10))
        layout.addWidget(info_label)
        
        file_list = QListWidget()
        file_list.setFont(QFont("微软雅黑", 9))
        file_list.setSelectionMode(QListWidget.MultiSelection)
        
        for audio_file in audio_files:
            match = re.search(r'(?:\[([^\]]+)\]_)?(.+?)_(\d+)_(.+)_([^_]+)_([^_]+)\.mp3', audio_file)
            if match:
                source_name = match.group(1)
                novel_name = match.group(2)
                chapter_num = match.group(3)
                chapter_title = match.group(4)
                voice_code = match.group(5)
                rate = match.group(6)
                voice_name = None
                for name, code in VOICE_MAP.items():
                    if code == voice_code:
                        voice_name = name
                        break
                source_prefix = f"[{source_name}] " if source_name else ""
                if voice_name:
                    display_text = f"{source_prefix}{novel_name} - 第{chapter_num}章 {chapter_title} - {voice_name}"
                else:
                    display_text = f"{source_prefix}{novel_name} - 第{chapter_num}章 {chapter_title} - {voice_code}"
            else:
                match = re.search(r'(.+)_(.+)\.mp3', audio_file)
                if match:
                    chapter_title = match.group(1)
                    voice_code = match.group(2)
                    voice_name = None
                    for name, code in VOICE_MAP.items():
                        if code == voice_code:
                            voice_name = name
                            break
                    if voice_name:
                        display_text = f"{chapter_title} - {voice_name}"
                    else:
                        display_text = f"{chapter_title} - {voice_code}"
                else:
                    display_text = audio_file
            
            file_list.addItem(display_text)
            item = file_list.item(file_list.count() - 1)
            item.setData(Qt.UserRole, audio_file)
        
        layout.addWidget(file_list)
        
        button_row = QHBoxLayout()
        button_row.addStretch()
        
        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(lambda: file_list.selectAll())
        select_all_btn.setMinimumWidth(80)
        
        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.clicked.connect(lambda: file_list.clearSelection())
        deselect_all_btn.setMinimumWidth(80)
        
        play_btn = QPushButton("播放选中")
        play_btn.clicked.connect(lambda: self.play_selected_audio_file(file_list, dialog))
        play_btn.setMinimumWidth(100)
        play_btn.setFont(QFont("微软雅黑", 10, QFont.Bold))
        
        delete_btn = QPushButton("删除选中")
        delete_btn.clicked.connect(lambda: self.delete_selected_audio_files(file_list, dialog))
        delete_btn.setMinimumWidth(100)
        delete_btn.setFont(QFont("微软雅黑", 10, QFont.Bold))
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        cancel_btn.setMinimumWidth(80)
        
        button_row.addWidget(select_all_btn)
        button_row.addWidget(deselect_all_btn)
        button_row.addWidget(play_btn)
        button_row.addWidget(delete_btn)
        button_row.addWidget(cancel_btn)
        
        layout.addLayout(button_row)
        
        dialog.exec()
    
    def play_selected_audio_file(self, file_list, dialog):
        selected_items = file_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先选择要播放的音频文件")
            return
        
        if len(selected_items) > 1:
            QMessageBox.warning(self, "提示", "请只选择一个音频文件进行播放")
            return
        
        audio_file = selected_items[0].data(Qt.UserRole)
        dialog.accept()
        
        self.play_existing_audio(audio_file)
    
    def delete_selected_audio_files(self, file_list, dialog):
        selected_items = file_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先选择要删除的音频文件")
            return
        
        reply = QMessageBox.question(
            self, 
            "确认删除", 
            f"确定要删除选中的 {len(selected_items)} 个音频文件吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            deleted_count = 0
            for item in selected_items:
                audio_file = item.data(Qt.UserRole)
                try:
                    os.remove(audio_file)
                    deleted_count += 1
                except:
                    pass
            
            QMessageBox.information(self, "成功", f"已删除 {deleted_count} 个音频文件")
            dialog.accept()
    
    def init_web_tab(self):
        layout = QVBoxLayout(self.web_tab)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.deqixs_color = "#4a90d9"
        self.xiaoshuoyuedu_color = "#e67e22"
        self.current_source_color = self.deqixs_color
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(2)
        
        self.deqixs_btn = QPushButton("得奇小说网")
        self.deqixs_btn.setCheckable(True)
        self.deqixs_btn.setChecked(True)
        self.deqixs_btn.setCursor(Qt.PointingHandCursor)
        self.deqixs_btn.setMinimumHeight(32)
        self.deqixs_btn.clicked.connect(lambda: self.switch_source("deqixs"))
        
        self.xiaoshuoyuedu_btn = QPushButton("小说阅读网")
        self.xiaoshuoyuedu_btn.setCheckable(True)
        self.xiaoshuoyuedu_btn.setCursor(Qt.PointingHandCursor)
        self.xiaoshuoyuedu_btn.setMinimumHeight(32)
        self.xiaoshuoyuedu_btn.clicked.connect(lambda: self.switch_source("xiaoshuoyuedu"))
        
        btn_layout.addWidget(self.deqixs_btn)
        btn_layout.addWidget(self.xiaoshuoyuedu_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        self.source_stack = QStackedWidget()
        
        deqixs_widget = self.create_deqixs_source_widget()
        self.source_stack.addWidget(deqixs_widget)
        
        xiaoshuoyuedu_widget = self.create_xiaoshuoyuedu_source_widget()
        self.source_stack.addWidget(xiaoshuoyuedu_widget)
        
        layout.addWidget(self.source_stack)
        
        self.web_status_label = QLabel("")
        self.web_status_label.setFont(QFont("微软雅黑", 10))
        self.web_status_label.setMinimumHeight(25)
        self.web_status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.web_status_label)
        
        self.update_source_style(self.deqixs_color)
    
    def update_source_style(self, color):
        checked_style = f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: bold;
            }}
        """
        
        unchecked_style = """
            QPushButton {
                background-color: #f0f0f0;
                color: #666;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """
        
        self.deqixs_btn.setStyleSheet(checked_style if self.deqixs_btn.isChecked() else unchecked_style)
        self.xiaoshuoyuedu_btn.setStyleSheet(checked_style if self.xiaoshuoyuedu_btn.isChecked() else unchecked_style)
        
        self.source_stack.setStyleSheet(f"""
            QStackedWidget {{
                background-color: white;
                border: 2px solid {color};
                border-radius: 8px;
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 8px;
                padding-top: 8px;
                background-color: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {color};
            }}
        """)
    
    def switch_source(self, source_name):
        self.deqixs_btn.setChecked(source_name == "deqixs")
        self.xiaoshuoyuedu_btn.setChecked(source_name == "xiaoshuoyuedu")
        
        if source_name == "deqixs":
            self.source_stack.setCurrentIndex(0)
            self.current_source_color = self.deqixs_color
        elif source_name == "xiaoshuoyuedu":
            self.source_stack.setCurrentIndex(1)
            self.current_source_color = self.xiaoshuoyuedu_color
        
        self.update_source_style(self.current_source_color)
    
    def create_deqixs_source_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        
        method1_group = QGroupBox("方式一：搜索获取")
        method1_group.setFont(QFont("微软雅黑", 10))
        method1_layout = QVBoxLayout(method1_group)
        method1_layout.setSpacing(10)
        
        method1_desc = QLabel("在搜索框中输入小说名称，点击搜索，从搜索结果中选择小说加载")
        method1_desc.setFont(QFont("微软雅黑", 9))
        method1_desc.setStyleSheet("color: #666666;")
        method1_layout.addWidget(method1_desc)
        
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入小说名称")
        search_layout.addWidget(self.search_edit)
        
        self.search_btn = QPushButton("搜索")
        self.search_btn.setMinimumWidth(80)
        self.search_btn.clicked.connect(self.web_search)
        search_layout.addWidget(self.search_btn)
        
        method1_layout.addLayout(search_layout)
        
        self.search_result_list = QListWidget()
        self.search_result_list.setMinimumHeight(100)
        self.search_result_list.itemDoubleClicked.connect(self.load_selected_novel)
        self.search_result_list.itemSelectionChanged.connect(
            lambda: self.load_selected_btn.setEnabled(len(self.search_result_list.selectedItems()) > 0)
        )
        method1_layout.addWidget(self.search_result_list)
        
        load_btn_layout = QHBoxLayout()
        load_btn_layout.addStretch()
        self.load_selected_btn = QPushButton("加载选中的小说")
        self.load_selected_btn.setMinimumWidth(150)
        self.load_selected_btn.clicked.connect(self.load_selected_novel)
        self.load_selected_btn.setEnabled(False)
        load_btn_layout.addWidget(self.load_selected_btn)
        method1_layout.addLayout(load_btn_layout)
        
        method2_group = QGroupBox("方式二：网页浏览获取")
        method2_group.setFont(QFont("微软雅黑", 10))
        method2_layout = QVBoxLayout(method2_group)
        method2_layout.setSpacing(10)
        
        method2_desc = QLabel("在下方浏览器中打开小说网站，找到小说后打开小说目录首页点击'从当前网页加载'按钮")
        method2_desc.setFont(QFont("微软雅黑", 9))
        method2_desc.setStyleSheet("color: #666666;")
        method2_layout.addWidget(method2_desc)
        
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(10)
        
        self.back_btn = QPushButton("后退")
        self.back_btn.setMinimumWidth(60)
        self.back_btn.clicked.connect(self.web_back)
        
        self.forward_btn = QPushButton("前进")
        self.forward_btn.setMinimumWidth(60)
        self.forward_btn.clicked.connect(self.web_forward)
        
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setMinimumWidth(60)
        self.refresh_btn.clicked.connect(self.web_refresh)
        
        self.home_btn = QPushButton("首页")
        self.home_btn.setMinimumWidth(60)
        self.home_btn.clicked.connect(self.web_home)
        
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://www.deqixs.co/")
        self.url_edit.setReadOnly(True)
        self.url_edit.returnPressed.connect(self.web_load_url)
        
        self.load_btn = QPushButton("前往")
        self.load_btn.setMinimumWidth(60)
        self.load_btn.clicked.connect(self.web_load_url)
        
        nav_layout.addWidget(self.back_btn)
        nav_layout.addWidget(self.forward_btn)
        nav_layout.addWidget(self.refresh_btn)
        nav_layout.addWidget(self.home_btn)
        nav_layout.addWidget(self.url_edit)
        nav_layout.addWidget(self.load_btn)
        
        method2_layout.addLayout(nav_layout)
        
        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl("https://www.deqixs.co/"))
        self.web_view.urlChanged.connect(self.update_url_edit)
        self.web_view.setMinimumHeight(300)
        method2_layout.addWidget(self.web_view)
        
        self.load_novel_from_web_btn = QPushButton("📖 从当前网页加载小说（请在小说目录页面点击）")
        self.load_novel_from_web_btn.setMinimumHeight(40)
        self.load_novel_from_web_btn.setFont(QFont("微软雅黑", 10))
        self.load_novel_from_web_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.load_novel_from_web_btn.clicked.connect(self.load_novel_from_web)
        method2_layout.addWidget(self.load_novel_from_web_btn)
        
        layout.addWidget(method1_group)
        layout.addWidget(method2_group)
        
        return widget
    
    def create_xiaoshuoyuedu_source_widget(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        
        method1_group = QGroupBox("方式一：搜索获取")
        method1_group.setFont(QFont("微软雅黑", 10))
        method1_layout = QVBoxLayout(method1_group)
        method1_layout.setSpacing(10)
        
        method1_desc = QLabel("在搜索框中输入小说名称，点击搜索，从搜索结果中选择小说加载")
        method1_desc.setFont(QFont("微软雅黑", 9))
        method1_desc.setStyleSheet("color: #666666;")
        method1_layout.addWidget(method1_desc)
        
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        self.xiaoshuoyuedu_search_edit = QLineEdit()
        self.xiaoshuoyuedu_search_edit.setPlaceholderText("输入小说名称")
        search_layout.addWidget(self.xiaoshuoyuedu_search_edit)
        
        self.xiaoshuoyuedu_search_btn = QPushButton("搜索")
        self.xiaoshuoyuedu_search_btn.setMinimumWidth(80)
        self.xiaoshuoyuedu_search_btn.clicked.connect(self.xiaoshuoyuedu_search)
        search_layout.addWidget(self.xiaoshuoyuedu_search_btn)
        
        method1_layout.addLayout(search_layout)
        
        self.xiaoshuoyuedu_search_result_list = QListWidget()
        self.xiaoshuoyuedu_search_result_list.setMinimumHeight(100)
        self.xiaoshuoyuedu_search_result_list.itemDoubleClicked.connect(self.load_xiaoshuoyuedu_novel)
        self.xiaoshuoyuedu_search_result_list.itemSelectionChanged.connect(
            lambda: self.xiaoshuoyuedu_load_selected_btn.setEnabled(len(self.xiaoshuoyuedu_search_result_list.selectedItems()) > 0)
        )
        method1_layout.addWidget(self.xiaoshuoyuedu_search_result_list)
        
        load_btn_layout = QHBoxLayout()
        load_btn_layout.addStretch()
        self.xiaoshuoyuedu_load_selected_btn = QPushButton("加载选中的小说")
        self.xiaoshuoyuedu_load_selected_btn.setMinimumWidth(150)
        self.xiaoshuoyuedu_load_selected_btn.clicked.connect(self.load_xiaoshuoyuedu_novel)
        self.xiaoshuoyuedu_load_selected_btn.setEnabled(False)
        load_btn_layout.addWidget(self.xiaoshuoyuedu_load_selected_btn)
        method1_layout.addLayout(load_btn_layout)
        
        method2_group = QGroupBox("方式二：网页浏览获取")
        method2_group.setFont(QFont("微软雅黑", 10))
        method2_layout = QVBoxLayout(method2_group)
        method2_layout.setSpacing(10)
        
        method2_desc = QLabel("在下方浏览器中打开小说网站，找到小说后打开小说目录首页点击'从当前网页加载'按钮")
        method2_desc.setFont(QFont("微软雅黑", 9))
        method2_desc.setStyleSheet("color: #666666;")
        method2_layout.addWidget(method2_desc)
        
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(10)
        
        self.xiaoshuoyuedu_back_btn = QPushButton("后退")
        self.xiaoshuoyuedu_back_btn.setMinimumWidth(60)
        self.xiaoshuoyuedu_back_btn.clicked.connect(self.xiaoshuoyuedu_web_back)
        
        self.xiaoshuoyuedu_forward_btn = QPushButton("前进")
        self.xiaoshuoyuedu_forward_btn.setMinimumWidth(60)
        self.xiaoshuoyuedu_forward_btn.clicked.connect(self.xiaoshuoyuedu_web_forward)
        
        self.xiaoshuoyuedu_refresh_btn = QPushButton("刷新")
        self.xiaoshuoyuedu_refresh_btn.setMinimumWidth(60)
        self.xiaoshuoyuedu_refresh_btn.clicked.connect(self.xiaoshuoyuedu_web_refresh)
        
        self.xiaoshuoyuedu_home_btn = QPushButton("首页")
        self.xiaoshuoyuedu_home_btn.setMinimumWidth(60)
        self.xiaoshuoyuedu_home_btn.clicked.connect(self.xiaoshuoyuedu_web_home)
        
        self.xiaoshuoyuedu_url_edit = QLineEdit()
        self.xiaoshuoyuedu_url_edit.setPlaceholderText("https://www.xiaoshuoyuedu.com/")
        self.xiaoshuoyuedu_url_edit.setReadOnly(True)
        
        self.xiaoshuoyuedu_load_btn = QPushButton("前往")
        self.xiaoshuoyuedu_load_btn.setMinimumWidth(60)
        self.xiaoshuoyuedu_load_btn.clicked.connect(self.xiaoshuoyuedu_web_load_url)
        
        nav_layout.addWidget(self.xiaoshuoyuedu_back_btn)
        nav_layout.addWidget(self.xiaoshuoyuedu_forward_btn)
        nav_layout.addWidget(self.xiaoshuoyuedu_refresh_btn)
        nav_layout.addWidget(self.xiaoshuoyuedu_home_btn)
        nav_layout.addWidget(self.xiaoshuoyuedu_url_edit)
        nav_layout.addWidget(self.xiaoshuoyuedu_load_btn)
        
        method2_layout.addLayout(nav_layout)
        
        self.xiaoshuoyuedu_web_view = QWebEngineView()
        self.xiaoshuoyuedu_web_view.setUrl(QUrl("https://www.xiaoshuoyuedu.com/"))
        self.xiaoshuoyuedu_web_view.urlChanged.connect(self.update_xiaoshuoyuedu_url_edit)
        self.xiaoshuoyuedu_web_view.setMinimumHeight(300)
        method2_layout.addWidget(self.xiaoshuoyuedu_web_view)
        
        self.xiaoshuoyuedu_load_novel_btn = QPushButton("📖 从当前网页加载小说（请在小说目录页面点击）")
        self.xiaoshuoyuedu_load_novel_btn.setMinimumHeight(40)
        self.xiaoshuoyuedu_load_novel_btn.setFont(QFont("微软雅黑", 10))
        self.xiaoshuoyuedu_load_novel_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.xiaoshuoyuedu_load_novel_btn.clicked.connect(self.load_xiaoshuoyuedu_from_web)
        method2_layout.addWidget(self.xiaoshuoyuedu_load_novel_btn)
        
        layout.addWidget(method1_group)
        layout.addWidget(method2_group)
        
        return widget
    
    def init_novel_shelf_tab(self):
        layout = QVBoxLayout(self.novel_shelf_tab)
        layout.setSpacing(15)
        
        header_layout = QHBoxLayout()
        
        shelf_title = QLabel("📚 我的书架")
        shelf_title.setFont(QFont("微软雅黑", 14, QFont.Bold))
        header_layout.addWidget(shelf_title)
        
        header_layout.addStretch()
        
        refresh_btn = QPushButton("刷新列表")
        refresh_btn.setMinimumWidth(100)
        refresh_btn.clicked.connect(self.refresh_shelf_list)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        desc_label = QLabel("已加载的小说会自动保存到书架，点击即可阅读")
        desc_label.setFont(QFont("微软雅黑", 9))
        desc_label.setStyleSheet("color: #666666;")
        layout.addWidget(desc_label)
        
        self.shelf_list = QListWidget()
        self.shelf_list.setFont(QFont("微软雅黑", 11))
        self.shelf_list.setMinimumHeight(300)
        self.shelf_list.itemDoubleClicked.connect(self.load_novel_from_shelf)
        layout.addWidget(self.shelf_list)
        
        btn_layout = QHBoxLayout()
        
        self.load_shelf_btn = QPushButton("📖 加载阅读")
        self.load_shelf_btn.setMinimumWidth(120)
        self.load_shelf_btn.setMinimumHeight(40)
        self.load_shelf_btn.setFont(QFont("微软雅黑", 11))
        self.load_shelf_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.load_shelf_btn.clicked.connect(self.load_novel_from_shelf)
        btn_layout.addWidget(self.load_shelf_btn)
        
        self.delete_shelf_btn = QPushButton("🗑️ 删除")
        self.delete_shelf_btn.setMinimumWidth(100)
        self.delete_shelf_btn.setMinimumHeight(40)
        self.delete_shelf_btn.setFont(QFont("微软雅黑", 10))
        self.delete_shelf_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.delete_shelf_btn.clicked.connect(self.delete_shelf_novel)
        btn_layout.addWidget(self.delete_shelf_btn)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        self.shelf_status_label = QLabel("")
        self.shelf_status_label.setFont(QFont("微软雅黑", 10))
        self.shelf_status_label.setAlignment(Qt.AlignCenter)
        self.shelf_status_label.setMinimumHeight(25)
        layout.addWidget(self.shelf_status_label)
        
        QTimer.singleShot(100, self.refresh_shelf_list)
    
    def refresh_shelf_list(self):
        self.shelf_list.clear()
        
        if not os.path.exists(NOVEL_DIR):
            self.shelf_status_label.setText("书架为空，快去加载一本小说吧！")
            return
        
        novel_files = [f for f in os.listdir(NOVEL_DIR) if f.endswith('.txt')]
        novel_files.sort(reverse=True)
        
        if not novel_files:
            self.shelf_status_label.setText("书架为空，快去加载一本小说吧！")
            return
        
        for novel_file in novel_files:
            file_path = os.path.join(NOVEL_DIR, novel_file)
            file_mtime = os.path.getmtime(file_path)
            from datetime import datetime
            mtime_str = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M')
            
            display_text = f"{novel_file[:-4]} ({mtime_str})"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, novel_file)
            self.shelf_list.addItem(item)
        
        count = len(novel_files)
        self.shelf_status_label.setText(f"共有 {count} 本小说")
    
    def load_novel_from_shelf(self):
        current_item = self.shelf_list.currentItem()
        if not current_item:
            if self.shelf_list.count() > 0:
                current_item = self.shelf_list.item(0)
                self.shelf_list.setCurrentItem(current_item)
            else:
                QMessageBox.warning(self, "提示", "书架为空！")
                return
        
        novel_file = current_item.data(Qt.UserRole)
        file_path = os.path.join(NOVEL_DIR, novel_file)
        
        if os.path.exists(file_path):
            self.shelf_status_label.setText(f"正在加载: {novel_file[:-4]}...")
            
            def finish_load(success):
                if success:
                    self.shelf_status_label.setText(f"已加载: {novel_file[:-4]}")
                    self.save_last_novel(novel_file)
                    self.tab_widget.setCurrentIndex(2)
                else:
                    self.shelf_status_label.setText("加载失败")
            
            QTimer.singleShot(100, lambda: self.load_novel(file_path=file_path, callback=finish_load))
    
    def delete_shelf_novel(self):
        current_item = self.shelf_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先选择要删除的小说！")
            return
        
        novel_file = current_item.data(Qt.UserRole)
        novel_name = novel_file[:-4]
        
        reply = QMessageBox.question(self, "确认删除", f"确定要删除《{novel_name}》吗？\n这只会删除书架记录，不会删除已下载的语音文件。",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            file_path = os.path.join(NOVEL_DIR, novel_file)
            if os.path.exists(file_path):
                os.remove(file_path)
                self.refresh_shelf_list()
                self.shelf_status_label.setText(f"已删除: {novel_name}")
    
    
    def save_novel_to_shelf(self, novel_title, file_path):
        ensure_dir(NOVEL_DIR)
        
        abs_src = os.path.abspath(file_path)
        abs_novel_dir = os.path.abspath(NOVEL_DIR)
        novel_file = os.path.basename(file_path)
        
        if abs_src.startswith(abs_novel_dir):
            self.save_last_novel(novel_file)
            QTimer.singleShot(200, self.refresh_shelf_list)
            return
        
        dest_path = os.path.join(NOVEL_DIR, novel_file)
        
        try:
            import shutil
            shutil.copy2(file_path, dest_path)
            
            self.save_last_novel(novel_file)
            
            QTimer.singleShot(200, self.refresh_shelf_list)
        except Exception as e:
            pass
    
    def save_last_novel(self, novel_file):
        try:
            with open(LAST_NOVEL_PATH, 'w', encoding='utf-8') as f:
                f.write(novel_file)
        except:
            pass
    
    def load_last_novel(self):
        if not os.path.exists(LAST_NOVEL_PATH):
            return
        
        try:
            with open(LAST_NOVEL_PATH, 'r', encoding='utf-8') as f:
                last_novel_file = f.read().strip()
            
            if not last_novel_file:
                return
            
            file_path = os.path.join(NOVEL_DIR, last_novel_file)
            
            if os.path.exists(file_path):
                novel_name = last_novel_file[:-4]
                
                def on_success(success):
                    if success:
                        self.tab_widget.setCurrentIndex(2)
                
                QTimer.singleShot(100, lambda fp=file_path: self.load_novel(file_path=fp, callback=on_success))
        except:
            pass
    
    def web_back(self):
        if self.web_view.history().canGoBack():
            self.web_view.back()
    
    def web_forward(self):
        if self.web_view.history().canGoForward():
            self.web_view.forward()
    
    def web_refresh(self):
        self.web_view.reload()
    
    def web_home(self):
        self.web_view.setUrl(QUrl("https://www.deqixs.co/"))
    
    def web_load_url(self):
        url = self.url_edit.text().strip()
        if url:
            if not url.startswith('http'):
                url = 'https://' + url
            self.web_view.setUrl(QUrl(url))
    
    def web_search(self):
        keyword = self.search_edit.text().strip()
        if keyword:
            print(f"[搜索] 开始搜索关键词: {keyword}")
            
            self.web_status_label.setText("⏳ 正在搜索...")
            self.web_status_label.setStyleSheet("color: blue; font-weight: bold;")
            
            def on_search_finished(results):
                print(f"[搜索] 完成，返回 {len(results)} 个结果")
                for i, r in enumerate(results):
                    print(f"  [{i+1}] {r.get('title', '未知')} - {r.get('url', '无链接')}")
                
                self.search_result_list.clear()
                
                for result in results:
                    title = result.get('title', '')
                    url = result.get('url', '')
                    if title and url:
                        self.search_result_list.addItem(title)
                        item = self.search_result_list.item(self.search_result_list.count() - 1)
                        item.setData(Qt.UserRole, url)
                
                if self.search_result_list.count() > 0:
                    self.load_selected_btn.setEnabled(True)
                    self.web_status_label.setText(f"✅ 找到 {self.search_result_list.count()} 个搜索结果")
                    self.web_status_label.setStyleSheet("color: green; font-weight: bold;")
                    
                    keyword = self.search_edit.text().strip()
                    search_url = f"https://www.deqixs.co/modules/article/search.php?searchkey={quote(keyword)}&action=login&searchtype=all&submit="
                    print(f"[搜索] 更新网页浏览到搜索结果页面: {search_url}")
                    self.web_view.setUrl(QUrl(search_url))
                else:
                    self.web_status_label.setText("❌ 未找到搜索结果")
                    self.web_status_label.setStyleSheet("color: red; font-weight: bold;")
                    self.load_selected_btn.setEnabled(False)
            
            def on_search_error(error_msg):
                print(f"[搜索] 错误: {error_msg}")
                self.web_status_label.setText(f"❌ 搜索失败: {error_msg}")
                self.web_status_label.setStyleSheet("color: red; font-weight: bold;")
                self.load_selected_btn.setEnabled(False)
            
            self.search_worker = NovelSearchWorker(keyword, source_name="得取小说")
            self.search_worker.finished.connect(on_search_finished)
            self.search_worker.error.connect(on_search_error)
            self.search_worker.start()
    
    def load_selected_novel(self):
        selected_items = self.search_result_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先选择一个小说")
            return
        
        selected_item = selected_items[0]
        novel_title = selected_item.text()
        novel_url = selected_item.data(Qt.UserRole)
        
        if not novel_url:
            QMessageBox.warning(self, "提示", "未找到小说链接")
            return
        
        self.load_novel_from_url(novel_url, novel_title)
    
    def update_url_edit(self, url):
        self.url_edit.setText(url.toString())
    
    def load_novel_from_url(self, novel_url, novel_title):
        if not novel_url:
            QMessageBox.warning(self, "提示", "请提供小说链接")
            return
        
        self.web_status_label.setText("⏳ 正在加载小说章节列表，请稍候...")
        self.web_status_label.setStyleSheet("color: blue; font-weight: bold;")
        
        QTimer.singleShot(100, lambda: self._do_load_novel_from_url_v3(novel_url, novel_title))
    
    def _do_load_novel_from_url_v3(self, novel_url, novel_title):
        print(f"[加载] 开始加载小说: {novel_url}")
        try:
            self.loading_worker = UniversalLoadingWorker(novel_url, novel_title)
            self.loading_worker.finished.connect(self._on_novel_load_finished)
            self.loading_worker.error.connect(self._on_novel_load_error)
            self.loading_worker.start()

        except Exception as e:
            print(f"[加载] 启动加载Worker失败: {e}")
            self.web_status_label.setText(f"❌ 加载失败: {str(e)}")
            self.web_status_label.setStyleSheet("color: red; font-weight: bold;")

    def _on_novel_load_finished(self, url, title, chapters, source_name=""):
        print(f"[加载] 小说信息获取完成: {title}, 章节数: {len(chapters)}, 源: {source_name}")
        if not chapters:
            print(f"[加载] 未找到章节列表")
            self.web_status_label.setText("❌ 未找到章节列表")
            self.web_status_label.setStyleSheet("color: red; font-weight: bold;")
            return

        print(f"[加载] 正在保存小说文件...")
        ensure_dir(NOVEL_DIR)

        safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
        safe_title = safe_title.strip()
        if not safe_title:
            safe_title = f"未知小说_{len(os.listdir(NOVEL_DIR)) + 1}"
        
        if source_name:
            safe_source = re.sub(r'[<>:"/\\|?*]', '', source_name)
            novel_file = f"[{safe_source}]_{safe_title}.txt"
        else:
            novel_file = f"{safe_title}.txt"
        
        novel_path = os.path.join(NOVEL_DIR, novel_file)
        
        print(f"[加载] 保存路径: {novel_path}")

        with open(novel_path, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n")
            if source_name:
                f.write(f"[SOURCE: {source_name}]\n")
            f.write("\n")
            for chapter_title, chapter_url in chapters:
                f.write(f"## {chapter_title}\n")
                f.write(f"[URL: {chapter_url}]")
                f.write("\n\n")
                f.write("-" * 80 + "\n\n")

        print(f"[加载] 文件保存完成")

        def on_web_load_success(success):
            print(f"[加载] 回调结果: success={success}")
            if success:
                self.tab_widget.setCurrentIndex(2)

        print(f"[加载] 开始加载小说到阅读界面...")
        self.load_novel(file_path=novel_path, show_loading_dialog=False, callback=on_web_load_success)

        QTimer.singleShot(500, self.refresh_shelf_list)

        print(f"[加载] 完成")
        self.web_status_label.setText(f"✅ 《{title}》已保存到书架，共 {len(chapters)} 章")
        self.web_status_label.setStyleSheet("color: green; font-weight: bold;")

    def _on_novel_load_error(self, error_msg):
        self.web_status_label.setText(f"❌ 加载失败: {error_msg}")
        self.web_status_label.setStyleSheet("color: red; font-weight: bold;")
    
    def load_novel_from_web(self):
        current_url = self.web_view.url().toString()
        if not current_url:
            QMessageBox.warning(self, "提示", "请先打开一个小说页面")
            return
        
        self.load_novel_from_url(current_url, "")
    
    def xiaoshuoyuedu_search(self):
        keyword = self.xiaoshuoyuedu_search_edit.text().strip()
        if not keyword:
            return
        
        print(f"[小说阅读网搜索] 开始搜索: {keyword}")
        self.web_status_label.setText("⏳ 正在搜索...")
        self.web_status_label.setStyleSheet("color: blue; font-weight: bold;")
        
        def on_search_finished(results):
            print(f"[小说阅读网搜索] 完成，返回 {len(results)} 个结果")
            for i, r in enumerate(results):
                print(f"  [{i+1}] {r.get('title', '未知')} - {r.get('url', '无链接')}")
            
            self.xiaoshuoyuedu_search_result_list.clear()
            
            for result in results:
                title = result.get('title', '')
                url = result.get('url', '')
                if title and url:
                    self.xiaoshuoyuedu_search_result_list.addItem(title)
                    item = self.xiaoshuoyuedu_search_result_list.item(self.xiaoshuoyuedu_search_result_list.count() - 1)
                    item.setData(Qt.UserRole, url)
            
            if self.xiaoshuoyuedu_search_result_list.count() > 0:
                self.xiaoshuoyuedu_load_selected_btn.setEnabled(True)
                self.web_status_label.setText(f"✅ 找到 {self.xiaoshuoyuedu_search_result_list.count()} 个搜索结果")
                self.web_status_label.setStyleSheet("color: green; font-weight: bold;")
                
                from urllib.parse import quote
                keyword = self.xiaoshuoyuedu_search_edit.text().strip()
                search_url = f"https://www.xiaoshuoyuedu.com/search?searchkey={quote(keyword)}"
                print(f"[小说阅读网搜索] 更新网页浏览到搜索结果页面: {search_url}")
                self.xiaoshuoyuedu_web_view.setUrl(QUrl(search_url))
            else:
                self.web_status_label.setText("❌ 未找到搜索结果")
                self.web_status_label.setStyleSheet("color: red; font-weight: bold;")
                self.xiaoshuoyuedu_load_selected_btn.setEnabled(False)
        
        def on_search_error(error_msg):
            print(f"[小说阅读网搜索] 错误: {error_msg}")
            self.web_status_label.setText(f"❌ 搜索失败: {error_msg}")
            self.web_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.xiaoshuoyuedu_load_selected_btn.setEnabled(False)
        
        self.xiaoshuoyuedu_search_worker = NovelSearchWorker(keyword, source_name="小说阅读网")
        self.xiaoshuoyuedu_search_worker.finished.connect(on_search_finished)
        self.xiaoshuoyuedu_search_worker.error.connect(on_search_error)
        self.xiaoshuoyuedu_search_worker.start()
    
    def load_xiaoshuoyuedu_novel(self):
        selected_items = self.xiaoshuoyuedu_search_result_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先选择一个小说")
            return
        
        selected_item = selected_items[0]
        novel_title = selected_item.text()
        novel_url = selected_item.data(Qt.UserRole)
        
        if not novel_url:
            QMessageBox.warning(self, "提示", "未找到小说链接")
            return
        
        self.load_novel_from_url(novel_url, novel_title)
    
    def update_xiaoshuoyuedu_url_edit(self, url):
        self.xiaoshuoyuedu_url_edit.setText(url.toString())
    
    def xiaoshuoyuedu_web_back(self):
        self.xiaoshuoyuedu_web_view.back()
    
    def xiaoshuoyuedu_web_forward(self):
        self.xiaoshuoyuedu_web_view.forward()
    
    def xiaoshuoyuedu_web_refresh(self):
        self.xiaoshuoyuedu_web_view.reload()
    
    def xiaoshuoyuedu_web_home(self):
        self.xiaoshuoyuedu_web_view.setUrl(QUrl("https://www.xiaoshuoyuedu.com/"))
    
    def xiaoshuoyuedu_web_load_url(self):
        url = self.xiaoshuoyuedu_url_edit.text().strip()
        if url:
            if not url.startswith('http'):
                url = 'https://' + url
            self.xiaoshuoyuedu_web_view.setUrl(QUrl(url))
    
    def load_xiaoshuoyuedu_from_web(self):
        current_url = self.xiaoshuoyuedu_web_view.url().toString()
        if not current_url:
            QMessageBox.warning(self, "提示", "请先打开一个小说页面")
            return
        
        self.load_novel_from_url(current_url, "")
    
    def closeEvent(self, event):
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        
        settings = QSettings("novel_reader.ini", QSettings.IniFormat)
        settings.setValue(LAST_VOICE_INDEX, self.voice_combo.currentIndex())
        settings.setValue(LAST_SPEED_VALUE, self.speed_slider.value())
        settings.setValue(LAST_AUTO_PLAY, self.auto_play_checkbox.isChecked())
        
        for worker in [self.tts_worker, self.content_worker, self.search_worker, self.loading_worker, self.preload_worker, self.preload_content_worker]:
            if worker and worker.isRunning():
                if hasattr(worker, 'request_stop'):
                    worker.request_stop()
                worker.quit()
                worker.wait(1000)
        
        event.accept()


if __name__ == "__main__":
    app = QApplication([])
    window = NovelReader()
    window.show()
    app.exec()
