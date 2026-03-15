# epub-to-pdf

Convierte archivos EPUB a PDF desde la terminal.

## Instalación Rápida (Binarios Precompilados) ⚡

**¡No requiere Python!** Descarga el ejecutable standalone para tu plataforma:

- **[Windows (x64)](../../releases/latest)**: `epub2pdf-windows-x64.zip` (~10 MB)
- **[Linux (x64)](../../releases/latest)**: `epub2pdf-linux-x64.tar.gz` (~8 MB)

Extrae y ejecuta:
```bash
# Windows (PowerShell)
.\epub2pdf.exe mybook.epub

# Linux
./epub2pdf mybook.epub
```

En la primera ejecución, TinyTeX (~100 MB) se descargará automáticamente. Ver [RELEASES.md](../../RELEASES.md) para más detalles.

---

## Instalación desde Código Fuente (Python)

Si prefieres instalar desde código fuente con Python:

El script gestiona automáticamente sus dependencias en la primera ejecución:

- Instala la dependencia Python faltante (`pypandoc`)
- Descarga `pandoc` si no está disponible
- Descarga `TinyTeX` en modo headless (sin instaladores GUI), en cache de usuario
- Descarga fuentes locales en `fonts/` para mejorar cobertura de símbolos matemáticos Unicode

### Instalación desde GitHub (un comando)

```bash
python -m pip install "git+https://github.com/fbettic/ScriptCollection.git#subdirectory=epub_to_pdf"
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
