import os
import sys
import math
import shutil
import ctypes
import hashlib
import subprocess
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPointF, QRectF, QTimer
from PyQt6.QtGui import QFont, QPainter, QPainterPath, QLinearGradient, QRadialGradient, QColor, QPen
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QProgressBar, QTextEdit,
    QMessageBox, QFrame, QScrollArea, QGraphicsDropShadowEffect, QTabWidget, QFileDialog
)

USER_PROFILE = os.environ.get("USERPROFILE", "C:\\Users\\User")
APP_NAME = "Tweak Pencinta Hanzala Saputra"
VERSION = "2.0 Ultimate"

DEEP_TEMP_DIRS = {
    "User Temp": os.path.join(USER_PROFILE, "AppData", "Local", "Temp"),
    "Windows Temp": "C:\\Windows\\Temp",
    "Prefetch": "C:\\Windows\\Prefetch",
    "Recent Files": os.path.join(USER_PROFILE, "AppData", "Roaming", "Microsoft", "Windows", "Recent"),
    "Chrome Cache": os.path.join(USER_PROFILE, "AppData", "Local", "Google", "Chrome", "User Data", "Default", "Cache"),
    "Edge Cache": os.path.join(USER_PROFILE, "AppData", "Local", "Microsoft", "Edge", "User Data", "Default", "Cache"),
    "Windows Update": "C:\\Windows\\SoftwareDistribution\\Download",
    "Thumbnail Cache": os.path.join(USER_PROFILE, "AppData", "Local", "Microsoft", "Windows", "Explorer"),
    "Crash Dumps": os.path.join(USER_PROFILE, "AppData", "Local", "CrashDumps"),
}

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0: return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def get_dir_size(path):
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False): total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False): total += get_dir_size(entry.path)
                except (PermissionError, FileNotFoundError, OSError): pass
    except (PermissionError, FileNotFoundError, OSError): pass
    return total

def get_file_hash(filepath, block_size=65536):
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            buf = f.read(block_size)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(block_size)
        return hasher.hexdigest()
    except Exception: return None

def clean_dir(path, log_callback):
    deleted_files = 0
    freed_space = 0
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            filepath = os.path.join(root, name)
            try:
                size = os.path.getsize(filepath)
                os.remove(filepath)
                deleted_files += 1
                freed_space += size
            except Exception: pass
        for name in dirs:
            try: shutil.rmtree(os.path.join(root, name), ignore_errors=True)
            except Exception: pass
    log_callback(f"  [OK] {path} -> {deleted_files} file dihapus.")
    return deleted_files, freed_space

class ScannerThread(QThread):
    update_log = pyqtSignal(str)
    scan_done = pyqtSignal(dict)
    def run(self):
        results = {}
        self.update_log.emit("Memulai Deep Scan file sampah...\n")
        for name, path in DEEP_TEMP_DIRS.items():
            if os.path.exists(path):
                self.update_log.emit(f"Scanning: {name}...")
                size = get_dir_size(path)
                results[name] = {"path": path, "size": size}
                self.update_log.emit(f"  -> Ditemukan {format_size(size)}\n")
        self.scan_done.emit(results)

class DuplicateScannerThread(QThread):
    update_log = pyqtSignal(str)
    scan_done = pyqtSignal(dict)
    def __init__(self, target_dir):
        super().__init__()
        self.target_dir = target_dir
    def run(self):
        self.update_log.emit(f"Memulai scan duplikat di: {self.target_dir}\n")
        size_map = {}
        for root, dirs, files in os.walk(self.target_dir):
            for name in files:
                filepath = os.path.join(root, name)
                try:
                    size = os.path.getsize(filepath)
                    if size > 1024 * 1024:
                        if size not in size_map: size_map[size] = []
                        size_map[size].append(filepath)
                except Exception: pass
        self.update_log.emit(f"Ditemukan {len(size_map)} grup ukuran file. Memeriksa hash (mohon tunggu)...")
        duplicates = {}
        for size, paths in size_map.items():
            if len(paths) > 1:
                hash_map = {}
                for p in paths:
                    h = get_file_hash(p)
                    if h:
                        if h not in hash_map: hash_map[h] = []
                        hash_map[h].append(p)
                for h, h_paths in hash_map.items():
                    if len(h_paths) > 1:
                        duplicates[f"Dup_{h[:8]}"] = {"paths": h_paths, "size": size}
        self.scan_done.emit(duplicates)

