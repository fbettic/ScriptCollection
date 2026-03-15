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

## Margenes del PDF

Puedes controlar el margen de pagina con `--margin` (usa sintaxis de LaTeX geometry).

Valor por defecto: `18mm`.

Ejemplos:

```bash
epub2pdf "/ruta/al/archivo.epub" --margin 15mm
epub2pdf "/ruta/al/archivo.epub" "/ruta/salida/archivo.pdf" --margin 12mm
epub2pdf "/ruta/al/archivo.epub" --margin 1.2cm
```

Referencias rapidas:

- `15mm`: equilibrio entre legibilidad y aprovechamiento de pagina.
- `12mm`: texto mas compacto, menos espacio en blanco.
- `10mm`: muy compacto; util para documentos largos.

## Motor PDF y fuente

Por defecto el script prioriza motores con mejor soporte Unicode (`xelatex`, `lualatex`) y luego prueba `tectonic`/`pdflatex`.

Puedes forzar motor:

```bash
epub2pdf "/ruta/al/archivo.epub" --pdf-engine xelatex
```

Tambien puedes indicar fuente principal (recomendado con `xelatex` o `lualatex`):

```bash
epub2pdf "/ruta/al/archivo.epub" --pdf-engine xelatex --mainfont "Noto Serif"
```

## Warnings frecuentes de TeX

- `Missing character ...`: la fuente actual no cubre ese simbolo (por ejemplo `pi` o `phi`).
	Suele mejorar usando `--pdf-engine xelatex --mainfont "Noto Serif"`.
- `Overfull/Underfull hbox`: ajuste de parrafos y saltos de linea. No suele impedir generar el PDF.
	Puedes mitigarlo subiendo margen (`--margin 15mm` o `18mm`) o cambiando fuente.
- `build may not be reproducible in other environments`: aviso informativo del motor por rutas temporales absolutas.
