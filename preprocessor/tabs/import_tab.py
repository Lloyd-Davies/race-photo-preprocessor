"""Import tab — folder picker and thumbnail grid."""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QObject,
    QRunnable,
    Qt,
    QThread,
    QThreadPool,
    Signal,
    Slot,
)
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap, QImage
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import preprocessor.config as cfg

if TYPE_CHECKING:
    from preprocessor.main_window import MainWindow

THUMB_SIZE = 160
VALID_EXTS = {".jpg", ".jpeg", ".JPG", ".JPEG"}


# ── Thumbnail loader (runs in thread pool) ────────────────────────────────────

class _ThumbSignals(QObject):
    done = Signal(int, QPixmap)   # (list_index, pixmap)


class _ThumbTask(QRunnable):
    def __init__(self, index: int, path: str, signals: _ThumbSignals) -> None:
        super().__init__()
        self._index = index
        self._path = path
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            from PIL import Image, ImageOps  # type: ignore[import-untyped]

            with Image.open(self._path) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
                # Convert to RGB for QImage
                if img.mode != "RGB":
                    img = img.convert("RGB")
                data = img.tobytes()
                qimg = QImage(
                    data,
                    img.width,
                    img.height,
                    img.width * 3,
                    QImage.Format.Format_RGB888,
                )
                pixmap = QPixmap.fromImage(qimg)
        except Exception:
            # Fallback: grey placeholder
            pixmap = QPixmap(THUMB_SIZE, THUMB_SIZE)
            pixmap.fill(Qt.GlobalColor.darkGray)

        self._signals.done.emit(self._index, pixmap)


# ── Thumbnail grid item ───────────────────────────────────────────────────────

class _ImageItem(QListWidgetItem):
    def __init__(self, path: str, valid: bool = True) -> None:
        super().__init__()
        self.path = path
        self.valid = valid
        name = Path(path).name
        # Truncate long names for display
        display = name if len(name) <= 20 else name[:17] + "…"
        self.setText(display)
        self.setToolTip(path)
        if not valid:
            self.setForeground(Qt.GlobalColor.darkGray)

        # Placeholder icon while loading
        placeholder = QPixmap(THUMB_SIZE, THUMB_SIZE)
        placeholder.fill(Qt.GlobalColor.darkGray)
        self.setIcon(QIcon(placeholder))

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self.setIcon(QIcon(pixmap))


# ── Import tab ────────────────────────────────────────────────────────────────

