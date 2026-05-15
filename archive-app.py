import mimetypes
import os
import sqlite3
import subprocess
import sys
import tarfile
import zipfile
from datetime import datetime
from functools import partial

from PySide6.QtCore import (
    QDate,
    QItemSelectionModel,
    QLocale,
    QObject,
    QRunnable,
    QSize,
    QSettings,
    Qt,
    QThreadPool,
    QTimer,
    QTranslator,
    Signal,
    QModelIndex,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QImageReader,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from logic import ArchiveLogic

APP_VERSION = "1.3.1"
COPYRIGHT = "KlapkiSzatana"
PASTEL_FOLDER_COLORS = [
    ("Bez koloru", ""),
    ("Turkusowy", "#58D6C3"),
    ("Koralowy", "#FF8E72"),
    ("Jagodowy", "#8F9BFF"),
    ("Złoty", "#E9C94F"),
    ("Malinowy", "#FF6FA0"),
    ("Szmaragdowy", "#4FCB8D"),
    ("Śliwkowy", "#A774FF"),
    ("Morski", "#4DB8FF"),
    ("Bursztynowy", "#FFB347"),
    ("Limonkowy", "#9FD356"),
]
PASTEL_FOLDER_COLOR_NAMES = {
    value: label for label, value in PASTEL_FOLDER_COLORS if value
}
DEFAULT_NEW_FOLDER_COLOR = PASTEL_FOLDER_COLORS[1][1]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp", ".svg"}
TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".log",
    ".py",
    ".js",
    ".ts",
    ".css",
    ".html",
    ".htm",
    ".sql",
    ".eml",
}
OFFICE_EXTENSIONS = {
    ".doc",
    ".docx",
    ".odt",
    ".rtf",
    ".xls",
    ".xlsx",
    ".ods",
    ".ppt",
    ".pptx",
    ".odp",
    ".pps",
    ".ppsx",
    ".odg",
}
ARCHIVE_EXTENSIONS = {
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".bz2",
    ".tbz2",
    ".xz",
    ".txz",
}
MAX_TEXT_PREVIEW_BYTES = 1024 * 1024
ARCHIVE_ENTRY_LIMIT = 300


class FolderDialog(QDialog):
    """Zbiera nazwę folderu, kolor oraz flagę ważności."""

    def __init__(self, parent, title, name="", color=None, important=False, default_color=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(name)
        form.addRow("Nazwa:", self.name_edit)

        self.color_combo = QComboBox()
        for label, value in PASTEL_FOLDER_COLORS:
            self.color_combo.addItem(label, value)
            index = self.color_combo.count() - 1
            if value:
                self.color_combo.setItemData(index, QColor(value), Qt.BackgroundRole)
                self.color_combo.setItemData(index, QColor("#2D2A26"), Qt.ForegroundRole)

        selected_color = color if color is not None else (default_color or "")
        color_index = self.color_combo.findData(selected_color)
        if color_index >= 0:
            self.color_combo.setCurrentIndex(color_index)
        form.addRow("Kolor:", self.color_combo)

        self.important_check = QCheckBox("Oznacz jako ważny")
        self.important_check.setChecked(bool(important))
        form.addRow("Ważne:", self.important_check)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def folder_data(self):
        """Zwraca dane wpisane w formularzu folderu."""
        return {
            "name": self.name_edit.text().strip(),
            "color": self.color_combo.currentData(),
            "important": self.important_check.isChecked(),
        }


class DocumentDialog(QDialog):
    """Zbiera metadane dokumentu, w tym flagę ważności."""

    def __init__(
        self,
        parent,
        title,
        document_title="",
        description="",
        document_date=None,
        important=False,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit(document_title)
        form.addRow("Tytuł:", self.title_edit)

        self.date_edit = QDateEdit(calendarPopup=True)
        self.date_edit.setDate(document_date or QDate.currentDate())
        form.addRow("Data:", self.date_edit)

        self.description_edit = QPlainTextEdit(description)
        self.description_edit.setMinimumHeight(120)
        form.addRow("Opis:", self.description_edit)

        self.important_check = QCheckBox("Oznacz jako ważny")
        self.important_check.setChecked(bool(important))
        form.addRow("Ważne:", self.important_check)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def document_data(self):
        """Zwraca dane wpisane w formularzu dokumentu."""
        return {
            "title": self.title_edit.text().strip(),
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "description": self.description_edit.toPlainText().strip(),
            "important": self.important_check.isChecked(),
        }


class ArchiveItemDelegate(QStyledItemDelegate):
    """Rysuje czerwony znacznik dla elementów oznaczonych jako ważne."""

    def paint(self, painter, option, index):
        data = index.data(Qt.UserRole) or {}
        important = bool(data.get("important"))

        option_copy = QStyleOptionViewItem(option)
        if important:
            option_copy.rect = option_copy.rect.adjusted(18, 0, 0, 0)

            background_data = index.data(Qt.BackgroundRole)
            if option.state & QStyle.State_Selected:
                painter.fillRect(option.rect.adjusted(0, 0, -option.rect.width() + 18, 0), option.palette.highlight())
            elif isinstance(background_data, QBrush):
                painter.fillRect(option.rect.adjusted(0, 0, -option.rect.width() + 18, 0), background_data)

        super().paint(painter, option_copy, index)

        if not important:
            return

        marker_rect = option.rect.adjusted(4, 0, 0, 0)
        marker_rect.setWidth(14)

        painter.save()
        font = painter.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        painter.setFont(font)
        painter.setPen(QColor("#C62828"))
        painter.drawText(marker_rect, Qt.AlignCenter, "!")
        painter.restore()


class ProcessingDialog(QDialog):
    """Wyświetla modalne okno z paskiem postępu dla długich operacji."""

    def __init__(self, parent, title, message):
        """Buduje prosty dialog informujący o trwającym przetwarzaniu."""
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 120)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(message))

        self.pbar = QProgressBar()
        layout.addWidget(self.pbar)


class BackupRestoreDialog(QDialog):
    """Obsługuje ręczne wykonywanie kopii zapasowej i przywracanie danych."""

    def __init__(self, parent, logic, settings):
        """Inicjalizuje okno zarządzania kopiami zapasowymi."""
        super().__init__(parent)
        self.logic = logic
        self.settings = settings
        self.setWindowTitle("Kopia Zapasowa")
        self.setFixedSize(500, 220)

        layout = QVBoxLayout(self)

        group_box = QGroupBox("Zarządzanie kopiami")
        form = QFormLayout()

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setText(self.settings.value("last_backup_dir", ""))

        btn_browse = QPushButton("...")
        btn_browse.setFixedWidth(30)
        btn_browse.clicked.connect(self.select_backup_dir)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(btn_browse)

        form.addRow("Katalog kopii:", path_layout)
        group_box.setLayout(form)
        layout.addWidget(group_box)

        button_layout = QHBoxLayout()
        self.btn_create = QPushButton("📦 Utwórz kopię teraz")
        self.btn_restore = QPushButton("📥 Przywróć z kopii")
        self.btn_create.clicked.connect(self.do_backup)
        self.btn_restore.clicked.connect(self.do_restore)
        button_layout.addWidget(self.btn_create)
        button_layout.addWidget(self.btn_restore)
        layout.addLayout(button_layout)

        self.btns = QDialogButtonBox(QDialogButtonBox.Close)
        self.btns.rejected.connect(self.reject)
        layout.addWidget(self.btns)

    def select_backup_dir(self):
        """Pozwala wybrać katalog przechowywania kopii zapasowych."""
        directory = QFileDialog.getExistingDirectory(self, "Wybierz folder")
        if not directory:
            return

        self.path_edit.setText(directory)
        self.settings.setValue("last_backup_dir", directory)

    def _create_processing_dialog(self, title, message):
        """Tworzy dialog postępu używany podczas backupu i przywracania."""
        dialog = ProcessingDialog(self, title, message)
        dialog.show()
        return dialog

    @staticmethod
    def _update_progress(dialog, value):
        """Aktualizuje pasek postępu i odświeża interfejs w trakcie pracy."""
        dialog.pbar.setValue(value)
        QApplication.processEvents()

    def do_backup(self):
        """Tworzy kopię zapasową w wybranym katalogu."""
        directory = self.path_edit.text().strip()
        if not directory:
            QMessageBox.warning(self, "Błąd", "Wybierz katalog dla kopii zapasowej.")
            return

        file_path = os.path.join(
            directory,
            f"Archiwum_{datetime.now().strftime('%Y%m%d')}.zip",
        )
        dialog = self._create_processing_dialog("Backup", "Pakowanie danych...")
        success, message = self.logic.backup_all(
            file_path,
            partial(self._update_progress, dialog),
        )
        dialog.close()

        if success:
            QMessageBox.information(self, "OK", f"Kopia utworzona:\n{file_path}")
            return

        QMessageBox.warning(self, "Błąd", message)

    def do_restore(self):
        """Przywraca dane z wybranego pliku kopii i restartuje aplikację."""
        directory = self.path_edit.text().strip()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Wybierz plik",
            directory,
            "Kopia (*.zip)",
        )
        if not file_path:
            return

        answer = QMessageBox.question(self, "Potwierdzenie", "Nadpisać dane?")
        if answer != QMessageBox.Yes:
            return

        dialog = self._create_processing_dialog("Restore", "Przywracanie...")
        success = self.logic.restore_all(
            file_path,
            partial(self._update_progress, dialog),
        )
        dialog.close()

        if not success:
            QMessageBox.critical(self, "Błąd", "Błąd przywracania!")
            return

        QMessageBox.information(self, "OK", "Przywrócono dane. Aplikacja zostanie uruchomiona ponownie.")
        restart_application()


