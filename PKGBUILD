# Maintainer: KlapkiSzatana
pkgname=archive-app
pkgver=1.3.1
pkgrel=1
pkgdesc="Menedżer Domowego Archiwum Dokumentów"
arch=('any')
url="https://github.com/KlapkiSzatana/archive-app"
license=('GPL-3.0')

depends=('python' 'pyside6')

source=("archive-app.py"
        "logic.py"
        "archive.png")

sha256sums=('1e321fadd8969dcec3ac8dcf2988aad69605e376acaa30a4fa832b483899e1bf'
            '8cb43d3bc44e38bfbef26f0c1138d677ebdf855fbb2d46c1fe52a0dad1010c9e'
            '77d73805e84952d5c07e6eccf27b22259ea4ed7688cf09805bb83bee8a885e64')

package() {
    install -d "${pkgdir}/usr/share/${pkgname}"
    install -m644 "${srcdir}/archive-app.py" "${pkgdir}/usr/share/${pkgname}/"
    install -m644 "${srcdir}/logic.py" "${pkgdir}/usr/share/${pkgname}/"

    install -Dm644 "${srcdir}/archive.png" "${pkgdir}/usr/share/pixmaps/${pkgname}.png"
    install -m644 "${srcdir}/archive.png" "${pkgdir}/usr/share/${pkgname}/archive.png"

    install -d "${pkgdir}/usr/bin"
    cat <<EOF > "${pkgdir}/usr/bin/${pkgname}"
#!/bin/sh
exec /usr/bin/python /usr/share/${pkgname}/archive-app.py "\$@"
EOF
    chmod 755 "${pkgdir}/usr/bin/${pkgname}"

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
