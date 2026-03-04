"""文字转语音引擎模块"""
import asyncio
import edge_tts
import os
import re
from typing import Optional
from PySide6.QtCore import QThread, Signal
from config import VOICE_MAP, MP3_DIR
from utils import ensure_dir, sanitize_filename


class TTSWorker(QThread):
    """TTS生成工作线程 - 与reader.py兼容"""
    finished = Signal()
    error = Signal(str)
    progress = Signal(int, str)
    
    def __init__(self, text, voice, rate, chapter_index, chapter_title, novel_title="", novel_source=""):
        super().__init__()
        self.text = text
        self.voice = voice
        self.rate = rate
        self.chapter_index = chapter_index
        self.chapter_title = chapter_title
        self._stop_requested = False
        safe_novel_title = re.sub(r'[<>:"/\\|?*]', '', novel_title) if novel_title else "未知小说"
        safe_novel_title = safe_novel_title[:20]
        safe_title = re.sub(r'[<>:"/\\|?*]', '', chapter_title)
        safe_title = safe_title[:30]
        chapter_num = chapter_index + 1 if chapter_index >= 0 else 1
        
        source_prefix = ""
        if novel_source:
            safe_source = re.sub(r'[<>:"/\\|?*]', '', novel_source)[:10]
            source_prefix = f"[{safe_source}]_"
        
        ensure_dir(MP3_DIR)
        
        self.output_file = os.path.join(MP3_DIR, f"{source_prefix}{safe_novel_title}_{chapter_num}_{safe_title}_{voice}_{self.rate}.mp3")
        self.signals_emitted = False
    
    def request_stop(self):
        self._stop_requested = True
    
    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            communicate = edge_tts.Communicate(self.text, self.voice, rate=self.rate)
            
            estimated_chunks = len(self.text) // 100
            if estimated_chunks < 10:
                estimated_chunks = 10
            
            async def generate_audio():
                chunk_count = 0
                with open(self.output_file, 'wb') as f:
                    async for chunk in communicate.stream():
                        if self._stop_requested:
                            return
                        if chunk["type"] == "audio":
                            f.write(chunk["data"])
                            chunk_count += 1
                            progress = min(int(chunk_count / estimated_chunks * 100), 95)
                            self.progress.emit(progress, f"正在生成音频... ({chunk_count} chunks)")
                
                self.progress.emit(100, "音频生成完成")
            
            try:
                loop.run_until_complete(generate_audio())
            except Exception as e:
                pass
            finally:
                try:
                    loop.close()
                except Exception:
                    pass
            
            if not self.signals_emitted and not self._stop_requested:
                if os.path.exists(self.output_file) and os.path.getsize(self.output_file) > 0:
                    self.signals_emitted = True
                    self.finished.emit()
                else:
                    self.signals_emitted = True
                    self.error.emit("语音文件生成失败")
                    
        except Exception as e:
            if not self.signals_emitted:
                self.signals_emitted = True
                self.error.emit(str(e))
