import sys
import os
import subprocess
import json
import time
import shutil
from enum import Enum
from pathlib import Path
from datetime import datetime, timezone, timedelta

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QSlider, QComboBox, QLineEdit, QColorDialog, 
                             QFrame, QSplitter, QMessageBox, QProgressBar, QCheckBox, QScrollArea)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QSize, QMimeData
from PyQt6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QColor, QFont, QImage, QDesktopServices
from PIL import Image, ImageDraw, ImageFont

VERSION = "v1.3"

# --- 工具函数与配置 ---

def get_ffmpeg_path():
    """检查ffmpeg是否在环境变量中"""
    # 优先检查当前目录下是否有 ffmpeg.exe (方便打包携带)
    local_ffmpeg = os.path.join(os.getcwd(), "ffmpeg.exe")
    if os.path.exists(local_ffmpeg):
        return local_ffmpeg
        
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    return None

def get_ffprobe_path():
    local_ffprobe = os.path.join(os.getcwd(), "ffprobe.exe")
    if os.path.exists(local_ffprobe):
        return local_ffprobe
        
    if shutil.which("ffprobe"):
        return "ffprobe"
    return None

class WatermarkPosition(Enum):
    TOP_LEFT = "左上"
    TOP_RIGHT = "右上"
    BOTTOM_LEFT = "左下"
    BOTTOM_RIGHT = "右下"
    CENTER = "居中"

# --- 工作线程：执行耗时的FFmpeg任务 ---

class ConvertWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str) # 成功返回路径
    error = pyqtSignal(str)
    log = pyqtSignal(str)

    def __init__(self, input_path, output_path, watermark_img_path, position_code, fps, scale_width):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.watermark_img_path = watermark_img_path
        self.position_code = position_code
        self.fps = fps
        self.scale_width = scale_width # -1 for keep original, or specific width

    def run(self):
        ffmpeg = get_ffmpeg_path()
        if not ffmpeg:
            self.error.emit("未找到 FFmpeg，请确保已安装并配置环境变量。")
            return

        # 构建滤镜复杂指令
        # 1. 缩放视频 (如果需要)
        # 2. 叠加水印
        
        # 计算 overlay 坐标
        overlay_cmd = ""
        if self.position_code == WatermarkPosition.TOP_LEFT:
            overlay_cmd = "overlay=10:10"
        elif self.position_code == WatermarkPosition.TOP_RIGHT:
            overlay_cmd = "overlay=W-w-10:10"
        elif self.position_code == WatermarkPosition.BOTTOM_LEFT:
            overlay_cmd = "overlay=10:H-h-10"
        elif self.position_code == WatermarkPosition.BOTTOM_RIGHT:
            overlay_cmd = "overlay=W-w-10:H-h-10"
        elif self.position_code == WatermarkPosition.CENTER:
            overlay_cmd = "overlay=(W-w)/2:(H-h)/2"

        # 如果需要调整视频尺寸
        scale_filter = ""
        if self.scale_width > 0:
            scale_filter = f"[0:v]scale={self.scale_width}:-1[scaled];[scaled][1:v]{overlay_cmd}"
        else:
            scale_filter = f"[0:v][1:v]{overlay_cmd}"

        # 命令构建
        cmd = [
            ffmpeg, '-y',
            '-i', self.input_path,
            '-i', self.watermark_img_path,
            '-filter_complex', scale_filter,
            '-r', str(self.fps),
            '-loop', '0',
            '-c:v', 'libwebp',
            '-lossless', '0',
            '-q:v', '75',
            '-preset', 'default',
            self.output_path
        ]

        self.log.emit(f"执行命令: {' '.join(cmd)}")
        
        try:
            # Windows下隐藏控制台窗口
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            # 修改重点：显式指定 encoding='utf-8' 和 errors='replace'
            # 这样即使 ffmpeg 输出的日志包含中文路径，也不会因为 gbk 解码失败而崩溃
            process = subprocess.Popen(
                cmd, 
                stderr=subprocess.PIPE, 
                universal_newlines=True, 
                encoding='utf-8', 
                errors='replace', 
                startupinfo=startupinfo
            )
            
            # 简单的进度模拟
            while True:
                if process.poll() is not None:
                    break
                # 此时 readline 会使用 utf-8 读取，遇到乱码字符会用 ? 替换，不会抛出异常
                line = process.stderr.readline()
                if line:
                    # print(line.strip()) # 调试用
                    pass
                self.progress.emit(50) # 模拟进度
                time.sleep(0.1)
            
            if process.returncode == 0:
                self.progress.emit(100)
                self.finished.emit(self.output_path)
            else:
                self.error.emit("转换失败，请检查源文件是否损坏。")
                
        except Exception as e:
            self.error.emit(str(e))


