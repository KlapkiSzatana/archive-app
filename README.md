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

👤 Autor

KlapkiSzatana


