import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from functools import partial

from PySide6.QtCore import QDate, QItemSelectionModel, QLocale, QSettings, Qt, QTranslator
from PySide6.QtGui import QFont, QIcon, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QApplication,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from logic import ArchiveLogic

APP_VERSION = "1.0.0"
COPYRIGHT = "KlapkiSzatana"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
PDF_PREVIEW_OUTPUT = "/tmp/archi_final.png"


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


class DynamicPreviewLabel(QLabel):
    """Skaluje podgląd obrazu do rozmiaru panelu bez utraty proporcji."""

    def __init__(self):
        """Przygotowuje etykietę do wyświetlania podglądu plików."""
        super().__init__()
        self.pix = None
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: #000;")
        self.setMinimumSize(1, 1)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.show_message("Podgląd")

    def set_pixmap(self, pixmap):
        """Zapamiętuje oryginalny obraz i uruchamia jego przeskalowanie."""
        self.pix = pixmap
        super().setText("")
        self.update_scaling()

    def show_message(self, text):
        """Czyści podgląd obrazu i pokazuje komunikat tekstowy."""
        self.pix = None
        super().setPixmap(QPixmap())
        super().setText(text)

    def update_scaling(self):
        """Przeskalowuje obraz do bieżącego rozmiaru etykiety."""
        if self.pix and not self.pix.isNull():
            scaled = self.pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            super().setPixmap(scaled)

    def resizeEvent(self, event):
        """Odświeża skalowanie po zmianie rozmiaru panelu."""
        self.update_scaling()
        super().resizeEvent(event)


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
        self.preview = DynamicPreviewLabel()
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

    def toggle_delete_lock(self):
        """Przełącza blokadę operacji usuwania w interfejsie."""
        self.delete_unlocked = not self.delete_unlocked
        self.lock_btn.setText(
            "🔓 Usuwanie odblokowane" if self.delete_unlocked else "🔒 Usuwanie zablokowane"
        )
        self.btn_delete.setEnabled(self.delete_unlocked)

    def _get_saved_expanded_ids(self):
        """Odczytuje z ustawień identyfikatory rozwiniętych folderów."""
        raw_expanded = self.settings.value("expanded_folders", [])
        if raw_expanded is None:
            return []

        values = raw_expanded if isinstance(raw_expanded, list) else [raw_expanded]
        return [int(value) for value in values if str(value).isdigit()]

    def odswiez_drzewo(self):
        """Odbudowuje drzewo folderów i dokumentów na podstawie stanu bazy."""
        filtr = self.search_in.text().lower().strip()
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
            item.setData({"id": folder["id"], "type": "folder"}, Qt.UserRole)
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
                    "info": dokument["opis"],
                    "date": dokument["data_dok"],
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

        self.btn_delete.setEnabled(self.delete_unlocked)
        prefix = "Znaleziono" if filtr else "Dokumentów"
        self.filter_summary_label.setText(f"{prefix}: {len(dokumenty)}")

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
        title, ok = QInputDialog.getText(
            self,
            "Tytuł",
            "Tytuł dokumentu:",
            text=suggested_title,
        )
        if not ok or not title:
            return

        selected_date = self._prompt_for_document_date("Data dokumentu")
        if not selected_date:
            return

        description, ok = QInputDialog.getMultiLineText(self, "Opis", "Dodaj notatkę:")
        if not ok:
            return

        try:
            self.logic.dodaj_dokument(path, title, description, selected_date, folder_id)
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
            current_name = idx.data().replace("📁 ", "", 1)
            new_name, ok = QInputDialog.getText(self, "Zmiana", "Nazwa:", text=current_name)
            if not ok or not new_name:
                return

            try:
                self.logic.zmien_nazwe_folderu(data["id"], new_name)
            except (FileExistsError, OSError, ValueError) as exc:
                self._show_error(str(exc))
                return

            self.odswiez_drzewo()
            return

        with sqlite3.connect(self.logic.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT tytul, opis, data_dok FROM dokumenty WHERE id = ?",
                (data["id"],),
            ).fetchone()

        if row is None:
            self._show_error("Nie znaleziono dokumentu.")
            return

        current_title = row["tytul"] or ""
        current_description = row["opis"] or ""
        current_date = QDate.fromString(row["data_dok"], "yyyy-MM-dd")
        if not current_date.isValid():
            current_date = QDate.currentDate()

        title, ok = QInputDialog.getText(self, "Zmiana", "Tytuł:", text=current_title)
        if not ok or not title:
            return

        selected_date = self._prompt_for_document_date("Data dokumentu", current_date)
        if not selected_date:
            return

        description, ok = QInputDialog.getMultiLineText(
            self,
            "Opis",
            "Opis:",
            text=current_description,
        )
        if not ok:
            return

        with sqlite3.connect(self.logic.db_path) as conn:
            conn.execute(
                "UPDATE dokumenty SET tytul = ?, opis = ?, data_dok = ? WHERE id = ?",
                (title, description, selected_date, data["id"]),
            )
            conn.commit()

        if not self.logic.zmien_nazwe_pliku_fizycznie(data["id"], title, selected_date):
            QMessageBox.warning(
                self,
                "Uwaga",
                "Metadane zapisano, ale nie udało się zmienić fizycznej nazwy pliku.",
            )

        self.odswiez_drzewo()

    def _show_pdf_preview(self, path):
        """Generuje miniaturę pierwszej strony pliku PDF i pokazuje ją w panelu."""
        try:
            subprocess.run(
                [
                    "convert",
                    "-density",
                    "150",
                    f"{path}[0]",
                    "-background",
                    "white",
                    "-alpha",
                    "remove",
                    "-alpha",
                    "off",
                    "-thumbnail",
                    "1200x1200",
                    PDF_PREVIEW_OUTPUT,
                ],
                check=True,
            )
        except (FileNotFoundError, OSError, subprocess.CalledProcessError):
            self.preview.show_message("Błąd PDF")
            return

        self.preview.set_pixmap(QPixmap(PDF_PREVIEW_OUTPUT))

    def on_item_clicked(self, idx):
        """Aktualizuje opis dokumentu i panel podglądu po kliknięciu w drzewie."""
        data = idx.data(Qt.UserRole)
        if not data or data["type"] != "doc":
            self.info_box.clear()
            self.preview.show_message("Katalog")
            return

        self.info_box.setText(f"Tytuł: {idx.data().split('] ', 1)[-1]}\n\nOpis: {data['info']}")

        path = os.path.join(self.archive_path, data["path"])
        if not os.path.exists(path):
            self.preview.show_message("Brak pliku")
            return

        extension = os.path.splitext(path)[1].lower()
        if extension in IMAGE_EXTENSIONS:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                self.preview.show_message("Błąd obrazu")
                return

            self.preview.set_pixmap(pixmap)
            return

        if extension == ".pdf":
            self._show_pdf_preview(path)
            return

        self.preview.show_message(f"Brak podglądu: {extension}")

    def otworz_zewnetrznie(self, idx):
        """Otwiera dokument w domyślnej aplikacji systemowej."""
        data = idx.data(Qt.UserRole)
        if not data or data["type"] != "doc":
            return

        path = os.path.join(self.archive_path, data["path"])
        if not os.path.exists(path):
            self._show_error("Plik nie istnieje.")
            return

        try:
            subprocess.run(["xdg-open", path], check=False)
        except OSError as exc:
            self._show_error(f"Nie udało się otworzyć pliku:\n{exc}")

    def action_new_sub(self):
        """Dodaje podfolder do aktualnie zaznaczonego folderu."""
        idx = self.tree_view.currentIndex()
        if idx.isValid() and idx.data(Qt.UserRole)["type"] == "folder":
            self.on_add_folder(idx)

    def action_add_file(self):
        """Dodaje plik do aktualnie zaznaczonego folderu."""
        idx = self.tree_view.currentIndex()
        if idx.isValid() and idx.data(Qt.UserRole)["type"] == "folder":
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
        name, ok = QInputDialog.getText(self, "Folder", "Nazwa:")
        if not ok or not name:
            return

        parent_id = parent_idx.data(Qt.UserRole)["id"] if parent_idx else None
        try:
            self.logic.dodaj_folder(name, parent_id)
        except (OSError, ValueError) as exc:
            self._show_error(str(exc))
            return

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
