import os
import shutil
import sqlite3
import tempfile
import zipfile


class ArchiveLogic:
    """Obsługuje bazę danych oraz operacje na plikach archiwum."""

    def __init__(self, base_dir):
        """Inicjalizuje ścieżki robocze i przygotowuje strukturę danych."""
        self.base_dir = os.path.abspath(base_dir)
        self.storage_dir = os.path.join(self.base_dir, "Pliki")
        self.db_path = os.path.join(self.base_dir, "archiwum_domowe.db")
        os.makedirs(self.storage_dir, exist_ok=True)
        self.init_db()

    def _connect(self):
        """Zwraca połączenie SQLite z włączoną obsługą kluczy obcych."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self):
        """Tworzy tabele aplikacji, jeśli nie istnieją."""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS foldery (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nazwa TEXT NOT NULL,
                    id_rodzica INTEGER,
                    FOREIGN KEY (id_rodzica) REFERENCES foldery(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dokumenty (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tytul TEXT,
                    opis TEXT,
                    data_dok DATE,
                    sciezka_fizyczna TEXT,
                    folder_id INTEGER,
                    FOREIGN KEY (folder_id) REFERENCES foldery(id) ON DELETE CASCADE
                )
                """
            )

    def _folder_name_exists(self, conn, nazwa, id_rodzica, exclude_id=None):
        """Sprawdza, czy w danym poziomie istnieje już folder o tej nazwie."""
        if id_rodzica is None:
            query = "SELECT 1 FROM foldery WHERE nazwa = ? AND id_rodzica IS NULL"
            params = [nazwa]
        else:
            query = "SELECT 1 FROM foldery WHERE nazwa = ? AND id_rodzica = ?"
            params = [nazwa, id_rodzica]

        if exclude_id is not None:
            query += " AND id != ?"
            params.append(exclude_id)

        return conn.execute(query, params).fetchone() is not None

    def _sanitize_document_title(self, tytul):
        """Czyści tytuł tak, aby dało się bezpiecznie zbudować nazwę pliku."""
        bezpieczny = "".join(
            znak for znak in tytul.strip() if znak.isalnum() or znak in (" ", "_", "-")
        )
        bezpieczny = " ".join(bezpieczny.split())
        return bezpieczny or "bez_nazwy"

    def _validate_folder_name(self, nazwa):
        """Waliduje nazwę folderu pod kątem pustych lub niepoprawnych wartości."""
        nazwa = " ".join(nazwa.split())
        if not nazwa:
            raise ValueError("Nazwa folderu nie może być pusta.")
        if nazwa in {".", ".."}:
            raise ValueError("Nazwa folderu jest nieprawidłowa.")
        if any(sep and sep in nazwa for sep in (os.sep, os.altsep)):
            raise ValueError("Nazwa folderu nie może zawierać separatorów ścieżek.")
        return nazwa

    def _build_document_filename(self, tytul, data_str, sciezka_zrodlowa):
        """Buduje nazwę pliku dokumentu na podstawie daty i tytułu."""
        rozszerzenie = os.path.splitext(sciezka_zrodlowa)[1]
        bezpieczny_tytul = self._sanitize_document_title(tytul)
        return f"{data_str}_{bezpieczny_tytul}{rozszerzenie}"

    def _ensure_unique_path(self, sciezka):
        """Zwraca unikalną ścieżkę, dodając licznik gdy plik już istnieje."""
        if not os.path.exists(sciezka):
            return sciezka

        katalog = os.path.dirname(sciezka)
        nazwa, rozszerzenie = os.path.splitext(os.path.basename(sciezka))
        licznik = 1

        while True:
            kandydat = os.path.join(katalog, f"{nazwa}_{licznik}{rozszerzenie}")
            if not os.path.exists(kandydat):
                return kandydat
            licznik += 1

    def dodaj_folder(self, nazwa, id_rodzica=None):
        """Dodaje folder do bazy oraz tworzy odpowiadający mu katalog na dysku."""
        nazwa = self._validate_folder_name(nazwa)

        with self._connect() as conn:
            if self._folder_name_exists(conn, nazwa, id_rodzica):
                raise ValueError("Folder o tej nazwie już istnieje w wybranej lokalizacji.")

            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO foldery (nazwa, id_rodzica) VALUES (?, ?)",
                (nazwa, id_rodzica),
            )
            nowy_id = cursor.lastrowid
            sciezka_rel = self._get_physical_path(nowy_id, conn)
            sciezka_full = os.path.join(self.storage_dir, sciezka_rel)
            os.makedirs(sciezka_full, exist_ok=True)
            conn.commit()
            return nowy_id

    def pobierz_strukture_folderow(self):
        """Pobiera pełną strukturę folderów z bazy danych."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM foldery ORDER BY id_rodzica IS NOT NULL, nazwa COLLATE NOCASE"
            ).fetchall()

    def pobierz_dokumenty(self, filtr=""):
        """Zwraca listę dokumentów, opcjonalnie przefiltrowaną po treści."""
        query = (
            "SELECT * FROM dokumenty "
            "ORDER BY data_dok DESC, tytul COLLATE NOCASE ASC"
        )
        params = ()

        if filtr:
            wzorzec = f"%{filtr}%"
            query = (
                "SELECT * FROM dokumenty "
                "WHERE COALESCE(tytul, '') LIKE ? "
                "OR COALESCE(opis, '') LIKE ? "
                "OR COALESCE(data_dok, '') LIKE ? "
                "ORDER BY data_dok DESC, tytul COLLATE NOCASE ASC"
            )
            params = (wzorzec, wzorzec, wzorzec)

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(query, params).fetchall()

    def dodaj_dokument(self, sciezka_zrodlowa, tytul, opis, data_str, folder_id):
        """Kopiuje dokument do archiwum i zapisuje jego metadane w bazie."""
        if folder_id is None or not self._folder_exists(folder_id):
            raise ValueError("Wybrany folder nie istnieje.")
        if not os.path.isfile(sciezka_zrodlowa):
            raise FileNotFoundError("Nie znaleziono wskazanego pliku źródłowego.")

        folder_rel = self._get_physical_path(folder_id)
        katalog_docelowy = os.path.join(self.storage_dir, folder_rel)
        os.makedirs(katalog_docelowy, exist_ok=True)

        nazwa_pliku = self._build_document_filename(tytul, data_str, sciezka_zrodlowa)
        sciezka_docelowa = self._ensure_unique_path(os.path.join(katalog_docelowy, nazwa_pliku))
        rel_path = os.path.relpath(sciezka_docelowa, self.base_dir)

        try:
            shutil.copy2(sciezka_zrodlowa, sciezka_docelowa)
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO dokumenty (tytul, opis, data_dok, sciezka_fizyczna, folder_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (tytul, opis, data_str, rel_path, folder_id),
                )
                conn.commit()
        except Exception:
            if os.path.exists(sciezka_docelowa):
                os.remove(sciezka_docelowa)
            raise

    def usun_element(self, typ, element_id):
        """Usuwa dokument lub folder razem z jego fizycznymi danymi."""
        with self._connect() as conn:
            if typ == "doc":
                wynik = conn.execute(
                    "SELECT sciezka_fizyczna FROM dokumenty WHERE id = ?",
                    (element_id,),
                ).fetchone()
                if wynik:
                    sciezka_pliku = os.path.join(self.base_dir, wynik[0])
                    if os.path.exists(sciezka_pliku):
                        os.remove(sciezka_pliku)
                conn.execute("DELETE FROM dokumenty WHERE id = ?", (element_id,))
            elif typ == "folder":
                folder_rel = self._get_physical_path(element_id, conn)
                folder_full = os.path.join(self.storage_dir, folder_rel)
                if os.path.exists(folder_full):
                    shutil.rmtree(folder_full)
                conn.execute("DELETE FROM foldery WHERE id = ?", (element_id,))
            else:
                raise ValueError("Nieobsługiwany typ elementu.")

            conn.commit()

    def _folder_exists(self, folder_id, conn=None):
        """Sprawdza, czy folder o podanym identyfikatorze istnieje."""
        should_close = conn is None
        if should_close:
            conn = self._connect()

        try:
            wynik = conn.execute("SELECT 1 FROM foldery WHERE id = ?", (folder_id,)).fetchone()
            return wynik is not None
        finally:
            if should_close:
                conn.close()

    def _is_descendant(self, conn, folder_id, potencjalny_rodzic_id):
        """Sprawdza, czy wskazany rodzic leży wewnątrz przenoszonego folderu."""
        aktualny_id = potencjalny_rodzic_id

        while aktualny_id is not None:
            if aktualny_id == folder_id:
                return True

            wynik = conn.execute(
                "SELECT id_rodzica FROM foldery WHERE id = ?",
                (aktualny_id,),
            ).fetchone()
            if wynik is None:
                return False
            aktualny_id = wynik[0]

        return False

    def przenies_element(self, typ, element_id, nowy_rodzic_id):
        """Przenosi dokument lub folder do nowej lokalizacji w strukturze archiwum."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row

            if typ == "doc":
                if nowy_rodzic_id is None or not self._folder_exists(nowy_rodzic_id, conn):
                    return False

                dokument = conn.execute(
                    "SELECT * FROM dokumenty WHERE id = ?",
                    (element_id,),
                ).fetchone()
                if dokument is None or dokument["folder_id"] == nowy_rodzic_id:
                    return False

                stara_fizyczna = os.path.join(self.base_dir, dokument["sciezka_fizyczna"])
                if not os.path.exists(stara_fizyczna):
                    return False

                folder_rel = self._get_physical_path(nowy_rodzic_id, conn)
                nowy_katalog = os.path.join(self.storage_dir, folder_rel)
                os.makedirs(nowy_katalog, exist_ok=True)

                kandydat = os.path.join(nowy_katalog, os.path.basename(stara_fizyczna))
                nowa_fizyczna = self._ensure_unique_path(kandydat)
                shutil.move(stara_fizyczna, nowa_fizyczna)

                nowa_rel = os.path.relpath(nowa_fizyczna, self.base_dir)
                conn.execute(
                    "UPDATE dokumenty SET folder_id = ?, sciezka_fizyczna = ? WHERE id = ?",
                    (nowy_rodzic_id, nowa_rel, element_id),
                )
                conn.commit()
                return True

            if typ != "folder":
                return False

            folder = conn.execute(
                "SELECT nazwa, id_rodzica FROM foldery WHERE id = ?",
                (element_id,),
            ).fetchone()
            if folder is None:
                return False
            if nowy_rodzic_id == element_id:
                return False
            if nowy_rodzic_id == folder["id_rodzica"]:
                return False
            if nowy_rodzic_id is not None and not self._folder_exists(nowy_rodzic_id, conn):
                return False
            if self._is_descendant(conn, element_id, nowy_rodzic_id):
                return False
            if self._folder_name_exists(
                conn,
                folder["nazwa"],
                nowy_rodzic_id,
                exclude_id=element_id,
            ):
                return False

            stara_relatywna = self._get_physical_path(element_id, conn)
            stara_full = os.path.join(self.storage_dir, stara_relatywna)

            conn.execute(
                "UPDATE foldery SET id_rodzica = ? WHERE id = ?",
                (nowy_rodzic_id, element_id),
            )

            nowa_relatywna = self._get_physical_path(element_id, conn)
            nowa_full = os.path.join(self.storage_dir, nowa_relatywna)

            if stara_full != nowa_full:
                if os.path.exists(nowa_full):
                    return False
                os.makedirs(os.path.dirname(nowa_full), exist_ok=True)
                if os.path.exists(stara_full):
                    shutil.move(stara_full, nowa_full)
                else:
                    os.makedirs(nowa_full, exist_ok=True)

            self._napraw_sciezki_plikow_w_folderze(element_id, conn)
            conn.commit()
            return True

    def _napraw_sciezki_plikow_w_folderze(self, folder_id, conn=None):
        """Aktualizuje ścieżki wszystkich dokumentów znajdujących się w folderze."""
        should_close = conn is None
        if should_close:
            conn = self._connect()
            conn.row_factory = sqlite3.Row

        try:
            self._napraw_sciezki_plikow_w_folderze_recursive(conn, folder_id)
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()

    def _napraw_sciezki_plikow_w_folderze_recursive(self, conn, folder_id):
        """Rekurencyjnie odświeża ścieżki plików dla folderu i jego podfolderów."""
        dokumenty = conn.execute(
            "SELECT id, sciezka_fizyczna FROM dokumenty WHERE folder_id = ?",
            (folder_id,),
        ).fetchall()

        folder_path = self._get_physical_path(folder_id, conn)
        for dokument in dokumenty:
            nazwa_pliku = os.path.basename(dokument["sciezka_fizyczna"])
            nowa_rel = os.path.join("Pliki", folder_path, nazwa_pliku)
            conn.execute(
                "UPDATE dokumenty SET sciezka_fizyczna = ? WHERE id = ?",
                (nowa_rel, dokument["id"]),
            )

        podfoldery = conn.execute(
            "SELECT id FROM foldery WHERE id_rodzica = ?",
            (folder_id,),
        ).fetchall()
        for podfolder in podfoldery:
            self._napraw_sciezki_plikow_w_folderze_recursive(conn, podfolder["id"])

    def _get_physical_path(self, folder_id, conn=None):
        """Wylicza fizyczną ścieżkę folderu względem katalogu `Pliki`."""
        if folder_id is None:
            return ""

        should_close = conn is None
        if should_close:
            conn = self._connect()

        try:
            elementy = []
            aktualny_id = folder_id
            odwiedzone = set()

            while aktualny_id is not None:
                if aktualny_id in odwiedzone:
                    raise ValueError("Wykryto cykliczną strukturę folderów.")
                odwiedzone.add(aktualny_id)

                wynik = conn.execute(
                    "SELECT nazwa, id_rodzica FROM foldery WHERE id = ?",
                    (aktualny_id,),
                ).fetchone()
                if wynik is None:
                    return ""

                elementy.append(wynik[0])
                aktualny_id = wynik[1]

            return os.path.join(*reversed(elementy)) if elementy else ""
        finally:
            if should_close:
                conn.close()

    def backup_all(self, zip_path, progress_callback=None):
        """Tworzy archiwum ZIP zawierające bieżący stan danych aplikacji."""
        try:
            archive_path = os.path.abspath(zip_path)
            files_to_zip = []

            for root, _, files in os.walk(self.base_dir):
                for nazwa_pliku in files:
                    sciezka_pliku = os.path.abspath(os.path.join(root, nazwa_pliku))
                    if sciezka_pliku == archive_path:
                        continue
                    files_to_zip.append(sciezka_pliku)

            total = len(files_to_zip)
            if total == 0:
                return True, archive_path

            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for indeks, sciezka_pliku in enumerate(files_to_zip, start=1):
                    arcname = os.path.relpath(sciezka_pliku, self.base_dir)
                    zipf.write(sciezka_pliku, arcname)
                    if progress_callback:
                        progress_callback(int(indeks / total * 100))

            return True, archive_path
        except Exception as exc:
            return False, str(exc)

    def restore_all(self, zip_path, progress_callback=None):
        """Przywraca pełną zawartość archiwum z pliku ZIP."""
        temp_dir = None
        archive_path = os.path.abspath(zip_path)

        try:
            try:
                if os.path.commonpath([archive_path, self.base_dir]) == self.base_dir:
                    temp_dir = tempfile.mkdtemp(prefix="domowe_archiwum_restore_")
                    kopia_zip = os.path.join(temp_dir, os.path.basename(archive_path))
                    shutil.copy2(archive_path, kopia_zip)
                    archive_path = kopia_zip
            except ValueError:
                pass

            if os.path.exists(self.base_dir):
                shutil.rmtree(self.base_dir)
            os.makedirs(self.base_dir, exist_ok=True)

            with zipfile.ZipFile(archive_path, "r") as zipf:
                lista_plikow = zipf.namelist()
                total = len(lista_plikow)

                for indeks, nazwa_pliku in enumerate(lista_plikow, start=1):
                    zipf.extract(nazwa_pliku, self.base_dir)
                    if progress_callback and total:
                        progress_callback(int(indeks / total * 100))

            return True
        except Exception:
            return False
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def zmien_nazwe_folderu(self, folder_id, nowa_nazwa):
        """Zmienia nazwę folderu, przenosi katalog i aktualizuje ścieżki dokumentów."""
        nowa_nazwa = self._validate_folder_name(nowa_nazwa)

        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            folder = conn.execute(
                "SELECT nazwa, id_rodzica FROM foldery WHERE id = ?",
                (folder_id,),
            ).fetchone()
            if folder is None:
                raise ValueError("Folder nie istnieje.")
            if folder["nazwa"] == nowa_nazwa:
                return
            if self._folder_name_exists(conn, nowa_nazwa, folder["id_rodzica"], exclude_id=folder_id):
                raise ValueError("Folder o tej nazwie już istnieje w wybranej lokalizacji.")

            stara_relatywna = self._get_physical_path(folder_id, conn)
            stara_full = os.path.join(self.storage_dir, stara_relatywna)

            conn.execute("UPDATE foldery SET nazwa = ? WHERE id = ?", (nowa_nazwa, folder_id))
            nowa_relatywna = self._get_physical_path(folder_id, conn)
            nowa_full = os.path.join(self.storage_dir, nowa_relatywna)

            if stara_full != nowa_full:
                if os.path.exists(nowa_full):
                    raise FileExistsError("Docelowy katalog już istnieje.")
                os.makedirs(os.path.dirname(nowa_full), exist_ok=True)
                if os.path.exists(stara_full):
                    shutil.move(stara_full, nowa_full)
                else:
                    os.makedirs(nowa_full, exist_ok=True)

            self._napraw_sciezki_plikow_w_folderze(folder_id, conn)
            conn.commit()

    def zmien_nazwe_pliku_fizycznie(self, doc_id, nowy_tytul, nowa_data):
        """Dostosowuje nazwę fizycznego pliku do nowych metadanych dokumentu."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            dokument = conn.execute(
                "SELECT * FROM dokumenty WHERE id = ?",
                (doc_id,),
            ).fetchone()
            if dokument is None:
                return False

            stara_sciezka = os.path.join(self.base_dir, dokument["sciezka_fizyczna"])
            if not os.path.exists(stara_sciezka):
                return False

            katalog_pliku = os.path.dirname(stara_sciezka)
            nowa_nazwa_pliku = self._build_document_filename(nowy_tytul, nowa_data, stara_sciezka)
            nowa_sciezka = os.path.join(katalog_pliku, nowa_nazwa_pliku)

            if stara_sciezka == nowa_sciezka:
                return True

            nowa_sciezka = self._ensure_unique_path(nowa_sciezka)
            shutil.move(stara_sciezka, nowa_sciezka)

            nowa_rel = os.path.relpath(nowa_sciezka, self.base_dir)
            conn.execute(
                "UPDATE dokumenty SET sciezka_fizyczna = ? WHERE id = ?",
                (nowa_rel, doc_id),
            )
            conn.commit()
            return True

    def pobierz_liczniki_plikow(self):
        """Zwraca słownik z liczbą dokumentów przypisaną do każdego folderu."""
        with self._connect() as conn:
            cursor = conn.execute("SELECT folder_id, COUNT(*) FROM dokumenty GROUP BY folder_id")
            return {row[0]: row[1] for row in cursor.fetchall()}
