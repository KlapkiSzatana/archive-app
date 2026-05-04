# 📁 Domowe Archiwum

| ![archive](archive.png) | **Menedżer domowego archiwum** |
|---|---|
|  | Menedżer domowego archiwum dokumentów napisany w Pythonie (PySide6).  
Aplikacja pozwala na wygodne zarządzanie skanami i dokumentami, oferując podgląd PDF dzięki integracji z Ghostscript i ImageMagick. |

---

## ⚙️ Wymagania

- Python  
- PySide6 (interfejs GUI)  
- Pillow (obsługa obrazów)  
- Ghostscript  
- ImageMagick  

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

## 🛠️ Rozwiązywanie problemów

Jeśli podgląd PDF nie działa poprawnie:

upewnij się, że ImageMagick ma włączoną obsługę PDF
sprawdź plik:
/etc/ImageMagick-7/policy.xml

👤 Autor

KlapkiSzatana


