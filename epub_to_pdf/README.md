# epub-to-pdf

Convierte archivos EPUB a PDF desde la terminal.

El script se autoaprovisiona en la primera ejecucion:

- Instala dependencias Python faltantes.
- Descarga `pandoc` si no esta disponible.
- Descarga un motor PDF `tectonic` en modo headless (sin instaladores GUI), en cache de usuario.

## Instalacion desde GitHub (un comando)

```bash
python -m pip install "git+https://github.com/<tu-org>/<tu-repo>.git#subdirectory=epub_to_pdf"
```

## Uso

```bash
epub2pdf "/ruta/al/archivo.epub"
```

Opcionalmente puedes definir salida:

```bash
epub2pdf "/ruta/al/archivo.epub" "/ruta/salida/archivo.pdf"
```
