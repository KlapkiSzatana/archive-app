# Maintainer: KlapkiSzatana
pkgname=archive-app
pkgver=1.0.0
pkgrel=1
pkgdesc="Menedżer Domowego Archiwum Dokumentów"
arch=('any')
url="https://github.com/KlapkiSzatana/archive-app"
license=('GPL-3.0')

depends=('python' 'pyside6' 'python-pillow' 'ghostscript' 'imagemagick')

source=("archive-app.py"
        "logic.py"
        "archive.png")

sha256sums=('096a53a72066a90c41fbff250502b32f336a71333d48edcdf8104a374dbb16e6'
            'd2f3cdff6eb53f9aa20568b8c19d25a4ddec90c095e1a160bfd3453f3eb5297c'
            'd25243e665f6a38f35e14bec53fdef35dfaf066f9c25dd85b14a11a2f4cae826')

package() {
    # Instalacja plików źródłowych Pythona
    install -d "${pkgdir}/usr/share/${pkgname}"
    install -m644 "${srcdir}/archive-app.py" "${pkgdir}/usr/share/${pkgname}/"
    install -m644 "${srcdir}/logic.py" "${pkgdir}/usr/share/${pkgname}/"

    # Ikona
    install -Dm644 "${srcdir}/archive.png" "${pkgdir}/usr/share/pixmaps/${pkgname}.png"
    install -m644 "${srcdir}/archive.png" "${pkgdir}/usr/share/${pkgname}/archive.png"

    # Skrypt uruchamiający w /usr/bin
    install -d "${pkgdir}/usr/bin"
    cat <<EOF > "${pkgdir}/usr/bin/${pkgname}"
#!/bin/sh
exec /usr/bin/python /usr/share/${pkgname}/archive-app.py "\$@"
EOF
    chmod 755 "${pkgdir}/usr/bin/${pkgname}"

    # Plik .desktop
    install -d "${pkgdir}/usr/share/applications"
    cat <<EOF > "${pkgdir}/usr/share/applications/${pkgname}.desktop"
[Desktop Entry]
Name=Home Archive
Name[pl]=Domowe Archiwum
Comment=Management of home documents
Comment[pl]=Zarządzanie Domowymi Dokumentami
Exec=/usr/bin/${pkgname}
Icon=${pkgname}
Terminal=false
Type=Application
Categories=Office;Utility;
StartupWMClass=archive-app
StartupNotify=true
EOF
    chmod 644 "${pkgdir}/usr/share/applications/${pkgname}.desktop"
}
