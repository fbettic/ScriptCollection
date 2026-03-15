# epub-to-pdf

Convierte archivos EPUB a PDF desde la terminal.

El script es autosuficiente en la primera ejecucion:

- Instala la dependencia Python faltante (`pypandoc`).
- Descarga `pandoc` si no esta disponible.
- Descarga `TinyTeX` en modo headless (sin instaladores GUI), en cache de usuario.
- Descarga fuentes locales en `fonts/` para mejorar cobertura de simbolos matematicos Unicode.

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

Puedes controlar el margen de pagina con `--margin` (sintaxis de LaTeX geometry).

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

## Motor PDF

El script usa **TinyTeX** y requiere un motor Unicode (`xelatex` o `lualatex`), priorizando `xelatex`.

Motivos:

- Instalacion automatica sin GUI.
- Buen manejo de contenido matematico y Unicode con `xelatex`.
- Compatible con Windows, Linux y macOS con el mismo flujo.

No hace falta elegir motor ni configurar fallback manual.

## Ajuste de texto e imagen

Opciones para mejorar maquetacion en PDFs complejos:

- `--text-layout adaptive|standard`:
  - `adaptive` (recomendado) reduce avisos `Overfull/Underfull hbox`.
- `--image-layout contain|standard`:
  - `contain` (recomendado) adapta imagenes grandes al ancho/alto de pagina sin deformarlas.

Ejemplo recomendado para libros con formulas y muchas imagenes:

```bash
epub2pdf "/ruta/al/archivo.epub" --profile math --text-layout adaptive --image-layout contain
```

Ejemplo recomendado para biologia (ilustraciones):

```bash
epub2pdf "/ruta/al/archivo.epub" --profile biology --text-layout adaptive --image-layout contain --dpi 300
```

## Warnings frecuentes de TeX

- `Missing character ...`: el documento puede incluir simbolos o glifos poco comunes.
  El script usa fuentes locales (`Noto Serif` y `Noto Sans Math`) para cubrir mejor simbolos como `φ` y `π`.
- `Overfull/Underfull hbox`: ajuste de parrafos y saltos de linea. No suele impedir generar el PDF.
  Puedes mitigarlo con `--text-layout adaptive`, subiendo margen (`--margin 15mm` o `18mm`).
- `build may not be reproducible in other environments`: aviso informativo por rutas temporales absolutas.
  No afecta normalmente al PDF final en tu equipo.

## Perfiles predefinidos

Puedes usar perfiles con `--profile`:

- `fiction`: `margin=12mm`, `dpi=180`.
- `math`: `margin=15mm`, `dpi=300`.
- `biology`: `margin=10mm`, `dpi=300`.

Ejemplos:

```bash
epub2pdf "/ruta/libro.epub" --profile fiction
epub2pdf "/ruta/libro.epub" --profile math
epub2pdf "/ruta/libro.epub" --profile biology
```

Tambien puedes sobrescribir cualquier valor del perfil:

```bash
epub2pdf "/ruta/libro.epub" --profile math --margin 12mm
epub2pdf "/ruta/libro.epub" --profile biology --dpi 240
```
