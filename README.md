# 📁 Domowe Archiwum

Menedżer domowego archiwum dokumentów napisany w Pythonie (PySide6).  
Aplikacja pozwala na wygodne zarządzanie (katalogowanie) skanami i dokumentami, oferując podgląd PDF, TXT, PNG, JPG itp...

---

## [Changelog](CHANGELOG.md)

## Budowa ze źródeł

Pełna instrukcja budowy lokalnej wersji developerskiej, binarki Linux oraz paczek `.deb` i `.rpm` znajduje się w [BUILD_FROM_SOURCE.md](BUILD_FROM_SOURCE.md).

## ⚙️ Wymagania

- Python  
- PySide6 (interfejs GUI)  
- Pillow (obsługa obrazów)  

---

# 🐧 Instalacja (Arch Linux i pochodne)

Aplikacja jest dostępna w AUR w dwóch wersjach.  
Wybierz jedną z poniższych metod:

---

### OPCJA A: Szybka instalacja – Gotowa binarka

Instalujesz gotowy program.  
Nie potrzebujesz Pythona, bibliotek ani kompilacji.

Pobiera się i działa natychmiast.

Jeśli używasz pomocnika AUR (`yay` lub `paru`), wpisz:

```bash
yay -S archive-app-bin
```

lub

```bash
paru -S archive-app-bin
```

---

### OPCJA B: Instalacja ze źródeł

Program buduje się bezpośrednio z kodu źródłowego.

System automatycznie pobierze:
- środowisko Python,
- PySide6,
- Pillow,
- oraz wszystkie wymagane zależności.

Jeśli używasz pomocnika AUR (`yay` lub `paru`), wpisz:

```bash
yay -S archive-app
```

lub

```bash
paru -S archive-app
```

---

### OPCJA C: Ręczna instalacja przez PKGBUILD (Bez pomocników AUR)

Jeśli nie używasz `yay` ani `paru`, możesz pobrać paczkę ręcznie i zbudować ją przez `makepkg`.

### Wersja binarna

```bash
git clone https://aur.archlinux.org/archive-app-bin.git
cd archive-app-bin
makepkg -si
```

### Wersja ze źródła

```bash
git clone https://aur.archlinux.org/archive-app.git
cd archive-app
makepkg -si
```

---

## 🚀 Uruchamianie

Po instalacji (niezależnie od wybranej opcji) aplikację uruchamiasz wpisując:

```bash
archive-app
```

Możesz także uruchomić ją z menu aplikacji swojego środowiska graficznego.

---

## 🗑️ Odinstalowanie

Aby całkowicie usunąć aplikację z systemu:

### Wersja binarna (`-bin`)

```bash
sudo pacman -Rs archive-app-bin
```

### Wersja ze źródła

```bash
sudo pacman -Rs archive-app
```

# Dostępna również gotowa wersja bin

Wersja aplikacji automatycznie kompilowana i publikowana przy użyciu GitHub Actions. Dzięki temu proces budowania pozostaje spójny i w pełni zautomatyzowany.

Poniżej link do pobrania gotowej aplikacji.

### Pobierz najnowszą wersję:

- [Pobierz dla Linux](https://github.com/KlapkiSzatana/archive-app/releases/latest/download/ArchiveApp_linux.tar.gz)

## 🐧 Instalacja i Deinstalacja (Linux)

Paczka zawiera gotowe skrypty, które automatycznie instalują aplikację w katalogu `/opt/ArchiveApp` oraz dodają skrót do systemowego menu aplikacji (dzięki czemu program jest dostępny dla wszystkich użytkowników systemu).

### Wymagania
Instalacja i deinstalacja wymagają uprawnień administratora (`sudo`). Skrypty same poproszą o podanie hasła w terminalu.

---

### 📥 Instrukcja Instalacji

1. Pobierz i rozpakuj archiwum `ArchiveApp_linux.tar.gz`.
2. Otwórz terminal w rozpakowanym katalogu `linux-package` i uruchom skrypt instalacyjny:

```bash
./install.run
```

3. Po zakończeniu instalacji ikona Domowe Archiwum pojawi się w Twoim menu aplikacji.

### 🗑️ Instrukcja Deinstalacji

Jeśli chcesz całkowicie usunąć aplikację wraz ze wszystkimi skrótami z systemu:

1. Otwórz terminal w katalogu linux-package.

2. Uruchom skrypt deinstalacyjny:

```bash
./uninstall.run
```

3. (Alternatywnie, możesz usunąć aplikację ręcznie, wpisując w terminalu: 

```bash
sudo rm -rf /opt/ArchiveApp /usr/share/applications/ArchiveApp.desktop && sudo update-desktop-database /usr/share/applications
```

**Enjoy!**

👤 Autor

KlapkiSzatana


