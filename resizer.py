import os
import sys
import json
import shutil
import subprocess
import io
import logging
import traceback
import datetime
import concurrent.futures
import copy
from PIL import Image, ImageOps, ImageEnhance, ImageDraw
from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QThread, QMimeData, QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QPixmap, QColor, QPainter, QPen, QAction, QDrag, QCursor, QFont, QFontMetrics, QImage, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QCheckBox, QSlider, QLineEdit, QComboBox, 
    QScrollArea, QFrame, QTabWidget, QFileDialog, QMessageBox, 
    QDialog, QGridLayout, QSizePolicy, QSizeGrip, QRadioButton, QButtonGroup,
    QProgressBar, QInputDialog, QListWidget, QColorDialog
)

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

ASSETS_DIR = os.path.join(APP_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True) 

def global_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logs_dir = os.path.join(APP_DIR, "error_logs")
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(logs_dir, f"error_{timestamp}.txt")
    with open(log_file, "w", encoding="utf-8") as f:
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
sys.excepthook = global_exception_handler

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
    primary_enc = c['PRIMARY'].replace('#', '%23')
    
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
    QPushButton#Secondary {{ background-color: {c['FRAME']}; color: {c['TEXT']}; border: 1px solid {c['PRIMARY']}; }}
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
    QListWidget {{ background-color: {c['FRAME']}; border: 1px solid {c['PRIMARY']}; border-radius: 6px; padding: 4px; }}
    QListWidget::item {{ padding: 6px; border-radius: 4px; outline: none; }}
    QListWidget::item:hover {{ background-color: {c['FRAME_HOVER']}; }}
    QListWidget::item:selected {{ background-color: {c['PRIMARY']}; color: white; }}
    QSizeGrip {{ width: 16px; height: 16px; background: transparent; image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16'%3E%3Cpath d='M16 0v16H0L16 0z' fill='{primary_enc}' opacity='0.7'/%3E%3C/svg%3E"); }}
    """

def get_asset_path(filename):
    if not filename: return ""
    direct_path = os.path.join(ASSETS_DIR, filename)
    if os.path.exists(direct_path): return direct_path
    target = filename.lower()
    try:
        for f in os.listdir(ASSETS_DIR):
            if f.lower() == target: return os.path.join(ASSETS_DIR, f)
    except Exception: pass
    return direct_path

def render_text_to_image(text, font_str, size, color, letter_spacing=0):
    if not text: return Image.new("RGBA", (1, 1), (0,0,0,0))
    font = QFont()
    if font_str: font.fromString(font_str)
    else: font.setFamily("Arial")
    
    font.setPixelSize(size)
    font.setLetterSpacing(QFont.AbsoluteSpacing, letter_spacing)
    
    fm = QFontMetrics(font)
    rect = fm.boundingRect(text)
    pad = int(size * 0.5) + max(10, abs(letter_spacing))
    w = rect.width() + pad*2
    h = rect.height() + pad*2
    
    if w <= 0 or h <= 0: return Image.new("RGBA", (1, 1), (0,0,0,0))
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    
    painter = QPainter(img)
    painter.setFont(font)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    c = QColor(color[0], color[1], color[2], color[3] if len(color)>3 else 255)
    painter.setPen(c)
    painter.drawText(pad, fm.ascent() + pad, text)
    painter.end()
    
    buffer = QByteArray()
    qbuf = QBuffer(buffer)
    qbuf.open(QIODevice.WriteOnly)
    img.save(qbuf, "PNG")
    pil_img = Image.open(io.BytesIO(buffer.data())).convert("RGBA")
    bbox = pil_img.getbbox()
    if bbox: pil_img = pil_img.crop(bbox)
    return pil_img

def pil_to_pixmap(pil_img):
    try:
        byte_io = io.BytesIO()
        pil_img.save(byte_io, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(byte_io.getvalue())
        return pixmap
    except Exception: return QPixmap()

def native_askopenfilenames(title="Выберите файлы"):
    paths, _ = QFileDialog.getOpenFileNames(None, title, "", "Images (*.png *.jpg *.jpeg *.webp)")
    return paths if paths else []

def native_askopenfilename(title="Выберите файл"):
    path, _ = QFileDialog.getOpenFileName(None, title, "", "All Files (*.*)")
    return path if path else ""

def native_askdirectory(title="Выберите папку"):
    path = QFileDialog.getExistingDirectory(None, title)
    return path if path else ""

def create_arrow_pixmap(val, color_str):
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    pen = QPen(QColor(color_str), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    painter.setRenderHint(QPainter.Antialiasing)
    if val == "tl": painter.drawLine(6, 6, 18, 18); painter.drawLine(6, 6, 12, 6); painter.drawLine(6, 6, 6, 12)
    elif val == "tc": painter.drawLine(12, 6, 12, 18); painter.drawLine(12, 6, 8, 10); painter.drawLine(12, 6, 16, 10)
    elif val == "tr": painter.drawLine(18, 6, 6, 18); painter.drawLine(18, 6, 12, 6); painter.drawLine(18, 6, 18, 12)
    elif val == "ml": painter.drawLine(6, 12, 18, 12); painter.drawLine(6, 12, 10, 8); painter.drawLine(6, 12, 10, 16)
    elif val == "mc": painter.setBrush(QColor(color_str)); painter.drawEllipse(8, 8, 8, 8)
    elif val == "mr": painter.drawLine(18, 12, 6, 12); painter.drawLine(18, 12, 14, 8); painter.drawLine(18, 12, 14, 16)
    elif val == "bl": painter.drawLine(6, 18, 18, 6); painter.drawLine(6, 18, 12, 18); painter.drawLine(6, 18, 6, 14)
    elif val == "bc": painter.drawLine(12, 18, 12, 6); painter.drawLine(12, 18, 8, 14); painter.drawLine(12, 18, 16, 14)
    elif val == "br": painter.drawLine(18, 18, 6, 6); painter.drawLine(18, 18, 12, 18); painter.drawLine(18, 18, 18, 14)
    painter.end()
    return pixmap

class DraggableDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._is_tracking = False
        self._start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_tracking = True
            self._start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if getattr(self, '_is_tracking', False):
            self.move(event.globalPosition().toPoint() - self._start_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_tracking = False

class FramelessColorDialog(DraggableDialog):
    def __init__(self, current_color_hex, parent=None):
        super().__init__(parent)
        self.resize(600, 500)
        main_frame = QFrame(self)
        main_frame.setObjectName("DialogCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(main_frame)
        flayout = QVBoxLayout(main_frame)
        flayout.setContentsMargins(0,0,0,0)
        lbl = QLabel("Выбор цвета")
        lbl.setObjectName("Title")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("margin-top: 15px; margin-bottom: 10px;")
        flayout.addWidget(lbl)
        self.color_widget = QColorDialog(QColor(current_color_hex), self)
        self.color_widget.setWindowFlags(Qt.Widget)
        self.color_widget.setOptions(QColorDialog.DontUseNativeDialog | QColorDialog.NoButtons)
        flayout.addWidget(self.color_widget)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(20, 10, 20, 20)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.setObjectName("Secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Выбрать")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        flayout.addLayout(btn_layout)
        
    def get_color_hex(self):
        return self.color_widget.currentColor().name()

class CustomFontDialog(DraggableDialog):
    def __init__(self, current_font_str, parent=None):
        super().__init__(parent)
        self.resize(550, 450)
        self.db = QFontDatabase()
        self.selected_font = QFont()
        if current_font_str: self.selected_font.fromString(current_font_str)
        else: self.selected_font.setFamily("Arial")
        main_frame = QFrame(self)
        main_frame.setObjectName("DialogCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(main_frame)
        flayout = QVBoxLayout(main_frame)
        flayout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("Выбор шрифта")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        flayout.addWidget(title)
        lists_layout = QHBoxLayout()
        fam_layout = QVBoxLayout()
        fam_layout.addWidget(QLabel("Семейство:"))
        self.family_list = QListWidget()
        self.family_list.addItems(self.db.families())
        fam_layout.addWidget(self.family_list)
        lists_layout.addLayout(fam_layout, 2)
        style_layout = QVBoxLayout()
        style_layout.addWidget(QLabel("Начертание:"))
        self.style_list = QListWidget()
        style_layout.addWidget(self.style_list)
        lists_layout.addLayout(style_layout, 1)
        flayout.addLayout(lists_layout)
        self.preview_lbl = QLabel("AaBbYyZz 1234567890\nАаБбВвГгДд 123")
        self.preview_lbl.setAlignment(Qt.AlignCenter)
        self.preview_lbl.setMinimumHeight(100)
        self.preview_lbl.setObjectName("Card")
        flayout.addWidget(self.preview_lbl)
        self.family_list.currentTextChanged.connect(self.update_styles)
        self.style_list.currentTextChanged.connect(self.update_preview)
        items = self.family_list.findItems(self.selected_font.family(), Qt.MatchExactly)
        if items:
            self.family_list.setCurrentItem(items[0])
            self.family_list.scrollToItem(items[0])
        self.update_styles(self.selected_font.family())
        style_str = self.db.styleString(self.selected_font)
        s_items = self.style_list.findItems(style_str, Qt.MatchExactly)
        if s_items: self.style_list.setCurrentItem(s_items[0])
        self.update_preview()
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Отмена")
        btn_cancel.setObjectName("Secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Применить")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        flayout.addLayout(btn_layout)
        
    def update_styles(self, family):
        self.style_list.clear()
        styles = self.db.styles(family)
        if not styles: styles = ["Regular"]
        self.style_list.addItems(styles)
        if styles: self.style_list.setCurrentRow(0)
            
    def update_preview(self):
        fam = self.family_list.currentItem().text() if self.family_list.currentItem() else "Arial"
        style = self.style_list.currentItem().text() if self.style_list.currentItem() else "Regular"
        self.selected_font = self.db.font(fam, style, 24)
        self.preview_lbl.setFont(self.selected_font)
        
    def get_font_str(self):
        return self.selected_font.toString()
        
    def get_display_name(self):
        fam = self.family_list.currentItem().text() if self.family_list.currentItem() else ""
        style = self.style_list.currentItem().text() if self.style_list.currentItem() else ""
        res = f"{fam} ({style})"
        return res if len(res) <= 18 else res[:15] + "..."

class InteractivePreview(QLabel):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref
        self.setAlignment(Qt.AlignCenter)
        self.bboxes = {}
        self.orig_bbox = None
        self.actual_size = (1200, 900)
        self.hovered_element = None
        self.active_element = None
        self.action_mode = None 
        self.resize_anchor = None 
        self.drag_start_pos = None
        self.elem_start_val = None 
        self.setMouseTracking(True)
        self.pixmap_offset = QPoint(0, 0)
        self.scale_factor = 1.0

    def set_preview(self, pixmap, bboxes, actual_size):
        self.setPixmap(pixmap)
        self.bboxes = bboxes
        self.actual_size = actual_size
        self.update()

    def map_to_actual(self, pos):
        if not self.pixmap(): return 0, 0
        rel_x = pos.x() - self.pixmap_offset.x()
        rel_y = pos.y() - self.pixmap_offset.y()
        return rel_x / self.scale_factor, rel_y / self.scale_factor

    def get_hit_target(self, pos):
        ax, ay = self.map_to_actual(pos)
        hs_act = 8 / self.scale_factor 
        for key, (x1, y1, x2, y2) in reversed(list(self.bboxes.items())):
            if abs(ax - x1) < hs_act and abs(ay - y1) < hs_act: return key, 'resize', 'tl'
            if abs(ax - x2) < hs_act and abs(ay - y1) < hs_act: return key, 'resize', 'tr'
            if abs(ax - x1) < hs_act and abs(ay - y2) < hs_act: return key, 'resize', 'bl'
            if abs(ax - x2) < hs_act and abs(ay - y2) < hs_act: return key, 'resize', 'br'
            if x1 <= ax <= x2 and y1 <= ay <= y2:
                return key, 'drag', None
        return None, None, None

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.pixmap(): return
        w, h = self.width(), self.height()
        px_w = self.pixmap().width() / self.pixmap().devicePixelRatio()
        px_h = self.pixmap().height() / self.pixmap().devicePixelRatio()
        self.pixmap_offset = QPoint((w - px_w) / 2, (h - px_h) / 2)
        self.scale_factor = px_w / self.actual_size[0]

        target = self.active_element or self.hovered_element
        if target and target in self.bboxes:
            x1, y1, x2, y2 = self.bboxes[target]
            dx1 = self.pixmap_offset.x() + x1 * self.scale_factor
            dy1 = self.pixmap_offset.y() + y1 * self.scale_factor
            dx2 = self.pixmap_offset.x() + x2 * self.scale_factor
            dy2 = self.pixmap_offset.y() + y2 * self.scale_factor

            painter = QPainter(self)
            pen = QPen(QColor("#00a8ff"), 1.5, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(dx1, dy1, dx2 - dx1, dy2 - dy1)

            painter.setBrush(QColor("white"))
            hs = 6
            painter.drawRect(dx1 - hs/2, dy1 - hs/2, hs, hs)
            painter.drawRect(dx2 - hs/2, dy1 - hs/2, hs, hs)
            painter.drawRect(dx1 - hs/2, dy2 - hs/2, hs, hs)
            painter.drawRect(dx2 - hs/2, dy2 - hs/2, hs, hs)
            painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or not self.pixmap() or not self.bboxes: return
        key, mode, anchor = self.get_hit_target(event.position().toPoint())
        if key:
            self.active_element = key
            self.action_mode = mode
            self.resize_anchor = anchor
            self.orig_bbox = self.bboxes[key]
            ax, ay = self.map_to_actual(event.position().toPoint())
            self.drag_start_pos = (ax, ay)
            if mode == 'drag':
                self.elem_start_val = self.app_ref.get_element_offset(key)
                self.setCursor(Qt.ClosedHandCursor)
            else:
                self.elem_start_val = self.app_ref.get_element_scale(key)
                
    def mouseMoveEvent(self, event):
        ax, ay = self.map_to_actual(event.position().toPoint())
        if self.active_element and self.drag_start_pos:
            dx = ax - self.drag_start_pos[0]
            dy = ay - self.drag_start_pos[1]
            if self.action_mode == 'drag':
                new_x = self.elem_start_val[0] + dx
                new_y = self.elem_start_val[1] + dy
                self.app_ref.set_element_offset(self.active_element, new_x, new_y, live=True)
                ox1, oy1, ox2, oy2 = self.orig_bbox
                self.bboxes[self.active_element] = (ox1+dx, oy1+dy, ox2+dx, oy2+dy)
            elif self.action_mode == 'resize':
                ox1, oy1, ox2, oy2 = self.orig_bbox
                orig_w = ox2 - ox1
                if self.resize_anchor in ('tr', 'br'): new_w = orig_w + dx
                else: new_w = orig_w - dx
                if new_w > 10 and orig_w > 0:
                    scale_mult = new_w / orig_w
                    new_scale = self.elem_start_val * scale_mult
                    self.app_ref.set_element_scale(self.active_element, new_scale, live=True)
                    nw, nh = ox2 - ox1, oy2 - oy1
                    self.bboxes[self.active_element] = (ox1, oy1, ox1 + nw*scale_mult, oy1 + nh*scale_mult)
        else:
            if not self.pixmap() or not self.bboxes: return
            key, mode, anchor = self.get_hit_target(event.position().toPoint())
            self.hovered_element = key
            if mode == 'resize':
                if anchor in ('tl', 'br'): self.setCursor(Qt.SizeFDiagCursor)
                else: self.setCursor(Qt.SizeBDiagCursor)
            elif mode == 'drag': self.setCursor(Qt.OpenHandCursor)
            else: self.setCursor(Qt.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.active_element:
            self.app_ref.render_cover_preview(fast_mode=False)
            if self.active_element.startswith("wm_"):
                self.app_ref.render_wm_preview(fast_mode=False)
            self.app_ref.push_history("Перемещение на холсте")
            self.setCursor(Qt.OpenHandCursor)
        self.active_element = None
        self.drag_start_pos = None

class SuccessBox(DraggableDialog):
    def __init__(self, parent, title, message, out_dir):
        super().__init__(parent)
        self.out_dir = out_dir
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
            if sys.platform == 'win32': os.startfile(path)
            elif sys.platform == 'darwin': subprocess.Popen(['open', path])
            else: subprocess.Popen(['xdg-open', path])
        self.accept()

class CustomMsgBox(DraggableDialog):
    def __init__(self, parent, title, message):
        super().__init__(parent)
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

class LoadingDialog(DraggableDialog):
    def __init__(self, parent, title="Загрузка файлов..."):
        super().__init__(parent)
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
        if is_cover: self.lbl_name.setStyleSheet("color: #f66b3c; font-weight: bold;")
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
        self.btn_del = QPushButton("✕")
        self.btn_del.setObjectName("Danger")
        self.btn_del.setFixedSize(32, 32)
        self.btn_del.setStyleSheet("font-size: 16px; font-weight: bold;")
        rl.addWidget(self.btn_del)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.drag_start_pos = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton): return
        if (event.position().toPoint() - self.drag_start_pos).manhattanLength() < 5: return
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
        else: event.ignore()

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
            if from_idx != to_idx: self.reordered.emit(from_idx, to_idx)
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
                except Exception: pass
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
                ci, _ = self.app_ref.build_final_image(p, "cover", pre_state=self.state, target_size_text=self.target_size_text)
                if ci:
                    ci.save(os.path.join(odir, cn))
                    successes += 1
                    if only_cover: return successes
            ri, _ = self.app_ref.build_final_image(p, "regular", pre_state=self.state, target_size_text=self.target_size_text)
            if ri:
                if ext == ".jpg": ri.save(os.path.join(odir, rn), quality=92, optimize=True)
                else: ri.save(os.path.join(odir, rn))
                successes += 1
        except Exception: pass
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
                if i == 0 and self.pref: cn = f"0_{self.pref}{current_count}.png"
                elif i == 0: cn = f"0_{oname}.png"
                elif self.pref: cn = f"0_Обложка_{self.pref}{current_count}.png"
                else: cn = f"0_Обложка_{oname}.png"
            rn = f"{self.pref}{current_count}{ext}" if self.pref else f"{oname}_res{ext}"
            tasks.append((p, odir, cn, rn, ext, self.state["only_cover"]))
            current_count += self.step

        threads_count = max(1, (os.cpu_count() or 4) - 1)
        with concurrent.futures.ThreadPoolExecutor(max_workers=threads_count) as executor:
            futures = [executor.submit(self.process_single, task) for task in tasks]
            processed = 0
            for future in concurrent.futures.as_completed(futures):
                try: succ += future.result()
                except Exception: pass
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
        
        self.btn_history = QPushButton("↺ История")
        self.btn_history.setToolTip("История изменений")
        self.btn_min = QPushButton("—")
        self.btn_max = QPushButton("🗖")
        self.btn_close = QPushButton("✕")
        
        self.btn_history.setObjectName("TitleBtn")
        self.btn_history.setFixedSize(110, 40)
        layout.addWidget(self.btn_history)
        
        for b in (self.btn_min, self.btn_max, self.btn_close):
            b.setObjectName("TitleBtn")
            b.setFixedSize(45, 40)
            layout.addWidget(b)
        self.btn_close.setObjectName("TitleCloseBtn")
        
        self.btn_history.clicked.connect(self.parent.toggle_history)
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
        if self._start_pos:
            if self.parent.isMaximized():
                screen_x = event.globalPosition().toPoint().x()
                ratio = event.position().x() / self.width()
                self.parent.showNormal()
                new_x = screen_x - int(self.parent.width() * ratio)
                new_y = event.globalPosition().toPoint().y() - event.position().y()
                self.parent.move(new_x, new_y)
                self._start_pos = QPoint(int(self.parent.width() * ratio), event.position().y())
            delta = event.globalPosition().toPoint() - self._start_pos
            self.parent.move(self.parent.pos() + delta)
            self._start_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if event.globalPosition().y() <= 0 and not self.parent.isMaximized():
            self.parent.showMaximized()
            self.btn_max.setText("🗗")
        self._start_pos = None
    
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton: self.toggle_max()

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
        if event.mimeData().hasUrls(): event.acceptProposedAction()
            
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        if paths: self.dropped.emit(paths)

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

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(1150, 800)
        self.setMinimumSize(900, 650)
        self.setAcceptDrops(True)

        self._history = []
        self._history_ptr = -1
        self._is_undoing = False
        self.thumb_cache = {}

        self._cached_orig_path = None
        self._cached_crop = None
        self._cached_orig_img = None

        gen_cfg = self.load_general_config()
        self.current_theme = gen_cfg.get("theme", "light")
        self.custom_sizes = gen_cfg.get("sizes", ["1200x900", "900x900"])
        self.remember_files = gen_cfg.get("remember_files", False)
        cached_files = gen_cfg.get("cached_files", [])
        self.files = [f for f in cached_files if os.path.exists(f)] if self.remember_files else []
        self.custom_colors = gen_cfg.get("custom_colors", [])
        for i, col_hex in enumerate(self.custom_colors):
            if i < QColorDialog.customCount():
                QColorDialog.setCustomColor(i, QColor(col_hex).rgb())
        
        self.crop_data = {}
        self.fill_settings = {}
        self.watermarks_config = self.load_wm_config()
        self.current_wm_edit = None
        
        self.cover_cfg_data = self.load_cover_config()
        self.global_transform = self.cover_cfg_data.get("global_transform", {"scale": 100, "x": 0, "y": 0})
        self.individual_transforms = self.cover_cfg_data.get("individual_transforms", {})
        self.global_price = self.cover_cfg_data.get("global_price", {"new": self.cover_cfg_data.get("price_new", "9990"), "old": self.cover_cfg_data.get("price_old", "14990")})
        self.individual_prices = self.cover_cfg_data.get("individual_prices", {})
        self.price_color_hex = self.cover_cfg_data.get("price_color_hex", "#B40000")
        
        self.current_cover_preview_idx = 0
        self.current_wm_preview_idx = 0
        self._is_switching = False
        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(lambda: self.render_cover_preview(fast_mode=False))
        
        self._wm_preview_timer = QTimer()
        self._wm_preview_timer.setSingleShot(True)
        self._wm_preview_timer.timeout.connect(lambda: self.render_wm_preview(fast_mode=False))
        
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
        self.push_history("Исходное состояние")

    def toggle_history(self):
        self.history_frame.setVisible(not self.history_frame.isVisible())

    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        key = event.key()
        char = event.text().lower()
        if modifiers == (Qt.ControlModifier | Qt.ShiftModifier):
            if key == Qt.Key_Z or char == 'я': self.redo(); return
        elif modifiers == Qt.ControlModifier:
            if key == Qt.Key_Z or char == 'я': self.undo(); return
            elif key == Qt.Key_Y or char == 'н': self.redo(); return
        super().keyPressEvent(event)

    def push_history(self, action_name="Изменение"):
        if self._is_undoing: return
        state = {"cover": copy.deepcopy(self.get_cover_state()), "wm": copy.deepcopy(self.watermarks_config)}
        self._history = self._history[:self._history_ptr + 1]
        self._history.append({"state": state, "name": action_name})
        if len(self._history) > 30: self._history.pop(0)
        self._history_ptr = len(self._history) - 1
        self.update_history_list()

    def update_history_list(self):
        self.history_list.blockSignals(True)
        self.history_list.clear()
        for i, h in enumerate(self._history):
            self.history_list.addItem(f"{i+1}. {h['name']}")
        if self._history_ptr >= 0:
            self.history_list.setCurrentRow(self._history_ptr)
        self.history_list.blockSignals(False)

    def update_history_selection(self):
        self.history_list.blockSignals(True)
        if 0 <= self._history_ptr < self.history_list.count():
            self.history_list.setCurrentRow(self._history_ptr)
        self.history_list.blockSignals(False)

    def on_history_item_clicked(self, item):
        idx = self.history_list.row(item)
        if idx != self._history_ptr:
            self._history_ptr = idx
            self.restore_state(self._history[idx]["state"])
            self.update_history_selection()

    def undo(self):
        if self._history_ptr > 0:
            self._history_ptr -= 1
            self.restore_state(self._history[self._history_ptr]["state"])
            self.update_history_selection()

    def redo(self):
        if self._history_ptr < len(self._history) - 1:
            self._history_ptr += 1
            self.restore_state(self._history[self._history_ptr]["state"])
            self.update_history_selection()

    def restore_state(self, state):
        self._is_undoing = True
        self.watermarks_config = copy.deepcopy(state["wm"])
        self.load_cover_state(state["cover"])
        if self.current_wm_edit and self.current_wm_edit in self.watermarks_config: self.edit_wm(self.current_wm_edit)
        else: self.refresh_wm_list()
        self._is_undoing = False
        self.render_cover_preview(fast_mode=False)
        self.render_wm_preview(fast_mode=False)

    def get_element_offset(self, key):
        if key == "transform": return self.sl_img_x.value(), self.sl_img_y.value()
        if key == "banner": return self.sl_ban_x.value(), self.sl_ban_y.value()
        if key == "logo": return self.sl_logo_x.value(), self.sl_logo_y.value()
        if key == "md_logo": return self.sl_md_x.value(), self.sl_md_y.value()
        if key == "price_new": return self.sl_pr_nx.value(), self.sl_pr_ny.value()
        if key == "price_old": return self.sl_pr_ox.value(), self.sl_pr_oy.value()
        if key.startswith("wm_"):
            return self.watermarks_config.get(key[3:], {}).get("dx", 0), self.watermarks_config.get(key[3:], {}).get("dy", 0)
        return 0, 0

    def set_element_offset(self, key, nx, ny, live=False):
        if key == "transform":
            self.sl_img_x.setValue(int(nx))
            self.sl_img_y.setValue(int(ny))
            t = self.get_cover_targets()
            if t:
                path = t[self.current_cover_preview_idx % len(t)]
                vals = {"scale": self.sl_img_sc.value(), "x": self.sl_img_x.value(), "y": self.sl_img_y.value()}
                if self.cb_individual.isChecked(): self.individual_transforms[path] = vals
                else: self.global_transform = vals
        elif key == "banner": self.sl_ban_x.setValue(int(nx)); self.sl_ban_y.setValue(int(ny))
        elif key == "logo": self.sl_logo_x.setValue(int(nx)); self.sl_logo_y.setValue(int(ny))
        elif key == "md_logo": self.sl_md_x.setValue(int(nx)); self.sl_md_y.setValue(int(ny))
        elif key == "price_new": self.sl_pr_nx.setValue(int(nx)); self.sl_pr_ny.setValue(int(ny))
        elif key == "price_old": self.sl_pr_ox.setValue(int(nx)); self.sl_pr_oy.setValue(int(ny))
        elif key.startswith("wm_"):
            name = key[3:]
            if name in self.watermarks_config:
                self.watermarks_config[name]["dx"] = int(nx)
                self.watermarks_config[name]["dy"] = int(ny)
                if self.current_wm_edit == name:
                    self.sl_wm_dx.setValue(int(nx)); self.sl_wm_dy.setValue(int(ny))
        
        if live:
            self.render_cover_preview(fast_mode=True)
            if key.startswith("wm_"): self.render_wm_preview(fast_mode=True)
        else:
            self.request_cover_preview(150)
            if key.startswith("wm_"): self.request_wm_preview(150)

    def get_element_scale(self, key):
        if key == "transform": return self.sl_img_sc.value()
        if key == "banner": return self.sl_ban_sc.value()
        if key == "logo": return self.sl_logo_sc.value()
        if key == "md_logo": return self.sl_md_sc.value()
        if key in ["price_new", "price_old"]: return self.sl_pr_sc.value()
        if key.startswith("wm_"): return self.watermarks_config.get(key[3:], {}).get("scale", 45)
        return 100

    def set_element_scale(self, key, scale, live=False):
        scale = int(max(1, min(300, scale)))
        if key == "transform":
            self.sl_img_sc.setValue(scale)
            t = self.get_cover_targets()
            if t:
                path = t[self.current_cover_preview_idx % len(t)]
                vals = {"scale": self.sl_img_sc.value(), "x": self.sl_img_x.value(), "y": self.sl_img_y.value()}
                if self.cb_individual.isChecked(): self.individual_transforms[path] = vals
                else: self.global_transform = vals
        elif key == "banner": self.sl_ban_sc.setValue(scale)
        elif key == "logo": self.sl_logo_sc.setValue(scale)
        elif key == "md_logo": self.sl_md_sc.setValue(scale)
        elif key in ["price_new", "price_old"]: self.sl_pr_sc.setValue(scale)
        elif key.startswith("wm_"):
            name = key[3:]
            if name in self.watermarks_config:
                self.watermarks_config[name]["scale"] = scale
                if self.current_wm_edit == name: self.sl_wm_sc.setValue(scale)

        if live:
            self.render_cover_preview(fast_mode=True)
            if key.startswith("wm_"): self.render_wm_preview(fast_mode=True)
        else:
            self.request_cover_preview(150)
            if key.startswith("wm_"): self.request_wm_preview(150)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
        if paths: self.on_files_dropped(paths)

    def on_files_dropped(self, paths):
        added_paths = []
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                added_paths.append(p)
        if added_paths: self.add_files_to_ui_async(added_paths)

    def closeEvent(self, event):
        self.save_general_config()
        self.save_cover_config()
        self.save_wm_config()
        event.accept()

    def load_general_config(self):
        if os.path.exists(GENERAL_CONFIG_FILE):
            try:
                with open(GENERAL_CONFIG_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except Exception: pass
        return {"sizes": ["1200x900", "900x900"], "remember_files": False, "cached_files": [], "theme": "light", "custom_colors": []}

    def save_general_config(self):
        rem = self.cb_remember_files.isChecked() if hasattr(self, 'cb_remember_files') else False
        custom_colors = []
        for i in range(QColorDialog.customCount()):
            c = QColorDialog.customColor(i)
            custom_colors.append(c.name() if c.isValid() else "#ffffff")
            
        data = {
            "sizes": self.custom_sizes,
            "remember_files": rem,
            "cached_files": self.files if rem else [],
            "theme": self.current_theme,
            "custom_colors": custom_colors
        }
        try:
            with open(GENERAL_CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception: pass

    def load_wm_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except Exception: pass
        return {}

    def save_wm_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(self.watermarks_config, f, ensure_ascii=False, indent=4)
        except Exception: pass

    def load_cover_config(self):
        if os.path.exists(COVER_CONFIG_FILE):
            try:
                with open(COVER_CONFIG_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except Exception: pass
        return {}

    def save_cover_config(self):
        data = self.get_cover_state()
        data["global_transform"] = self.global_transform
        data["individual_transforms"] = self.individual_transforms
        data["global_price"] = self.global_price
        data["individual_prices"] = self.individual_prices
        data["price_color_hex"] = self.price_color_hex
        try:
            with open(COVER_CONFIG_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception: pass

    def apply_theme(self):
        QApplication.instance().setStyleSheet(get_stylesheet(self.current_theme))
        self.update_dynamic_text()
        self.refresh_wm_list()
        self.update_file_row_labels()
        self.update_pos_icons()

    def update_pos_icons(self):
        color_str = THEMES[self.current_theme]['TEXT']
        if hasattr(self, 'wm_pos_icons'):
            for val, lbl in self.wm_pos_icons.items(): lbl.setPixmap(create_arrow_pixmap(val, color_str))

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
        entry.setText(str(slider.value()))
        callback = command if command else lambda: self.request_cover_preview(150)
        slider.valueChanged.connect(callback)
        slider.sliderReleased.connect(lambda: self.push_history("Сдвиг ползунка"))
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

        main_content_widget = QWidget()
        main_content_layout = QHBoxLayout(main_content_widget)
        main_content_layout.setContentsMargins(0,0,0,0)
        main_content_layout.setSpacing(0)

        left_side = QWidget()
        content_layout = QVBoxLayout(left_side)
        content_layout.setContentsMargins(0,0,0,0)

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

        main_content_layout.addWidget(left_side, 1)

        self.history_frame = QFrame()
        self.history_frame.setObjectName("Card")
        self.history_frame.setFixedWidth(240)
        self.history_frame.hide()
        hl = QVBoxLayout(self.history_frame)
        hl.setContentsMargins(10, 10, 10, 10)
        lbl_h = QLabel("История изменений")
        lbl_h.setObjectName("Title")
        lbl_h.setAlignment(Qt.AlignCenter)
        hl.addWidget(lbl_h)
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.on_history_item_clicked)
        hl.addWidget(self.history_list)
        main_content_layout.addWidget(self.history_frame)

        main_layout.addWidget(main_content_widget, 1)

        bot_widget = QWidget()
        bot_layout = QHBoxLayout(bot_widget)
        bot_layout.setContentsMargins(15, 10, 15, 15)
        
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
        
        main_layout.addWidget(bot_widget)
        win_layout.addWidget(self.app_frame)

        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)

        self.build_files_tab()
        self.build_cover_tab()
        self.build_wm_tab()
        self.build_out_tab()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grip.move(self.width() - self.grip.width(), self.height() - self.grip.height())

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
                if is_cover: w.lbl_name.setStyleSheet("color: #f66b3c; font-weight: bold;")
                else: w.lbl_name.setStyleSheet("")

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
        if self.loading_dialog: self.loading_dialog.update_progress(curr, total)
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
        self.request_cover_preview(150)
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
            self.request_cover_preview(150)
            self.render_wm_preview()
            self.push_history("Пересортировка файлов")

    def toggle_fill(self, path, checked):
        self.fill_settings[path] = checked
        self.render_out_preview()
        self.render_wm_preview()
        self.push_history("Без полей")

    def open_crop(self, path):
        dlg = CropDialog(path, self.crop_data.get(path), self)
        if dlg.exec():
            self.crop_data[path] = dlg.get_result()
            self.render_out_preview()
            self.request_cover_preview(150)
            self.render_wm_preview()
            self.push_history("Кадрирование")

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
        if not self.files: self.refresh_file_list_ui()
        self.update_file_row_labels()
        self.update_dropdown_files()
        self.request_cover_preview(150)
        self.render_wm_preview()
        self.push_history("Удаление файла")

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
            self.push_history("Добавление файлов")

    def clear_list(self):
        self.files.clear()
        self.crop_data.clear()
        self.thumb_cache.clear()
        self.refresh_file_list_ui()
        self.update_dropdown_files()
        self.request_cover_preview(150)
        self.render_wm_preview()
        self.push_history("Очистка списка")

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
        self.cb_active_cover.toggled.connect(lambda _: self.push_history("Обложка Вкл/Выкл"))
        self.cb_only_cover.toggled.connect(self.save_cover_config)
        self.cb_only_cover.toggled.connect(lambda _: self.push_history("ТОЛЬКО обложка Вкл/Выкл"))
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
        btn_rst_ban.clicked.connect(lambda: (self.sl_ban_sc.setValue(100), self.sl_ban_x.setValue(0), self.sl_ban_y.setValue(0), self.push_history("Сброс плашки")))
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
        lr.addWidget(btn_sel_logo); lr.addWidget(btn_del_logo); lr.addWidget(self.lbl_logo_name)
        b_logo.content_layout.addLayout(lr)
        self.sl_logo_sc, self.e_logo_sc = self.create_slider_row(b_logo.content_layout, "Масштаб %:", 10, 300)
        self.sl_logo_x, self.e_logo_x = self.create_slider_row(b_logo.content_layout, "Позиция X:", -1000, 1000)
        self.sl_logo_y, self.e_logo_y = self.create_slider_row(b_logo.content_layout, "Позиция Y:", -1000, 1000)
        btn_rst_logo = QPushButton("Сбросить")
        btn_rst_logo.setObjectName("Secondary")
        btn_rst_logo.clicked.connect(lambda: (self.sl_logo_sc.setValue(100), self.sl_logo_x.setValue(0), self.sl_logo_y.setValue(0), self.push_history("Сброс логотипа")))
        b_logo.content_layout.addWidget(btn_rst_logo)
        self.left_l.addWidget(b_logo)

        b_md = CollapsibleBox("Уценка (Цены и значок)")
        self.cb_md_active = QCheckBox("Включить отображение")
        self.cb_md_active.toggled.connect(lambda _: self.request_cover_preview(150))
        self.cb_md_active.toggled.connect(lambda _: self.push_history("Уценка Вкл/Выкл"))
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
        btn_sel_price_font = QPushButton("ШРИФТ")
        btn_sel_price_font.setObjectName("Secondary")
        self.lbl_price_font = QLabel("Arial")
        self.lbl_price_font.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.price_font_str = "" 
        btn_sel_price_font.clicked.connect(self.select_price_font)
        f_r.addWidget(btn_sel_price_font)
        f_r.addWidget(self.lbl_price_font)
        
        self.btn_price_color = QPushButton()
        self.btn_price_color.setFixedSize(30, 30)
        self.btn_price_color.setStyleSheet(f"background-color: {self.price_color_hex}; border-radius: 4px; border: 1px solid #888;")
        self.btn_price_color.clicked.connect(self.select_price_color)
        f_r.addWidget(self.btn_price_color)
        b_md.content_layout.addLayout(f_r)

        self.sl_pr_sc, self.e_pr_sc = self.create_slider_row(b_md.content_layout, "Масштаб цен:", 10, 300)
        self.sl_pr_nx, self.e_pr_nx = self.create_slider_row(b_md.content_layout, "Нов. цена X:", -1000, 1000)
        self.sl_pr_ny, self.e_pr_ny = self.create_slider_row(b_md.content_layout, "Нов. цена Y:", -1000, 1000)
        self.sl_pr_ox, self.e_pr_ox = self.create_slider_row(b_md.content_layout, "Стар. цена X:", -1000, 1000)
        self.sl_pr_oy, self.e_pr_oy = self.create_slider_row(b_md.content_layout, "Стар. цена Y:", -1000, 1000)
        self.sl_str_w, self.e_str_w = self.create_slider_row(b_md.content_layout, "Толщина черты:", 1, 30)
        self.sl_pr_space, self.e_pr_space = self.create_slider_row(b_md.content_layout, "Интервал:", -50, 100)

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

        self.cov_preview_lbl = InteractivePreview(self)
        self.cov_preview_lbl.setText("Загрузите фото во вкладке 'Файлы'")
        self.cov_preview_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        rl.addWidget(self.cov_preview_lbl, 1)

        l.addWidget(right, 1)

    def select_price_color(self):
        dlg = FramelessColorDialog(self.price_color_hex, self)
        if dlg.exec():
            self.price_color_hex = dlg.get_color_hex()
            self.btn_price_color.setStyleSheet(f"background-color: {self.price_color_hex}; border-radius: 4px; border: 1px solid #888;")
            self.save_cover_config()
            self.request_cover_preview(150)
            self.push_history("Цвет ценника")

    def select_price_font(self):
        dlg = CustomFontDialog(self.price_font_str, self)
        if dlg.exec():
            self.price_font_str = dlg.get_font_str()
            self.lbl_price_font.setText(dlg.get_display_name())
            self.request_cover_preview(150)
            self.push_history("Шрифт ценника")

    def on_cover_target_change(self, text):
        self.btn_sel_tgt.setVisible(text == "Выборочно")
        self.update_file_row_labels()
        self.request_cover_preview(150)
        self.push_history("Смена цели обложки")

    def open_target_selector(self):
        if not self.files: 
            CustomMsgBox(self, "Пусто", "Сначала загрузите фотографии во вкладке 'Файлы'").exec()
            return
        dlg = CoverTargetSelector(self.files, self.entry_target_indices.text(), self)
        if dlg.exec():
            self.entry_target_indices.setText(dlg.get_result())
            self.save_cover_config()
            self.update_file_row_labels()
            self.request_cover_preview(150)
            self.push_history("Выбор целевых обложек")

    def add_banner(self):
        paths = native_askopenfilenames(title="Выберите картинки плашек")
        if not paths: return
        for path in paths:
            filename = os.path.basename(path)
            dest = os.path.join(ASSETS_DIR, filename)
            try: shutil.copy(path, dest)
            except Exception: pass
            if filename not in self.banners_list: self.banners_list.append(filename)
        self.save_cover_config()
        self.refresh_banners_list_ui()
        self.request_cover_preview(150)
        self.push_history("Добавление плашки")

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
            except Exception: pass
            l.addWidget(thumb)
            lbl = QLabel(f if len(f)<18 else f[:15]+"...")
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            l.addWidget(lbl)
            btn_del = QPushButton("X")
            btn_del.setObjectName("Danger")
            btn_del.setFixedSize(32, 32)
            btn_del.setStyleSheet("font-size: 16px; font-weight: bold;")
            btn_del.clicked.connect(lambda _, name=f: self.delete_banner(name))
            l.addWidget(btn_del)
            self.ban_list_widget.addWidget(row)

    def select_banner(self, name, checked):
        self.active_banner = name if checked else ""
        self.refresh_banners_list_ui()
        self.request_cover_preview(150)
        self.push_history("Переключение плашки")

    def delete_banner(self, name):
        self.banners_list.remove(name)
        if self.active_banner == name: self.active_banner = ""
        self.refresh_banners_list_ui()
        self.request_cover_preview(150)
        self.push_history("Удаление плашки")

    def select_logo(self):
        p = native_askopenfilename(title="Выберите логотип")
        if p:
            f = os.path.basename(p)
            try: shutil.copy(p, os.path.join(ASSETS_DIR, f))
            except Exception: pass
            self.lbl_logo_name.setText(f)
            self.request_cover_preview(150)
            self.push_history("Выбор логотипа")

    def clear_logo(self):
        self.lbl_logo_name.setText("")
        self.request_cover_preview(150)
        self.push_history("Удаление логотипа")

    def select_md_logo(self):
        p = native_askopenfilename(title="Выберите логотип уценки")
        if p:
            f = os.path.basename(p)
            try: shutil.copy(p, os.path.join(ASSETS_DIR, f))
            except Exception: pass
            self.lbl_md_name.setText(f)
            self.request_cover_preview(150)
            self.push_history("Выбор значка уценки")

    def clear_md_logo(self):
        self.lbl_md_name.setText("")
        self.request_cover_preview(150)
        self.push_history("Удаление значка уценки")

    def _on_transform_change(self):
        if self._is_switching: return
        t = self.get_cover_targets()
        if not t: return
        path = t[self.current_cover_preview_idx % len(t)]
        vals = {"scale": self.sl_img_sc.value(), "x": self.sl_img_x.value(), "y": self.sl_img_y.value()}
        if self.cb_individual.isChecked(): self.individual_transforms[path] = vals
        else: self.global_transform = vals
        self.request_cover_preview(150)

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
        self.request_cover_preview(150)
        self.push_history("Индивидуальные настройки")

    def reset_product_transform(self):
        self._is_switching = True
        self.sl_img_x.setValue(0); self.sl_img_y.setValue(0); self.sl_img_sc.setValue(100)
        self._is_switching = False
        self._on_transform_change()
        self.request_cover_preview(150)
        self.push_history("Сброс товара")

    def _on_price_change(self):
        if self._is_switching: return
        t = self.get_cover_targets()
        if not t: return
        path = t[self.current_cover_preview_idx % len(t)]
        vals = {"new": self.e_pr_new.text(), "old": self.e_pr_old.text()}
        if self.cb_individual_price.isChecked(): self.individual_prices[path] = vals
        else: self.global_price = vals
        self.request_cover_preview(150)

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
        self.request_cover_preview(150)
        self.push_history("Индивидуальная цена")

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
        self.render_cover_preview(fast_mode=False)

    def request_cover_preview(self, delay=150):
        self._preview_timer.start(delay)
        
    def request_wm_preview(self, delay=150):
        self._wm_preview_timer.start(delay)

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
            "price_font_str": self.price_font_str,
            "price_font_display": self.lbl_price_font.text(),
            "price_color_hex": self.price_color_hex, 
            "price_scale": self.sl_pr_sc.value(),
            "price_new_x": self.sl_pr_nx.value(), "price_new_y": self.sl_pr_ny.value(),
            "price_old_x": self.sl_pr_ox.value(), "price_old_y": self.sl_pr_oy.value(),
            "strike_width": self.sl_str_w.value(),
            "price_letter_spacing": self.sl_pr_space.value()
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
        
        self.price_font_str = d.get("price_font_str", "")
        self.lbl_price_font.setText(d.get("price_font_display", "Arial (Regular)"))
        self.price_color_hex = d.get("price_color_hex", "#B40000")
        self.btn_price_color.setStyleSheet(f"background-color: {self.price_color_hex}; border-radius: 4px; border: 1px solid #888;")
        
        # ВАЖНО: Восстанавливаем словарь общих трансформаций
        self.global_transform = d.get("global_transform", {"scale": 100, "x": 0, "y": 0})
        self.individual_transforms = d.get("individual_transforms", {})
        self.global_price = d.get("global_price", {"new": "9990", "old": "14990"})
        self.individual_prices = d.get("individual_prices", {})
        
        gt = self.global_transform
        self.sl_img_sc.setValue(gt["scale"])
        self.sl_img_x.setValue(gt["x"])
        self.sl_img_y.setValue(gt["y"])
        
        self.sl_pr_sc.setValue(d.get("price_scale", 100))
        self.sl_pr_nx.setValue(d.get("price_new_x", 0)); self.sl_pr_ny.setValue(d.get("price_new_y", 0))
        self.sl_pr_ox.setValue(d.get("price_old_x", 0)); self.sl_pr_oy.setValue(d.get("price_old_y", 0))
        self.sl_pr_space.setValue(d.get("price_letter_spacing", 0))
        self.e_pr_new.setText(self.global_price.get("new", "9990"))
        self.e_pr_old.setText(self.global_price.get("old", "14990"))
        self.sl_str_w.setValue(d.get("strike_width", 5))

        self._is_switching = False
        
        for sl in [self.sl_ban_sc, self.sl_ban_x, self.sl_ban_y, self.sl_logo_sc, self.sl_logo_x, self.sl_logo_y,
                   self.sl_md_sc, self.sl_md_x, self.sl_md_y, self.sl_pr_sc, self.sl_pr_nx, self.sl_pr_ny,
                   self.sl_pr_ox, self.sl_pr_oy, self.sl_pr_space, self.sl_str_w, self.sl_img_sc, self.sl_img_x, self.sl_img_y]:
            sl.valueChanged.emit(sl.value())

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
        
        self.wm_text_container = QWidget()
        wtc_l = QVBoxLayout(self.wm_text_container)
        wtc_l.setContentsMargins(0,0,0,0)
        
        self.e_wm_text = QLineEdit()
        self.e_wm_text.setPlaceholderText("Введите текст ВЗ")
        self.e_wm_text.textChanged.connect(self.save_wm_settings)
        wtc_l.addWidget(self.e_wm_text)
        
        self.wm_font_layout = QHBoxLayout()
        self.btn_wm_font = QPushButton("ШРИФТ")
        self.btn_wm_font.setObjectName("Secondary")
        self.lbl_wm_font = QLabel("Arial")
        self.lbl_wm_font.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.wm_font_str = ""
        self.btn_wm_font.clicked.connect(self.select_wm_font)
        self.wm_font_layout.addWidget(self.btn_wm_font)
        self.wm_font_layout.addWidget(self.lbl_wm_font)
        
        self.wm_color_hex = "#000000"
        self.btn_wm_color = QPushButton()
        self.btn_wm_color.setFixedSize(30, 30)
        self.btn_wm_color.setStyleSheet(f"background-color: {self.wm_color_hex}; border-radius: 4px; border: 1px solid #888;")
        self.btn_wm_color.clicked.connect(self.select_wm_color)
        self.wm_font_layout.addWidget(self.btn_wm_color)
        
        wtc_l.addLayout(self.wm_font_layout)
        s_l.addWidget(self.wm_text_container)
        
        self.cb_wm_grid = QCheckBox("Защитная сетка (замостить)")
        self.cb_wm_grid.toggled.connect(lambda c: self.save_wm_settings())
        s_l.addWidget(self.cb_wm_grid)
        self.sl_wm_op, self.e_wm_op = self.create_slider_row(s_l, "Прозрачность %:", 0, 100, command=self.save_wm_settings)
        self.sl_wm_sc, self.e_wm_sc = self.create_slider_row(s_l, "Размер %:", 1, 300, command=self.save_wm_settings)
        self.sl_wm_dx, self.e_wm_dx = self.create_slider_row(s_l, "Сдвиг X:", -1000, 1000, command=self.save_wm_settings)
        self.sl_wm_dy, self.e_wm_dy = self.create_slider_row(s_l, "Сдвиг Y:", -1000, 1000, command=self.save_wm_settings)

        pos_lbl = QLabel("Позиция:")
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

        self.wm_preview_lbl = InteractivePreview(self)
        self.wm_preview_lbl.setText("Загрузите фото во вкладке 'Файлы'")
        self.wm_preview_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        rl.addWidget(self.wm_preview_lbl, 1)

        l.addWidget(right, 1)
        self.disable_wm_settings()

    def select_wm_color(self):
        if not self.current_wm_edit: return
        dlg = FramelessColorDialog(self.wm_color_hex, self)
        if dlg.exec():
            self.wm_color_hex = dlg.get_color_hex()
            self.btn_wm_color.setStyleSheet(f"background-color: {self.wm_color_hex}; border-radius: 4px; border: 1px solid #888;")
            self.save_wm_settings()
            self.push_history("Цвет ВЗ")

    def select_wm_font(self):
        if not self.current_wm_edit: return
        dlg = CustomFontDialog(self.wm_font_str, self)
        if dlg.exec():
            self.wm_font_str = dlg.get_font_str()
            self.lbl_wm_font.setText(dlg.get_display_name())
            self.save_wm_settings()
            self.push_history("Шрифт ВЗ")

    def switch_wm_preview(self, delta):
        if not self.files: return
        self.current_wm_preview_idx = (self.current_wm_preview_idx + delta) % len(self.files)
        self.render_wm_preview(fast_mode=False)

    def render_wm_preview(self, fast_mode=False):
        if not self.files:
            self.wm_preview_lbl.setPixmap(QPixmap())
            self.wm_preview_lbl.setText("Нет фото")
            return
        idx = self.current_wm_preview_idx % len(self.files)
        self.lbl_wm_prev_title.setText(f"Превью (Фото {idx+1} из {len(self.files)}):")
        img, bboxes = self.build_final_image(self.files[idx], "regular", fast_mode=fast_mode)
        if img:
            t_img = img.copy()
            resample_filter = Image.Resampling.NEAREST if fast_mode else Image.Resampling.LANCZOS
            t_img.thumbnail((800, 600), resample_filter)
            self.wm_preview_lbl.set_preview(pil_to_pixmap(t_img), bboxes, (img.width, img.height))
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
                "active": True, "type": "text", "text": text, "color_hex": "#000000", 
                "font_str": "", "font_display": "Arial (Regular)",
                "opacity": 50, "scale": 15, "pos": "c", "dx": 0, "dy": 0, "grid": False
            }
            self.save_wm_config()
            self.edit_wm(name)
            self.push_history("Добавление текстового ВЗ")

    def add_wm(self):
        paths = native_askopenfilenames(title="Выберите ВЗ")
        if not paths: return
        last_f = None
        for p in paths:
            f = os.path.basename(p)
            try: shutil.copy(p, os.path.join(ASSETS_DIR, f))
            except Exception: pass
            self.watermarks_config[f] = {"active": True, "type": "image", "opacity": 50, "scale": 45, "pos": "bl", "dx": 20, "dy": -20, "grid": False}
            last_f = f
        self.save_wm_config()
        if last_f: self.edit_wm(last_f)
        else: self.refresh_wm_list()
        self.push_history("Добавление ВЗ")

    def refresh_wm_list(self):
        while self.wm_layout.count() > 1:
            w = self.wm_layout.takeAt(1).widget()
            if w: w.deleteLater()
        for f, cfg in self.watermarks_config.items():
            row = QFrame()
            row.setObjectName("ActiveCard" if self.current_wm_edit == f else "Card")
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
            if self.current_wm_edit == f: btn_edit.setStyleSheet(f"background-color: {THEMES[self.current_theme]['ACCENT']}; color: {THEMES[self.current_theme]['BG']};")
            else: btn_edit.setObjectName("Secondary")
            btn_edit.clicked.connect(lambda _, name=f: self.edit_wm(name))
            btn_del = QPushButton("X")
            btn_del.setObjectName("Danger")
            btn_del.setFixedSize(32, 32)
            btn_del.setStyleSheet("font-size: 16px; font-weight: bold;")
            btn_del.clicked.connect(lambda _, name=f: self.delete_wm(name))
            l.addWidget(cb); l.addWidget(lbl); l.addStretch(); l.addWidget(btn_edit); l.addWidget(btn_del)
            self.wm_layout.addWidget(row)

    def toggle_wm_active(self, name, checked):
        self.watermarks_config[name]["active"] = checked
        self.save_wm_config()
        if checked: self.edit_wm(name)
        else:
            if self.current_wm_edit == name: self.disable_wm_settings()
        self.render_out_preview(fast_mode=False)
        self.render_wm_preview(fast_mode=False)
        self.push_history("Переключение ВЗ")

    def delete_wm(self, name):
        if self.watermarks_config[name].get("type") != "text":
            try: os.remove(get_asset_path(name))
            except Exception: pass
        del self.watermarks_config[name]
        if self.current_wm_edit == name: self.disable_wm_settings()
        self.save_wm_config()
        self.refresh_wm_list()
        self.render_out_preview(fast_mode=False)
        self.render_wm_preview(fast_mode=False)
        self.push_history("Удаление ВЗ")

    def edit_wm(self, name):
        self.current_wm_edit = name
        c = self.watermarks_config[name]
        self.lbl_wm_title.setText(f"Настройка: {name}")
        self._is_switching = True
        is_text = c.get("type") == "text"
        self.wm_text_container.setVisible(is_text)
        
        if is_text:
            self.e_wm_text.setText(c.get("text", ""))
            hex_c = c.get("color_hex")
            if not hex_c: hex_c = "#000000" if c.get("color", "Черный") == "Черный" else "#ffffff"
            self.wm_color_hex = hex_c
            self.btn_wm_color.setStyleSheet(f"background-color: {self.wm_color_hex}; border-radius: 4px; border: 1px solid #888;")
            self.wm_font_str = c.get("font_str", "")
            self.lbl_wm_font.setText(c.get("font_display", "Arial (Regular)"))
            
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
        
        if is_text:
            self.e_wm_text.setEnabled(True)
            self.btn_wm_font.setEnabled(True)
            self.btn_wm_color.setEnabled(True)
            
        self.cb_wm_grid.setEnabled(True)
        self.sl_wm_op.setEnabled(True); self.e_wm_op.setEnabled(True)
        self.sl_wm_sc.setEnabled(True); self.e_wm_sc.setEnabled(True)
        self.sl_wm_dx.setEnabled(True); self.e_wm_dx.setEnabled(True)
        self.sl_wm_dy.setEnabled(True); self.e_wm_dy.setEnabled(True)
        for b in self.wm_pos_group.buttons(): b.setEnabled(True)
        self.refresh_wm_list()
        self.render_wm_preview(fast_mode=False)

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
            updates["color_hex"] = self.wm_color_hex
            updates["font_str"] = self.wm_font_str
            updates["font_display"] = self.lbl_wm_font.text()
        self.watermarks_config[self.current_wm_edit].update(updates)
        self.save_wm_config()
        self.request_out_preview(150)
        self.request_wm_preview(150)

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
        self.wm_text_container.setVisible(False)
        self.cb_wm_grid.setEnabled(False)
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
        self.cb_out_files.currentTextChanged.connect(lambda _: self.request_out_preview(150))
        btn_upd = QPushButton("Обновить")
        btn_upd.clicked.connect(lambda: self.render_out_preview(fast_mode=False))
        top.addWidget(self.cb_out_files)
        top.addWidget(btn_upd)
        top.addStretch()
        l.addLayout(top)

        self.lbl_out_prev = InteractivePreview(self)
        self.lbl_out_prev.setText("Добавьте файлы во вкладке 'Файлы'")
        self.lbl_out_prev.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        l.addWidget(self.lbl_out_prev, 1)

        bot = QFrame()
        bot.setObjectName("Card")
        bl = QGridLayout(bot)
        bl.addWidget(QLabel("Размер:"), 0, 0)
        self.cb_sizes = QComboBox()
        self.cb_sizes.addItems(self.custom_sizes)
        self.cb_sizes.currentTextChanged.connect(lambda _: self.request_out_preview(150))
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
        
        self._out_preview_timer = QTimer()
        self._out_preview_timer.setSingleShot(True)
        self._out_preview_timer.timeout.connect(lambda: self.render_out_preview(fast_mode=False))

    def request_out_preview(self, delay=150):
        self._out_preview_timer.start(delay)

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
        if curr in names: self.cb_out_files.setCurrentText(curr)
        elif names: self.cb_out_files.setCurrentIndex(0) 
        self.cb_out_files.blockSignals(False)
        self.request_out_preview(150)

    def build_final_image(self, path, mode="regular", pre_state=None, target_size_text=None, fast_mode=False):
        state = pre_state if pre_state else self.get_cover_state()
        if mode == "cover": t_size = (1200, 900)
        else: 
            sz_txt = target_size_text if target_size_text else self.cb_sizes.currentText()
            t_size = tuple(map(int, sz_txt.split('x')))
            
        resample_filter = Image.Resampling.NEAREST if fast_mode else Image.Resampling.LANCZOS
        
        canvas = Image.new("RGBA", t_size, (255, 255, 255, 255))
        bboxes = {}
        
        try:
            if self._cached_orig_path == path and self._cached_crop == self.crop_data.get(path):
                orig = self._cached_orig_img.copy()
            else:
                with Image.open(path) as img:
                    orig = img.convert("RGBA")
                    if path in self.crop_data:
                        c = self.crop_data[path]
                        orig = orig.crop((max(0, c[0]), max(0, c[1]), min(img.width, c[2]), min(img.height, c[3])))
                self._cached_orig_path = path
                self._cached_crop = self.crop_data.get(path)
                self._cached_orig_img = orig.copy()
                
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
                    res = orig.resize((nw, nh), resample_filter)
                    px = bw_off + (aw - nw)//2 + dx
                    py = (t_size[1] - nh)//2 + dy
                    canvas.paste(res, (px, py), res)
                    bboxes["transform"] = (px, py, px+nw, py+nh)
                    
                if ban:
                    bw = int(ban.width * (t_size[1] / ban.height))
                    nw, nh = max(1, int(bw * state["banner_scale"]/100.0)), max(1, int(t_size[1] * state["banner_scale"]/100.0))
                    ban_res = ban.resize((nw, nh), resample_filter)
                    ban_x, ban_y = state["banner_x"], state["banner_y"]
                    canvas.paste(ban_res, (ban_x, ban_y), ban_res)
                    bboxes["banner"] = (ban_x, ban_y, ban_x+nw, ban_y+nh)
                    
                if state["top_logo"]:
                    lp = get_asset_path(state["top_logo"])
                    if os.path.exists(lp):
                        logo = Image.open(lp).convert("RGBA")
                        bw = int(t_size[0] * 0.35)
                        bh = int(logo.height * (bw / logo.width))
                        lsc = state["logo_scale"]/100.0
                        nw, nh = max(1, int(bw*lsc)), max(1, int(bh*lsc))
                        lres = logo.resize((nw, nh), resample_filter)
                        logo_x = t_size[0] - nw - 20 + state["logo_x"]
                        logo_y = 20 + state["logo_y"]
                        canvas.paste(lres, (logo_x, logo_y), lres)
                        bboxes["logo"] = (logo_x, logo_y, logo_x+nw, logo_y+nh)

                if state["show_markdown"]:
                    bp = 40
                    if state["markdown_logo"]:
                        mp = get_asset_path(state["markdown_logo"])
                        if os.path.exists(mp):
                            md = Image.open(mp).convert("RGBA")
                            bh = 150
                            bw = int(md.width * (bh / md.height))
                            msc = state["md_logo_scale"]/100.0
                            nw, nh = max(1, int(bw*msc)), max(1, int(bh*msc))
                            mres = md.resize((nw, nh), resample_filter)
                            md_x = t_size[0] - nw - bp + state["md_logo_x"]
                            md_y = t_size[1] - nh - bp + state["md_logo_y"]
                            canvas.paste(mres, (md_x, md_y), mres)
                            bboxes["md_logo"] = (md_x, md_y, md_x+nw, md_y+nh)
                    
                    pr_x_anch = t_size[0] - 40
                    pr_y_anch = t_size[1] - 80
                    psc = state["price_scale"]/100.0
                    f_family = state.get("price_font_str", "")
                    
                    c_qcolor = QColor(state.get("price_color_hex", "#B40000"))
                    c_n = (c_qcolor.red(), c_qcolor.green(), c_qcolor.blue(), 255)
                    c_o = (108, 117, 125, 255)
                    
                    l_spacing = state.get("price_letter_spacing", 0)
                    
                    if state.get("individual_price_active", False) and path in self.individual_prices: price_data = self.individual_prices[path]
                    else: price_data = self.global_price
                        
                    p_new = price_data.get("new", "")
                    p_old = price_data.get("old", "")
                    
                    oh = 0
                    if p_old:
                        ox = pr_x_anch + state["price_old_x"]
                        oy = pr_y_anch + state["price_old_y"]
                        img_o = render_text_to_image(p_old, f_family, max(1, int(70*psc)), c_o, l_spacing)
                        if img_o.width > 1:
                            px = ox - img_o.width
                            py = oy - img_o.height
                            canvas.paste(img_o, (px, py), img_o)
                            ly = py + img_o.height // 2
                            draw = ImageDraw.Draw(canvas)
                            draw.line([(px - 5, ly), (px + img_o.width + 5, ly)], fill=c_n, width=max(1, int(state["strike_width"]*psc)))
                            oh = img_o.height + 10
                            bboxes["price_old"] = (px, py, px + img_o.width, py + img_o.height)
                    
                    if p_new:
                        nx = pr_x_anch + state["price_new_x"]
                        ny = pr_y_anch - oh + state["price_new_y"]
                        img_n = render_text_to_image(p_new, f_family, max(1, int(100*psc)), c_n, l_spacing)
                        if img_n.width > 1:
                            px_n = nx - img_n.width
                            py_n = ny - img_n.height
                            canvas.paste(img_n, (px_n, py_n), img_n)
                            bboxes["price_new"] = (px_n, py_n, px_n + img_n.width, py_n + img_n.height)

            elif mode == "regular":
                if self.fill_settings.get(path, False): res = ImageOps.fit(orig, t_size, method=resample_filter)
                else: res = ImageOps.pad(orig, t_size, method=resample_filter, color=(255, 255, 255, 255))
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
                        w_font_str = cfg.get("font_str", "")
                        
                        hex_c = cfg.get("color_hex", "#000000")
                        qc = QColor(hex_c)
                        col = (qc.red(), qc.green(), qc.blue(), int(255 * op))
                        
                        wm = render_text_to_image(txt, w_font_str, f_size, col, letter_spacing=0)
                        if wm.width <= 1: continue
                    else:
                        wp = get_asset_path(wname)
                        if not os.path.exists(wp): continue
                        orig_wm = Image.open(wp).convert("RGBA")
                        ww = max(1, int(dim * wsc * 0.85))
                        wh = max(1, int(ww * (orig_wm.height/orig_wm.width)))
                        wm = orig_wm.resize((ww, wh), resample_filter)
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
                        x_pos = x + cfg.get("dx", 0)
                        y_pos = y + cfg.get("dy", 0)
                        canvas.paste(wm, (x_pos, y_pos), wm)
                        bboxes[f"wm_{wname}"] = (x_pos, y_pos, x_pos + wm.width, y_pos + wm.height)

            return canvas.convert("RGB"), bboxes
        except Exception: 
            return None, {}
    
    def render_cover_preview(self, fast_mode=False):
        t = self.get_cover_targets()
        if not t:
            if hasattr(self, 'cov_preview_lbl'):
                self.cov_preview_lbl.setPixmap(QPixmap())
                self.cov_preview_lbl.setText("Нет фото")
            return
        idx = self.current_cover_preview_idx % len(t)
        self.lbl_cov_title.setText(f"Превью (Фото {idx+1} из {len(t)}):")
        img, bboxes = self.build_final_image(t[idx], "cover", fast_mode=fast_mode)
        if img:
            t_img = img.copy()
            resample_filter = Image.Resampling.NEAREST if fast_mode else Image.Resampling.LANCZOS
            t_img.thumbnail((800, 600), resample_filter)
            self.cov_preview_lbl.set_preview(pil_to_pixmap(t_img), bboxes, (img.width, img.height))
        else: self.cov_preview_lbl.setText("Ошибка рендера")

    def render_out_preview(self, fast_mode=False):
        if self.cb_out_files.currentIndex() < 0 or not self.files:
            self.lbl_out_prev.setPixmap(QPixmap())
            self.lbl_out_prev.setText("Нет фото")
            return
        idx = self.cb_out_files.currentIndex() % len(self.files)
        img, bboxes = self.build_final_image(self.files[idx], "regular", fast_mode=fast_mode)
        if img:
            t_img = img.copy()
            resample_filter = Image.Resampling.NEAREST if fast_mode else Image.Resampling.LANCZOS
            t_img.thumbnail((800, 600), resample_filter)
            self.lbl_out_prev.set_preview(pil_to_pixmap(t_img), bboxes, (img.width, img.height))
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
        if idx == 1: self.request_cover_preview(150)
        elif idx == 2: self.request_wm_preview(150)
        elif idx == 3: self.request_out_preview(150)

if __name__ == "__main__":
    if not os.path.exists(GENERAL_CONFIG_FILE):
        os.makedirs(ASSETS_DIR, exist_ok=True)
        with open(GENERAL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"sizes": ["1200x900", "900x900"], "remember_files": False, "cached_files": [], "theme": "light"}, f, ensure_ascii=False)
            
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())