class CleanerThread(QThread):
    update_log = pyqtSignal(str)
    clean_done = pyqtSignal(int, int)
    def __init__(self, paths_to_clean):
        super().__init__()
        self.paths = paths_to_clean
    def run(self):
        total_files = 0
        total_freed = 0
        self.update_log.emit("\n--- MEMULAI PEMBERSIHAN ---\n")
        for name, path in self.paths.items():
            self.update_log.emit(f"Membersihkan {name}...")
            files, freed = clean_dir(path, self.update_log.emit)
            total_files += files
            total_freed += freed
        self.update_log.emit("Mengosongkan Recycle Bin...")
        try:
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x00000001 | 0x00000002 | 0x00000004)
            self.update_log.emit("  [OK] Recycle Bin dikosongkan.\n")
        except Exception: pass
        self.clean_done.emit(total_files, total_freed)

class DuplicateCleanerThread(QThread):
    update_log = pyqtSignal(str)
    clean_done = pyqtSignal(int, int)
    def __init__(self, paths_to_delete):
        super().__init__()
        self.paths = paths_to_delete
    def run(self):
        total_files = 0
        total_freed = 0
        self.update_log.emit("\n--- MENGHAPUS FILE DUPLIKAT ---\n")
        for p in self.paths:
            try:
                size = os.path.getsize(p)
                os.remove(p)
                total_files += 1
                total_freed += size
                self.update_log.emit(f"  [HAPUS] {p}")
            except Exception: pass
        self.clean_done.emit(total_files, total_freed)

class SystemOptimizerThread(QThread):
    update_log = pyqtSignal(str)
    done = pyqtSignal()
    def run(self):
        self.update_log.emit("\n--- OPTIMASI SISTEM ---")
        self.update_log.emit("1. Membersihkan RAM (Working Set)...")
        try:
            ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
            self.update_log.emit("   [OK] RAM dibersihkan.")
        except Exception as e: self.update_log.emit(f"   [GAGAL] {e}")
        self.update_log.emit("2. Flush DNS Cache...")
        try:
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True)
            self.update_log.emit("   [OK] DNS di-flush.")
        except Exception as e: self.update_log.emit(f"   [GAGAL] {e}")
        self.update_log.emit("3. Reset TCP/IP Stack...")
        try:
            subprocess.run(["netsh", "int", "ip", "reset"], capture_output=True)
            self.update_log.emit("   [OK] TCP/IP di-reset (Perlu restart).")
        except Exception as e: self.update_log.emit(f"   [GAGAL] {e}")
        self.done.emit()

class GlassCard(QFrame):
    def __init__(self, radius=18, tint_alpha=24, parent=None):
        super().__init__(parent)
        self.radius = radius
        self.tint_alpha = tint_alpha
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5)
        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)
        bg_grad = QLinearGradient(0, 0, self.width() * 0.4, self.height())
        bg_grad.setColorAt(0.0, QColor(255, 255, 255, self.tint_alpha + 24))
        bg_grad.setColorAt(0.45, QColor(255, 255, 255, self.tint_alpha))
        bg_grad.setColorAt(1.0, QColor(220, 240, 255, max(8, self.tint_alpha - 6)))
        painter.fillPath(path, bg_grad)
        border_grad = QLinearGradient(0, 0, self.width(), self.height())
        border_grad.setColorAt(0.0, QColor(255, 255, 255, 130))
        border_grad.setColorAt(0.5, QColor(255, 255, 255, 32))
        border_grad.setColorAt(1.0, QColor(180, 230, 255, 78))
        painter.setPen(QPen(border_grad, 1.1))
        painter.drawPath(path)