class ImportTab(QWidget):
    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent)
        self._main = parent
        self._items: list[_ImageItem] = []
        self._pool = QThreadPool.globalInstance()
        self._signals = _ThumbSignals()
        self._signals.done.connect(self._on_thumb_done)

        self.setAcceptDrops(True)
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._folder_btn = QPushButton("Open Folder…")
        self._folder_btn.clicked.connect(self._pick_folder)
        toolbar.addWidget(self._folder_btn)

        self._folder_label = QLabel("No folder selected")
        self._folder_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        self._folder_label.setWordWrap(False)
        toolbar.addWidget(self._folder_label, 1)

        select_all_btn = QPushButton("Select All")
        select_all_btn.setProperty("secondary", True)
        select_all_btn.clicked.connect(self._select_all)
        toolbar.addWidget(select_all_btn)

        deselect_btn = QPushButton("Deselect All")
        deselect_btn.setProperty("secondary", True)
        deselect_btn.clicked.connect(self._deselect_all)
        toolbar.addWidget(deselect_btn)

        root.addLayout(toolbar)

        # ── Drop hint ─────────────────────────────────────────────────────────
        self._drop_hint = QLabel(
            "Drop a folder of JPEGs here, or use Open Folder above"
        )
        self._drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_hint.setStyleSheet(
            "color: #4b5563; font-size: 14px; padding: 60px 0;"
        )

        # ── Grid ──────────────────────────────────────────────────────────────
        self._grid = QListWidget()
        self._grid.setViewMode(QListWidget.ViewMode.IconMode)
        self._grid.setIconSize(
            self._grid.iconSize().__class__(THUMB_SIZE, THUMB_SIZE)
        )
        self._grid.setGridSize(
            self._grid.gridSize().__class__(THUMB_SIZE + 30, THUMB_SIZE + 40)
        )
        self._grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._grid.setMovement(QListWidget.Movement.Static)
        self._grid.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._grid.setUniformItemSizes(True)
        self._grid.setSpacing(6)
        self._grid.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self._grid.hide()

        root.addWidget(self._drop_hint, 1)
        root.addWidget(self._grid, 1)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QHBoxLayout()
        self._count_label = QLabel("0 images selected")
        self._count_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        footer.addWidget(self._count_label)
        footer.addStretch()

        self._total_label = QLabel()
        self._total_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        footer.addWidget(self._total_label)

        root.addLayout(footer)

    # ── Drag and drop ─────────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if os.path.isdir(path):
            self._load_folder(path)
        elif os.path.isfile(path):
            self._load_folder(str(Path(path).parent))
        event.acceptProposedAction()

    # ── Folder loading ────────────────────────────────────────────────────────

    def _pick_folder(self) -> None:
        start = cfg.get_last_import_folder() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Select photo folder", start)
        if folder:
            self._load_folder(folder)

    def _load_folder(self, folder: str) -> None:
        cfg.set_last_import_folder(folder)
        self._folder_label.setText(folder)

        # Collect files
        folder_path = Path(folder)
        all_files = sorted(folder_path.iterdir())

        jpeg_files: list[Path] = []
        other_files: list[Path] = []
        for f in all_files:
            if f.is_file():
                if f.suffix in VALID_EXTS:
                    jpeg_files.append(f)
                else:
                    other_files.append(f)

        self._grid.clear()
        self._items.clear()

        if not jpeg_files and not other_files:
            self._drop_hint.setText("No image files found in this folder.")
            self._drop_hint.show()
            self._grid.hide()
            self._update_footer()
            return

        self._drop_hint.hide()
        self._grid.show()

        # Add JPEG items
        for i, f in enumerate(jpeg_files):
            item = _ImageItem(str(f), valid=True)
            self._grid.addItem(item)
            self._items.append(item)
            # Queue thumbnail load
            task = _ThumbTask(i, str(f), self._signals)
            self._pool.start(task)

        # Add non-JPEG items (greyed out, non-selectable)
        for f in other_files:
            item = _ImageItem(str(f), valid=False)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._grid.addItem(item)

        # Auto-select all valid images
        self._select_all()
        self._update_footer()

        # Notify sibling tabs
        self._main.set_status(
            f"Loaded {len(jpeg_files)} images"
            + (f" ({len(other_files)} skipped)" if other_files else "")
        )

    # ── Thumbnail callback ────────────────────────────────────────────────────

    @Slot(int, QPixmap)
    def _on_thumb_done(self, index: int, pixmap: QPixmap) -> None:
        if index < len(self._items):
            self._items[index].set_pixmap(pixmap)

    # ── Selection helpers ─────────────────────────────────────────────────────

    def _select_all(self) -> None:
        self._grid.selectAll()

    def _deselect_all(self) -> None:
        self._grid.clearSelection()

    def _on_selection_changed(self) -> None:
        self._update_footer()

    def _update_footer(self) -> None:
        selected = len([
            i for i in self._grid.selectedItems()
            if isinstance(i, _ImageItem) and i.valid
        ])
        total = len(self._items)
        self._count_label.setText(f"{selected} of {total} images selected")
        self._total_label.setText(f"{total} total")

    # ── Public API ────────────────────────────────────────────────────────────

    def selected_paths(self) -> list[str]:
        """Return file paths of all selected valid images."""
        return [
            i.path
            for i in self._grid.selectedItems()
            if isinstance(i, _ImageItem) and i.valid
        ]

    def all_paths(self) -> list[str]:
        """Return all valid image paths regardless of selection."""
        return [i.path for i in self._items]