def _format_file_size(size):
    """Zamienia rozmiar pliku w bajtach na czytelny zapis dla użytkownika."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if unit == "B":
            if value < 1024:
                return f"{int(value)} {unit}"
        elif value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def _looks_like_text_file(path):
    """Heurystycznie rozpoznaje, czy plik nadaje się do wyświetlenia jako tekst."""
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type and (
        mime_type.startswith("text/")
        or mime_type in {"application/json", "application/xml", "application/x-sh"}
    ):
        return True

    with open(path, "rb") as handle:
        sample = handle.read(4096)

    if not sample:
        return True
    if b"\x00" in sample:
        return False

    printable = sum(
        1
        for byte in sample
        if byte in b"\t\n\r\f\b" or 32 <= byte <= 126 or byte >= 128
    )
    return printable / len(sample) >= 0.9


def _read_text_preview(path):
    """Wczytuje tekstowy podgląd pliku z limitem wielkości i prostym fallbackiem kodowania."""
    with open(path, "rb") as handle:
        raw = handle.read(MAX_TEXT_PREVIEW_BYTES + 1)

    truncated = len(raw) > MAX_TEXT_PREVIEW_BYTES
    raw = raw[:MAX_TEXT_PREVIEW_BYTES]

    for encoding in ("utf-8", "cp1250", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")

    if truncated:
        text += "\n\n[Podgląd skrócony do 1 MB]"
    return text


def _build_archive_preview(path):
    """Tworzy tekstową listę zawartości obsługiwanych archiwów."""
    lines = [f"Archiwum: {os.path.basename(path)}", ""]

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            lines.append(f"Liczba plików: {len(entries)}")
            lines.append("")
            for info in entries[:ARCHIVE_ENTRY_LIMIT]:
                marker = "/" if info.is_dir() else ""
                size = "-" if info.is_dir() else _format_file_size(info.file_size)
                lines.append(f"{info.filename}{marker}    {size}")
            if len(entries) > ARCHIVE_ENTRY_LIMIT:
                lines.append("")
                lines.append(f"... i jeszcze {len(entries) - ARCHIVE_ENTRY_LIMIT} pozycji")
            return "\n".join(lines)

    if tarfile.is_tarfile(path):
        with tarfile.open(path) as archive:
            entries = archive.getmembers()
            lines.append(f"Liczba plików: {len(entries)}")
            lines.append("")
            for info in entries[:ARCHIVE_ENTRY_LIMIT]:
                marker = "/" if info.isdir() else ""
                size = "-" if info.isdir() else _format_file_size(info.size)
                lines.append(f"{info.name}{marker}    {size}")
            if len(entries) > ARCHIVE_ENTRY_LIMIT:
                lines.append("")
                lines.append(f"... i jeszcze {len(entries) - ARCHIVE_ENTRY_LIMIT} pozycji")
            return "\n".join(lines)

    raise ValueError("Ten typ archiwum nie ma wbudowanego podglądu.")


def _build_binary_summary(path):
    """Buduje krótki opis pliku, gdy nie ma lepszego podglądu zawartości."""
    stat_result = os.stat(path)
    mime_type, _ = mimetypes.guess_type(path)
    extension = os.path.splitext(path)[1].lower() or "(brak)"

    return "\n".join(
        [
            f"Nazwa: {os.path.basename(path)}",
            f"Rozszerzenie: {extension}",
            f"Rozmiar: {_format_file_size(stat_result.st_size)}",
            f"MIME: {mime_type or 'nieznany'}",
            "",
            "Brak wbudowanego podglądu dla tego typu pliku.",
            "Kliknij dokument dwa razy, aby otworzyć go w zewnętrznej aplikacji.",
        ]
    )


def _detect_office_document(path):
    """Rozpoznaje dokumenty Office po rozszerzeniu, MIME lub strukturze archiwum."""
    extension = os.path.splitext(path)[1].lower()
    if extension in OFFICE_EXTENSIONS:
        return "Dokument Office"

    mime_type, _ = mimetypes.guess_type(path)
    if mime_type:
        if mime_type.startswith("application/vnd.oasis.opendocument"):
            return "Dokument OpenDocument"
        if mime_type.startswith("application/vnd.openxmlformats-officedocument"):
            return "Dokument Office Open XML"
        if mime_type in {
            "application/msword",
            "application/vnd.ms-excel",
            "application/vnd.ms-powerpoint",
            "application/rtf",
        }:
            return "Dokument Office"

    if not zipfile.is_zipfile(path):
        return None

    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())

            if "mimetype" in names:
                odf_mime = archive.read("mimetype").decode("utf-8", errors="replace").strip()
                if odf_mime.startswith("application/vnd.oasis.opendocument"):
                    return "Dokument OpenDocument"

            if "[Content_Types].xml" in names:
                if any(name.startswith("word/") for name in names):
                    return "Dokument Word"
                if any(name.startswith("xl/") for name in names):
                    return "Arkusz Excel"
                if any(name.startswith("ppt/") for name in names):
                    return "Prezentacja PowerPoint"
                return "Dokument Office Open XML"
    except (KeyError, OSError, zipfile.BadZipFile):
        return None

    return None


def _build_office_summary(path, office_type):
    """Buduje informację zastępczą dla dokumentów Office otwieranych zewnętrznie."""
    stat_result = os.stat(path)
    mime_type, _ = mimetypes.guess_type(path)
    extension = os.path.splitext(path)[1].lower() or "(brak)"

    return "\n".join(
        [
            f"Nazwa: {os.path.basename(path)}",
            f"Typ: {office_type}",
            f"Rozszerzenie: {extension}",
            f"Rozmiar: {_format_file_size(stat_result.st_size)}",
            f"MIME: {mime_type or 'nieznany'}",
            "",
            "Podgląd dla dokumentów Office jest wyłączony.",
            "Otwórz plik dwuklikiem, aby uruchomić go w zewnętrznej aplikacji.",
        ]
    )


def _resolve_preview_data(path):
    """Dobiera najlepszy sposób podglądu dla wskazanego pliku."""
    office_type = _detect_office_document(path)
    if office_type:
        return {
            "kind": "text",
            "content": _build_office_summary(path, office_type),
            "label": "Office",
        }

    extension = os.path.splitext(path)[1].lower()
    if extension in TEXT_EXTENSIONS or _looks_like_text_file(path):
        return {
            "kind": "text",
            "content": _read_text_preview(path),
            "label": "Tekst",
        }

    if extension in ARCHIVE_EXTENSIONS or zipfile.is_zipfile(path) or tarfile.is_tarfile(path):
        return {
            "kind": "text",
            "content": _build_archive_preview(path),
            "label": "Archiwum",
        }

    return {
        "kind": "text",
        "content": _build_binary_summary(path),
        "label": "Plik",
    }


class PreviewWorkerSignals(QObject):
    """Udostępnia sygnał z wynikiem generowania podglądu w tle."""

    finished = Signal(dict)


class PreviewWorker(QRunnable):
    """Przygotowuje dane podglądu w tle, aby nie blokować interfejsu."""

    def __init__(self, request_id, path):
        """Zapamiętuje identyfikator żądania i ścieżkę pliku do analizy."""
        super().__init__()
        self.request_id = request_id
        self.path = path
        self.signals = PreviewWorkerSignals()

    def run(self):
        """Generuje wynik podglądu i odsyła go do wątku GUI."""
        try:
            result = _resolve_preview_data(self.path)
        except Exception as exc:
            result = {
                "kind": "error",
                "message": str(exc) or "Nie udało się przygotować podglądu.",
            }

        result["request_id"] = self.request_id
        self.signals.finished.emit(result)


class DynamicPreviewLabel(QLabel):
    """Skaluje obraz do całego pola podglądu i przechwytuje kółko do zmiany stron."""

    resized = Signal()
    page_step_requested = Signal(int)

    def __init__(self):
        """Przygotowuje etykietę do wyświetlania podglądu obrazu."""
        super().__init__()
        self.pix = None
        self.wheel_paging_enabled = False
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: #000;")
        self.setMinimumSize(1, 1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_pixmap(self, pixmap):
        """Zapamiętuje oryginalny obraz i uruchamia jego przeskalowanie."""
        self.pix = pixmap
        super().setText("")
        self.update_scaling()

    def clear_pixmap(self):
        """Czyści obecny obraz, pozostawiając pusty stan kontrolki."""
        self.pix = None
        super().setPixmap(QPixmap())

    def set_wheel_paging_enabled(self, enabled):
        """Włącza lub wyłącza traktowanie kółka myszy jako zmiany strony."""
        self.wheel_paging_enabled = enabled

    def update_scaling(self):
        """Dopasowuje obraz do całego dostępnego pola, zachowując proporcje."""
        if not self.pix or self.pix.isNull():
            return

        available_width = max(1, self.width() - 24)
        available_height = max(1, self.height() - 24)
        scaled = self.pix.scaled(
            available_width,
            available_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        super().setPixmap(scaled)

    def resizeEvent(self, event):
        """Skaluje obraz po zmianie rozmiaru i informuje panel o nowym viewportcie."""
        self.update_scaling()
        self.resized.emit()
        super().resizeEvent(event)

    def wheelEvent(self, event):
        """Dla dokumentów wielostronicowych zamienia ruch kółka na zmianę strony."""
        if self.wheel_paging_enabled and event.angleDelta().y():
            step = 1 if event.angleDelta().y() < 0 else -1
            self.page_step_requested.emit(step)
            event.accept()
            return
        event.ignore()


class PreviewPanel(QWidget):
    """Wielotypowy panel podglądu dla obrazów, PDF i plików tekstowych."""

    def __init__(self):
        """Buduje pasek narzędzi oraz widoki używane przez różne typy plików."""
        super().__init__()
        self.request_id = 0
        self.thread_pool = QThreadPool.globalInstance()
        self.current_preview_kind = None
        self.current_pdf_page = 0
        self.pdf_mode_label = "PDF"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)

        self.mode_label = QLabel("Podgląd")
        self.page_label = QLabel("")

        self.btn_prev = QPushButton("◀")
        self.btn_next = QPushButton("▶")
        self.btn_prev.setFocusPolicy(Qt.NoFocus)
        self.btn_next.setFocusPolicy(Qt.NoFocus)
        self.btn_prev.setFixedWidth(42)
        self.btn_next.setFixedWidth(42)
        self.btn_prev.clicked.connect(self.show_previous_page)
        self.btn_next.clicked.connect(self.show_next_page)

        toolbar.addWidget(self.mode_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self.btn_prev)
        toolbar.addWidget(self.page_label)
        toolbar.addWidget(self.btn_next)

        self.stack = QStackedWidget()

        self.status_label = QLabel("Podgląd")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(
            "background: #101010; color: #f2f2f2; font-size: 16px; border: 1px solid #222;"
        )

        self.preview_label = DynamicPreviewLabel()
        self.preview_label.page_step_requested.connect(self._change_pdf_page)
        self.preview_label.resized.connect(self._handle_preview_resized)

        self.text_view = QPlainTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.text_view.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.text_view.setStyleSheet(
            "QPlainTextEdit { background: #101010; color: #f2f2f2; border: 1px solid #222; }"
        )

        self.pdf_document = QPdfDocument(self)
        self.pdf_document.statusChanged.connect(self._on_pdf_status_changed)
        self.pdf_document.pageCountChanged.connect(self._update_pdf_controls)

        self.pdf_render_timer = QTimer(self)
        self.pdf_render_timer.setSingleShot(True)
        self.pdf_render_timer.timeout.connect(self._render_current_pdf_page)

        self.stack.addWidget(self.status_label)
        self.stack.addWidget(self.preview_label)
        self.stack.addWidget(self.text_view)

        layout.addLayout(toolbar)
        layout.addWidget(self.stack, 1)

        self.show_message("Podgląd")

    def show_message(self, text, mode="Podgląd"):
        """Pokazuje prosty komunikat statusu zamiast właściwego podglądu."""
        self.current_preview_kind = None
        self.current_pdf_page = 0
        self.pdf_render_timer.stop()
        self.pdf_document.close()
        self.preview_label.set_wheel_paging_enabled(False)
        self.preview_label.clear_pixmap()
        self.text_view.clear()
        self.mode_label.setText(mode)
        self.page_label.setText("")
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.status_label.setText(text)
        self.stack.setCurrentWidget(self.status_label)

    def set_loading(self, text):
        """Pokazuje stan ładowania podczas pracy w tle."""
        self.show_message(text, "Ładowanie")

    def show_folder(self):
        """Pokazuje pusty stan dla zaznaczonego folderu."""
        self.request_id += 1
        self.show_message("Katalog")

    def preview_file(self, path):
        """Dobiera odpowiedni renderer i uruchamia podgląd wskazanego pliku."""
        self.request_id += 1

        if not path or not os.path.exists(path):
            self.show_message("Brak pliku")
            return

        extension = os.path.splitext(path)[1].lower()
        if extension in IMAGE_EXTENSIONS:
            self._show_image(path)
            return

        if extension == ".pdf":
            self._show_pdf(path, "PDF")
            return

        loading_message = "Ładowanie podglądu..."
        if extension in OFFICE_EXTENSIONS:
            loading_message = "Przygotowanie informacji o dokumencie Office..."
        elif extension in ARCHIVE_EXTENSIONS:
            loading_message = "Odczyt archiwum..."

        self.set_loading(loading_message)
        worker = PreviewWorker(self.request_id, path)
        worker.signals.finished.connect(self._handle_worker_result)
        self.thread_pool.start(worker)

    def _show_image(self, path):
        """Wczytuje obraz lokalnie i dopasowuje go do całego obszaru podglądu."""
        self.current_preview_kind = "image"
        self.current_pdf_page = 0
        self.pdf_render_timer.stop()
        self.pdf_document.close()
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            self.show_message("Błąd obrazu")
            return

        self.preview_label.set_wheel_paging_enabled(False)
        self.preview_label.set_pixmap(QPixmap.fromImage(image))
        self.mode_label.setText("Obraz")
        self.page_label.setText("1 / 1")
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.stack.setCurrentWidget(self.preview_label)

    def _show_text(self, text, mode):
        """Wyświetla tekstowy podgląd pliku lub opis fallbackowy."""
        self.current_preview_kind = "text"
        self.current_pdf_page = 0
        self.pdf_render_timer.stop()
        self.pdf_document.close()
        self.preview_label.set_wheel_paging_enabled(False)
        self.preview_label.clear_pixmap()
        self.text_view.setPlainText(text)
        self.text_view.verticalScrollBar().setValue(0)
        self.mode_label.setText(mode)
        self.page_label.setText("")
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.stack.setCurrentWidget(self.text_view)

    def _show_pdf(self, path, mode):
        """Ładuje dokument PDF i renderuje zawsze jedną pełną stronę w panelu."""
        self.current_preview_kind = "pdf"
        self.current_pdf_page = 0
        self.pdf_mode_label = mode
        self.pdf_render_timer.stop()
        self.preview_label.clear_pixmap()
        self.preview_label.set_wheel_paging_enabled(True)
        self.text_view.clear()
        self.mode_label.setText(mode)
        self.page_label.setText("")
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.status_label.setText("Ładowanie PDF...")
        self.stack.setCurrentWidget(self.status_label)

        self.pdf_document.close()
        error = self.pdf_document.load(path)
        if error != QPdfDocument.Error.None_:
            self.show_message("Błąd podglądu PDF")
            return

        if self.pdf_document.status() == QPdfDocument.Status.Ready:
            self._render_current_pdf_page()

    def _handle_worker_result(self, result):
        """Nakłada wynik pracy w tle tylko wtedy, gdy dotyczy aktualnego dokumentu."""
        if result.get("request_id") != self.request_id:
            return

        kind = result.get("kind")
        if kind == "pdf":
            self._show_pdf(result["path"], result.get("label", "Dokument"))
            return

        if kind == "text":
            self._show_text(result.get("content", ""), result.get("label", "Podgląd"))
            return

        self.show_message(result.get("message", "Brak podglądu"))

    def _on_pdf_status_changed(self, status):
        """Reaguje na zmianę statusu ładowania dokumentu PDF."""
        if self.current_preview_kind != "pdf":
            return

        if status == QPdfDocument.Status.Ready and self.pdf_document.pageCount() > 0:
            self.current_pdf_page = min(self.current_pdf_page, self.pdf_document.pageCount() - 1)
            self._render_current_pdf_page()
            return

        if status == QPdfDocument.Status.Error:
            self.show_message("Błąd podglądu PDF")

    def _handle_preview_resized(self):
        """Przy zmianie rozmiaru okna odświeża stronę PDF z krótkim debounce."""
        if self.current_preview_kind != "pdf":
            return
        if self.pdf_document.status() != QPdfDocument.Status.Ready:
            return
        self.pdf_render_timer.start(60)

    def _render_current_pdf_page(self):
        """Renderuje bieżącą stronę PDF tak, aby zawsze mieściła się cała w panelu."""
        if self.current_preview_kind != "pdf":
            return
        if self.pdf_document.status() != QPdfDocument.Status.Ready:
            return

        total_pages = self.pdf_document.pageCount()
        if total_pages <= 0:
            self.show_message("Pusty PDF")
            return

        self.current_pdf_page = max(0, min(self.current_pdf_page, total_pages - 1))
        page_size = self.pdf_document.pagePointSize(self.current_pdf_page)
        if page_size.width() <= 0 or page_size.height() <= 0:
            self.show_message("Błąd rozmiaru strony PDF")
            return

        available_width = max(1, self.preview_label.width() - 24)
        available_height = max(1, self.preview_label.height() - 24)
        scale = min(
            available_width / page_size.width(),
            available_height / page_size.height(),
        )
        if scale <= 0:
            return

        render_size = QSize(
            max(1, int(page_size.width() * scale)),
            max(1, int(page_size.height() * scale)),
        )
        image = self.pdf_document.render(self.current_pdf_page, render_size)
        if image.isNull():
            self.show_message("Błąd renderowania PDF")
            return

        # Importujemy klasy potrzebne do dodania białego tła
        from PySide6.QtGui import QImage, QPainter, QColor

        # Tworzymy nowy obraz o stałym, białym tle
        white_image = QImage(image.size(), QImage.Format_RGB32)
        white_image.fill(QColor(Qt.white))

        # Naniesienie wyrenderowanego pliku na przygotowane tło
        painter = QPainter(white_image)
        painter.drawImage(0, 0, image)
        painter.end()

        self.preview_label.set_pixmap(QPixmap.fromImage(white_image))
        self.mode_label.setText(self.pdf_mode_label)
        self.stack.setCurrentWidget(self.preview_label)
        self._update_pdf_controls()

    def _update_pdf_controls(self, *_args):
        """Aktualizuje licznik stron i stan przycisków nawigacji PDF."""
        if self.current_preview_kind != "pdf":
            return

        total_pages = self.pdf_document.pageCount()
        if total_pages <= 0:
            self.page_label.setText("")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            return

        self.page_label.setText(f"{self.current_pdf_page + 1} / {total_pages}")
        self.btn_prev.setEnabled(self.current_pdf_page > 0)
        self.btn_next.setEnabled(self.current_pdf_page < total_pages - 1)

    def _change_pdf_page(self, step):
        """Zmienia stronę PDF o wskazany krok i renderuje ją na nowo."""
        if self.current_preview_kind != "pdf":
            return
        if self.pdf_document.status() != QPdfDocument.Status.Ready:
            return

        total_pages = self.pdf_document.pageCount()
        new_page = max(0, min(self.current_pdf_page + step, total_pages - 1))
        if new_page == self.current_pdf_page:
            return

        self.current_pdf_page = new_page
        self._render_current_pdf_page()

    def show_previous_page(self):
        """Przechodzi do poprzedniej strony w aktywnym dokumencie PDF."""
        self._change_pdf_page(-1)

    def show_next_page(self):
        """Przechodzi do następnej strony w aktywnym dokumencie PDF."""
        self._change_pdf_page(1)


class ArchiveModel(QStandardItemModel):
    """Model drzewa obsługujący przeciąganie folderów i dokumentów."""

    def __init__(self, logic, parent):
        """Łączy model widoku z warstwą logiki i oknem głównym."""
        super().__init__()
        self.logic = logic
        self.parent_win = parent

    def dropMimeData(self, data, action, row, column, parent_idx):
        """Przenosi elementy w drzewie archiwum metodą przeciągnij i upuść."""
        del data, action, row, column

        item_idx = self.parent_win.tree_view.currentIndex()
        if not item_idx.isValid():
            return False

        source_data = item_idx.data(Qt.UserRole)
        if not source_data:
            return False

        if not parent_idx.isValid():
            if source_data["type"] != "folder":
                return False

            moved = self.logic.przenies_element("folder", source_data["id"], None)
            if moved:
                self.parent_win.odswiez_drzewo()
            return moved

        target_data = parent_idx.data(Qt.UserRole)
        if not target_data:
            return False

        if target_data["type"] == "doc":
            with sqlite3.connect(self.logic.db_path) as conn:
                result = conn.execute(
                    "SELECT folder_id FROM dokumenty WHERE id = ?",
                    (target_data["id"],),
                ).fetchone()
                target_folder_id = result[0] if result else None
        else:
            target_folder_id = target_data["id"]

        if target_folder_id == source_data["id"]:
            return False

        moved = self.logic.przenies_element(
            source_data["type"],
            source_data["id"],
            target_folder_id,
        )
        if moved:
            self.parent_win.odswiez_drzewo()
        return moved


class HardcodedSystemTranslator(QTranslator):
    """Zapewnia ręczne tłumaczenie podstawowych etykiet Qt na język polski."""

    def __init__(self):
        """Ładuje zestaw najczęściej używanych tłumaczeń interfejsu systemowego."""
        super().__init__()
        self.translations = {
            "&Yes": "Tak",
            "Yes": "Tak",
            "&No": "Nie",
            "No": "Nie",
            "&Cancel": "Anuluj",
            "Cancel": "Anuluj",
            "&OK": "OK",
            "OK": "OK",
            "&Save": "Zapisz",
            "Save": "Zapisz",
            "&Open": "Otwórz",
            "Open": "Otwórz",
            "&Close": "Zamknij",
            "Close": "Zamknij",
            "Apply": "Zastosuj",
            "Reset": "Resetuj",
            "&Discard": "Porzuć",
            "Discard": "Porzuć",
            "Help": "Pomoc",
            "&Help": "Pomoc",
            "Show Details...": "Pokaż szczegóły...",
            "Hide Details...": "Ukryj szczegóły...",
            "AM": "AM",
            "PM": "PM",
            "Look in:": "Szukaj w:",
            "File name:": "Nazwa pliku:",
            "Files of type:": "Pliki typu:",
            "All Files (*)": "Wszystkie pliki (*)",
            "Back": "Wstecz",
            "Parent Directory": "Katalog nadrzędny",
            "Create New Folder": "Utwórz nowy folder",
            "List View": "Lista",
            "Detail View": "Szczegóły",
            "%1 already exists.\nDo you want to replace it?": "%1 już istnieje.\nCzy chcesz go nadpisać?",
            "The file %1 already exists.\nDo you want to replace it?": "Plik %1 już istnieje.\nCzy chcesz go nadpisać?",
            "%1\nFile not found.\nPlease verify the correct file name was given.": "%1\nNie znaleziono pliku.",
            "Could not delete directory.": "Nie można usunąć katalogu.",
            "New Folder": "Nowy folder",
            "Directory:": "Katalog:",
        }

    def translate(self, context, source_text, disambiguation=None, n=-1):
        """Zwraca tłumaczenie lub tekst oryginalny, gdy wpisu brak w słowniku."""
        del context, disambiguation, n
        return self.translations.get(source_text, source_text)

from PySide6.QtGui import QKeySequence, QShortcut

class ShortcutHandler(QObject):
    """Zarządza skrótami klawiszowymi w oknie głównym programu."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.init_shortcuts()

    def init_shortcuts(self):
        # Skróty są obecnie zarządzane przez menu (QAction).
        # Ta klasa zostaje, aby w przyszłości móc dodawać ewentualne skróty
        # nieobsługiwane przez pasek menu.
        pass

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import QObject, Qt

