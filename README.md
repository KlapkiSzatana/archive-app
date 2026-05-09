# 📁 Domowe Archiwum

Menedżer domowego archiwum dokumentów napisany w Pythonie (PySide6).  
Aplikacja pozwala na wygodne zarządzanie (katalogowanie) skanami i dokumentami, oferując podgląd PDF, TXT, PNG, JPG itp...

---

## ⚙️ Wymagania

- Python  
- PySide6 (interfejs GUI)  
- Pillow (obsługa obrazów)  

---

## 🐧 Instalacja (Arch Linux i pochodne)

Najprostszym sposobem instalacji jest użycie dołączonego pliku `PKGBUILD`.

### 1. Sklonuj repozytorium i przejdź do katalogu

```bash
git clone https://github.com/KlapkiSzatana/archive-app.git
cd archive-app
```

### 2. Zbuduj i zainstaluj pakiet
```bash
makepkg -si
```

lub

## Instalacja (Arch z AUR)

Aplikację można łatwo zainstalować z repozytorium **AUR (Arch User Repository)**.

### Szybka instalacja (zalecana)

Jeśli używasz pomocnika AUR (np. `yay` lub `paru`), wpisz w terminalu:

```bash
yay -S archive-app
```
lub
```bash
paru -S archive-app
```

## 🚀 Uruchamianie

Po instalacji aplikację możesz uruchomić:
```bash
archive-app
```

Lub znaleźć ją w menu aplikacji jako Domowe Archiwum.

## 🗑️ Odinstalowanie

Jeśli instalacja odbyła się przez pacmana:

```bash
sudo pacman -Rs archive-app
```

## Dostępna również gotowa wersja bin

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


