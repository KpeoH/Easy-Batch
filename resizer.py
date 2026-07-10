import os
import sys
import json
import shutil
import subprocess
import io
import logging
import concurrent.futures
from PIL import Image, ImageOps, ImageEnhance, ImageDraw, ImageFont
from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QThread, QMimeData
from PySide6.QtGui import QPixmap, QColor, QPainter, QPen, QAction, QDrag, QCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QCheckBox, QSlider, QLineEdit, QComboBox, 
    QScrollArea, QFrame, QTabWidget, QFileDialog, QMessageBox, 
    QDialog, QGridLayout, QSizePolicy, QSizeGrip, QRadioButton, QButtonGroup,
    QProgressBar, QInputDialog
)

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

ASSETS_DIR = os.path.join(APP_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True) 

LOG_FILE = os.path.join(APP_DIR, "error_log.txt")
logging.basicConfig(filename=LOG_FILE, level=logging.WARNING, 
                    format='%(asctime)s [%(levelname)s] %(funcName)s: %(message)s')

CONFIG_FILE = os.path.join(ASSETS_DIR, "wm_config.json")
CROP_CONFIG_FILE = os.path.join(ASSETS_DIR, "crop_config.json")
COVER_CONFIG_FILE = os.path.join(ASSETS_DIR, "cover_config.json")
GENERAL_CONFIG_FILE = os.path.join(ASSETS_DIR, "general_config.json")

THEMES = {
    "dark": {
        "BG": "#060404", "TEXT": "#eeecec", "PRIMARY": "#c33809",
        "SEC": "#712f19", "ACCENT": "#a9350f", "FRAME": "#140c0c", "FRAME_HOVER": "#1c1313", "DISABLED": "#333333"
    },
    "light": {
        "BG": "#fbf9f9", "TEXT": "#131111", "PRIMARY": "#f66b3c",
        "SEC": "#e6a48e", "ACCENT": "#f07d56", "FRAME": "#ece6e6", "FRAME_HOVER": "#dfd6d6", "DISABLED": "#cccccc"
    }
}

def get_stylesheet(theme_name):
    c = THEMES[theme_name]
    text_enc = c['TEXT'].replace('#', '%23')
    
    return f"""
    * {{ outline: none; }}
    QWidget {{ background-color: {c['BG']}; color: {c['TEXT']}; font-family: 'Montserrat', 'Segoe UI', sans-serif; font-size: 13px; }}
    QFrame {{ border: none; }}
    QFrame#AppWindow {{ border: 1px solid {c['PRIMARY']}; border-radius: 10px; background-color: {c['BG']}; }}
    QFrame#TitleBar {{ background-color: {c['FRAME']}; border-top-left-radius: 10px; border-top-right-radius: 10px; }}
    QPushButton#TitleBtn {{ background-color: transparent; color: {c['TEXT']}; font-size: 16px; border-radius: 0px; }}
    QPushButton#TitleBtn:hover {{ background-color: {c['FRAME_HOVER']}; }}
    QPushButton#TitleCloseBtn {{ background-color: transparent; color: {c['TEXT']}; font-size: 16px; border-radius: 0px; border-top-right-radius: 10px; }}
    QPushButton#TitleCloseBtn:hover {{ background-color: #d32f2f; color: white; }}
    QFrame#Card {{ background-color: {c['FRAME']}; border-radius: 8px; }}
    QFrame#DialogCard {{ background-color: {c['BG']}; border: 2px solid {c['PRIMARY']}; border-radius: 8px; }}
    QFrame#ActiveCard {{ background-color: {c['FRAME']}; border: 2px solid {c['PRIMARY']}; border-radius: 8px; }}
    QPushButton {{ background-color: {c['PRIMARY']}; color: {c['BG']}; border: none; border-radius: 4px; padding: 8px 16px; font-weight: bold; }}
    QPushButton:hover {{ background-color: {c['ACCENT']}; }}
    QPushButton:disabled {{ background-color: {c['FRAME_HOVER']}; color: {c['TEXT']}; }}
    QPushButton#Secondary {{ background-color: {c['FRAME']}; color: {c['TEXT']}; }}
    QPushButton#Secondary:hover {{ background-color: {c['FRAME_HOVER']}; }}
    QPushButton#Danger {{ background-color: {c['SEC']}; color: {c['TEXT']}; }}
    QPushButton#Danger:hover {{ background-color: {c['ACCENT']}; color: {c['BG']}; }}
    QPushButton#PosBtn {{ background-color: {c['FRAME']}; color: {c['TEXT']}; border-radius: 4px; padding: 4px; font-size: 16px; }}
    QPushButton#PosBtn:checked {{ background-color: {c['PRIMARY']}; color: {c['BG']}; }}
    QPushButton#PosBtn:disabled {{ color: {c['DISABLED']}; }}
    QScrollArea {{ border: none; background-color: transparent; }}
    QScrollArea > QWidget > QWidget {{ background-color: transparent; }}
    QScrollBar:vertical {{ border: none; background: {c['BG']}; width: 8px; border-radius: 4px; }}
    QScrollBar::handle:vertical {{ background: {c['FRAME_HOVER']}; border-radius: 4px; }}
    QTabWidget::pane {{ border: none; background: {c['BG']}; }}
    QTabBar::tab {{ background: transparent; color: {c['TEXT']}; padding: 8px 16px; margin-right: 2px; border-radius: 4px; font-weight: bold; }}
    QTabBar::tab:selected {{ background: {c['PRIMARY']}; color: {c['BG']}; }}
    QTabBar::tab:hover:!selected {{ background: {c['FRAME_HOVER']}; }}
    QLineEdit {{ background-color: {c['FRAME']}; border: 1px solid {c['PRIMARY']}; border-radius: 4px; padding: 4px 8px; color: {c['TEXT']}; }}
    QLineEdit:disabled {{ background-color: {c['BG']}; border: 1px solid {c['FRAME_HOVER']}; color: {c['DISABLED']}; }}
    QComboBox {{ background-color: {c['FRAME']}; border: 1px solid {c['PRIMARY']}; border-radius: 6px; padding: 6px 12px; color: {c['TEXT']}; font-weight: bold; }}
    QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 30px; border: none; }}
    QComboBox::down-arrow {{ image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='{text_enc}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E"); width: 16px; height: 16px; }}
    QComboBox QAbstractItemView {{ background-color: {c['FRAME']}; color: {c['TEXT']}; border: 1px solid {c['PRIMARY']}; selection-background-color: {c['PRIMARY']}; selection-color: white; border-radius: 6px; outline: none; padding: 4px; }}
    QSlider::groove:horizontal {{ border-radius: 2px; height: 4px; background: {c['FRAME_HOVER']}; }}
    QSlider::groove:horizontal:disabled {{ background: {c['FRAME']}; }}
    QSlider::handle:horizontal {{ background: {c['PRIMARY']}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}
    QSlider::handle:horizontal:hover {{ background: {c['ACCENT']}; }}
    QSlider::handle:horizontal:disabled {{ background: {c['DISABLED']}; }}
    QSlider::sub-page:horizontal {{ background: {c['PRIMARY']}; border-radius: 2px; }}
    QSlider::sub-page:horizontal:disabled {{ background: {c['DISABLED']}; }}
    QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 5px; border: 2px solid {c['PRIMARY']}; background-color: {c['FRAME']}; }}
    QCheckBox::indicator:hover {{ border: 2px solid {c['ACCENT']}; }}
    QCheckBox::indicator:checked {{ background-color: {c['PRIMARY']}; border: 2px solid {c['PRIMARY']}; image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='20 6 9 17 4 12'/%3E%3C/svg%3E"); }}
    QRadioButton::indicator {{ width: 18px; height: 18px; border-radius: 9px; border: 2px solid {c['PRIMARY']}; background-color: {c['FRAME']}; }}
    QRadioButton::indicator:checked {{ background-color: {c['PRIMARY']}; image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white'%3E%3Ccircle cx='12' cy='12' r='6'/%3E%3C/svg%3E"); }}
    QRadioButton::indicator:disabled {{ border: 2px solid {c['DISABLED']}; background-color: transparent; }}
    QLabel#Title {{ font-size: 16px; font-weight: bold; }}
    QLabel#Placeholder {{ color: #888888; font-size: 16px; font-weight: bold; }}
    QProgressBar {{ background-color: {c['FRAME']}; border: 1px solid {c['PRIMARY']}; border-radius: 4px; text-align: center; color: {c['TEXT']}; font-weight: bold; }}
    QProgressBar::chunk {{ background-color: {c['PRIMARY']}; border-radius: 3px; }}
    """

def get_asset_path(filename):
    if not filename: return ""
    direct_path = os.path.join(ASSETS_DIR, filename)
    if os.path.exists(direct_path): return direct_path
    target = filename.lower()
    try:
        for f in os.listdir(ASSETS_DIR):
            if f.lower() == target: return os.path.join(ASSETS_DIR, f)
    except Exception as e:
        logging.warning(f"Error reading ASSETS_DIR: {e}")
    return direct_path

