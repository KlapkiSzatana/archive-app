# Budowa ze źródeł

Ta instrukcja opisuje trzy scenariusze budowy projektu `archive-app`:

1. uruchomienie aplikacji bezpośrednio ze źródeł,
2. zbudowanie binarki Linux przez `PyInstaller`,
3. spakowanie gotowej binarki do paczek `.deb` i `.rpm`.

Instrukcja jest zgodna z aktualnym układem repozytorium oraz buildem Linux opartym o `PyInstaller`.

## 1. Wymagania

Do pełnej budowy potrzebujesz:

- `git`
- `python` 3.11 lub nowszy
- `python -m venv`
- `pip`
- `ruby` + `rubygems`
- narzędzia systemowe potrzebne przez `PyInstaller` i `fpm`

Przykładowy zestaw zależności systemowych:

- Arch Linux:

```bash
sudo pacman -S --needed git python python-pip python-pyside6 ruby base-devel
```

- Debian/Ubuntu:

```bash
sudo apt install git python3 python3-venv python3-pip ruby ruby-dev build-essential
```

- Fedora:

```bash
sudo dnf install git python3 python3-pip ruby ruby-devel gcc make
```

## 2. Pobranie repozytorium

```bash
git clone https://github.com/KlapkiSzatana/archive-app.git
cd archive-app
```

## 3. Uruchomienie bezpośrednio ze źródeł

Utwórz lokalne środowisko i zainstaluj zależności:

```bash
python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install PySide6 pyinstaller
```

Uruchom aplikację:

```bash
python archive-app.py
```

## 4. Budowa binarki Linux

To buduje katalog `dist/archive-app/` z gotową binarką i zależnościami.

```bash
source .venv/bin/activate

rm -rf build dist archive-app.spec

python -m PyInstaller --noconfirm --clean --onedir --windowed \
  --name archive-app \
  --add-data "archive.png:." \
  archive-app.py
```

Po zakończeniu możesz uruchomić wynik lokalnie:

```bash
./dist/archive-app/archive-app
```

## 5. Przygotowanie narzędzia `fpm`

Paczki `.deb` i `.rpm` najprościej zbudować z tej samej binarki przez `fpm`.

Instalacja:

```bash
gem install --user-install fpm
```

Jeżeli po instalacji `fpm` nie jest w `PATH`, dodaj katalog gemów użytkownika do ścieżki i otwórz nową sesję terminala.

Szybka kontrola:

```bash
fpm --version
```

## 6. Budowa paczki `.deb`

Najpierw przygotuj strukturę paczki:

```bash
VERSION="1.2.1"

rm -rf build/package-root build/packages
mkdir -p build/package-root/usr/lib/archive-app
mkdir -p build/package-root/usr/bin
mkdir -p build/package-root/usr/share/applications
mkdir -p build/package-root/usr/share/pixmaps
mkdir -p build/packages

cp -a dist/archive-app/. build/package-root/usr/lib/archive-app/
install -m 644 archive.png build/package-root/usr/share/pixmaps/archive-app.png

cat > build/package-root/usr/bin/archive-app <<'EOF'
#!/bin/sh
exec /usr/lib/archive-app/archive-app "$@"
EOF
chmod 755 build/package-root/usr/bin/archive-app

cat > build/package-root/usr/share/applications/archive-app.desktop <<'EOF'
[Desktop Entry]
Name=Home Archive
Name[pl]=Domowe Archiwum
Comment=Management of home documents
Comment[pl]=Zarządzanie Domowymi Dokumentami
Exec=archive-app
Icon=archive-app
Terminal=false
Type=Application
Categories=Office;Utility;
EOF
```

Zbuduj paczkę:

```bash
fpm -s dir -t deb \
  -n archive-app \
  -v "$VERSION" \
  --iteration 1 \
  --architecture native \
  --license "GPL-3.0" \
  --url "https://github.com/KlapkiSzatana/archive-app" \
  --maintainer "KlapkiSzatana" \
  --description "Menedżer Domowego Archiwum Dokumentów" \
  --prefix / \
  -C build/package-root \
  -p build/packages \
  .
```

Gotowa paczka pojawi się w katalogu `build/packages/`.

## 7. Budowa paczki `.rpm`

Zakładając, że katalog `build/package-root/` nadal istnieje po poprzednim kroku:

```bash
fpm -s dir -t rpm \
  -n archive-app \
  -v "$VERSION" \
  --iteration 1 \
  --architecture native \
  --license "GPL-3.0" \
  --url "https://github.com/KlapkiSzatana/archive-app" \
  --maintainer "KlapkiSzatana" \
  --description "Menedżer Domowego Archiwum Dokumentów" \
  --prefix / \
  -C build/package-root \
  -p build/packages \
  .
```

Gotowa paczka pojawi się w katalogu `build/packages/`.

## 8. Artefakty wynikowe

Po pełnej budowie otrzymasz:

- binarkę Linux:

```text
dist/archive-app/
```

- paczkę Debian:

```text
build/packages/*.deb
```

- paczkę RPM:

```text
build/packages/*.rpm
```

## 9. Uwagi

- Aplikacja wykorzystuje `PySide6` do interfejsu graficznego Qt.
- Paczki `.deb` i `.rpm` są budowane z lokalnej binarki `PyInstaller`, więc przed pakowaniem zawsze wykonaj krok z sekcji 4.
- Na bardzo minimalnych systemach może być potrzebne doinstalowanie podstawowych bibliotek desktopowych Qt/GL dostępnych w dystrybucji.