class FolderItemCard(GlassCard):
    def __init__(self, name, path, size, is_dup=False, parent=None):
        super().__init__(radius=14, tint_alpha=22, parent=parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(not is_dup)
        layout.addWidget(self.checkbox)
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        lbl_name = QLabel(name)
        lbl_name.setStyleSheet("color: rgba(255, 255, 255, 245); font-size: 13px; font-weight: 600; background: transparent;")
        lbl_path = QLabel(path)
        lbl_path.setStyleSheet("color: rgba(215, 232, 250, 145); font-size: 11px; background: transparent;")
        lbl_path.setWordWrap(True)
        text_box.addWidget(lbl_name)
        text_box.addWidget(lbl_path)
        layout.addLayout(text_box, 1)
        size_badge = QLabel(format_size(size))
        size_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size_badge.setStyleSheet("QLabel { color: #e0f7ff; background-color: rgba(56, 189, 248, 45); border: 1px solid rgba(186, 230, 253, 95); border-radius: 11px; padding: 4px 10px; font-size: 11px; font-weight: 600; }")
        layout.addWidget(size_badge)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.checkbox.isEnabled():
            self.checkbox.toggle()
        super().mousePressEvent(event)

class LiquidGlassCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.phase = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(40)
    def _animate(self):
        self.phase += 0.015
        self.update()
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(1.0, 1.0, w - 2.0, h - 2.0)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(rect, 26, 26)
        painter.setClipPath(clip_path)
        base_grad = QLinearGradient(0, 0, w, h)
        base_grad.setColorAt(0.0, QColor(14, 22, 38, 228))
        base_grad.setColorAt(0.5, QColor(18, 26, 46, 220))
        base_grad.setColorAt(1.0, QColor(12, 20, 36, 232))
        painter.fillPath(clip_path, base_grad)
        orbs = [
            (w * (0.18 + 0.08 * math.sin(self.phase)), h * (0.16 + 0.06 * math.cos(self.phase * 0.8)), w * 0.48, QColor(56, 189, 248, 82)),
            (w * (0.84 + 0.07 * math.cos(self.phase * 0.7)), h * (0.28 + 0.08 * math.sin(self.phase * 0.9)), w * 0.45, QColor(129, 140, 248, 72)),
            (w * (0.48 + 0.10 * math.sin(self.phase * 0.6 + 1.5)), h * (0.86 + 0.05 * math.cos(self.phase * 0.7)), w * 0.50, QColor(45, 212, 191, 65)),
        ]
        for cx, cy, radius, color in orbs:
            grad = QRadialGradient(QPointF(cx, cy), radius)
            grad.setColorAt(0.0, color)
            grad.setColorAt(0.55, QColor(color.red(), color.green(), color.blue(), 22))
            grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.fillRect(self.rect(), grad)
        sheen = QLinearGradient(0, 0, w * 0.6, h * 0.7)
        sheen.setColorAt(0.0, QColor(255, 255, 255, 42))
        sheen.setColorAt(0.32, QColor(255, 255, 255, 10))
        sheen.setColorAt(0.65, QColor(255, 255, 255, 0))
        sheen.setColorAt(1.0, QColor(200, 235, 255, 18))
        painter.fillPath(clip_path, sheen)
        painter.setClipping(False)
        rim_grad = QLinearGradient(0, 0, w, h)
        rim_grad.setColorAt(0.0, QColor(255, 255, 255, 185))
        rim_grad.setColorAt(0.35, QColor(186, 230, 253, 65))
        rim_grad.setColorAt(0.75, QColor(255, 255, 255, 35))
        rim_grad.setColorAt(1.0, QColor(165, 243, 252, 130))
        painter.setPen(QPen(rim_grad, 1.5))
        painter.drawPath(clip_path)

class CleanerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} - {VERSION}")
        self.resize(850, 750)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._drag_pos = None
        self.checkboxes = {}
        self.dup_checkboxes = {}
        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        outer = QWidget()
        outer.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(16, 16, 16, 16)
        self.setCentralWidget(outer)
        self.canvas = LiquidGlassCanvas()
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.canvas.setGraphicsEffect(shadow)
        outer_layout.addWidget(self.canvas)
        layout = QVBoxLayout(self.canvas)
        layout.setContentsMargins(24, 18, 24, 24)
        layout.setSpacing(14)

        title_bar = QHBoxLayout()
        title_bar.setSpacing(10)
        app_badge = QLabel("●  Tweak Pencinta")
        app_badge.setStyleSheet("QLabel { color: rgba(255, 255, 255, 235); font-size: 12px; font-weight: 700; letter-spacing: 0.5px; background: rgba(255, 255, 255, 20); border: 1px solid rgba(255, 255, 255, 55); border-radius: 12px; padding: 4px 12px; }")
        title_bar.addWidget(app_badge)
        title_bar.addStretch()
        self.btn_min = QPushButton("–")
        self.btn_min.setObjectName("winBtn")
        self.btn_min.setFixedSize(30, 30)
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close = QPushButton("×")
        self.btn_close.setObjectName("closeBtn")
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.clicked.connect(self.close)
        title_bar.addWidget(self.btn_min)
        title_bar.addWidget(self.btn_close)
        layout.addLayout(title_bar)

        header_card = GlassCard(radius=20, tint_alpha=28)
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(20, 16, 20, 16)
        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        header = QLabel(APP_NAME)
        header.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.setStyleSheet("color: #ffffff; background: transparent;")
        subheader = QLabel("Pembersih Mendalam, Pencari Duplikat, dan Optimasi Sistem Windows.")
        subheader.setStyleSheet("color: rgba(226, 240, 255, 185); font-size: 12px; background: transparent;")
        title_col.addWidget(header)
        title_col.addWidget(subheader)
        header_layout.addLayout(title_col, 1)
        self.total_pill = QLabel("Siap")
        self.total_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_pill.setStyleSheet("QLabel { color: #f0f9ff; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(56, 189, 248, 70), stop:1 rgba(129, 140, 248, 70)); border: 1px solid rgba(255, 255, 255, 110); border-radius: 16px; padding: 8px 16px; font-size: 12px; font-weight: 700; }")
        header_layout.addWidget(self.total_pill)
        layout.addWidget(header_card)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("glassTabs")
        self.tab_sampah = QWidget()
        self.tab_dup = QWidget()
        self.tab_opt = QWidget()
        self.tabs.addTab(self.tab_sampah, "Pembersih Sampah")
        self.tabs.addTab(self.tab_dup, "File Duplikat")
        self.tabs.addTab(self.tab_opt, "Optimasi Sistem")
        self._build_tab_sampah()
        self._build_tab_dup()
        self._build_tab_opt()
        layout.addWidget(self.tabs, 4)

        log_card = GlassCard(radius=18, tint_alpha=14)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(12, 10, 12, 10)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Log aktivitas...")
        log_layout.addWidget(self.log_box)
        layout.addWidget(log_card, 2)

    def _build_tab_sampah(self):
        t_layout = QVBoxLayout(self.tab_sampah)
        t_layout.setContentsMargins(0, 10, 0, 0)
        list_card = GlassCard(radius=20, tint_alpha=18)
        list_card_layout = QVBoxLayout(list_card)
        list_card_layout.setContentsMargins(12, 12, 12, 12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("glassScroll")
        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.list_layout.setSpacing(10)
        self.empty_hint = QLabel("Klik 'Scan' untuk mendeteksi file sampah.")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint.setStyleSheet("color: rgba(215, 232, 250, 140); font-size: 13px; padding: 36px; background: transparent;")
        self.list_layout.addWidget(self.empty_hint)
        scroll.setWidget(self.list_container)
        list_card_layout.addWidget(scroll)
        t_layout.addWidget(list_card, 1)
        btn_layout = QHBoxLayout()
        self.btn_scan = QPushButton("Scan Sampah")
        self.btn_scan.setObjectName("primaryGlassBtn")
        self.btn_scan.setFixedHeight(44)
        self.btn_scan.clicked.connect(self.start_scan)
        self.btn_clean = QPushButton("Bersihkan")
        self.btn_clean.setObjectName("dangerGlassBtn")
        self.btn_clean.setFixedHeight(44)
        self.btn_clean.clicked.connect(self.start_clean)
        self.btn_clean.setEnabled(False)
        btn_layout.addWidget(self.btn_scan)
        btn_layout.addWidget(self.btn_clean)
        t_layout.addLayout(btn_layout)
        self.progress_sampah = QProgressBar()
        self.progress_sampah.setTextVisible(False)
        self.progress_sampah.setFixedHeight(7)
        self.progress_sampah.hide()
        t_layout.addWidget(self.progress_sampah)

    def _build_tab_dup(self):
        t_layout = QVBoxLayout(self.tab_dup)
        t_layout.setContentsMargins(0, 10, 0, 0)
        list_card = GlassCard(radius=20, tint_alpha=18)
        list_card_layout = QVBoxLayout(list_card)
        list_card_layout.setContentsMargins(12, 12, 12, 12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("glassScroll")
        self.dup_container = QWidget()
        self.dup_container.setStyleSheet("background: transparent;")
        self.dup_layout = QVBoxLayout(self.dup_container)
        self.dup_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.dup_layout.setSpacing(10)
        self.dup_hint = QLabel("Pilih folder target dan klik 'Scan Duplikat'.")
        self.dup_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dup_hint.setStyleSheet("color: rgba(215, 232, 250, 140); font-size: 13px; padding: 36px; background: transparent;")
        self.dup_layout.addWidget(self.dup_hint)
        scroll.setWidget(self.dup_container)
        list_card_layout.addWidget(scroll)
        t_layout.addWidget(list_card, 1)
        path_row = QHBoxLayout()
        self.lbl_dup_path = QLabel("Target: " + os.path.join(USER_PROFILE, "Downloads"))
        self.lbl_dup_path.setStyleSheet("color: #a5f3fc; font-size: 11px;")
        btn_browse = QPushButton("Ganti Folder")
        btn_browse.setFixedHeight(28)
        btn_browse.setStyleSheet("background: rgba(255,255,255,30); border-radius: 6px; color: white; padding: 0 10px;")
        btn_browse.clicked.connect(self._browse_dup_folder)
        path_row.addWidget(self.lbl_dup_path, 1)
        path_row.addWidget(btn_browse)
        t_layout.addLayout(path_row)
        btn_dup_layout = QHBoxLayout()
        self.btn_scan_dup = QPushButton("Scan Duplikat")
        self.btn_scan_dup.setObjectName("primaryGlassBtn")
        self.btn_scan_dup.setFixedHeight(44)
        self.btn_scan_dup.clicked.connect(self.start_dup_scan)
        self.btn_clean_dup = QPushButton("Hapus Duplikat")
        self.btn_clean_dup.setObjectName("dangerGlassBtn")
        self.btn_clean_dup.setFixedHeight(44)
        self.btn_clean_dup.clicked.connect(self.start_dup_clean)
        self.btn_clean_dup.setEnabled(False)
        btn_dup_layout.addWidget(self.btn_scan_dup)
        btn_dup_layout.addWidget(self.btn_clean_dup)
        t_layout.addLayout(btn_dup_layout)
        self.progress_dup = QProgressBar()
        self.progress_dup.setTextVisible(False)
        self.progress_dup.setFixedHeight(7)
        self.progress_dup.hide()
        t_layout.addWidget(self.progress_dup)
        self.dup_target_dir = os.path.join(USER_PROFILE, "Downloads")

    def _build_tab_opt(self):
        t_layout = QVBoxLayout(self.tab_opt)
        t_layout.setContentsMargins(10, 20, 10, 20)
        info_label = QLabel("Bersihkan RAM, Flush DNS, dan Reset Jaringan.\n\nPerhatian: Beberapa aksi mungkin memerlukan restart.")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: white; font-size: 14px;")
        t_layout.addWidget(info_label)
        t_layout.addStretch()
        self.btn_optimize = QPushButton("Jalankan Optimasi")
        self.btn_optimize.setObjectName("primaryGlassBtn")
        self.btn_optimize.setFixedHeight(50)
        self.btn_optimize.setFixedWidth(250)
        self.btn_optimize.clicked.connect(self.run_optimization)
        opt_btn_layout = QHBoxLayout()
        opt_btn_layout.addStretch()
        opt_btn_layout.addWidget(self.btn_optimize)
        opt_btn_layout.addStretch()
        t_layout.addLayout(opt_btn_layout)
        t_layout.addStretch()

    def _browse_dup_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder Target")
        if folder:
            self.dup_target_dir = folder
            self.lbl_dup_path.setText(f"Target: {folder}")

    def _apply_styles(self):
        self.setStyleSheet("""
            * { font-family: 'Segoe UI'; }
            QScrollArea#glassScroll { border: none; background: transparent; }
            QTabWidget#glassTabs::pane { border: 1px solid rgba(255,255,255,40); border-radius: 16px; background: rgba(255,255,255,10); }
            QTabBar::tab { background: rgba(255,255,255,20); color: white; padding: 8px 20px; border-radius: 8px; margin-right: 4px; font-weight: 600; border: 1px solid transparent; }
            QTabBar::tab:selected { background: rgba(56, 189, 248, 80); border: 1px solid rgba(255,255,255,100); }
            QCheckBox { background: transparent; spacing: 8px; }
            QCheckBox::indicator { width: 20px; height: 20px; border-radius: 7px; border: 1.5px solid rgba(255, 255, 255, 115); background-color: rgba(255, 255, 255, 22); }
            QCheckBox::indicator:hover { border: 1.5px solid rgba(186, 230, 253, 210); background-color: rgba(255, 255, 255, 40); }
            QCheckBox::indicator:checked { border: 1.5px solid rgba(186, 230, 253, 235); background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(56, 189, 248, 225), stop:1 rgba(99, 102, 241, 225)); }
            QPushButton#winBtn, QPushButton#closeBtn { background-color: rgba(255, 255, 255, 24); color: rgba(255, 255, 255, 230); border: 1px solid rgba(255, 255, 255, 65); border-radius: 15px; font-size: 16px; font-weight: bold; padding-bottom: 2px; }
            QPushButton#winBtn:hover { background-color: rgba(255, 255, 255, 55); border: 1px solid rgba(255, 255, 255, 130); }
            QPushButton#closeBtn:hover { background-color: rgba(244, 63, 94, 185); border: 1px solid rgba(255, 180, 195, 180); }
            QPushButton#primaryGlassBtn { color: #ffffff; font-size: 13px; font-weight: 700; border-radius: 22px; padding: 8px 20px; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(56, 189, 248, 175), stop:0.55 rgba(59, 130, 246, 165), stop:1 rgba(99, 102, 241, 175)); border: 1px solid rgba(255, 255, 255, 135); }
            QPushButton#primaryGlassBtn:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(96, 205, 255, 215), stop:0.55 rgba(80, 150, 255, 205), stop:1 rgba(129, 140, 248, 215)); border: 1px solid rgba(255, 255, 255, 200); }
            QPushButton#primaryGlassBtn:disabled { background: rgba(255, 255, 255, 20); color: rgba(255, 255, 255, 95); border: 1px solid rgba(255, 255, 255, 35); }
            QPushButton#dangerGlassBtn { color: #ffffff; font-size: 13px; font-weight: 700; border-radius: 22px; padding: 8px 20px; background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(251, 113, 133, 185), stop:1 rgba(225, 29, 72, 185)); border: 1px solid rgba(255, 215, 225, 145); }
            QPushButton#dangerGlassBtn:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(253, 140, 158, 220), stop:1 rgba(244, 63, 94, 220)); border: 1px solid rgba(255, 235, 240, 210); }
            QPushButton#dangerGlassBtn:disabled { background: rgba(255, 255, 255, 20); color: rgba(255, 255, 255, 95); border: 1px solid rgba(255, 255, 255, 35); }
            QProgressBar { background: rgba(255, 255, 255, 24); border: 1px solid rgba(255, 255, 255, 55); border-radius: 3px; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:0.5 #a5f3fc, stop:1 #818cf8); border-radius: 3px; }
            QTextEdit { background-color: rgba(6, 10, 20, 135); color: #7dd3fc; font-family: 'Consolas', 'Cascadia Mono', monospace; font-size: 11px; border: 1px solid rgba(255, 255, 255, 35); border-radius: 12px; padding: 8px; }
            QScrollBar:vertical { background: transparent; width: 7px; margin: 4px 0 4px 0; }
            QScrollBar::handle:vertical { background: rgba(255, 255, 255, 65); border-radius: 3px; min-height: 24px; }
            QScrollBar::handle:vertical:hover { background: rgba(186, 230, 253, 135); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()

    def _styled_message(self, icon, title, text, buttons=QMessageBox.StandardButton.Ok):
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        box.setStyleSheet("""
            QMessageBox { background-color: #131c30; color: #f0f9ff; }
            QLabel { color: #f0f9ff; font-size: 13px; }
            QPushButton { background-color: rgba(56, 189, 248, 180); color: white; border: 1px solid rgba(255, 255, 255, 110); border-radius: 12px; padding: 6px 18px; font-weight: 600; min-width: 72px; }
            QPushButton:hover { background-color: rgba(96, 205, 255, 220); }
        """)
        return box.exec()

    def log(self, text):
        self.log_box.append(text)
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def start_scan(self):
        self.btn_scan.setEnabled(False)
        self.btn_clean.setEnabled(False)
        self.total_pill.setText("Memindai Sampah...")
        self.log_box.clear()
        self.checkboxes.clear()
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.scanner = ScannerThread()
        self.scanner.update_log.connect(self.log)
        self.scanner.scan_done.connect(self.on_scan_done)
        self.progress_sampah.show()
        self.progress_sampah.setRange(0, 0)
        self.scanner.start()

    def on_scan_done(self, results):
        self.progress_sampah.hide()
        if not results:
            self.total_pill.setText("0 B")
            self.log("Tidak ada file sampah ditemukan.")
            self.btn_scan.setEnabled(True)
            return
        total_size = sum(data["size"] for data in results.values())
        self.total_pill.setText(f"Total: {format_size(total_size)}")
        for name, data in results.items():
            row = FolderItemCard(name, data["path"], data["size"], is_dup=False)
            self.list_layout.addWidget(row)
            self.checkboxes[name] = {"cb": row.checkbox, "path": data["path"]}
        self.btn_scan.setEnabled(True)
        self.btn_clean.setEnabled(True)

    def start_clean(self):
        paths_to_clean = {name: data["path"] for name, data in self.checkboxes.items() if data["cb"].isChecked()}
        if not paths_to_clean:
            self._styled_message(QMessageBox.Icon.Warning, "Peringatan", "Pilih minimal satu folder.")
            return
        reply = self._styled_message(QMessageBox.Icon.Question, "Konfirmasi", "Hapus file sampah ini secara permanen?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        self.btn_scan.setEnabled(False)
        self.btn_clean.setEnabled(False)
        self.total_pill.setText("Membersihkan...")
        for data in self.checkboxes.values(): data["cb"].setEnabled(False)
        self.progress_sampah.show()
        self.progress_sampah.setRange(0, 0)
        self.cleaner = CleanerThread(paths_to_clean)
        self.cleaner.update_log.connect(self.log)
        self.cleaner.clean_done.connect(self.on_clean_done)
        self.cleaner.start()

    def on_clean_done(self, total_files, total_freed):
        self.progress_sampah.hide()
        self.btn_scan.setEnabled(True)
        self.total_pill.setText(f"Bebas: {format_size(total_freed)}")
        msg = f"{total_files} file dihapus.\nRuang dibebaskan: {format_size(total_freed)}"
        self._styled_message(QMessageBox.Icon.Information, "Selesai", msg)
        self.log(f"\n=== SELESAI: {total_files} file, {format_size(total_freed)} dibebaskan ===")

    def start_dup_scan(self):
        self.btn_scan_dup.setEnabled(False)
        self.btn_clean_dup.setEnabled(False)
        self.total_pill.setText("Memindai Duplikat...")
        self.log_box.clear()
        self.dup_checkboxes.clear()
        while self.dup_layout.count():
            item = self.dup_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.dup_scanner = DuplicateScannerThread(self.dup_target_dir)
        self.dup_scanner.update_log.connect(self.log)
        self.dup_scanner.scan_done.connect(self.on_dup_scan_done)
        self.progress_dup.show()
        self.progress_dup.setRange(0, 0)
        self.dup_scanner.start()

    def on_dup_scan_done(self, duplicates):
        self.progress_dup.hide()
        if not duplicates:
            self.total_pill.setText("0 Duplikat")
            self.log("Tidak ada file duplikat besar ditemukan.")
            self.btn_scan_dup.setEnabled(True)
            return
        total_size = sum(data["size"] * (len(data["paths"]) - 1) for data in duplicates.values())
        self.total_pill.setText(f"Potensi: {format_size(total_size)}")
        for gid, data in duplicates.items():
            paths = data["paths"]
            size = data["size"]
            for i, p in enumerate(paths):
                name = f"[Asli] {os.path.basename(p)}" if i == 0 else f"[Duplikat] {os.path.basename(p)}"
                row = FolderItemCard(name, p, size, is_dup=(i != 0))
                self.dup_layout.addWidget(row)
                self.dup_checkboxes[p] = {"cb": row.checkbox, "path": p}
        self.btn_scan_dup.setEnabled(True)
        self.btn_clean_dup.setEnabled(True)

    def start_dup_clean(self):
        paths_to_clean = [p for p, data in self.dup_checkboxes.items() if data["cb"].isChecked()]
        if not paths_to_clean:
            self._styled_message(QMessageBox.Icon.Warning, "Peringatan", "Pilih file duplikat yang mau dihapus.")
            return
        reply = self._styled_message(QMessageBox.Icon.Warning, "Konfirmasi", f"Hapus {len(paths_to_clean)} file terpilih secara permanen?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes: return
        self.btn_scan_dup.setEnabled(False)
        self.btn_clean_dup.setEnabled(False)
        self.total_pill.setText("Menghapus...")
        for data in self.dup_checkboxes.values(): data["cb"].setEnabled(False)
        self.progress_dup.show()
        self.progress_dup.setRange(0, 0)
        self.dup_cleaner = DuplicateCleanerThread(paths_to_clean)
        self.dup_cleaner.update_log.connect(self.log)
        self.dup_cleaner.clean_done.connect(self.on_dup_clean_done)
        self.dup_cleaner.start()

    def on_dup_clean_done(self, total_files, total_freed):
        self.progress_dup.hide()
        self.btn_scan_dup.setEnabled(True)
        self.total_pill.setText(f"Bebas: {format_size(total_freed)}")
        msg = f"{total_files} file duplikat dihapus.\nRuang dibebaskan: {format_size(total_freed)}"
        self._styled_message(QMessageBox.Icon.Information, "Selesai", msg)
        self.log(f"\n=== SELESAI: {total_files} file duplikat, {format_size(total_freed)} dibebaskan ===")

    def run_optimization(self):
        self.btn_optimize.setEnabled(False)
        self.total_pill.setText("Optimasi...")
        self.log_box.clear()
        self.optimizer = SystemOptimizerThread()
        self.optimizer.update_log.connect(self.log)
        self.optimizer.done.connect(self.on_optimize_done)
        self.optimizer.start()

    def on_optimize_done(self):
        self.btn_optimize.setEnabled(True)
        self.total_pill.setText("Optimasi Selesai")
        self._styled_message(QMessageBox.Icon.Information, "Selesai", "Optimasi sistem berhasil dijalankan!")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CleanerApp()
    window.show()
    sys.exit(app.exec())