class ApplicationMenu(QObject):
    """Zarządza paskiem menu w oknie głównym programu."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setup_menu()

    def setup_menu(self):
        menu_bar = self.window.menuBar()

        # 1. Menu Plik
        file_menu = menu_bar.addMenu("Plik")

        act_backup = QAction("📦 Kopia Zapasowa", self.window)
        act_backup.setShortcut(QKeySequence("Ctrl+B"))
        act_backup.triggered.connect(self.window.on_backup_dialog)
        file_menu.addAction(act_backup)

        act_change = QAction("⚙️ Zmień katalog", self.window)
        act_change.triggered.connect(self.window.on_change_path)
        file_menu.addAction(act_change)

        file_menu.addSeparator()

        act_exit = QAction("Zamknij", self.window)
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(self.window.close)
        file_menu.addAction(act_exit)

        # 2. Menu Edycja
        edit_menu = menu_bar.addMenu("Edycja")

        act_add_root = QAction("📁 Nowy folder główny", self.window)
        act_add_root.setShortcut(QKeySequence("Ctrl+Shift+N"))
        act_add_root.triggered.connect(lambda: self.window.on_add_folder(None))
        edit_menu.addAction(act_add_root)

        act_add_sub = QAction("📂 Nowy podfolder", self.window)
        act_add_sub.setShortcut(QKeySequence("Ctrl+N"))
        act_add_sub.triggered.connect(self.window.action_new_sub)
        edit_menu.addAction(act_add_sub)

        act_add_file = QAction("📄 Dodaj plik", self.window)
        act_add_file.setShortcut(QKeySequence("Ctrl+Shift+A"))
        act_add_file.triggered.connect(self.window.action_add_file)
        edit_menu.addAction(act_add_file)

        # --- DODANA NOWA OPCJA DLA KATALOGU ---
        act_add_dir = QAction("📁 Dodaj katalog", self.window)
        act_add_dir.setShortcut(QKeySequence("Ctrl+Shift+D"))
        act_add_dir.triggered.connect(self.window.on_add_directory)
        edit_menu.addAction(act_add_dir)

        edit_menu.addSeparator()

        act_edit = QAction("✏️ Edytuj", self.window)
        act_edit.setShortcut(QKeySequence("Ctrl+E"))
        act_edit.triggered.connect(self.window.action_edit)
        edit_menu.addAction(act_edit)

        self.act_delete = QAction("🗑️ Usuń", self.window)
        self.act_delete.setShortcut(QKeySequence("Delete"))
        self.act_delete.setEnabled(self.window.delete_unlocked)
        self.act_delete.triggered.connect(self.window.action_delete)
        edit_menu.addAction(self.act_delete)

        # 3. Menu Narzędzia
        tools_menu = menu_bar.addMenu("Narzędzia")

        self.act_lock = QAction("🔒 Zablokuj usuwanie", self.window)
        self.act_lock.triggered.connect(self.window.toggle_delete_lock)
        tools_menu.addAction(self.act_lock)

        act_refresh = QAction("🔄 Odśwież drzewo", self.window)
        act_refresh.setShortcut(QKeySequence("F5"))
        act_refresh.triggered.connect(self.window.odswiez_drzewo)
        tools_menu.addAction(act_refresh)

        act_open = QAction("📂 Otwórz dokument", self.window)
        act_open.setShortcut(QKeySequence(Qt.Key_Return))
        act_open.triggered.connect(
            lambda: self.window.otworz_zewnetrznie(self.window.tree_view.currentIndex())
        )
        tools_menu.addAction(act_open)

    def update_lock_action(self, unlocked):
        """Aktualizuje etykietę i ikonę blokady w menu."""
        if unlocked:
            self.act_lock.setText("🔓 Odblokuj usuwanie")
            self.act_delete.setEnabled(True)
        else:
            self.act_lock.setText("🔒 Zablokuj usuwanie")
            self.act_delete.setEnabled(False)


class DomoweArchiwum(QMainWindow):
    """Główne okno aplikacji do zarządzania domowym archiwum dokumentów."""

    def __init__(self):
        """Ładuje ustawienia użytkownika, logikę i interfejs programu."""
        super().__init__()
        self.setWindowTitle("Domowe Archiwum Dokumentów")
        self.settings = QSettings("domowe-archiwum", "DomoweArchiwum")

        default_path = os.path.expanduser("~/Domowe_Archiwum")
        self.archive_path = self.settings.value("archive_path", default_path)
        self.logic = ArchiveLogic(self.archive_path)
        self.delete_unlocked = False

        self.setup_ui()
        self.resize(1400, 900)
        self.splitter.setSizes([450, 950])
        self.load_settings()
        self.odswiez_drzewo()
        self.shortcut_handler = ShortcutHandler(self)
        self.menu_handler = ApplicationMenu(self)

    def _sync_expanded_state(self):
        """Zapisuje listę rozwiniętych folderów, gdy aktywne jest pełne drzewo."""
        if self.search_in.text().strip():
            return

        expanded = []
        for row in range(self.model.rowCount()):
            self._collect_expanded_ids(self.model.index(row, 0), expanded)
        self.settings.setValue("expanded_folders", expanded)

    def setup_ui(self):
        """Buduje główny interfejs aplikacji."""
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.create_btn("📦 Kopia Zapasowa", self.on_backup_dialog))
        toolbar.addWidget(self.create_btn("⚙️ Zmień Katalog", self.on_change_path))

        self.lock_btn = self.create_btn("🔒 Usuwanie zablokowane", self.toggle_delete_lock)
        toolbar.addWidget(self.lock_btn)
        toolbar.addStretch()

        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText("🔍 Szukaj...")
        self.search_in.setFixedWidth(300)
        self.search_in.textChanged.connect(self.odswiez_drzewo)
        toolbar.addWidget(self.search_in)
        self.main_layout.addLayout(toolbar)

        self.splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        self.tree_view = QTreeView()
        self.tree_view.setStyleSheet("QTreeView { font-size: 14px; }")

        self.model = ArchiveModel(self.logic, self)
        self.tree_view.setModel(self.model)
        self.tree_view.setItemDelegate(ArchiveItemDelegate(self.tree_view))
        self.tree_view.expanded.connect(self._sync_expanded_state)
        self.tree_view.collapsed.connect(self._sync_expanded_state)
        self.tree_view.setEditTriggers(QTreeView.NoEditTriggers)
        self.tree_view.setDragDropMode(QTreeView.InternalMove)
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.pokaz_menu)
        self.tree_view.clicked.connect(self.on_item_clicked)
        self.tree_view.doubleClicked.connect(self.otworz_zewnetrznie)

        btn_panel = QHBoxLayout()
        self.btn_new_root = self.create_small_btn("📁+", "Folder główny", lambda: self.on_add_folder(None))
        self.btn_new_sub = self.create_small_btn("📂+", "Podfolder", self.action_new_sub)
        self.btn_add_file = self.create_small_btn("📄+", "Plik", self.action_add_file)
        self.btn_edit = self.create_small_btn("✏️", "Edytuj", self.action_edit)
        self.btn_delete = self.create_small_btn("🗑️", "Usuń", self.action_delete)
        self.btn_delete.setEnabled(False)

        btn_panel.addWidget(self.btn_new_root)
        btn_panel.addWidget(self.btn_new_sub)
        btn_panel.addWidget(self.btn_add_file)
        btn_panel.addWidget(self.btn_edit)
        btn_panel.addWidget(self.btn_delete)
        btn_panel.addStretch()

        self.info_box = QTextEdit()
        self.info_box.setReadOnly(True)
        self.info_box.setMaximumHeight(150)

        left_layout.addWidget(self.tree_view, 1)
        left_layout.addLayout(btn_panel)
        left_layout.addWidget(QLabel("<b>OPIS DOKUMENTU:</b>"))
        left_layout.addWidget(self.info_box)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self.preview = PreviewPanel()
        right_layout.addWidget(self.preview, 1)

        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)
        self.main_layout.addWidget(self.splitter, 1)
        self.setup_footer()

    def setup_footer(self):
        """Buduje stopkę z wersją, ścieżką bazy i licznikiem filtrów."""
        footer_widget = QWidget()
        footer_widget.setFixedHeight(30)

        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(10, 0, 10, 5)

        style = (
            "QLabel { font-size: 10px; font-weight: bold; color: gray; "
            "padding: 1px 8px; border: 1px solid gray; border-radius: 5px; }"
        )

        lbl_version = QLabel(f"v{APP_VERSION}")
        lbl_version.setStyleSheet(style)

        lbl_path_title = QLabel("Ścieżka Bazy:")
        lbl_path_title.setStyleSheet("font-size: 10px; font-weight: bold; color: gray;")

        lbl_path = QLabel(f"📂 {self.archive_path}")
        lbl_path.setStyleSheet(style)

        self.filter_summary_label = QLabel("Gotowy")
        self.filter_summary_label.setStyleSheet(
            "QLabel { font-size: 11px; font-weight: bold; padding: 1px 12px; "
            "border: 1px solid palette(mid); border-radius: 6px; "
            "background-color: palette(alternate-base); }"
        )
        self.filter_summary_label.setAlignment(Qt.AlignCenter)

        lbl_copy = QLabel(f"© {COPYRIGHT} {datetime.now().year}")
        lbl_copy.setStyleSheet(style)

        footer_layout.addWidget(lbl_version)
        footer_layout.addSpacing(55)
        footer_layout.addWidget(lbl_path_title)
        footer_layout.addWidget(lbl_path)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.filter_summary_label)
        footer_layout.addStretch(1)
        footer_layout.addWidget(lbl_copy)

        self.main_layout.addWidget(footer_widget, 0)

    def on_backup_dialog(self):
        """Otwiera okno zarządzania kopiami zapasowymi."""
        BackupRestoreDialog(self, self.logic, self.settings).exec()

    def on_change_path(self):
        """Zmienia katalog archiwum i restartuje aplikację po potwierdzeniu."""
        new_path = QFileDialog.getExistingDirectory(self, "Wybierz katalog", self.archive_path)
        if not new_path:
            return

        answer = QMessageBox.question(
            self,
            "Potwierdzenie",
            f"Zmienić katalog archiwum na:\n{new_path}?\nAplikacja zostanie uruchomiona ponownie.",
        )
        if answer != QMessageBox.Yes:
            return

        self.settings.setValue("archive_path", new_path)
        self.settings.sync()
        restart_application()

    def create_btn(self, text, callback):
        """Tworzy standardowy przycisk paska narzędzi."""
        button = QPushButton(text)
        button.clicked.connect(callback)
        return button

    def create_small_btn(self, text, tooltip, callback):
        """Tworzy mały przycisk akcji używany pod drzewem dokumentów."""
        button = QPushButton(text)
        button.clicked.connect(callback)
        button.setToolTip(tooltip)
        button.setFixedSize(45, 30)
        return button

    @staticmethod
    def _stable_item_data(data):
        """Zwraca stabilny identyfikator elementu do odtworzenia zaznaczenia."""
        if not data:
            return None
        return {"id": data.get("id"), "type": data.get("type")}

    @staticmethod
    def _apply_folder_item_style(item, color_value):
        """Nadaje folderowi pastelowe tło, jeśli wybrano kolor."""
        if not color_value:
            return

        item.setBackground(QBrush(QColor(color_value)))
        item.setForeground(QBrush(QColor("#2D2A26")))

    @staticmethod
    def _folder_color_label(color_value):
        """Zwraca czytelną etykietę dla zapisanego kodu koloru folderu."""
        if not color_value:
            return "Bez koloru"
        return PASTEL_FOLDER_COLOR_NAMES.get(color_value, color_value)

    def toggle_delete_lock(self):
        """Przełącza blokadę operacji usuwania w interfejsie."""
        self.delete_unlocked = not self.delete_unlocked
        self.lock_btn.setText(
            "🔓 Usuwanie odblokowane" if self.delete_unlocked else "🔒 Usuwanie zablokowane"
        )
        self.btn_delete.setEnabled(self.delete_unlocked)
        self.menu_handler.update_lock_action(self.delete_unlocked)

    def _get_saved_expanded_ids(self):
        """Odczytuje z ustawień identyfikatory rozwiniętych folderów."""
        raw_expanded = self.settings.value("expanded_folders", [])
        if raw_expanded is None:
            return []

        values = raw_expanded if isinstance(raw_expanded, list) else [raw_expanded]
        return [int(value) for value in values if str(value).isdigit()]

    def get_folder_details(self, folder_id):
        """Zwraca liczbę podkatalogów, liczbę dokumentów i łączny rozmiar dla wskazanego folderu i jego podfolderów."""
        with sqlite3.connect(self.logic.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Zliczamy bezpośrednie podkatalogi
            subfolders = conn.execute(
                "SELECT count(*) FROM foldery WHERE id_rodzica = ?",
                (folder_id,)
            ).fetchone()[0]

            # Zliczamy dokumenty w tym folderze i jego podfolderach rekurencyjnie
            query = """
            WITH RECURSIVE
            folders(id) AS (
                SELECT ?
                UNION
                SELECT f.id FROM foldery f JOIN folders fd ON f.id_rodzica = fd.id
            )
            SELECT d.sciezka_fizyczna
            FROM dokumenty d
            WHERE d.folder_id IN (SELECT id FROM folders)
            """

            docs = conn.execute(query, (folder_id,)).fetchall()
            count = len(docs)

            total_size = 0
            for d in docs:
                path = os.path.join(self.archive_path, d["sciezka_fizyczna"])
                if os.path.exists(path):
                    total_size += os.path.getsize(path)

        return subfolders, count, _format_file_size(total_size)

    def _find_index_recursive(self, parent_idx, target_data):
        """Pomocnicza metoda do odnalezienia wskaźnika w zrekonstruowanym drzewie."""
        for row in range(self.model.rowCount(parent_idx)):
            idx = self.model.index(row, 0, parent_idx)
            data = idx.data(Qt.UserRole)
            if (
                data
                and target_data
                and data.get("id") == target_data.get("id")
                and data.get("type") == target_data.get("type")
            ):
                return idx
            if self.model.rowCount(idx) > 0:
                found = self._find_index_recursive(idx, target_data)
                if found.isValid():
                    return found
        return QModelIndex()

    def _oblicz_rozmiar_dokumentow(self, dokumenty):
        """Wylicza sumaryczną wielkość listy dokumentów na dysku."""
        total_bytes = 0
        for doc in dokumenty:
            path = os.path.join(self.archive_path, doc["sciezka_fizyczna"])
            if os.path.exists(path):
                total_bytes += os.path.getsize(path)
        return _format_file_size(total_bytes)

    def odswiez_drzewo(self):
        """Odbudowuje drzewo folderów i dokumentów na podstawie stanu bazy."""
        filtr = self.search_in.text().lower().strip()

        current_idx = self.tree_view.currentIndex()
        current_data = (
            self._stable_item_data(current_idx.data(Qt.UserRole))
            if current_idx.isValid()
            else None
        )

        self.model.clear()
        self.model.setHorizontalHeaderLabels(["Struktura Archiwum"])

        font_root = QFont()
        font_root.setBold(True)
        font_root.setPointSize(12)

        font_sub = QFont()
        font_sub.setBold(True)
        font_sub.setPointSize(10)

        font_doc = QFont()
        font_doc.setPointSize(10)

        foldery = list(self.logic.pobierz_strukture_folderow())
        dokumenty = list(self.logic.pobierz_dokumenty(filtr))

        item_map = {}
        for folder in foldery:
            item = QStandardItem(f"📁 {folder['nazwa']}")
            item.setFont(font_root if folder["id_rodzica"] is None else font_sub)
            item.setData(
                {
                    "id": folder["id"],
                    "type": "folder",
                    "name": folder["nazwa"],
                    "color": folder["kolor"],
                    "important": bool(folder["wazne"]),
                },
                Qt.UserRole,
            )
            self._apply_folder_item_style(item, folder["kolor"])
            item_map[folder["id"]] = item

        for folder in foldery:
            item = item_map[folder["id"]]
            if folder["id_rodzica"] is None:
                self.model.appendRow(item)
                continue

            parent_item = item_map.get(folder["id_rodzica"])
            if parent_item:
                parent_item.appendRow(item)

        for dokument in dokumenty:
            folder_item = item_map.get(dokument["folder_id"])
            if not folder_item:
                continue

            item = QStandardItem(f"📄 [{dokument['data_dok']}] {dokument['tytul']}")
            item.setFont(font_doc)
            item.setData(
                {
                    "id": dokument["id"],
                    "type": "doc",
                    "path": dokument["sciezka_fizyczna"],
                    "info": dokument["opis"] or "",
                    "date": dokument["data_dok"],
                    "title": dokument["tytul"] or "",
                    "important": bool(dokument["wazne"]),
                },
                Qt.UserRole,
            )
            folder_item.appendRow(item)

        selection_model = self.tree_view.selectionModel()
        if selection_model is not None:
            selection_model.clearSelection()

        if filtr:
            self.tree_view.expandAll()
            if selection_model is not None:
                self._select_matching_items(self.model.invisibleRootItem(), filtr, selection_model)
        else:
            self._restore_expanded_state(self._get_saved_expanded_ids())
            if current_data:
                idx = self._find_index_recursive(QModelIndex(), current_data)
                if idx.isValid():
                    self.tree_view.setCurrentIndex(idx)
                    self.tree_view.scrollTo(idx)

        self.btn_delete.setEnabled(self.delete_unlocked)
        prefix = "Znaleziono" if filtr else "Łącznie Dokumentów"
        rozmiar_str = self._oblicz_rozmiar_dokumentow(dokumenty)
        self.filter_summary_label.setText(f"{prefix}: {len(dokumenty)} | Łączne miejsce: {rozmiar_str}")

    def _select_matching_items(self, parent_item, filtr, selection_model):
        """Rekurencyjnie zaznacza dokumenty pasujące do aktywnego filtra."""
        for row in range(parent_item.rowCount()):
            item = parent_item.child(row)
            if item is None:
                continue

            data = item.data(Qt.UserRole)
            if data and data.get("type") == "doc":
                tytul = item.text().lower()
                opis = str(data.get("info", "")).lower()
                if filtr in tytul or filtr in opis:
                    selection_model.select(item.index(), QItemSelectionModel.Select)

            if item.rowCount() > 0:
                self._select_matching_items(item, filtr, selection_model)

    def _restore_expanded_state(self, ids):
        """Przywraca rozwinięcie folderów zapisane w ustawieniach użytkownika."""
        for row in range(self.model.rowCount()):
            self._recursive_restore(self.model.index(row, 0), ids)

    def _recursive_restore(self, index, ids):
        """Rekurencyjnie rozwija foldery znajdujące się na liście zapisanych identyfikatorów."""
        data = index.data(Qt.UserRole)
        if not data or data["type"] != "folder":
            return

        if int(data["id"]) in ids:
            self.tree_view.setExpanded(index, True)

        for row in range(self.model.rowCount(index)):
            self._recursive_restore(self.model.index(row, 0, index), ids)

    def closeEvent(self, event):
        """Zapisuje geometrię okna i stan drzewa przed zamknięciem aplikacji."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter_v3", self.splitter.saveState())

        expanded = []
        for row in range(self.model.rowCount()):
            self._collect_expanded_ids(self.model.index(row, 0), expanded)

        self.settings.setValue("expanded_folders", expanded)
        self.settings.sync()
        super().closeEvent(event)

    def _collect_expanded_ids(self, index, expanded):
        """Zbiera identyfikatory folderów aktualnie rozwiniętych w widoku."""
        if not self.tree_view.isExpanded(index):
            return

        data = index.data(Qt.UserRole)
        if data and data["type"] == "folder":
            expanded.append(int(data["id"]))

        for row in range(self.model.rowCount(index)):
            self._collect_expanded_ids(self.model.index(row, 0, index), expanded)

    def _show_error(self, message, title="Błąd"):
        """Wyświetla użytkownikowi komunikat błędu."""
        QMessageBox.warning(self, title, message)

    def _prompt_for_document_date(self, title, initial_date=None):
        """Otwiera prosty dialog wyboru daty dokumentu."""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Wybierz datę:"))

        date_edit = QDateEdit(calendarPopup=True)
        date_edit.setDate(initial_date or QDate.currentDate())
        layout.addWidget(date_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return None

        return date_edit.date().toString("yyyy-MM-dd")

    def on_add_doc(self, folder_idx):
        """Dodaje nowy dokument do wskazanego folderu."""
        if folder_idx is None or not folder_idx.isValid():
            return

        folder_data = folder_idx.data(Qt.UserRole)
        folder_id = int(folder_data["id"])
        path, _ = QFileDialog.getOpenFileName(self, "Wybierz plik")
        if not path:
            return

        suggested_title = os.path.splitext(os.path.basename(path))[0]
        dialog = DocumentDialog(
            self,
            "Nowy dokument",
            document_title=suggested_title,
        )
        if dialog.exec() != QDialog.Accepted:
            return

        document_data = dialog.document_data()
        if not document_data["title"]:
            self._show_error("Tytuł dokumentu nie może być pusty.")
            return

        try:
            self.logic.dodaj_dokument(
                path,
                document_data["title"],
                document_data["description"],
                document_data["date"],
                folder_id,
                wazne=document_data["important"],
            )
        except (OSError, ValueError) as exc:
            self._show_error(str(exc))
            return

        expanded = self._get_saved_expanded_ids()
        if folder_id not in expanded:
            expanded.append(folder_id)
            self.settings.setValue("expanded_folders", expanded)

        self.odswiez_drzewo()

    def on_rename(self, idx):
        """Zmienia nazwę folderu albo edytuje metadane dokumentu."""
        if not idx.isValid():
            return

        data = idx.data(Qt.UserRole)
        if data["type"] == "folder":
            folder = self.logic.pobierz_folder(data["id"])
            if folder is None:
                self._show_error("Nie znaleziono folderu.")
                return

            dialog = FolderDialog(
                self,
                "Edycja folderu",
                name=folder["nazwa"] or "",
                color=folder["kolor"],
                important=bool(folder["wazne"]),
            )
            if dialog.exec() != QDialog.Accepted:
                return

            folder_data = dialog.folder_data()
            if not folder_data["name"]:
                self._show_error("Nazwa folderu nie może być pusta.")
                return

            try:
                self.logic.aktualizuj_folder(
                    data["id"],
                    folder_data["name"],
                    folder_data["color"],
                    folder_data["important"],
                )
            except (FileExistsError, OSError, ValueError) as exc:
                self._show_error(str(exc))
                return

            self.odswiez_drzewo()
            return

        row = self.logic.pobierz_dokument(data["id"])
        if row is None:
            self._show_error("Nie znaleziono dokumentu.")
            return

        current_title = row["tytul"] or ""
        current_description = row["opis"] or ""
        current_date = QDate.fromString(row["data_dok"] or "", "yyyy-MM-dd")
        if not current_date.isValid():
            current_date = QDate.currentDate()

        dialog = DocumentDialog(
            self,
            "Edycja dokumentu",
            document_title=current_title,
            description=current_description,
            document_date=current_date,
            important=bool(row["wazne"]),
        )
        if dialog.exec() != QDialog.Accepted:
            return

        document_data = dialog.document_data()
        if not document_data["title"]:
            self._show_error("Tytuł dokumentu nie może być pusty.")
            return

        try:
            renamed = self.logic.aktualizuj_dokument(
                data["id"],
                document_data["title"],
                document_data["description"],
                document_data["date"],
                document_data["important"],
            )
        except (OSError, ValueError) as exc:
            self._show_error(str(exc))
            return

        if not renamed:
            QMessageBox.warning(
                self,
                "Uwaga",
                "Metadane zapisano, ale nie udało się zmienić fizycznej nazwy pliku.",
            )

        self.odswiez_drzewo()

    def on_item_clicked(self, idx):
        """Aktualizuje opis dokumentu i panel podglądu po kliknięciu w drzewie."""
        data = idx.data(Qt.UserRole)
        if not data:
            self.info_box.clear()
            self.preview.show_folder()
            return

        if data["type"] == "folder":
            folder_id = data["id"]
            subfolders, count, size_str = self.get_folder_details(folder_id)
            folder_name = data.get("name", "")

            self.info_box.setText(
                f"Katalog: {folder_name}\n\n"
                f"Kolor: {self._folder_color_label(data.get('color'))}\n"
                f"Ważne: {'Tak' if data.get('important') else 'Nie'}\n"
                f"Liczba podkatalogów: {subfolders}\n"
                f"Liczba dokumentów: {count}\n"
                f"Zajmowane miejsce: {size_str}"
            )
            self.preview.show_folder()
            return

        if data["type"] == "doc":
            path = os.path.join(self.archive_path, data["path"])
            size_str = "Brak pliku"
            mime_type = "Nieznany"

            if os.path.exists(path):
                size_str = _format_file_size(os.path.getsize(path))
                mime_type, _ = mimetypes.guess_type(path)
                if not mime_type:
                    ext = os.path.splitext(path)[1]
                    mime_type = ext if ext else "Nieznany"

            self.info_box.setText(
                f"Tytuł: {data.get('title', '')}\n\n"
                f"Ważne: {'Tak' if data.get('important') else 'Nie'}\n\n"
                f"Opis: {data['info']}\n\n"
                f"Rozmiar: {size_str} | Format: {mime_type}"
            )
            self.preview.preview_file(path)

    def otworz_zewnetrznie(self, idx):
        """Otwiera dokument w domyślnej aplikacji systemowej, czyszcząc środowisko PyInstallera."""
        if not idx:
            return

        if hasattr(idx, "data"):
            data = idx.data(Qt.UserRole)
        else:
            data = idx

        if not data or data.get("type") != "doc":
            return

        path = os.path.join(self.archive_path, data["path"])

        if not os.path.exists(path):
            self._show_error(f"Plik nie istnieje:\n{path}")
            return

        try:
            env = os.environ.copy()

            if "LD_LIBRARY_PATH_ORIG" in env:
                env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
                del env["LD_LIBRARY_PATH_ORIG"]
            elif "LD_LIBRARY_PATH" in env:
                del env["LD_LIBRARY_PATH"]

            # Używamy listy [komenda, argument], co chroni przed błędami w ścieżkach ze spacjami.
            # xdg-open jest najbardziej uniwersalny (zadziała na KDE, GNOME, XFCE).
            subprocess.Popen(["xdg-open", path], env=env)

        except Exception as exc:
            self._show_error(f"Nie udało się otworzyć pliku:\n{exc}")

    def action_new_sub(self):
        """Dodaje podfolder do aktualnie zaznaczonego folderu."""
        idx = self.tree_view.currentIndex()
        if not idx.isValid() or idx.data(Qt.UserRole)["type"] != "folder":
            self._show_error("Zaznacz najpierw gdzie dodać")
            return
        self.on_add_folder(idx)

    def action_add_file(self):
        """Dodaje plik do aktualnie zaznaczonego folderu."""
        idx = self.tree_view.currentIndex()
        if not idx.isValid() or idx.data(Qt.UserRole)["type"] != "folder":
            self._show_error("Zaznacz najpierw gdzie dodać")
            return
        self.on_add_doc(idx)


    def action_edit(self):
        """Uruchamia edycję aktualnie zaznaczonego elementu."""
        idx = self.tree_view.currentIndex()
        if idx.isValid():
            self.on_rename(idx)

    def action_delete(self):
        """Usuwa zaznaczony element, jeśli blokada usuwania jest wyłączona."""
        if not self.delete_unlocked:
            return

        idx = self.tree_view.currentIndex()
        if idx.isValid():
            self.on_delete(idx)

    def pokaz_menu(self, pos):
        """Buduje i pokazuje menu kontekstowe drzewa archiwum."""
        idx = self.tree_view.indexAt(pos)
        menu = QMenu()

        if idx.isValid():
            data = idx.data(Qt.UserRole)
            if data["type"] == "folder":
                menu.addAction("📂 Nowy Podfolder", lambda: self.on_add_folder(idx))
                menu.addAction("📄 Dodaj Plik", lambda: self.on_add_doc(idx))
                menu.addAction("📁 Dodaj katalog z plikami", lambda: self.on_add_directory(idx))
                menu.addAction("✏️ Zmień nazwę", lambda: self.on_rename(idx))
            else:
                menu.addAction("📂 Otwórz", lambda: self.otworz_zewnetrznie(idx))
                menu.addAction("✏️ Edytuj", lambda: self.on_rename(idx))

            if self.delete_unlocked:
                menu.addAction("⚠️ Usuń", lambda: self.on_delete(idx))
        else:
            menu.addAction("📂 Nowy Folder główny", lambda: self.on_add_folder(None))

        menu.exec(self.tree_view.mapToGlobal(pos))

    def on_add_folder(self, parent_idx=None):
        """Dodaje folder główny lub podfolder do zaznaczonego miejsca."""
        dialog = FolderDialog(
            self,
            "Nowy folder",
            default_color=DEFAULT_NEW_FOLDER_COLOR,
        )
        if dialog.exec() != QDialog.Accepted:
            return

        folder_data = dialog.folder_data()
        if not folder_data["name"]:
            self._show_error("Nazwa folderu nie może być pusta.")
            return

        parent_id = parent_idx.data(Qt.UserRole)["id"] if parent_idx else None
        try:
            self.logic.dodaj_folder(
                folder_data["name"],
                parent_id,
                kolor=folder_data["color"],
                wazne=folder_data["important"],
            )
        except (OSError, ValueError) as exc:
            self._show_error(str(exc))
            return

        self.odswiez_drzewo()

    def on_add_directory(self, folder_idx=None):
        """Dodaje cały katalog wraz z zawartymi w nim plikami do wskazanego folderu z paskiem postępu."""
        # Jeśli przekazano wartość logiczną (np. z menu) lub indeks jest nieprawidłowy, pobierz zaznaczenie z widoku
        if folder_idx is None or isinstance(folder_idx, bool) or not folder_idx.isValid():
            folder_idx = self.tree_view.currentIndex()

        if not folder_idx.isValid() or folder_idx.data(Qt.UserRole)["type"] != "folder":
            self._show_error("Zaznacz najpierw gdzie dodać")
            return

        folder_data = folder_idx.data(Qt.UserRole)
        folder_id = int(folder_data["id"])

        directory_path = QFileDialog.getExistingDirectory(self, "Wybierz katalog do dodania")
        if not directory_path:
            return

        folder_dialog = FolderDialog(
            self,
            "Parametry importowanego folderu",
            name=os.path.basename(directory_path),
            default_color=DEFAULT_NEW_FOLDER_COLOR,
        )
        if folder_dialog.exec() != QDialog.Accepted:
            return

        folder_form_data = folder_dialog.folder_data()
        if not folder_form_data["name"]:
            self._show_error("Nazwa folderu nie może być pusta.")
            return

        selected_date = self._prompt_for_document_date("Data dla dokumentów w katalogu")
        if not selected_date:
            return

        # Utworzenie i wyświetlenie okna dialogowego postępu
        dialog = ProcessingDialog(self, "Import", "Dodawanie katalogu i plików...")
        dialog.show()

        try:
            new_folder_id = self.logic.dodaj_folder(
                folder_form_data["name"],
                folder_id,
                kolor=folder_form_data["color"],
                wazne=folder_form_data["important"],
            )

            files = [f for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]

            # Konfiguracja paska postępu
            dialog.pbar.setMaximum(len(files))
            dialog.pbar.setValue(0)

            for i, f in enumerate(files):
                file_path = os.path.join(directory_path, f)
                title = os.path.splitext(f)[0]
                description = ""
                self.logic.dodaj_dokument(file_path, title, description, selected_date, new_folder_id)

                # Aktualizacja paska postępu oraz odświeżenie GUI
                dialog.pbar.setValue(i + 1)
                QApplication.processEvents()

            dialog.close()

        except (OSError, ValueError, Exception) as exc:
            dialog.close()
            self._show_error(str(exc))
            return

        expanded = self._get_saved_expanded_ids()
        if folder_id not in expanded:
            expanded.append(folder_id)
            self.settings.setValue("expanded_folders", expanded)

        self.odswiez_drzewo()

    def on_delete(self, idx):
        """Usuwa wskazany element po potwierdzeniu użytkownika."""
        answer = QMessageBox.question(self, "Potwierdzenie", "Usunąć?")
        if answer != QMessageBox.Yes:
            return

        data = idx.data(Qt.UserRole)
        try:
            self.logic.usun_element(data["type"], data["id"])
        except (OSError, ValueError) as exc:
            self._show_error(str(exc))
            return

        self.odswiez_drzewo()

    def load_settings(self):
        """Przywraca geometrię okna i pozycję splittera z ustawień użytkownika."""
        geometry = self.settings.value("geometry")
        splitter_state = self.settings.value("splitter_v3")

        if geometry:
            self.restoreGeometry(geometry)
        if splitter_state:
            self.splitter.restoreState(splitter_state)


def restart_application():
    """Restartuje aplikację z użyciem aktualnego interpretera Pythona."""
    os.execl(sys.executable, sys.executable, *sys.argv)


def install_polish_translator(app):
    """Instaluje ręczne tłumaczenie systemowych etykiet Qt dla języka polskiego."""
    if QLocale.system().language() != QLocale.Language.Polish:
        return

    translator = HardcodedSystemTranslator()
    app.installTranslator(translator)
    app._manual_translator_ref = translator


def set_application_icon(app):
    """Ustawia ikonę aplikacji z systemu lub z lokalnego katalogu projektu."""
    system_icon = "/usr/share/pixmaps/archive.png"
    local_icon = os.path.join(os.path.dirname(__file__), "archive.png")
    icon_path = system_icon if os.path.exists(system_icon) else local_icon
    app.setWindowIcon(QIcon(icon_path))


def main():
    """Uruchamia aplikację okienkową."""
    app = QApplication(sys.argv)
    install_polish_translator(app)
    app.setDesktopFileName(os.environ.get("APP_ID", "archive-app"))
    set_application_icon(app)

    window = DomoweArchiwum()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
