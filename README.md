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

Poniżej link do pobrania gotowej aplikacji **bin**, wystarczy zezwolić na uruchamianie i gotowe.

### Pobierz najnowszą wersję:

- [Pobierz dla Linux](https://github.com/KlapkiSzatana/archive-app/releases/latest/download/archive-app-linux.bin)

👤 Autor

KlapkiSzatana