# --- 自定义控件：支持拖拽的区域 ---

class DragDropArea(QLabel):
    fileDropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setText("拖拽视频文件到这里\n或点击选择文件")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 10px;
                background-color: #f0f0f0;
                font-size: 16px;
                color: #555;
            }
            QLabel:hover {
                background-color: #e0e0e0;
                border-color: #666;
            }
        """)
        self.setAcceptDrops(True)
        self.setMinimumHeight(150)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.gif', '.webm')):
                self.fileDropped.emit(file_path)
                return # 只接受第一个
        event.acceptProposedAction()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            file_path, _ = QFileDialog.getOpenFileName(self, "选择视频文件", "", "Video Files (*.mp4 *.mov *.avi *.mkv *.gif *.webm)")
            if file_path:
                self.fileDropped.emit(file_path)


# --- 主窗口 ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"视频转 WebP 动图工具 (含水印) {VERSION}")
        self.resize(1200, 850) # 稍微增加高度以容纳新选项
        
        # 核心数据
        self.current_video_path = None
        self.video_info = {"width": 0, "height": 0}
        self.preview_frame_pil = None # 保存原始第一帧PIL对象
        self.font_path = "msyh.ttc" 
        self.text_color = "#FFFFFF"
        self.temp_dir = Path("temp_convert")
        self.temp_dir.mkdir(exist_ok=True)
        
        self.init_ui()
        self.check_env()

    def check_env(self):
        if not get_ffmpeg_path() or not get_ffprobe_path():
            QMessageBox.critical(self, "错误", "未检测到 FFmpeg 或 FFprobe。\n请确保它们已安装并添加到系统 PATH 环境变量中。")

    def init_ui(self):
        # 主部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- 左侧：控制面板 ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        
        # 1. 输入区域
        self.drop_area = DragDropArea()
        self.drop_area.fileDropped.connect(self.load_video)
        left_layout.addWidget(self.drop_area)

        # 2. 水印设置组
        settings_group = QFrame()
        settings_group.setFrameShape(QFrame.Shape.StyledPanel)
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.addWidget(QLabel("<b>水印设置</b>"))

        # 水印内容
        self.input_text = QLineEdit("这里是水印")
        self.input_text.setPlaceholderText("输入水印文字")
        settings_layout.addWidget(self.input_text)

        # 字体颜色与选择
        h_font = QHBoxLayout()
        self.btn_font = QPushButton("选择字体文件")
        self.btn_font.clicked.connect(self.choose_font)
        self.btn_color = QPushButton("颜色")
        self.btn_color.setStyleSheet(f"background-color: {self.text_color}; color: black;")
        self.btn_color.clicked.connect(self.choose_color)
        h_font.addWidget(self.btn_font)
        h_font.addWidget(self.btn_color)
        settings_layout.addLayout(h_font)

        # 位置
        h_pos = QHBoxLayout()
        h_pos.addWidget(QLabel("位置:"))
        self.combo_pos = QComboBox()
        for pos in WatermarkPosition:
            self.combo_pos.addItem(pos.value, pos)
        self.combo_pos.setCurrentText("右下")
        h_pos.addWidget(self.combo_pos)
        settings_layout.addLayout(h_pos)

        # 大小 (相对比例)
        h_size = QHBoxLayout()
        h_size.addWidget(QLabel("大小比例:"))
        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setRange(5, 80) # 5% to 80%
        self.slider_size.setValue(20)
        self.slider_size.valueChanged.connect(lambda: self.lbl_size_val.setText(f"{self.slider_size.value()}%"))
        self.lbl_size_val = QLabel("20%")
        h_size.addWidget(self.slider_size)
        h_size.addWidget(self.lbl_size_val)
        settings_layout.addLayout(h_size)

        # 透明度
        h_opacity = QHBoxLayout()
        h_opacity.addWidget(QLabel("透明度:"))
        self.slider_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_opacity.setRange(10, 255)
        self.slider_opacity.setValue(200)
        h_opacity.addWidget(self.slider_opacity)
        settings_layout.addLayout(h_opacity)
        
        # 添加刷新预览按钮
        self.btn_preview = QPushButton("刷新预览 / 应用设置")
        self.btn_preview.setStyleSheet("background-color: #eee; padding: 5px;")
        self.btn_preview.clicked.connect(self.trigger_preview)
        settings_layout.addWidget(self.btn_preview)
        
        left_layout.addWidget(settings_group)

        # 3. 输出设置
        out_group = QFrame()
        out_group.setFrameShape(QFrame.Shape.StyledPanel)
        out_layout = QVBoxLayout(out_group)
        out_layout.addWidget(QLabel("<b>输出设置</b>"))
        
        # 输出目录选择
        h_folder = QHBoxLayout()
        self.input_out_folder = QLineEdit()
        self.input_out_folder.setPlaceholderText("默认保存在原视频同目录，点击右侧按钮修改")
        self.btn_select_folder = QPushButton("选择输出目录")
        self.btn_select_folder.clicked.connect(self.choose_output_folder)
        h_folder.addWidget(self.input_out_folder)
        h_folder.addWidget(self.btn_select_folder)
        out_layout.addLayout(h_folder)

        # 时区选择
        h_tz = QHBoxLayout()
        h_tz.addWidget(QLabel("时间基准:"))
        self.combo_tz = QComboBox()
        self.combo_tz.addItems([
            "本地时间 (Local)", 
            "UTC", 
            "UTC+8 (北京/新加坡)", 
            "UTC+9 (东京/首尔)", 
            "UTC-5 (纽约/多伦多 EST)", 
            "UTC-8 (洛杉矶/温哥华 PST)",
            "UTC+0 (伦敦/格林威治)",
            "UTC+1 (柏林/巴黎 CET)"
        ])
        self.combo_tz.setCurrentText("本地时间 (Local)")
        h_tz.addWidget(self.combo_tz)
        out_layout.addLayout(h_tz)

        # 命名格式
        h_name = QHBoxLayout()
        h_name.addWidget(QLabel("文件名格式:"))
        self.input_name_pattern = QLineEdit("{name}")
        self.input_name_pattern.setPlaceholderText("如: {name}_{time}")
        self.input_name_pattern.setToolTip("可用占位符:\n{name}: 原文件名\n{time}: 当前时间 (如 20231124_153000)")
        h_name.addWidget(self.input_name_pattern)
        out_layout.addLayout(h_name)

        # 帧率
        h_fps = QHBoxLayout()
        h_fps.addWidget(QLabel("FPS:"))
        self.combo_fps = QComboBox()
        self.combo_fps.addItems(["10", "15", "20", "24", "30", "60"])
        self.combo_fps.setCurrentText("15")
        h_fps.addWidget(self.combo_fps)
        out_layout.addLayout(h_fps)

        left_layout.addWidget(out_group)

        # 4. 转换按钮和状态
        self.btn_convert = QPushButton("开始转换")
        self.btn_convert.setMinimumHeight(50)
        self.btn_convert.setStyleSheet("font-size: 18px; font-weight: bold; background-color: #0078d7; color: white;")
        self.btn_convert.clicked.connect(self.start_convert)
        left_layout.addWidget(self.btn_convert)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        left_layout.addStretch()

        # --- 右侧：预览面板 ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # 输入预览（第一帧+水印）
        right_layout.addWidget(QLabel("<b>水印效果预览 (原视频第一帧)</b>"))
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #333; color: #aaa;")
        self.preview_label.setText("请加载视频后点击“刷新预览”")
        self.preview_label.setMinimumSize(400, 300)
        right_layout.addWidget(self.preview_label, 2) # 权重2

        # 输出预览 (转换完成后的WebP)
        right_layout.addWidget(QLabel("<b>输出 WebP 预览</b>"))
        self.result_label = QLabel()
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_label.setStyleSheet("background-color: #333; color: #aaa;")
        self.result_label.setText("等待转换...")
        self.result_label.setMinimumSize(400, 300)
        right_layout.addWidget(self.result_label, 2)
        
        self.btn_open_folder = QPushButton("打开输出文件夹")
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self.open_output_folder)
        right_layout.addWidget(self.btn_open_folder)

        # 添加到 Splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800])

    # --- 逻辑处理 ---

    def choose_font(self):
        # 默认打开 Windows 字体目录
        # 使用环境变量获取系统目录，以防 Windows 不在 C 盘
        if os.name == 'nt':
            start_dir = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
        else:
            start_dir = ""

        # 修改关键点：添加 options=QFileDialog.Option.DontUseNativeDialog
        # Windows 的 Fonts 文件夹是特殊系统目录，原生对话框会试图按“字体家族”显示，导致无法直接选择 .ttf 文件
        # 强制使用 Qt 自己的对话框可以把它当作普通文件夹浏览，从而看到所有文件
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择字体文件", 
            start_dir, 
            "Font Files (*.ttf *.otf *.ttc);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog
        )
        
        if file_path:
            self.font_path = file_path
            self.btn_font.setText(os.path.basename(file_path))

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.text_color = color.name()
            self.btn_color.setStyleSheet(f"background-color: {self.text_color}; color: {'black' if color.lightness() > 128 else 'white'};")

    def choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self.input_out_folder.setText(folder)

    def load_video(self, path):
        self.current_video_path = path
        self.drop_area.setText(f"当前文件:\n{os.path.basename(path)}")
        
        # 获取视频第一帧
        if self.extract_first_frame(path):
            self.trigger_preview() # 加载视频时自动触发一次
        else:
            QMessageBox.warning(self, "错误", "无法读取视频文件")

    def extract_first_frame(self, video_path):
        """使用ffmpeg提取第一帧作为预览底图"""
        ffmpeg = get_ffmpeg_path()
        if not ffmpeg: return False
        
        try:
            # 获取分辨率
            cmd_probe = [get_ffprobe_path(), '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'json', video_path]
            # 同样添加 encoding='utf-8', errors='replace' 增加健壮性
            info = subprocess.check_output(
                cmd_probe, 
                startupinfo=self._get_startup_info(),
                encoding='utf-8',
                errors='replace'
            )
            data = json.loads(info)
            self.video_info['width'] = int(data['streams'][0]['width'])
            self.video_info['height'] = int(data['streams'][0]['height'])

            # 获取第一帧图片数据 (PNG格式)
            cmd = [ffmpeg, '-i', video_path, '-vframes', '1', '-f', 'image2pipe', '-vcodec', 'png', '-']
            # stdout 使用 binary 模式读取图片数据，stderr 保持默认
            pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, startupinfo=self._get_startup_info())
            out, _ = pipe.communicate()
            
            if out:
                # 直接从内存加载到PIL
                from io import BytesIO
                self.preview_frame_pil = Image.open(BytesIO(out)).convert("RGBA")
                return True
        except Exception as e:
            print(e)
        return False

    def _get_startup_info(self):
        if os.name == 'nt':
            info = subprocess.STARTUPINFO()
            info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return info
        return None

    def generate_watermark_layer(self, base_width, base_height):
        """生成一张和视频等大的透明图，并在上面绘制水印"""
        layer = Image.new('RGBA', (base_width, base_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        
        text = self.input_text.text()
        if not text: return layer

        # 自适应字体大小算法
        target_width = base_width * (self.slider_size.value() / 100.0)
        
        font_size = 10
        try:
            font = ImageFont.truetype(self.font_path, font_size)
        except:
            font = ImageFont.load_default()
            
        # 逐步增大字体直到宽度接近目标宽度
        while True:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            if text_width >= target_width or font_size > base_height:
                break
            font_size += 2
            try:
                font = ImageFont.truetype(self.font_path, font_size)
            except:
                break
        
        # 获取最终文本尺寸
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        # 计算位置
        margin = 20
        x, y = 0, 0
        pos = self.combo_pos.currentData()
        
        if pos == WatermarkPosition.TOP_LEFT:
            x, y = margin, margin
        elif pos == WatermarkPosition.TOP_RIGHT:
            x, y = base_width - w - margin, margin
        elif pos == WatermarkPosition.BOTTOM_LEFT:
            x, y = margin, base_height - h - margin
        elif pos == WatermarkPosition.BOTTOM_RIGHT:
            x, y = base_width - w - margin, base_height - h - margin
        elif pos == WatermarkPosition.CENTER:
            x, y = (base_width - w) // 2, (base_height - h) // 2

        # 绘制文本 (解析颜色 + Alpha)
        c = QColor(self.text_color)
        fill_color = (c.red(), c.green(), c.blue(), self.slider_opacity.value())
        
        draw.text((x, y), text, font=font, fill=fill_color)
        return layer

    def trigger_preview(self):
        if self.preview_frame_pil is None:
            return

        # 1. 复制原始帧
        base_img = self.preview_frame_pil.copy()
        
        # 2. 生成水印层
        watermark_layer = self.generate_watermark_layer(base_img.width, base_img.height)
        
        # 3. 合成
        combined = Image.alpha_composite(base_img, watermark_layer)
        
        # 4. 显示在 QLabel
        qim = self.pil2qimage(combined)
        pix = QPixmap.fromImage(qim)
        
        # 保持纵横比缩放
        w = self.preview_label.width()
        h = self.preview_label.height()
        self.preview_label.setPixmap(pix.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def pil2qimage(self, pil_img):
        im_data = pil_img.tobytes()
        if pil_img.mode == "RGBA":
            format_ = QImage.Format.Format_RGBA8888
            stride = pil_img.width * 4
        else:
            format_ = QImage.Format.Format_RGB888
            stride = pil_img.width * 3
        return QImage(im_data, pil_img.width, pil_img.height, stride, format_).copy()

    def resizeEvent(self, event):
        self.trigger_preview()
        super().resizeEvent(event)
    
    def get_selected_time(self):
        """根据选择的时区返回当前时间"""
        tz_text = self.combo_tz.currentText()
        now_local = datetime.now()
        
        if "Local" in tz_text:
            return now_local
            
        now_utc = datetime.now(timezone.utc)
        
        # 简单解析 offset
        if "UTC" == tz_text:
            return now_utc
            
        try:
            # 解析形如 "UTC+8 ..." 的字符串
            # 提取 "+8" 或 "-5"
            offset_str = tz_text.split(' ')[0].replace("UTC", "")
            offset = int(offset_str)
            tz = timezone(timedelta(hours=offset))
            return now_utc.astimezone(tz)
        except:
            return now_local # 解析失败则回退到本地时间

    def start_convert(self):
        if not self.current_video_path:
            QMessageBox.warning(self, "提示", "请先拖入视频文件")
            return

        self.btn_convert.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # 1. 生成临时水印图片文件
        watermark_layer = self.generate_watermark_layer(self.video_info['width'], self.video_info['height'])
        temp_wm_path = self.temp_dir / "temp_watermark.png"
        watermark_layer.save(temp_wm_path)

        # 2. 准备输出路径
        pattern = self.input_name_pattern.text()
        if not pattern:
            pattern = "{name}" # 默认保持原名
            
        p = Path(self.current_video_path)
        
        # 计算文件名
        # 替换 {time}
        dt = self.get_selected_time()
        time_str = dt.strftime("%Y%m%d_%H%M%S")
        
        new_stem = pattern.replace("{name}", p.stem).replace("{time}", time_str)
        
        # 检查是否选择了自定义输出文件夹
        custom_out_folder = self.input_out_folder.text().strip()
        if custom_out_folder and os.path.exists(custom_out_folder):
            out_dir = Path(custom_out_folder)
        else:
            # 默认为输入文件所在目录
            out_dir = Path(self.current_video_path).parent
            
        out_name = f"{new_stem}.webp"
        out_path = out_dir / out_name

        # 3. 启动线程
        self.worker = ConvertWorker(
            input_path=str(p),
            output_path=str(out_path),
            watermark_img_path=str(temp_wm_path),
            position_code=self.combo_pos.currentData(),
            fps=int(self.combo_fps.currentText()),
            scale_width=-1
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.on_convert_finished)
        self.worker.error.connect(self.on_convert_error)
        self.worker.start()

    def on_convert_finished(self, out_path):
        self.btn_convert.setEnabled(True)
        self.progress_bar.setValue(100)
        self.last_output_path = out_path
        self.btn_open_folder.setEnabled(True)
        
        QMessageBox.information(self, "成功", f"转换完成！\n文件已保存至: {out_path}")
        
        # 显示结果预览
        self.result_label.setText("")
        pix = QPixmap(out_path)
        w = self.result_label.width()
        h = self.result_label.height()
        self.result_label.setPixmap(pix.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        
        # 清理临时文件
        try:
            shutil.rmtree(self.temp_dir)
            self.temp_dir.mkdir(exist_ok=True)
        except:
            pass

    def on_convert_error(self, msg):
        self.btn_convert.setEnabled(True)
        QMessageBox.critical(self, "错误", f"转换出错: {msg}")

    def open_output_folder(self):
        if hasattr(self, 'last_output_path'):
            folder = os.path.dirname(self.last_output_path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

if __name__ == "__main__":
    # 高DPI 适配设置
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    
    # 设置全局字体大小，防止在4K屏过小
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())