def pil_to_pixmap(pil_img):
    try:
        byte_io = io.BytesIO()
        pil_img.save(byte_io, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(byte_io.getvalue())
        return pixmap
    except Exception as e:
        logging.error(f"Failed to convert PIL Image to QPixmap: {e}")
        return QPixmap()

def native_askopenfilenames(title="Выберите файлы"):
    if sys.platform.startswith("linux"):
        try:
            res = subprocess.run(['kdialog', '--getopenfilename', '.', 'Все файлы (*)', '--multiple', '--separate-output', '--title', title], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip(): return res.stdout.strip().split('\n')
        except Exception as e: logging.debug(f"kdialog failed: {e}")
        try:
            res = subprocess.run(['zenity', '--file-selection', '--multiple', '--separator=|', '--title', title], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip(): return res.stdout.strip().split('|')
        except Exception as e: logging.debug(f"zenity failed: {e}")
    paths, _ = QFileDialog.getOpenFileNames(None, title, "", "Images (*.png *.jpg *.jpeg *.webp)")
    return paths if paths else []

def native_askopenfilename(title="Выберите файл"):
    if sys.platform.startswith("linux"):
        try:
            res = subprocess.run(['kdialog', '--getopenfilename', '.', 'Все файлы (*)', '--title', title], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip(): return res.stdout.strip()
        except Exception as e: logging.debug(f"kdialog failed: {e}")
        try:
            res = subprocess.run(['zenity', '--file-selection', '--title', title], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip(): return res.stdout.strip()
        except Exception as e: logging.debug(f"zenity failed: {e}")
    path, _ = QFileDialog.getOpenFileName(None, title, "", "All Files (*.*)")
    return path if path else ""

def native_askdirectory(title="Выберите папку"):
    if sys.platform.startswith("linux"):
        try:
            res = subprocess.run(['kdialog', '--getexistingdirectory', '.', '--title', title], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip(): return res.stdout.strip()
        except Exception as e: logging.debug(f"kdialog failed: {e}")
        try:
            res = subprocess.run(['zenity', '--file-selection', '--directory', '--title', title], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip(): return res.stdout.strip()
        except Exception as e: logging.debug(f"zenity failed: {e}")
    path = QFileDialog.getExistingDirectory(None, title)
    return path if path else ""

def create_arrow_pixmap(val, color_str):
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    pen = QPen(QColor(color_str), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setRenderHint(QPainter.Antialiasing)

    if val == "tl":
        painter.drawLine(6, 6, 18, 18)
        painter.drawLine(6, 6, 12, 6)
        painter.drawLine(6, 6, 6, 12)
    elif val == "tc":
        painter.drawLine(12, 6, 12, 18)
        painter.drawLine(12, 6, 8, 10)
        painter.drawLine(12, 6, 16, 10)
    elif val == "tr":
        painter.drawLine(18, 6, 6, 18)
        painter.drawLine(18, 6, 12, 6)
        painter.drawLine(18, 6, 18, 12)
    elif val == "ml":
        painter.drawLine(6, 12, 18, 12)
        painter.drawLine(6, 12, 10, 8)
        painter.drawLine(6, 12, 10, 16)
    elif val == "mc":
        painter.setBrush(QColor(color_str))
        painter.drawEllipse(8, 8, 8, 8)
    elif val == "mr":
        painter.drawLine(18, 12, 6, 12)
        painter.drawLine(18, 12, 14, 8)
        painter.drawLine(18, 12, 14, 16)
    elif val == "bl":
        painter.drawLine(6, 18, 18, 6)
        painter.drawLine(6, 18, 12, 18)
        painter.drawLine(6, 18, 6, 14)
    elif val == "bc":
        painter.drawLine(12, 18, 12, 6)
        painter.drawLine(12, 18, 8, 14)
        painter.drawLine(12, 18, 16, 14)
    elif val == "br":
        painter.drawLine(18, 18, 6, 6)
        painter.drawLine(18, 18, 12, 18)
        painter.drawLine(18, 18, 18, 14)

    painter.end()
    return pixmap

class SuccessBox(QDialog):
    def __init__(self, parent, title, message, out_dir):
        super().__init__(parent)
        self.out_dir = out_dir
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(400, 160)
        
        main_frame = QFrame(self)
        main_frame.setObjectName("DialogCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(main_frame)
        
        flayout = QVBoxLayout(main_frame)
        flayout.setContentsMargins(20, 20, 20, 20)
        
        lbl_title = QLabel(title)
        lbl_title.setObjectName("Title")
        lbl_title.setAlignment(Qt.AlignCenter)
        flayout.addWidget(lbl_title)
        
        lbl_msg = QLabel(message)
        lbl_msg.setAlignment(Qt.AlignCenter)
        lbl_msg.setWordWrap(True)
        flayout.addWidget(lbl_msg, 1)
        
        btn_layout = QHBoxLayout()
        btn_open = QPushButton("Открыть папку")
        btn_open.setObjectName("Secondary")
        btn_open.clicked.connect(self.open_folder)
        
        btn_ok = QPushButton("OK")
        btn_ok.setFixedWidth(100)
        btn_ok.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_open)
        btn_layout.addWidget(btn_ok)
        btn_layout.addStretch()
        flayout.addLayout(btn_layout)
        
    def open_folder(self):
        path = self.out_dir
        if os.path.exists(path):
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        self.accept()

class CustomMsgBox(QDialog):
    def __init__(self, parent, title, message):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(380, 160)
        
        main_frame = QFrame(self)
        main_frame.setObjectName("DialogCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(main_frame)
        
        flayout = QVBoxLayout(main_frame)
        flayout.setContentsMargins(20, 20, 20, 20)
        
        lbl_title = QLabel(title)
        lbl_title.setObjectName("Title")
        lbl_title.setAlignment(Qt.AlignCenter)
        flayout.addWidget(lbl_title)
        
        lbl_msg = QLabel(message)
        lbl_msg.setAlignment(Qt.AlignCenter)
        lbl_msg.setWordWrap(True)
        flayout.addWidget(lbl_msg, 1)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.setFixedWidth(100)
        btn_ok.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addStretch()
        flayout.addLayout(btn_layout)

class LoadingDialog(QDialog):
    def __init__(self, parent, title="Загрузка файлов..."):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(380, 160)
        
        main_frame = QFrame(self)
        main_frame.setObjectName("DialogCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(main_frame)
        
        flayout = QVBoxLayout(main_frame)
        flayout.setContentsMargins(20, 20, 20, 20)
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("Title")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        flayout.addWidget(self.lbl_title)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        flayout.addWidget(self.progress_bar)
        
        self.lbl_pct = QLabel("0% (0 из 0)")
        self.lbl_pct.setAlignment(Qt.AlignCenter)
        flayout.addWidget(self.lbl_pct)

    def update_progress(self, curr, total):
        if self.progress_bar.maximum() != total:
            self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(curr)
        pct = int((curr / total) * 100) if total > 0 else 0
        self.lbl_pct.setText(f"{pct}% ({curr} из {total})")

class FileRow(QFrame):
    reordered = Signal(int, int)
    
    def __init__(self, idx, file_path, is_cover, fill_checked, thumb_pixmap, theme_name, parent=None):
        super().__init__(parent)
        self.idx = idx
        self.file_path = file_path
        self.theme_name = theme_name
        self.setObjectName("Card")
        self.setAcceptDrops(True)
        
        rl = QHBoxLayout(self)
        rl.setContentsMargins(15, 10, 15, 10)
        
        drag_handle = QLabel("⋮⋮")
        drag_handle.setStyleSheet("color: #888888; font-size: 18px; font-weight: bold; background: transparent;")
        drag_handle.setCursor(Qt.OpenHandCursor)
        drag_handle.setToolTip("Потяните, чтобы переместить файл")
        rl.addWidget(drag_handle)
        
        self.lbl_num = QLabel(f"{idx+1}.")
        rl.addWidget(self.lbl_num)
        
        thumb = QLabel()
        thumb.setFixedSize(80, 80)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setPixmap(thumb_pixmap)
        rl.addWidget(thumb)

        name = os.path.basename(file_path)
        prefix = "[ОБЛОЖКА] " if is_cover else ""
        self.lbl_name = QLabel(prefix + (name if len(name)<40 else name[:37]+"..."))
        if is_cover: 
            self.lbl_name.setStyleSheet("color: #f66b3c; font-weight: bold;")
        rl.addWidget(self.lbl_name)
        rl.addStretch()

        self.cb_fill = QCheckBox("Без полей")
        self.cb_fill.setChecked(fill_checked)
        rl.addWidget(self.cb_fill)

        self.btn_crop = QPushButton("Кроп")
        rl.addWidget(self.btn_crop)

        self.btn_up = QPushButton("▲")
        self.btn_up.setObjectName("Secondary")
        self.btn_up.setFixedWidth(40)
        rl.addWidget(self.btn_up)

        self.btn_down = QPushButton("▼")
        self.btn_down.setObjectName("Secondary")
        self.btn_down.setFixedWidth(40)
        rl.addWidget(self.btn_down)

        self.btn_del = QPushButton("Удалить")
        self.btn_del.setObjectName("Danger")
        rl.addWidget(self.btn_del)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton): return
        if (event.pos() - self.drag_start_pos).manhattanLength() < 5: return
        
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(self.idx))
        drag.setMimeData(mime)
        drag.exec(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().isdigit():
            event.acceptProposedAction()
            self.setObjectName("ActiveCard")
            self.style().unpolish(self)
            self.style().polish(self)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setObjectName("Card")
        self.style().unpolish(self)
        self.style().polish(self)

    def dropEvent(self, event):
        self.setObjectName("Card")
        self.style().unpolish(self)
        self.style().polish(self)
        if event.mimeData().hasText():
            from_idx = int(event.mimeData().text())
            to_idx = self.idx
            if from_idx != to_idx:
                self.reordered.emit(from_idx, to_idx)
            event.acceptProposedAction()

class LoadWorker(QThread):
    progress = Signal(int, int, str, bytes)
    finished = Signal()

    def __init__(self, paths, cached_paths):
        super().__init__()
        self.paths = paths
        self.cached_paths = cached_paths

    def run(self):
        total = len(self.paths)
        for i, path in enumerate(self.paths):
            data = b""
            if path not in self.cached_paths:
                try:
                    img = Image.open(path)
                    img.thumbnail((80, 80))
                    byte_io = io.BytesIO()
                    img.save(byte_io, format="PNG")
                    data = byte_io.getvalue()
                except Exception as e:
                    logging.warning(f"Error thumbnailing {path}: {e}")
            
            self.progress.emit(i + 1, total, path, data)
        self.finished.emit()

class ProcessWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(int, int)
    error = Signal(str)

    def __init__(self, app_ref, files, state, use_c, has_wm, pref, start_count, step, targets, out_dir, target_size_text):
        super().__init__()
        self.app_ref = app_ref
        self.files = files
        self.state = state
        self.use_c = use_c
        self.has_wm = has_wm
        self.pref = pref
        self.count = start_count
        self.step = step
        self.targets = targets
        self.out_dir = out_dir
        self.target_size_text = target_size_text

    def process_single(self, task):
        p, odir, cn, rn, ext, only_cover = task
        successes = 0
        try:
            if cn:
                ci = self.app_ref.build_final_image(p, "cover", pre_state=self.state, target_size_text=self.target_size_text)
                if ci:
                    ci.save(os.path.join(odir, cn))
                    successes += 1
                    if only_cover:
                        return successes
            
            ri = self.app_ref.build_final_image(p, "regular", pre_state=self.state, target_size_text=self.target_size_text)
            if ri:
                if ext == ".jpg": 
                    ri.save(os.path.join(odir, rn), quality=92, optimize=True)
                else: 
                    ri.save(os.path.join(odir, rn))
                successes += 1
        except Exception as e:
            logging.error(f"Worker thread error on {p}: {e}")
        return successes

    def run(self):
        succ = 0
        total = len(self.files)
        
        tasks = []
        current_count = self.count
        
        for i, p in enumerate(self.files):
            oname = os.path.splitext(os.path.basename(p))[0]
            odir = self.out_dir if self.use_c else os.path.join(os.path.dirname(p), "Обработанные")
            os.makedirs(odir, exist_ok=True)
            ext = ".png" if self.has_wm else ".jpg"
            
            cn = None
            if self.state["active"] and p in self.targets and (self.state["active_banner"] or self.state["top_logo"] or self.state["show_markdown"]):
                if i == 0 and self.pref:
                    cn = f"0_{self.pref}{current_count}.png"
                elif i == 0:
                    cn = f"0_{oname}.png"
                elif self.pref:
                    cn = f"0_Обложка_{self.pref}{current_count}.png"
                else:
                    cn = f"0_Обложка_{oname}.png"
                    
            rn = f"{self.pref}{current_count}{ext}" if self.pref else f"{oname}_res{ext}"
            
            tasks.append((p, odir, cn, rn, ext, self.state["only_cover"]))
            current_count += self.step

        threads_count = max(1, (os.cpu_count() or 4) - 1)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads_count) as executor:
            futures = [executor.submit(self.process_single, task) for task in tasks]
            
            processed = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    succ += future.result()
                except Exception as e:
                    logging.error(f"Future crash: {e}")
                    
                processed += 1
                self.progress.emit(processed, total)
                
        self.finished.emit(succ, current_count)

class TitleBar(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setObjectName("TitleBar")
        self.setFixedHeight(40)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 0, 0)
        layout.setSpacing(0)
        
        lbl = QLabel("EasyBatch")
        lbl.setStyleSheet("font-weight: bold; font-size: 14px; background: transparent;")
        layout.addWidget(lbl)
        layout.addStretch()
        
        self.btn_min = QPushButton("—")
        self.btn_max = QPushButton("🗖")
        self.btn_close = QPushButton("✕")
        
        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setObjectName("TitleBtn")
            b.setFixedSize(45, 40)
            layout.addWidget(b)
        self.btn_close.setObjectName("TitleCloseBtn")
        
        self.btn_min.clicked.connect(self.parent.showMinimized)
        self.btn_max.clicked.connect(self.toggle_max)
        self.btn_close.clicked.connect(self.parent.close)
        
        self._start_pos = None

    def toggle_max(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.btn_max.setText("🗖")
        else:
            self.parent.showMaximized()
            self.btn_max.setText("🗗")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._start_pos and not self.parent.isMaximized():
            delta = event.globalPosition().toPoint() - self._start_pos
            self.parent.move(self.parent.pos() + delta)
            self._start_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._start_pos = None
    
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_max()

class DropZone(QWidget):
    dropped = Signal(list)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        self.lbl = QLabel("📥\n\nПеретащите фотографии сюда\nили нажмите кнопку «Добавить фото»")
        self.lbl.setAlignment(Qt.AlignCenter)
        self.lbl.setObjectName("Placeholder")
        self.lbl.setStyleSheet("font-size: 16px; background: transparent;")
        layout.addWidget(self.lbl)
        
    def paintEvent(self, event):
        p = QPainter(self)
        pen = QPen(QColor("#888888"), 2, Qt.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(10, 10, self.width()-20, self.height()-20, 10, 10)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        if paths:
            self.dropped.emit(paths)

class CollapsibleBox(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.toggle_btn = QPushButton(f"[ - ] {title}")
        self.toggle_btn.setStyleSheet("text-align: left; padding-left: 10px;")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(True)
        
        self.content_area = QFrame()
        self.content_area.setObjectName("Card")
        self.content_layout = QVBoxLayout(self.content_area)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.toggle_btn)
        main_layout.addWidget(self.content_area)
        
        self.toggle_btn.toggled.connect(self.toggle)
        
    def toggle(self, checked):
        self.toggle_btn.setText(self.toggle_btn.text().replace("[ + ]", "[ - ]") if checked else self.toggle_btn.text().replace("[ - ]", "[ + ]"))
        self.content_area.setVisible(checked)

class CoverTargetSelector(QDialog):
    def __init__(self, files, current_indices_str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(600, 500)
        
        main_frame = QFrame(self)
        main_frame.setObjectName("DialogCard")
        l = QVBoxLayout(self)
        l.setContentsMargins(0,0,0,0)
        l.addWidget(main_frame)
        layout = QVBoxLayout(main_frame)

        title = QLabel("Выбор фото для обложки")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        self.files = files
        try:
            self.selected_indices = [int(x.strip()) - 1 for x in current_indices_str.split(",") if x.strip().isdigit()]
        except ValueError:
            self.selected_indices = []

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.scroll_layout = QVBoxLayout(container)
        self.scroll_layout.setAlignment(Qt.AlignTop)

        self.checkboxes = []
        for i, path in enumerate(files):
            row = QFrame()
            row.setObjectName("Card")
            rl = QHBoxLayout(row)
            
            cb = QCheckBox()
            cb.setChecked(i in self.selected_indices)
            self.checkboxes.append((i, cb))
            rl.addWidget(cb)
            
            thumb = QLabel()
            try:
                img = Image.open(path)
                img.thumbnail((50, 50))
                thumb.setPixmap(pil_to_pixmap(img))
            except Exception as e: 
                logging.warning(f"Error loading thumb for selector {path}: {e}")
            rl.addWidget(thumb)
            
            name = os.path.basename(path)
            lbl = QLabel(f"{i+1}. {name}")
            rl.addWidget(lbl)
            rl.addStretch()
            self.scroll_layout.addWidget(row)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Сохранить выбор")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.setObjectName("Secondary")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def get_result(self):
        selected = [str(i + 1) for i, cb in self.checkboxes if cb.isChecked()]
        return ", ".join(selected)

class CropOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.l, self.t, self.r, self.b = 0.1, 0.1, 0.9, 0.9
        self.active_edge = None
        self.setMouseTracking(True)
        self.margin = 15

    def get_px_coords(self):
        w, h = self.width(), self.height()
        return int(w*self.l), int(h*self.t), int(w*self.r), int(h*self.b)

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        x1, y1, x2, y2 = self.get_px_coords()

        p.fillRect(0, 0, w, y1, QColor(0, 0, 0, 160))
        p.fillRect(0, y2, w, h-y2, QColor(0, 0, 0, 160))
        p.fillRect(0, y1, x1, y2-y1, QColor(0, 0, 0, 160))
        p.fillRect(x2, y1, w-x2, y2-y1, QColor(0, 0, 0, 160))

        pen = QPen(QColor("#f66b3c"), 3, Qt.DashLine)
        p.setPen(pen)
        p.drawRect(x1, y1, x2-x1, y2-y1)

    def mousePressEvent(self, event):
        ex, ey = event.position().x(), event.position().y()
        x1, y1, x2, y2 = self.get_px_coords()
        dists = {
            'l': abs(ex - x1), 'r': abs(ex - x2),
            't': abs(ey - y1), 'b': abs(ey - y2)
        }
        closest = min(dists, key=dists.get)
        if dists[closest] < self.margin:
            self.active_edge = closest

    def mouseMoveEvent(self, event):
        ex, ey = event.position().x(), event.position().y()
        x1, y1, x2, y2 = self.get_px_coords()

        if not self.active_edge:
            if abs(ex - x1) < self.margin or abs(ex - x2) < self.margin:
                self.setCursor(Qt.SizeHorCursor)
            elif abs(ey - y1) < self.margin or abs(ey - y2) < self.margin:
                self.setCursor(Qt.SizeVerCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            return

        w, h = self.width(), self.height()
        nx, ny = max(0, min(ex, w)), max(0, min(ey, h))
        nl, nt, nr, nb = nx / w, ny / h, nx / w, ny / h

        if self.active_edge == 'l' and nl < self.r - 0.05: self.l = nl
        elif self.active_edge == 'r' and nr > self.l + 0.05: self.r = nr
        elif self.active_edge == 't' and nt < self.b - 0.05: self.t = nt
        elif self.active_edge == 'b' and nb > self.t + 0.05: self.b = nb
        
        self.update()

    def mouseReleaseEvent(self, event):
        self.active_edge = None

class CropDialog(QDialog):
    def __init__(self, img_path, coords, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(900, 750)
        self.img_path = img_path
        
        self._is_tracking = False
        self._start_pos = None

        main_frame = QFrame(self)
        main_frame.setObjectName("DialogCard")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.addWidget(main_frame)
        
        frame_layout = QVBoxLayout(main_frame)

        title_lbl = QLabel("Обрезка фото")
        title_lbl.setObjectName("Title")
        title_lbl.setAlignment(Qt.AlignCenter)
        frame_layout.addWidget(title_lbl)
        
        self.view_container = QWidget()
        self.view_layout = QVBoxLayout(self.view_container)
        self.view_layout.setContentsMargins(0,0,0,0)
        self.view_layout.setAlignment(Qt.AlignCenter)
        
        self.img_lbl = QLabel()
        self.img_lbl.setAlignment(Qt.AlignCenter)
        
        self.view_layout.addWidget(self.img_lbl)
        frame_layout.addWidget(self.view_container, 1)

        btn_layout = QHBoxLayout()
        btn_apply = QPushButton("Применить")
        btn_save_tpl = QPushButton("Сохранить шаблон")
        btn_save_tpl.setObjectName("Secondary")
        btn_cancel = QPushButton("Отмена")
        btn_cancel.setObjectName("Secondary")

        btn_layout.addWidget(btn_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save_tpl)
        btn_layout.addWidget(btn_apply)
        frame_layout.addLayout(btn_layout)

        btn_apply.clicked.connect(self.accept)
        btn_save_tpl.clicked.connect(self.save_template)
        btn_cancel.clicked.connect(self.reject)

        try:
            self.original_img = Image.open(img_path)
            self.display_img = self.original_img.copy()
            
            self.display_img.thumbnail((850, 600), Image.Resampling.LANCZOS)
            self.pixmap = pil_to_pixmap(self.display_img)
            self.img_lbl.setFixedSize(self.pixmap.size())
            self.img_lbl.setPixmap(self.pixmap)
            
            self.overlay = CropOverlay(self.img_lbl)
            self.overlay.resize(self.img_lbl.size())
            
            self.scale_x = self.original_img.width / self.display_img.width
            self.scale_y = self.original_img.height / self.display_img.height
        except Exception as e:
            logging.error(f"Error opening image for crop {img_path}: {e}")

        if coords:
            self.overlay.l = coords[0] / self.original_img.width
            self.overlay.t = coords[1] / self.original_img.height
            self.overlay.r = coords[2] / self.original_img.width
            self.overlay.b = coords[3] / self.original_img.height
        else:
            guides = self.load_crop_config()
            self.overlay.l, self.overlay.r, self.overlay.t, self.overlay.b = guides['left'], guides['right'], guides['top'], guides['bottom']

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_tracking = True
            self._start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._is_tracking:
            self.move(event.globalPosition().toPoint() - self._start_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_tracking = False

    def load_crop_config(self):
        if os.path.exists(CROP_CONFIG_FILE):
            try:
                with open(CROP_CONFIG_FILE, 'r') as f: return json.load(f)
            except Exception as e:
                logging.error(f"Failed to load crop config: {e}")
        return {'left': 0.1, 'right': 0.9, 'top': 0.1, 'bottom': 0.9}

    def save_template(self):
        guides = {'left': self.overlay.l, 'right': self.overlay.r, 'top': self.overlay.t, 'bottom': self.overlay.b}
        try:
            with open(CROP_CONFIG_FILE, 'w') as f: json.dump(guides, f)
            CustomMsgBox(self, "Сохранено", "Позиции направляющих сохранены по умолчанию").exec()
        except Exception as e:
            logging.error(f"Failed to save crop config: {e}")

    def get_result(self):
        return (
            self.overlay.l * self.display_img.width * self.scale_x,
            self.overlay.t * self.display_img.height * self.scale_y,
            self.overlay.r * self.display_img.width * self.scale_x,
            self.overlay.b * self.display_img.height * self.scale_y
        )

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(1150, 800)
        self.setMinimumSize(900, 650)
        self.setAcceptDrops(True)

        self.thumb_cache = {}

        gen_cfg = self.load_general_config()
        self.current_theme = gen_cfg.get("theme", "light")
        self.custom_sizes = gen_cfg.get("sizes", ["1200x900", "900x900"])
        self.remember_files = gen_cfg.get("remember_files", False)
        cached_files = gen_cfg.get("cached_files", [])
        self.files = [f for f in cached_files if os.path.exists(f)] if self.remember_files else []
        
        self.crop_data = {}
        self.fill_settings = {}
        self.watermarks_config = self.load_wm_config()
        self.current_wm_edit = None
        
        self.cover_cfg_data = self.load_cover_config()
        self.global_transform = self.cover_cfg_data.get("global_transform", {"scale": 100, "x": 0, "y": 0})
        self.individual_transforms = self.cover_cfg_data.get("individual_transforms", {})
        self.global_price = self.cover_cfg_data.get("global_price", {"new": self.cover_cfg_data.get("price_new", "9990"), "old": self.cover_cfg_data.get("price_old", "14990")})
        self.individual_prices = self.cover_cfg_data.get("individual_prices", {})
        
        self.current_cover_preview_idx = 0
        self.current_wm_preview_idx = 0
        self._is_switching = False
        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self.render_cover_preview)
        
        self.wm_pos_icons = {}
        self.worker = None
        self.load_worker = None
        self.loading_dialog = None

        self.setup_ui()
        
        self.theme_cb.blockSignals(True)
        self.theme_cb.setChecked(self.current_theme == "light")
        self.theme_cb.blockSignals(False)
        self.apply_theme()
        
        self.load_cover_state(self.cover_cfg_data)
        self.refresh_wm_list()
        self.refresh_banners_list_ui()
        self.refresh_file_list_ui()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        if paths:
            self.on_files_dropped(paths)

    def on_files_dropped(self, paths):
        added_paths = []
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                added_paths.append(p)
        if added_paths:
            self.add_files_to_ui_async(added_paths)

    def closeEvent(self, event):
        self.save_general_config()
        self.save_cover_config()
        self.save_wm_config()
        event.accept()

    def load_general_config(self):
        if os.path.exists(GENERAL_CONFIG_FILE):
            try:
                with open(GENERAL_CONFIG_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except Exception as e:
                logging.error(f"Failed to load general config: {e}")
        return {"sizes": ["1200x900", "900x900"], "remember_files": False, "cached_files": [], "theme": "light"}

    def save_general_config(self):
        rem = self.cb_remember_files.isChecked() if hasattr(self, 'cb_remember_files') else False
        data = {
            "sizes": self.custom_sizes,
            "remember_files": rem,
            "cached_files": self.files if rem else [],
            "theme": self.current_theme
        }
        try:
            with open(GENERAL_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Failed to save general config: {e}")

    def load_wm_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except Exception as e:
                logging.error(f"Failed to load wm config: {e}")
        return {}

    def save_wm_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.watermarks_config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Failed to save wm config: {e}")

    def load_cover_config(self):
        if os.path.exists(COVER_CONFIG_FILE):
            try:
                with open(COVER_CONFIG_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except Exception as e:
                logging.error(f"Failed to load cover config: {e}")
        return {}

    def save_cover_config(self):
        data = self.get_cover_state()
        data["global_transform"] = self.global_transform
        data["individual_transforms"] = self.individual_transforms
        data["global_price"] = self.global_price
        data["individual_prices"] = self.individual_prices
        try:
            with open(COVER_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Failed to save cover config: {e}")

    def apply_theme(self):
        QApplication.instance().setStyleSheet(get_stylesheet(self.current_theme))
        self.update_dynamic_text()
        self.refresh_wm_list()
        self.update_file_row_labels()
        self.update_pos_icons()

    def update_pos_icons(self):
        color_str = THEMES[self.current_theme]['TEXT']
        if hasattr(self, 'wm_pos_icons'):
            for val, lbl in self.wm_pos_icons.items():
                lbl.setPixmap(create_arrow_pixmap(val, color_str))

    def update_dynamic_text(self):
        color = THEMES[self.current_theme]['PRIMARY']
        if hasattr(self, 'bot_drop_lbl'):
            self.bot_drop_lbl.setText(f'Вы можете перетащить сюда новые фото или <a href="#add" style="color:{color}; text-decoration:none;">добавить их кликом</a>')

    def toggle_theme(self):
        self.loading_dialog = LoadingDialog(self, "Смена темы...")
        self.loading_dialog.progress_bar.setRange(0, 0)
        self.loading_dialog.lbl_pct.setText("Перерисовка стилей интерфейса...")
        self.loading_dialog.show()
        
        QApplication.processEvents()

        self.current_theme = "light" if self.theme_cb.isChecked() else "dark"
        self.setUpdatesEnabled(False)
        self.apply_theme()
        self.setUpdatesEnabled(True)
        
        if self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None

    def create_slider_row(self, layout, text, min_v, max_v, command=None):
        row = QWidget()
        l = QHBoxLayout(row)
        l.setContentsMargins(0, 2, 0, 2)
        lbl = QLabel(text)
        lbl.setFixedWidth(110)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_v, max_v)
        entry = QLineEdit()
        entry.setFixedWidth(50)
        entry.setAlignment(Qt.AlignCenter)
        
        slider.valueChanged.connect(lambda v: entry.setText(str(v)))
        entry.textChanged.connect(lambda t: slider.setValue(int(t)) if t.lstrip('-').isdigit() else None)
        
        callback = command if command else self.request_cover_preview
        slider.valueChanged.connect(callback)
        
        l.addWidget(lbl)
        l.addWidget(slider)
        l.addWidget(entry)
        layout.addWidget(row)
        return slider, entry

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        win_layout = QVBoxLayout(central)
        win_layout.setContentsMargins(0,0,0,0)

        self.app_frame = QFrame()
        self.app_frame.setObjectName("AppWindow")
        main_layout = QVBoxLayout(self.app_frame)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        self.title_bar = TitleBar(self)
        main_layout.addWidget(self.title_bar)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        self.tabview = QTabWidget()
        self.tab_files = QWidget()
        self.tab_cover = QWidget()
        self.tab_wm = QWidget()
        self.tab_out = QWidget()

        self.tabview.addTab(self.tab_files, "Файлы")
        self.tabview.addTab(self.tab_cover, "Обложка")
        self.tabview.addTab(self.tab_wm, "Водяные знаки")
        self.tabview.addTab(self.tab_out, "Вывод и Превью")
        self.tabview.currentChanged.connect(self.on_tab_change)
        content_layout.addWidget(self.tabview)

        bot_layout = QHBoxLayout()
        
        left_bot_layout = QVBoxLayout()
        left_bot_layout.setSpacing(2)
        self.theme_cb = QCheckBox("Смена темы")
        self.theme_cb.toggled.connect(self.toggle_theme)
        copyright_lbl = QLabel("© 2026 KpeoH. Все права защищены.")
        copyright_lbl.setStyleSheet("color: #888888; font-size: 10px; background: transparent;")
        
        left_bot_layout.addWidget(self.theme_cb)
        left_bot_layout.addWidget(copyright_lbl)
        bot_layout.addLayout(left_bot_layout)
        
        bot_layout.addStretch()
        
        right_bot_layout = QVBoxLayout()
        right_bot_layout.setSpacing(5)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(12) 
        self.progress_bar.setTextVisible(False)
        
        self.btn_process = QPushButton("ОБРАБОТАТЬ ФОТО")
        self.btn_process.setMinimumHeight(45)
        self.btn_process.clicked.connect(self.process_images)
        
        right_bot_layout.addWidget(self.progress_bar)
        right_bot_layout.addWidget(self.btn_process)
        
        bot_layout.addLayout(right_bot_layout, 2)
        
        self.grip = QSizeGrip(self.app_frame)
        self.grip.setFixedSize(15, 15)
        bot_layout.addWidget(self.grip, 0, Qt.AlignBottom | Qt.AlignRight)
        
        content_layout.addLayout(bot_layout)
        main_layout.addWidget(content_widget, 1)
        win_layout.addWidget(self.app_frame)

        self.build_files_tab()
        self.build_cover_tab()
        self.build_wm_tab()
        self.build_out_tab()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grip.move(self.width() - 25, self.height() - 25)

    def build_files_tab(self):
        l = QVBoxLayout(self.tab_files)
        top = QHBoxLayout()
        btn_add = QPushButton("Добавить фото")
        btn_clear = QPushButton("Очистить список")
        btn_clear.setObjectName("Secondary")
        self.cb_remember_files = QCheckBox("Запоминать файлы при выходе")
        self.cb_remember_files.setChecked(self.remember_files)
        
        btn_add.clicked.connect(self.add_files)
        btn_clear.clicked.connect(self.clear_list)
        top.addWidget(btn_add)
        top.addWidget(btn_clear)
        top.addWidget(self.cb_remember_files)
        top.addStretch()
        l.addLayout(top)

        self.drop_zone = DropZone()
        self.drop_zone.dropped.connect(self.on_files_dropped)
        l.addWidget(self.drop_zone, 1)

        self.files_scroll = QScrollArea()
        self.files_scroll.setWidgetResizable(True)
        self.files_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.files_container = QWidget()
        self.files_layout = QVBoxLayout(self.files_container)
        self.files_layout.setAlignment(Qt.AlignTop)
        self.files_scroll.setWidget(self.files_container)
        self.files_scroll.hide() 
        l.addWidget(self.files_scroll, 1)
        
        self.bot_drop_lbl = QLabel()
        self.bot_drop_lbl.setTextFormat(Qt.RichText)
        self.bot_drop_lbl.setAlignment(Qt.AlignCenter)
        self.bot_drop_lbl.linkActivated.connect(lambda _: self.add_files())
        self.bot_drop_lbl.hide()
        l.addWidget(self.bot_drop_lbl)

    def get_current_cover_indices(self):
        mode = self.cb_target_mode.currentText() if hasattr(self, 'cb_target_mode') else "Только 1-е фото"
        cover_indices = []
        if hasattr(self, 'cb_active_cover') and self.cb_active_cover.isChecked():
            if mode == "Только 1-е фото": cover_indices = [0]
            elif mode == "Ко всем": cover_indices = list(range(len(self.files)))
            elif mode == "Выборочно":
                try: cover_indices = [int(x.strip()) - 1 for x in self.entry_target_indices.text().split(",") if x.strip().isdigit()]
                except Exception: pass
        return cover_indices

    def update_file_row_labels(self):
        cover_indices = self.get_current_cover_indices()
        for i in range(self.files_layout.count()):
            w = self.files_layout.itemAt(i).widget()
            if isinstance(w, FileRow):
                is_cover = i in cover_indices
                name = os.path.basename(w.file_path)
                prefix = "[ОБЛОЖКА] " if is_cover else ""
                w.lbl_name.setText(prefix + (name if len(name)<40 else name[:37]+"..."))
                if is_cover: 
                    w.lbl_name.setStyleSheet("color: #f66b3c; font-weight: bold;")
                else:
                    w.lbl_name.setStyleSheet("")

    def refresh_file_list_ui(self):
        while self.files_layout.count():
            w = self.files_layout.takeAt(0).widget()
            if w: w.deleteLater()
            
        if not self.files:
            self.drop_zone.show()
            self.files_scroll.hide()
            self.bot_drop_lbl.hide()
            return
            
        self.add_files_to_ui_async(self.files)

    def add_files_to_ui_async(self, new_paths):
        self.drop_zone.hide()
        self.files_scroll.show()
        self.bot_drop_lbl.show()

        self.loading_dialog = LoadingDialog(self, "Загрузка и создание миниатюр...")
        self.loading_dialog.setModal(True)
        self.loading_dialog.show()

        self.files_container.setUpdatesEnabled(False)
        self._temp_cover_indices = self.get_current_cover_indices()

        cached_paths = set(self.thumb_cache.keys())
        self.load_worker = LoadWorker(new_paths, cached_paths)
        self.load_worker.progress.connect(self.on_file_loaded)
        self.load_worker.finished.connect(self.on_load_finished)
        self.load_worker.start()

    def on_file_loaded(self, curr, total, path, data):
        if self.loading_dialog:
            self.loading_dialog.update_progress(curr, total)
        
        if data:
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            self.thumb_cache[path] = pixmap
        elif path not in self.thumb_cache:
            self.thumb_cache[path] = QPixmap()

        thumb_pixmap = self.thumb_cache[path]
        idx = self.files.index(path)
        is_cover = idx in self._temp_cover_indices
        fill_checked = self.fill_settings.get(path, False)

        row = FileRow(idx, path, is_cover, fill_checked, thumb_pixmap, self.current_theme)
        row.cb_fill.toggled.connect(lambda c, p=path: self.toggle_fill(p, c))
        row.btn_crop.clicked.connect(lambda _, p=path: self.open_crop(p))
        row.btn_up.clicked.connect(lambda _, p=path: self.move_file(p, -1))
        row.btn_down.clicked.connect(lambda _, p=path: self.move_file(p, 1))
        row.btn_del.clicked.connect(lambda _, p=path: self.remove_file(p))
        row.reordered.connect(self.reorder_files)
        
        if idx == 0: row.btn_up.setEnabled(False)
        if idx == len(self.files) - 1: row.btn_down.setEnabled(False)

        self.files_layout.addWidget(row)

    def on_load_finished(self):
        self.files_container.setUpdatesEnabled(True)
        
        if hasattr(self, 'loading_dialog') and self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None
            
        self.update_file_row_labels()
        self.update_dropdown_files()
        self.request_cover_preview()
        self.render_wm_preview()

    def reorder_files(self, from_idx, to_idx):
        if 0 <= from_idx < len(self.files) and 0 <= to_idx < len(self.files):
            item = self.files.pop(from_idx)
            self.files.insert(to_idx, item)
            
            self.files_container.setUpdatesEnabled(False)
            
            widget = self.files_layout.takeAt(from_idx).widget()
            self.files_layout.insertWidget(to_idx, widget)
            
            for i in range(self.files_layout.count()):
                w = self.files_layout.itemAt(i).widget()
                if isinstance(w, FileRow):
                    w.idx = i
                    w.lbl_num.setText(f"{i+1}.")
                    w.btn_up.setEnabled(i > 0)
                    w.btn_down.setEnabled(i < self.files_layout.count() - 1)
            
            self.files_container.setUpdatesEnabled(True)
            
            self.update_file_row_labels()
            self.update_dropdown_files()
            self.request_cover_preview()
            self.render_wm_preview()

    def toggle_fill(self, path, checked):
        self.fill_settings[path] = checked
        self.render_out_preview()
        self.render_wm_preview()

    def open_crop(self, path):
        dlg = CropDialog(path, self.crop_data.get(path), self)
        if dlg.exec():
            self.crop_data[path] = dlg.get_result()
            self.render_out_preview()
            self.request_cover_preview()
            self.render_wm_preview()

    def move_file(self, path, dir):
        idx = self.files.index(path)
        nidx = idx + dir
        self.reorder_files(idx, nidx)

    def remove_file(self, path):
        idx = self.files.index(path)
        self.files.pop(idx)
        if path in self.crop_data: del self.crop_data[path]
        
        self.files_container.setUpdatesEnabled(False)
        w = self.files_layout.takeAt(idx).widget()
        if w: w.deleteLater()
        
        for i in range(self.files_layout.count()):
            w = self.files_layout.itemAt(i).widget()
            if isinstance(w, FileRow):
                w.idx = i
                w.lbl_num.setText(f"{i+1}.")
                w.btn_up.setEnabled(i > 0)
                w.btn_down.setEnabled(i < self.files_layout.count() - 1)
        self.files_container.setUpdatesEnabled(True)

        if not self.files:
            self.refresh_file_list_ui()
            
        self.update_file_row_labels()
        self.update_dropdown_files()
        self.request_cover_preview()
        self.render_wm_preview()

    def add_files(self):
        paths = native_askopenfilenames(title="Выберите фотографии")
        if not paths: return
        added_paths = []
        for p in paths:
            if p not in self.files: 
                self.files.append(p)
                added_paths.append(p)
        if added_paths:
            self.add_files_to_ui_async(added_paths)

    def clear_list(self):
        self.files.clear()
        self.crop_data.clear()
        self.thumb_cache.clear()
        self.refresh_file_list_ui()
        self.update_dropdown_files()
        self.request_cover_preview()
        self.render_wm_preview()

    def build_cover_tab(self):
        l = QHBoxLayout(self.tab_cover)
        
        left = QScrollArea()
        left.setFixedWidth(420)
        left.setWidgetResizable(True)
        left.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_w = QWidget()
        self.left_l = QVBoxLayout(left_w)
        self.left_l.setAlignment(Qt.AlignTop)
        left.setWidget(left_w)
        l.addWidget(left)

        self.cb_active_cover = QCheckBox("Создавать обложку")
        self.cb_only_cover = QCheckBox("ТОЛЬКО обложка (без обычного фото)")
        self.cb_active_cover.toggled.connect(self.save_cover_config)
        self.cb_active_cover.toggled.connect(self.update_file_row_labels)
        self.cb_only_cover.toggled.connect(self.save_cover_config)
        
        self.left_l.addWidget(self.cb_active_cover)
        self.left_l.addWidget(self.cb_only_cover)

        tgt_row = QHBoxLayout()
        tgt_row.addWidget(QLabel("Применять к:"))
        self.cb_target_mode = QComboBox()
        self.cb_target_mode.addItems(["Только 1-е фото", "Ко всем", "Выборочно"])
        self.cb_target_mode.currentTextChanged.connect(self.on_cover_target_change)
        tgt_row.addWidget(self.cb_target_mode)
        
        self.btn_sel_tgt = QPushButton("Выбрать фото")
        self.btn_sel_tgt.setObjectName("Secondary")
        self.btn_sel_tgt.clicked.connect(self.open_target_selector)
        tgt_row.addWidget(self.btn_sel_tgt)
        self.entry_target_indices = QLineEdit("1")
        self.entry_target_indices.hide()
        self.left_l.addLayout(tgt_row)

        b_prod = CollapsibleBox("Трансформация товара")
        self.cb_individual = QCheckBox("Индивидуально для этого фото")
        self.cb_individual.toggled.connect(self.on_individual_toggle)
        b_prod.content_layout.addWidget(self.cb_individual)
        self.sl_img_sc, self.e_img_sc = self.create_slider_row(b_prod.content_layout, "Масштаб %:", 10, 300)
        self.sl_img_x, self.e_img_x = self.create_slider_row(b_prod.content_layout, "Позиция X:", -1000, 1000)
        self.sl_img_y, self.e_img_y = self.create_slider_row(b_prod.content_layout, "Позиция Y:", -1000, 1000)
        
        self.sl_img_sc.valueChanged.connect(self._on_transform_change)
        self.sl_img_x.valueChanged.connect(self._on_transform_change)
        self.sl_img_y.valueChanged.connect(self._on_transform_change)

        btn_rst_prod = QPushButton("Сбросить товар")
        btn_rst_prod.setObjectName("Secondary")
        btn_rst_prod.clicked.connect(self.reset_product_transform)
        b_prod.content_layout.addWidget(btn_rst_prod)
        self.left_l.addWidget(b_prod)

        b_ban = CollapsibleBox("Дополнительная плашка")
        btn_add_ban = QPushButton("Выбрать картинку плашки")
        btn_add_ban.clicked.connect(self.add_banner)
        b_ban.content_layout.addWidget(btn_add_ban)
        
        self.ban_list_widget = QVBoxLayout()
        b_ban.content_layout.addLayout(self.ban_list_widget)
        self.active_banner = ""
        self.banners_list = []

        self.sl_ban_sc, self.e_ban_sc = self.create_slider_row(b_ban.content_layout, "Масштаб %:", 10, 300)
        self.sl_ban_x, self.e_ban_x = self.create_slider_row(b_ban.content_layout, "Позиция X:", -1000, 1000)
        self.sl_ban_y, self.e_ban_y = self.create_slider_row(b_ban.content_layout, "Позиция Y:", -1000, 1000)
        btn_rst_ban = QPushButton("Сбросить")
        btn_rst_ban.setObjectName("Secondary")
        btn_rst_ban.clicked.connect(lambda: (self.sl_ban_sc.setValue(100), self.sl_ban_x.setValue(0), self.sl_ban_y.setValue(0)))
        b_ban.content_layout.addWidget(btn_rst_ban)
        self.left_l.addWidget(b_ban)

        b_logo = CollapsibleBox("Основной логотип")
        lr = QHBoxLayout()
        btn_sel_logo = QPushButton("Выбрать...")
        btn_del_logo = QPushButton("Удалить")
        btn_del_logo.setObjectName("Danger")
        self.lbl_logo_name = QLabel("")
        btn_sel_logo.clicked.connect(self.select_logo)
        btn_del_logo.clicked.connect(self.clear_logo)
        lr.addWidget(btn_sel_logo)
        lr.addWidget(btn_del_logo)
        lr.addWidget(self.lbl_logo_name)
        b_logo.content_layout.addLayout(lr)

        self.sl_logo_sc, self.e_logo_sc = self.create_slider_row(b_logo.content_layout, "Масштаб %:", 10, 300)
        self.sl_logo_x, self.e_logo_x = self.create_slider_row(b_logo.content_layout, "Позиция X:", -1000, 1000)
        self.sl_logo_y, self.e_logo_y = self.create_slider_row(b_logo.content_layout, "Позиция Y:", -1000, 1000)
        btn_rst_logo = QPushButton("Сбросить")
        btn_rst_logo.setObjectName("Secondary")
        btn_rst_logo.clicked.connect(lambda: (self.sl_logo_sc.setValue(100), self.sl_logo_x.setValue(0), self.sl_logo_y.setValue(0)))
        b_logo.content_layout.addWidget(btn_rst_logo)
        self.left_l.addWidget(b_logo)

        b_md = CollapsibleBox("Уценка (Цены и значок)")
        self.cb_md_active = QCheckBox("Включить отображение")
        self.cb_md_active.toggled.connect(self.request_cover_preview)
        b_md.content_layout.addWidget(self.cb_md_active)
        
        self.cb_individual_price = QCheckBox("Индивидуальные цены для этого фото")
        self.cb_individual_price.toggled.connect(self.on_individual_price_toggle)
        b_md.content_layout.addWidget(self.cb_individual_price)

        md_lr = QHBoxLayout()
        btn_sel_md = QPushButton("Выбрать Лого")
        btn_del_md = QPushButton("Удалить")
        btn_del_md.setObjectName("Danger")
        self.lbl_md_name = QLabel("")
        btn_sel_md.clicked.connect(self.select_md_logo)
        btn_del_md.clicked.connect(self.clear_md_logo)
        md_lr.addWidget(btn_sel_md); md_lr.addWidget(btn_del_md); md_lr.addWidget(self.lbl_md_name)
        b_md.content_layout.addLayout(md_lr)

        self.sl_md_sc, self.e_md_sc = self.create_slider_row(b_md.content_layout, "Масштаб лого:", 10, 300)
        self.sl_md_x, self.e_md_x = self.create_slider_row(b_md.content_layout, "X (лого):", -1000, 1000)
        self.sl_md_y, self.e_md_y = self.create_slider_row(b_md.content_layout, "Y (лого):", -1000, 1000)

        pr_r = QHBoxLayout()
        pr_r.addWidget(QLabel("Новая:"))
        self.e_pr_new = QLineEdit("9990")
        self.e_pr_new.textChanged.connect(self._on_price_change)
        pr_r.addWidget(self.e_pr_new)
        pr_r.addWidget(QLabel("Старая:"))
        self.e_pr_old = QLineEdit("14990")
        self.e_pr_old.textChanged.connect(self._on_price_change)
        pr_r.addWidget(self.e_pr_old)
        b_md.content_layout.addLayout(pr_r)

        f_r = QHBoxLayout()
        btn_sel_f = QPushButton("Шрифт...")
        btn_del_f = QPushButton("Удалить")
        btn_del_f.setObjectName("Danger")
        self.lbl_font_name = QLabel("")
        btn_sel_f.clicked.connect(self.select_font)
        btn_del_f.clicked.connect(self.clear_font)
        f_r.addWidget(btn_sel_f); f_r.addWidget(btn_del_f); f_r.addWidget(self.lbl_font_name)
        b_md.content_layout.addLayout(f_r)

        self.sl_pr_sc, self.e_pr_sc = self.create_slider_row(b_md.content_layout, "Масштаб цен:", 10, 300)
        self.sl_pr_nx, self.e_pr_nx = self.create_slider_row(b_md.content_layout, "Нов. цена X:", -1000, 1000)
        self.sl_pr_ny, self.e_pr_ny = self.create_slider_row(b_md.content_layout, "Нов. цена Y:", -1000, 1000)
        self.sl_pr_ox, self.e_pr_ox = self.create_slider_row(b_md.content_layout, "Стар. цена X:", -1000, 1000)
        self.sl_pr_oy, self.e_pr_oy = self.create_slider_row(b_md.content_layout, "Стар. цена Y:", -1000, 1000)
        self.sl_str_w, self.e_str_w = self.create_slider_row(b_md.content_layout, "Толщина черты:", 1, 30)

        self.left_l.addWidget(b_md)
        self.left_l.addStretch()

        right = QWidget()
        rl = QVBoxLayout(right)
        nav = QHBoxLayout()
        btn_prev = QPushButton("<")
        btn_next = QPushButton(">")
        btn_prev.setFixedWidth(40)
        btn_next.setFixedWidth(40)
        btn_prev.clicked.connect(lambda: self.switch_cover_preview(-1))
        btn_next.clicked.connect(lambda: self.switch_cover_preview(1))
        self.lbl_cov_title = QLabel("Превью обложки:")
        self.lbl_cov_title.setObjectName("Title")
        
        nav.addWidget(btn_prev)
        nav.addWidget(self.lbl_cov_title)
        nav.addWidget(btn_next)
        nav.addStretch()
        rl.addLayout(nav)

        self.cov_preview_lbl = QLabel("Загрузите фото во вкладке 'Файлы'")
        self.cov_preview_lbl.setAlignment(Qt.AlignCenter)
        self.cov_preview_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        rl.addWidget(self.cov_preview_lbl, 1)

        l.addWidget(right, 1)

    def on_cover_target_change(self, text):
        self.btn_sel_tgt.setVisible(text == "Выборочно")
        self.update_file_row_labels()
        self.request_cover_preview()

    def open_target_selector(self):
        if not self.files: 
            CustomMsgBox(self, "Пусто", "Сначала загрузите фотографии во вкладке 'Файлы'").exec()
            return
        dlg = CoverTargetSelector(self.files, self.entry_target_indices.text(), self)
        if dlg.exec():
            self.entry_target_indices.setText(dlg.get_result())
            self.save_cover_config()
            self.update_file_row_labels()
            self.request_cover_preview()

    def add_banner(self):
        paths = native_askopenfilenames(title="Выберите картинки плашек")
        if not paths: return
        for path in paths:
            filename = os.path.basename(path)
            dest = os.path.join(ASSETS_DIR, filename)
            try: shutil.copy(path, dest)
            except Exception as e: logging.error(f"Error copying banner {path}: {e}")
            if filename not in self.banners_list: self.banners_list.append(filename)
        self.save_cover_config()
        self.refresh_banners_list_ui()
        self.request_cover_preview()

    def refresh_banners_list_ui(self):
        while self.ban_list_widget.count():
            w = self.ban_list_widget.takeAt(0).widget()
            if w: w.deleteLater()
            
        for f in self.banners_list:
            row = QFrame()
            row.setObjectName("Card")
            l = QHBoxLayout(row)
            l.setContentsMargins(5, 5, 5, 5)
            
            cb = QCheckBox()
            cb.setChecked(f == self.active_banner)
            cb.toggled.connect(lambda c, name=f: self.select_banner(name, c))
            l.addWidget(cb)
            
            thumb = QLabel()
            thumb.setFixedSize(40, 40)
            thumb.setAlignment(Qt.AlignCenter)
            try:
                img = Image.open(get_asset_path(f))
                img.thumbnail((40, 40))
                thumb.setPixmap(pil_to_pixmap(img))
            except Exception as e: logging.warning(f"Banner thumb error: {e}")
            l.addWidget(thumb)
            
            lbl = QLabel(f if len(f)<15 else f[:12]+"...")
            l.addWidget(lbl)
            l.addStretch()
            
            btn_del = QPushButton("Удалить")
            btn_del.setObjectName("Danger")
            btn_del.setFixedWidth(70)
            btn_del.clicked.connect(lambda _, name=f: self.delete_banner(name))
            l.addWidget(btn_del)
            
            self.ban_list_widget.addWidget(row)

    def select_banner(self, name, checked):
        self.active_banner = name if checked else ""
        self.refresh_banners_list_ui()
        self.request_cover_preview()

    def delete_banner(self, name):
        self.banners_list.remove(name)
        if self.active_banner == name: self.active_banner = ""
        self.refresh_banners_list_ui()
        self.request_cover_preview()

    def select_logo(self):
        p = native_askopenfilename(title="Выберите логотип")
        if p:
            f = os.path.basename(p)
            try: shutil.copy(p, os.path.join(ASSETS_DIR, f))
            except Exception as e: logging.error(f"Copy logo error: {e}")
            self.lbl_logo_name.setText(f)
            self.request_cover_preview()

    def clear_logo(self):
        self.lbl_logo_name.setText("")
        self.request_cover_preview()

    def select_md_logo(self):
        p = native_askopenfilename(title="Выберите логотип уценки")
        if p:
            f = os.path.basename(p)
            try: shutil.copy(p, os.path.join(ASSETS_DIR, f))
            except Exception as e: logging.error(f"Copy markdown logo error: {e}")
            self.lbl_md_name.setText(f)
            self.request_cover_preview()

    def clear_md_logo(self):
        self.lbl_md_name.setText("")
        self.request_cover_preview()

    def select_font(self):
        p = native_askopenfilename(title="Выберите шрифт")
        if p:
            f = os.path.basename(p)
            try: shutil.copy(p, os.path.join(ASSETS_DIR, f))
            except Exception as e: logging.error(f"Copy font error: {e}")
            self.lbl_font_name.setText(f)
            self.request_cover_preview()

    def clear_font(self):
        self.lbl_font_name.setText("")
        self.request_cover_preview()

    def _on_transform_change(self):
        if self._is_switching: return
        t = self.get_cover_targets()
        if not t: return
        path = t[self.current_cover_preview_idx % len(t)]
        vals = {"scale": self.sl_img_sc.value(), "x": self.sl_img_x.value(), "y": self.sl_img_y.value()}
        if self.cb_individual.isChecked(): self.individual_transforms[path] = vals
        else: self.global_transform = vals
        self.request_cover_preview()

    def on_individual_toggle(self):
        t = self.get_cover_targets()
        if not t: return
        path = t[self.current_cover_preview_idx % len(t)]
        if self.cb_individual.isChecked():
            self.individual_transforms[path] = {"scale": self.sl_img_sc.value(), "x": self.sl_img_x.value(), "y": self.sl_img_y.value()}
        else:
            if path in self.individual_transforms: del self.individual_transforms[path]
            self._is_switching = True
            self.sl_img_sc.setValue(self.global_transform["scale"])
            self.sl_img_x.setValue(self.global_transform["x"])
            self.sl_img_y.setValue(self.global_transform["y"])
            self._is_switching = False
        self.request_cover_preview()

    def reset_product_transform(self):
        self._is_switching = True
        self.sl_img_x.setValue(0); self.sl_img_y.setValue(0); self.sl_img_sc.setValue(100)
        self._is_switching = False
        self._on_transform_change()
        self.request_cover_preview()

    def _on_price_change(self):
        if self._is_switching: return
        t = self.get_cover_targets()
        if not t: return
        path = t[self.current_cover_preview_idx % len(t)]
        vals = {"new": self.e_pr_new.text(), "old": self.e_pr_old.text()}
        if self.cb_individual_price.isChecked():
            self.individual_prices[path] = vals
        else:
            self.global_price = vals
        self.request_cover_preview()

    def on_individual_price_toggle(self):
        t = self.get_cover_targets()
        if not t: return
        path = t[self.current_cover_preview_idx % len(t)]
        if self.cb_individual_price.isChecked():
            self.individual_prices[path] = {"new": self.e_pr_new.text(), "old": self.e_pr_old.text()}
        else:
            if path in self.individual_prices: del self.individual_prices[path]
            self._is_switching = True
            self.e_pr_new.setText(self.global_price.get("new", ""))
            self.e_pr_old.setText(self.global_price.get("old", ""))
            self._is_switching = False
        self.request_cover_preview()

    def switch_cover_preview(self, delta):
        t = self.get_cover_targets()
        if not t: return
        self.current_cover_preview_idx = (self.current_cover_preview_idx + delta) % len(t)
        path = t[self.current_cover_preview_idx]
        
        self._is_switching = True
        
        if path in self.individual_transforms:
            self.cb_individual.setChecked(True)
            v = self.individual_transforms[path]
            self.sl_img_sc.setValue(v["scale"]); self.sl_img_x.setValue(v["x"]); self.sl_img_y.setValue(v["y"])
        else:
            self.cb_individual.setChecked(False)
            self.sl_img_sc.setValue(self.global_transform["scale"]); self.sl_img_x.setValue(self.global_transform["x"]); self.sl_img_y.setValue(self.global_transform["y"])
            
        if path in self.individual_prices:
            self.cb_individual_price.setChecked(True)
            self.e_pr_new.setText(self.individual_prices[path].get("new", ""))
            self.e_pr_old.setText(self.individual_prices[path].get("old", ""))
        else:
            self.cb_individual_price.setChecked(False)
            self.e_pr_new.setText(self.global_price.get("new", ""))
            self.e_pr_old.setText(self.global_price.get("old", ""))
            
        self._is_switching = False
        self.render_cover_preview()

    def request_cover_preview(self):
        self._preview_timer.start(150)

    def get_cover_targets(self):
        if not self.files: return []
        m = self.cb_target_mode.currentText()
        if m == "Только 1-е фото": return [self.files[0]]
        if m == "Ко всем": return self.files
        try:
            indices = [int(x.strip()) - 1 for x in self.entry_target_indices.text().split(",") if x.strip().isdigit()]
            return [self.files[i] for i in indices if 0 <= i < len(self.files)]
        except Exception: return []

    def get_cover_state(self):
        return {
            "active": self.cb_active_cover.isChecked(),
            "only_cover": self.cb_only_cover.isChecked(),
            "target_mode": self.cb_target_mode.currentText(),
            "target_indices": self.entry_target_indices.text(),
            "banners_list": self.banners_list,
            "active_banner": self.active_banner,
            "individual_price_active": self.cb_individual_price.isChecked(),
            "banner_scale": self.sl_ban_sc.value(), "banner_x": self.sl_ban_x.value(), "banner_y": self.sl_ban_y.value(),
            "top_logo": self.lbl_logo_name.text(),
            "logo_scale": self.sl_logo_sc.value(), "logo_x": self.sl_logo_x.value(), "logo_y": self.sl_logo_y.value(),
            "show_markdown": self.cb_md_active.isChecked(),
            "markdown_logo": self.lbl_md_name.text(),
            "md_logo_scale": self.sl_md_sc.value(), "md_logo_x": self.sl_md_x.value(), "md_logo_y": self.sl_md_y.value(),
            "price_font": self.lbl_font_name.text(),
            "price_scale": self.sl_pr_sc.value(),
            "price_new_x": self.sl_pr_nx.value(), "price_new_y": self.sl_pr_ny.value(),
            "price_old_x": self.sl_pr_ox.value(), "price_old_y": self.sl_pr_oy.value(),
            "strike_width": self.sl_str_w.value()
        }

    def load_cover_state(self, d):
        self._is_switching = True
        self.cb_active_cover.setChecked(d.get("active", False))
        self.cb_only_cover.setChecked(d.get("only_cover", False))
        self.cb_target_mode.setCurrentText(d.get("target_mode", "Только 1-е фото"))
        self.entry_target_indices.setText(d.get("target_indices", "1"))
        self.banners_list = d.get("banners_list", [])
        self.active_banner = d.get("active_banner", "")
        self.sl_ban_sc.setValue(d.get("banner_scale", 100)); self.sl_ban_x.setValue(d.get("banner_x", 0)); self.sl_ban_y.setValue(d.get("banner_y", 0))
        self.lbl_logo_name.setText(d.get("top_logo", ""))
        self.sl_logo_sc.setValue(d.get("logo_scale", 100)); self.sl_logo_x.setValue(d.get("logo_x", 0)); self.sl_logo_y.setValue(d.get("logo_y", 0))
        self.cb_md_active.setChecked(d.get("show_markdown", False))
        self.lbl_md_name.setText(d.get("markdown_logo", ""))
        self.sl_md_sc.setValue(d.get("md_logo_scale", 100)); self.sl_md_x.setValue(d.get("md_logo_x", 0)); self.sl_md_y.setValue(d.get("md_logo_y", 0))
        self.lbl_font_name.setText(d.get("price_font", ""))
        self.sl_pr_sc.setValue(d.get("price_scale", 100))
        self.sl_pr_nx.setValue(d.get("price_new_x", 0)); self.sl_pr_ny.setValue(d.get("price_new_y", 0))
        self.sl_pr_ox.setValue(d.get("price_old_x", 0)); self.sl_pr_oy.setValue(d.get("price_old_y", 0))
        self.e_pr_new.setText(self.global_price.get("new", "9990"))
        self.e_pr_old.setText(self.global_price.get("old", "14990"))
        self.sl_str_w.setValue(d.get("strike_width", 5))
        self.sl_img_sc.setValue(self.global_transform["scale"])
        self.sl_img_x.setValue(self.global_transform["x"])
        self.sl_img_y.setValue(self.global_transform["y"])
        self._is_switching = False

    def build_wm_tab(self):
        l = QHBoxLayout(self.tab_wm)
        
        left = QScrollArea()
        left.setFixedWidth(320)
        left.setWidgetResizable(True)
        left.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_w = QWidget()
        self.wm_layout = QVBoxLayout(left_w)
        self.wm_layout.setAlignment(Qt.AlignTop)
        
        top_wm_btns = QHBoxLayout()
        btn_add_wm = QPushButton("Добавить картинку")
        btn_add_text_wm = QPushButton("Добавить текст")
        btn_add_wm.clicked.connect(self.add_wm)
        btn_add_text_wm.clicked.connect(self.add_text_wm)
        top_wm_btns.addWidget(btn_add_wm)
        top_wm_btns.addWidget(btn_add_text_wm)
        self.wm_layout.addLayout(top_wm_btns)
        
        left.setWidget(left_w)
        l.addWidget(left)

        mid = QWidget()
        mid.setFixedWidth(300)
        ml = QVBoxLayout(mid)
        ml.setAlignment(Qt.AlignTop)
        self.lbl_wm_title = QLabel("Выберите ВЗ из списка")
        self.lbl_wm_title.setObjectName("Title")
        ml.addWidget(self.lbl_wm_title)

        settings_frame = QFrame()
        settings_frame.setObjectName("Card")
        s_l = QVBoxLayout(settings_frame)
        s_l.setAlignment(Qt.AlignTop)
        
        self.e_wm_text = QLineEdit()
        self.e_wm_text.setPlaceholderText("Введите текст ВЗ")
        self.e_wm_text.textChanged.connect(self.save_wm_settings)
        s_l.addWidget(self.e_wm_text)
        
        self.cb_wm_color = QComboBox()
        self.cb_wm_color.addItems(["Белый", "Черный"])
        self.cb_wm_color.currentTextChanged.connect(lambda _: self.save_wm_settings())
        s_l.addWidget(self.cb_wm_color)
        
        self.cb_wm_grid = QCheckBox("Защитная сетка (замостить)")
        self.cb_wm_grid.toggled.connect(lambda c: self.save_wm_settings())
        s_l.addWidget(self.cb_wm_grid)
        
        self.sl_wm_op, self.e_wm_op = self.create_slider_row(s_l, "Прозрачность %:", 0, 100, command=self.save_wm_settings)
        self.sl_wm_sc, self.e_wm_sc = self.create_slider_row(s_l, "Размер %:", 1, 300, command=self.save_wm_settings)
        self.sl_wm_dx, self.e_wm_dx = self.create_slider_row(s_l, "Сдвиг X:", -1000, 1000, command=self.save_wm_settings)
        self.sl_wm_dy, self.e_wm_dy = self.create_slider_row(s_l, "Сдвиг Y:", -1000, 1000, command=self.save_wm_settings)

        pos_lbl = QLabel("Позиция (игнорируется сеткой):")
        pos_lbl.setStyleSheet("margin-top: 10px; font-weight: bold;")
        s_l.addWidget(pos_lbl)
        
        pos_grid_w = QWidget()
        pos_grid = QGridLayout(pos_grid_w)
        pos_grid.setContentsMargins(10,10,10,10)
        pos_grid.setSpacing(15)
        pos_grid.setAlignment(Qt.AlignCenter)
        
        self.wm_pos_group = QButtonGroup(self)
        self.wm_pos_group.setExclusive(True)
        
        vals = ["tl", "tc", "tr", "ml", "mc", "mr", "bl", "bc", "br"]
        
        for i, val in enumerate(vals):
            rb = QRadioButton()
            rb.setProperty("pos_val", val)
            rb.toggled.connect(lambda c, b=rb: self.save_wm_settings() if c else None)
            self.wm_pos_group.addButton(rb)
            
            btn_lbl = QLabel()
            btn_lbl.setAlignment(Qt.AlignCenter)
            self.wm_pos_icons[val] = btn_lbl
            
            box = QVBoxLayout()
            box.addWidget(btn_lbl)
            box.addWidget(rb)
            box.setAlignment(Qt.AlignCenter)
            
            w = QWidget()
            w.setLayout(box)
            pos_grid.addWidget(w, i // 3, i % 3)
            
        s_l.addWidget(pos_grid_w)
        ml.addWidget(settings_frame)
        ml.addStretch()
        l.addWidget(mid)

        right = QWidget()
        rl = QVBoxLayout(right)
        nav = QHBoxLayout()
        btn_prev = QPushButton("<")
        btn_next = QPushButton(">")
        btn_prev.setFixedWidth(40)
        btn_next.setFixedWidth(40)
        btn_prev.clicked.connect(lambda: self.switch_wm_preview(-1))
        btn_next.clicked.connect(lambda: self.switch_wm_preview(1))
        self.lbl_wm_prev_title = QLabel("Превью ВЗ:")
        self.lbl_wm_prev_title.setObjectName("Title")
        
        nav.addWidget(btn_prev)
        nav.addWidget(self.lbl_wm_prev_title)
        nav.addWidget(btn_next)
        nav.addStretch()
        rl.addLayout(nav)

        self.wm_preview_lbl = QLabel("Загрузите фото во вкладке 'Файлы'")
        self.wm_preview_lbl.setAlignment(Qt.AlignCenter)
        self.wm_preview_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        rl.addWidget(self.wm_preview_lbl, 1)

        l.addWidget(right, 1)
        self.disable_wm_settings()

    def switch_wm_preview(self, delta):
        if not self.files: return
        self.current_wm_preview_idx = (self.current_wm_preview_idx + delta) % len(self.files)
        self.render_wm_preview()

    def render_wm_preview(self):
        if not self.files:
            self.wm_preview_lbl.setPixmap(QPixmap())
            self.wm_preview_lbl.setText("Нет фото")
            return
        idx = self.current_wm_preview_idx % len(self.files)
        self.lbl_wm_prev_title.setText(f"Превью (Фото {idx+1} из {len(self.files)}):")
        
        img = self.build_final_image(self.files[idx], "regular")
        if img:
            img.thumbnail((800, 600), Image.Resampling.LANCZOS)
            self.wm_preview_lbl.setPixmap(pil_to_pixmap(img))
        else: self.wm_preview_lbl.setText("Ошибка рендера")

    def add_text_wm(self):
        text, ok = QInputDialog.getText(self, "Текст ВЗ", "Введите текст для водяного знака:")
        if ok and text:
            name = f"Текст: {text[:10]}"
            base_name = name
            count = 1
            while name in self.watermarks_config:
                name = f"{base_name} ({count})"
                count += 1
            self.watermarks_config[name] = {
                "active": True, "type": "text", "text": text, "color": "Черный",
                "opacity": 50, "scale": 15, "pos": "c", "dx": 0, "dy": 0, "grid": False
            }
            self.save_wm_config()
            self.edit_wm(name)

    def add_wm(self):
        paths = native_askopenfilenames(title="Выберите ВЗ")
        if not paths: return
        last_f = None
        for p in paths:
            f = os.path.basename(p)
            try: shutil.copy(p, os.path.join(ASSETS_DIR, f))
            except Exception as e: logging.error(f"Copy watermark error: {e}")
            self.watermarks_config[f] = {"active": True, "type": "image", "opacity": 50, "scale": 45, "pos": "bl", "dx": 20, "dy": -20, "grid": False}
            last_f = f
        self.save_wm_config()
        if last_f:
            self.edit_wm(last_f)
        else:
            self.refresh_wm_list()

    def refresh_wm_list(self):
        while self.wm_layout.count() > 1:
            w = self.wm_layout.takeAt(1).widget()
            if w: w.deleteLater()
            
        for f, cfg in self.watermarks_config.items():
            row = QFrame()
            if self.current_wm_edit == f:
                row.setObjectName("ActiveCard")
            else:
                row.setObjectName("Card")
            
            l = QHBoxLayout(row)
            
            cb = QCheckBox()
            cb.blockSignals(True)
            cb.setChecked(cfg.get("active", False))
            cb.blockSignals(False)
            cb.toggled.connect(lambda c, name=f: self.toggle_wm_active(name, c))
            
            lbl = QLabel(f if len(f)<15 else f[:12]+"...")
            lbl.setStyleSheet("font-weight: bold; background: transparent;")
            
            btn_edit = QPushButton("Настроить")
            btn_edit.setFixedWidth(110)
            if self.current_wm_edit == f:
                btn_edit.setStyleSheet(f"background-color: {THEMES[self.current_theme]['ACCENT']}; color: {THEMES[self.current_theme]['BG']};")
            else:
                btn_edit.setObjectName("Secondary")
            btn_edit.clicked.connect(lambda _, name=f: self.edit_wm(name))
            
            btn_del = QPushButton("X")
            btn_del.setObjectName("Danger")
            btn_del.setFixedWidth(35)
            btn_del.clicked.connect(lambda _, name=f: self.delete_wm(name))
            
            l.addWidget(cb); l.addWidget(lbl); l.addStretch(); l.addWidget(btn_edit); l.addWidget(btn_del)
            self.wm_layout.addWidget(row)

    def toggle_wm_active(self, name, checked):
        self.watermarks_config[name]["active"] = checked
        self.save_wm_config()
        if checked:
            self.edit_wm(name)
        else:
            if self.current_wm_edit == name:
                self.disable_wm_settings()
        self.render_out_preview()
        self.render_wm_preview()

    def delete_wm(self, name):
        if self.watermarks_config[name].get("type") != "text":
            try: os.remove(get_asset_path(name))
            except Exception as e: logging.error(f"Error removing watermark: {e}")
        del self.watermarks_config[name]
        if self.current_wm_edit == name: 
            self.disable_wm_settings()
        self.save_wm_config()
        self.refresh_wm_list()
        self.render_out_preview()
        self.render_wm_preview()

    def edit_wm(self, name):
        self.current_wm_edit = name
        c = self.watermarks_config[name]
        self.lbl_wm_title.setText(f"Настройка: {name}")
        
        self._is_switching = True
        
        is_text = c.get("type") == "text"
        self.e_wm_text.setVisible(is_text)
        self.cb_wm_color.setVisible(is_text)
        if is_text:
            self.e_wm_text.setText(c.get("text", ""))
            self.cb_wm_color.setCurrentText(c.get("color", "Черный"))
            
        self.cb_wm_grid.setChecked(c.get("grid", False))
        
        self.sl_wm_op.setValue(int(c.get("opacity", 50)))
        self.sl_wm_sc.setValue(int(c.get("scale", 45)))
        self.sl_wm_dx.setValue(int(c.get("dx", 20)))
        self.sl_wm_dy.setValue(int(c.get("dy", -20)))
        pos = c.get("pos", "bl")
        for b in self.wm_pos_group.buttons():
            if b.property("pos_val") == pos:
                b.setChecked(True)
                break
        self._is_switching = False
        
        self.e_wm_text.setEnabled(True); self.cb_wm_color.setEnabled(True); self.cb_wm_grid.setEnabled(True)
        self.sl_wm_op.setEnabled(True); self.e_wm_op.setEnabled(True)
        self.sl_wm_sc.setEnabled(True); self.e_wm_sc.setEnabled(True)
        self.sl_wm_dx.setEnabled(True); self.e_wm_dx.setEnabled(True)
        self.sl_wm_dy.setEnabled(True); self.e_wm_dy.setEnabled(True)
        for b in self.wm_pos_group.buttons(): b.setEnabled(True)
        
        self.refresh_wm_list()
        self.render_wm_preview()

    def save_wm_settings(self, *_):
        if not self.current_wm_edit or self._is_switching: return
        pos = "bl"
        checked_btn = self.wm_pos_group.checkedButton()
        if checked_btn: pos = checked_btn.property("pos_val")
            
        def s_int(v, d=0):
            try: return int(v)
            except ValueError: return d
            
        c = self.watermarks_config[self.current_wm_edit]
        updates = {
            "opacity": max(0, min(100, s_int(self.e_wm_op.text(), 50))),
            "scale": max(1, min(100, s_int(self.e_wm_sc.text(), 45))),
            "pos": pos,
            "dx": s_int(self.e_wm_dx.text(), 0),
            "dy": s_int(self.e_wm_dy.text(), 0),
            "grid": self.cb_wm_grid.isChecked()
        }
        if c.get("type") == "text":
            updates["text"] = self.e_wm_text.text()
            updates["color"] = self.cb_wm_color.currentText()
            
        self.watermarks_config[self.current_wm_edit].update(updates)
        self.save_wm_config()
        self.render_out_preview()
        self.render_wm_preview()

    def disable_wm_settings(self):
        self.current_wm_edit = None
        self.lbl_wm_title.setText("Выберите ВЗ из списка")
        
        self._is_switching = True
        self.e_wm_text.setText(""); self.cb_wm_grid.setChecked(False)
        self.sl_wm_op.setValue(0); self.e_wm_op.setText("")
        self.sl_wm_sc.setValue(0); self.e_wm_sc.setText("")
        self.sl_wm_dx.setValue(0); self.e_wm_dx.setText("")
        self.sl_wm_dy.setValue(0); self.e_wm_dy.setText("")
        self._is_switching = False
        
        self.e_wm_text.setEnabled(False); self.cb_wm_color.setEnabled(False); self.cb_wm_grid.setEnabled(False)
        self.sl_wm_op.setEnabled(False); self.e_wm_op.setEnabled(False)
        self.sl_wm_sc.setEnabled(False); self.e_wm_sc.setEnabled(False)
        self.sl_wm_dx.setEnabled(False); self.e_wm_dx.setEnabled(False)
        self.sl_wm_dy.setEnabled(False); self.e_wm_dy.setEnabled(False)
        for b in self.wm_pos_group.buttons(): b.setEnabled(False)
        
        self.refresh_wm_list()

    def build_out_tab(self):
        l = QVBoxLayout(self.tab_out)
        
        top = QHBoxLayout()
        top.addWidget(QLabel("Превью:"))
        self.cb_out_files = QComboBox()
        self.cb_out_files.setMinimumWidth(300)
        self.cb_out_files.currentTextChanged.connect(lambda _: self.render_out_preview())
        btn_upd = QPushButton("Обновить")
        btn_upd.clicked.connect(self.render_out_preview)
        top.addWidget(self.cb_out_files)
        top.addWidget(btn_upd)
        top.addStretch()
        l.addLayout(top)

        self.lbl_out_prev = QLabel("Добавьте файлы во вкладке 'Файлы'")
        self.lbl_out_prev.setAlignment(Qt.AlignCenter)
        self.lbl_out_prev.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        l.addWidget(self.lbl_out_prev, 1)

        bot = QFrame()
        bot.setObjectName("Card")
        bl = QGridLayout(bot)
        
        bl.addWidget(QLabel("Размер:"), 0, 0)
        self.cb_sizes = QComboBox()
        self.cb_sizes.addItems(self.custom_sizes)
        self.cb_sizes.currentTextChanged.connect(lambda _: self.render_out_preview())
        self.e_new_size = QLineEdit()
        self.e_new_size.setPlaceholderText("800x800")
        btn_add_sz = QPushButton("+")
        btn_del_sz = QPushButton("X")
        btn_del_sz.setObjectName("Danger")
        btn_add_sz.clicked.connect(self.add_size)
        btn_del_sz.clicked.connect(self.del_size)
        
        sz_l = QHBoxLayout()
        sz_l.addWidget(self.cb_sizes); sz_l.addWidget(self.e_new_size); sz_l.addWidget(btn_add_sz); sz_l.addWidget(btn_del_sz)
        bl.addLayout(sz_l, 0, 1)

        bl.addWidget(QLabel("Префикс:"), 0, 2)
        self.e_prefix = QLineEdit()
        self.e_prefix.textChanged.connect(self.update_dropdown_files)
        bl.addWidget(self.e_prefix, 0, 3)

        bl.addWidget(QLabel("Ст.:"), 0, 4)
        self.e_start = QLineEdit("1")
        self.e_start.textChanged.connect(self.update_dropdown_files)
        bl.addWidget(self.e_start, 0, 5)

        bl.addWidget(QLabel("Шаг:"), 1, 4)
        self.e_step = QLineEdit("1")
        self.e_step.textChanged.connect(self.update_dropdown_files)
        bl.addWidget(self.e_step, 1, 5)

        bl.addWidget(QLabel("Папка:"), 0, 6)
        self.lbl_out_dir = QLabel("Рядом с оригиналом")
        btn_out_dir = QPushButton("Выбрать")
        btn_out_dir.clicked.connect(self.sel_out_dir)
        bl.addWidget(self.lbl_out_dir, 0, 7)
        bl.addWidget(btn_out_dir, 1, 7)

        l.addWidget(bot)

    def add_size(self):
        s = self.e_new_size.text().strip().lower().replace('*', 'x').replace('х', 'x')
        if 'x' in s and s not in self.custom_sizes:
            try:
                int(s.split('x')[0]); int(s.split('x')[1])
                self.custom_sizes.append(s)
                self.cb_sizes.clear(); self.cb_sizes.addItems(self.custom_sizes)
                self.cb_sizes.setCurrentText(s)
                self.e_new_size.clear()
                self.save_general_config()
            except Exception: pass

    def del_size(self):
        s = self.cb_sizes.currentText()
        if s in self.custom_sizes and len(self.custom_sizes) > 1:
            self.custom_sizes.remove(s)
            self.cb_sizes.clear(); self.cb_sizes.addItems(self.custom_sizes)
            self.save_general_config()

    def sel_out_dir(self):
        d = native_askdirectory(title="Выберите папку для сохранения")
        if d: self.lbl_out_dir.setText(d)

    def update_dropdown_files(self):
        if not self.files:
            self.cb_out_files.clear()
            self.lbl_out_prev.setPixmap(QPixmap())
            return
        
        prefix = self.e_prefix.text().strip()
        try: st = int(self.e_start.text())
        except ValueError: st = 1
        try: step = int(self.e_step.text())
        except ValueError: step = 1

        curr = self.cb_out_files.currentText()
        self.cb_out_files.blockSignals(True)
        self.cb_out_files.clear()
        names = []
        for i, f in enumerate(self.files):
            orig = os.path.splitext(os.path.basename(f))[0]
            n = f"{i+1}. {prefix}{st}.jpg" if prefix else f"{i+1}. {orig}_res.jpg"
            names.append(n)
            st += step
        self.cb_out_files.addItems(names)
        if curr in names: 
            self.cb_out_files.setCurrentText(curr)
        elif names: 
            self.cb_out_files.setCurrentIndex(0) 
            
        self.cb_out_files.blockSignals(False)
        self.render_out_preview()

    def get_price_font(self, size, font_name=""):
        if font_name:
            p = get_asset_path(font_name)
            if os.path.exists(p):
                try: return ImageFont.truetype(p, size)
                except Exception as e: logging.warning(f"Error loading user font {font_name}: {e}")
        
        default_font_path = os.path.join(ASSETS_DIR, "default.ttf")
        if os.path.exists(default_font_path):
            try: return ImageFont.truetype(default_font_path, size)
            except Exception as e: logging.warning(f"Error loading bundle font default.ttf: {e}")

        system_fonts = ["arialbd.ttf", "segoeuib.ttf", "Ubuntu-B.ttf", "SanFrancisco.ttf"]
        for sys_f in system_fonts:
            try: return ImageFont.truetype(sys_f, size)
            except Exception: continue
            
        return ImageFont.load_default()

    def build_final_image(self, path, mode="regular", pre_state=None, target_size_text=None):
        state = pre_state if pre_state else self.get_cover_state()
        
        if mode == "cover": 
            t_size = (1200, 900)
        else: 
            sz_txt = target_size_text if target_size_text else self.cb_sizes.currentText()
            t_size = tuple(map(int, sz_txt.split('x')))
        
        canvas = Image.new("RGBA", t_size, (255, 255, 255, 255))
        
        try:
            with Image.open(path) as img:
                orig = img.convert("RGBA")
                if path in self.crop_data:
                    c = self.crop_data[path]
                    orig = orig.crop((max(0, c[0]), max(0, c[1]), min(img.width, c[2]), min(img.height, c[3])))
                
                if mode == "cover":
                    tr = self.individual_transforms.get(path, self.global_transform)
                    sc, dx, dy = tr["scale"]/100.0, tr["x"], tr["y"]
                    
                    ban = None
                    if state["active_banner"]:
                        bp = get_asset_path(state["active_banner"])
                        if os.path.exists(bp): ban = Image.open(bp).convert("RGBA")
                    
                    bw_off = 0
                    if ban:
                        bw = int(ban.width * (t_size[1] / ban.height))
                        bw_off = min(max(0, state["banner_x"] + int(bw * state["banner_scale"]/100.0)), t_size[0]-10)
                    
                    aw = t_size[0] - bw_off
                    if aw > 10:
                        ratio = min(aw / orig.width, t_size[1] / orig.height)
                        nw, nh = max(1, int(orig.width * ratio * sc)), max(1, int(orig.height * ratio * sc))
                        res = orig.resize((nw, nh), Image.Resampling.LANCZOS)
                        px = bw_off + (aw - nw)//2 + dx
                        py = (t_size[1] - nh)//2 + dy
                        canvas.paste(res, (px, py), res)
                        
                    if ban:
                        bw = int(ban.width * (t_size[1] / ban.height))
                        nw, nh = max(1, int(bw * state["banner_scale"]/100.0)), max(1, int(t_size[1] * state["banner_scale"]/100.0))
                        ban_res = ban.resize((nw, nh), Image.Resampling.LANCZOS)
                        canvas.paste(ban_res, (state["banner_x"], state["banner_y"]), ban_res)
                        
                    if state["top_logo"]:
                        lp = get_asset_path(state["top_logo"])
                        if os.path.exists(lp):
                            logo = Image.open(lp).convert("RGBA")
                            bw = int(t_size[0] * 0.35)
                            bh = int(logo.height * (bw / logo.width))
                            lsc = state["logo_scale"]/100.0
                            nw, nh = max(1, int(bw*lsc)), max(1, int(bh*lsc))
                            lres = logo.resize((nw, nh), Image.Resampling.LANCZOS)
                            canvas.paste(lres, (t_size[0] - nw - 20 + state["logo_x"], 20 + state["logo_y"]), lres)

                    if state["show_markdown"]:
                        draw = ImageDraw.Draw(canvas)
                        bp = 40
                        
                        if state["markdown_logo"]:
                            mp = get_asset_path(state["markdown_logo"])
                            if os.path.exists(mp):
                                md = Image.open(mp).convert("RGBA")
                                bh = 150
                                bw = int(md.width * (bh / md.height))
                                msc = state["md_logo_scale"]/100.0
                                nw, nh = max(1, int(bw*msc)), max(1, int(bh*msc))
                                mres = md.resize((nw, nh), Image.Resampling.LANCZOS)
                                md_pos = (t_size[0] - nw - bp + state["md_logo_x"], t_size[1] - nh - bp + state["md_logo_y"])
                                canvas.paste(mres, md_pos, mres)
                        
                        pr_x_anch = t_size[0] - 40
                        pr_y_anch = t_size[1] - 80
                        
                        psc = state["price_scale"]/100.0
                        
                        f_n = self.get_price_font(max(1, int(100*psc)), state.get("price_font", ""))
                        f_o = self.get_price_font(max(1, int(70*psc)), state.get("price_font", ""))
                        c_n, c_o = (220, 53, 69, 255), (108, 117, 125, 255)
                        
                        if state.get("individual_price_active", False) and path in self.individual_prices:
                            price_data = self.individual_prices[path]
                        else:
                            price_data = self.global_price
                            
                        p_new = price_data.get("new", "")
                        p_old = price_data.get("old", "")
                        
                        oh = 0
                        
                        if p_old:
                            ox = pr_x_anch + state["price_old_x"]
                            oy = pr_y_anch + state["price_old_y"]
                            try:
                                draw.text((ox, oy), p_old, font=f_o, fill=c_o, anchor="rs")
                                box = draw.textbbox((ox, oy), p_old, font=f_o, anchor="rs")
                            except Exception:
                                w_o = int(draw.textlength(p_old, font=f_o))
                                draw.text((ox - w_o, oy - 20), p_old, font=f_o, fill=c_o)
                                box = (ox - w_o, oy - 20, ox, oy)
                                
                            ly = (box[1] + box[3]) // 2
                            draw.line([(box[0], ly), (box[2], ly)], fill=c_n, width=max(1, int(state["strike_width"]*psc)))
                            oh = box[3] - box[1] + 10 
                        
                        if p_new:
                            nx = pr_x_anch + state["price_new_x"]
                            ny = pr_y_anch - oh + state["price_new_y"]
                            try:
                                draw.text((nx, ny), p_new, font=f_n, fill=c_n, anchor="rs")
                            except Exception:
                                w_n = int(draw.textlength(p_new, font=f_n))
                                draw.text((nx - w_n, ny - 20), p_new, font=f_n, fill=c_n)

                elif mode == "regular":
                    if self.fill_settings.get(path, False):
                        res = ImageOps.fit(orig, t_size, method=Image.Resampling.LANCZOS)
                    else:
                        res = ImageOps.pad(orig, t_size, method=Image.Resampling.LANCZOS, color=(255, 255, 255, 255))
                    canvas.paste(res, (0,0), res)
                    
                    for wname, cfg in self.watermarks_config.items():
                        if not cfg.get("active", False): continue
                        
                        is_text = cfg.get("type") == "text"
                        grid = cfg.get("grid", False)
                        op = cfg.get("opacity", 50)/100.0
                        wsc = cfg.get("scale", 45)/100.0
                        dim = min(t_size)
                        
                        wm = None
                        
                        if is_text:
                            txt = cfg.get("text", "")
                            if not txt: continue
                            f_size = max(12, int(dim * wsc * 0.4))
                            font = self.get_price_font(f_size)
                            
                            dummy = Image.new("RGBA", (1,1))
                            d = ImageDraw.Draw(dummy)
                            try:
                                bbox = d.textbbox((0,0), txt, font=font)
                                tw = bbox[2] - bbox[0]
                                th = bbox[3] - bbox[1]
                                offset_x = bbox[0]
                                offset_y = bbox[1]
                            except:
                                tw, th = int(d.textlength(txt, font=font)), f_size
                                offset_x = 0
                                offset_y = 0
                                
                            if tw <= 0 or th <= 0: continue
                            
                            pad = 4
                            wm = Image.new("RGBA", (tw + pad*2, th + pad*2), (255, 255, 255, 0))
                            draw = ImageDraw.Draw(wm)
                            col = (0, 0, 0) if cfg.get("color") == "Черный" else (255, 255, 255)
                            draw.text((pad - offset_x, pad - offset_y), txt, font=font, fill=(col[0], col[1], col[2], int(255 * op)))
                        else:
                            wp = get_asset_path(wname)
                            if not os.path.exists(wp): continue
                            orig_wm = Image.open(wp).convert("RGBA")
                            ww = max(1, int(dim * wsc * 0.85))
                            wh = max(1, int(ww * (orig_wm.height/orig_wm.width)))
                            wm = orig_wm.resize((ww, wh), Image.Resampling.LANCZOS)
                            if op < 1.0: 
                                alpha = wm.split()[3]
                                alpha = ImageEnhance.Brightness(alpha).enhance(op)
                                wm.putalpha(alpha)
                                
                        if not wm: continue

                        if grid:
                            wm_rot = wm.rotate(30, expand=True, fillcolor=(0,0,0,0))
                            step_x = wm_rot.width + max(20, int(t_size[0] * 0.05))
                            step_y = wm_rot.height + max(20, int(t_size[1] * 0.05))
                            for y_grid in range(-step_y, t_size[1] + step_y, step_y):
                                offset = step_x // 2 if (y_grid // step_y) % 2 != 0 else 0
                                for x_grid in range(-step_x, t_size[0] + step_x, step_x):
                                    canvas.paste(wm_rot, (x_grid + offset, y_grid), wm_rot)
                        else:
                            pos = cfg.get("pos", "bl")
                            y = 0 if 't' in pos else (t_size[1]-wm.height)//2 if 'm' in pos else t_size[1]-wm.height
                            x = 0 if 'l' in pos else (t_size[0]-wm.width)//2 if 'c' in pos else t_size[0]-wm.width
                            canvas.paste(wm, (x + cfg.get("dx", 0), y + cfg.get("dy", 0)), wm)

            return canvas.convert("RGB")
        except Exception as e: 
            logging.error(f"Failed to build image {path}: {e}", exc_info=True)
            return None
    
    def render_cover_preview(self):
        t = self.get_cover_targets()
        if not t:
            if hasattr(self, 'cov_preview_lbl'):
                self.cov_preview_lbl.setPixmap(QPixmap())
                self.cov_preview_lbl.setText("Нет фото")
            return
        idx = self.current_cover_preview_idx % len(t)
        self.lbl_cov_title.setText(f"Превью (Фото {idx+1} из {len(t)}):")
        img = self.build_final_image(t[idx], "cover")
        if img:
            img.thumbnail((800, 600), Image.Resampling.LANCZOS)
            self.cov_preview_lbl.setPixmap(pil_to_pixmap(img))
        else: self.cov_preview_lbl.setText("Ошибка рендера")

    def render_out_preview(self):
        if self.cb_out_files.currentIndex() < 0 or not self.files:
            self.lbl_out_prev.setPixmap(QPixmap())
            self.lbl_out_prev.setText("Нет фото")
            return
        idx = self.cb_out_files.currentIndex() % len(self.files)
        img = self.build_final_image(self.files[idx], "regular")
        if img:
            img.thumbnail((800, 600), Image.Resampling.LANCZOS)
            self.lbl_out_prev.setPixmap(pil_to_pixmap(img))
        else: self.lbl_out_prev.setText("Ошибка рендера")

    def process_images(self):
        if not self.files: 
            CustomMsgBox(self, "Пусто", "Добавьте фото для обработки").exec()
            return
        
        st = self.get_cover_state()
        use_c = self.lbl_out_dir.text() != "Рядом с оригиналом"
        has_wm = any(c.get("active", False) for c in self.watermarks_config.values())
        pref = self.e_prefix.text().strip()
        try: count = int(self.e_start.text())
        except ValueError: count = 1
        try: step = int(self.e_step.text())
        except ValueError: step = 1
        
        targets = self.get_cover_targets()
        out_dir = self.lbl_out_dir.text()
        target_sz = self.cb_sizes.currentText()

        self.btn_process.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.files))
        self.progress_bar.setValue(0)

        self.worker = ProcessWorker(self, self.files, st, use_c, has_wm, pref, count, step, targets, out_dir, target_sz)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.process_finished)
        self.worker.start()

    def update_progress(self, curr, total):
        self.progress_bar.setValue(curr)

    def process_finished(self, succ, next_count):
        self.e_start.setText(str(next_count))
        self.btn_process.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        final_dir = self.lbl_out_dir.text()
        if final_dir == "Рядом с оригиналом" and self.files:
            final_dir = os.path.join(os.path.dirname(self.files[0]), "Обработанные")
            
        SuccessBox(self, "Готово", f"Обработка завершена!\nУспешно создано файлов: {succ}", final_dir).exec()

    def on_tab_change(self, idx):
        if idx == 1: self.request_cover_preview()
        elif idx == 2: self.render_wm_preview()
        elif idx == 3: self.render_out_preview()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())