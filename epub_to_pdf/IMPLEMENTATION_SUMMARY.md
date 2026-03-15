# Sistema de Releases Automatizado - Implementación Completada

**Fecha:** 15 de marzo de 2026  
**Estado:** ✅ Listo para producción

## Archivos Creados

### 1. Core Refactoring
- **epub_to_pdf/epub_to_pdf.py** - Refactorizado con:
  - ✅ Soporte `sys._MEIPASS` para PyInstaller
  - ✅ Descarga lazy de TinyTeX en `~/.cache/epub2pdf/`
  - ✅ Búsqueda dinámica: cache → TINYTEX_HOME → PATH → descarga automática
  - ✅ Fix `LD_LIBRARY_PATH_ORIG` para Linux (evita conflictos de libs)
  - ✅ Imports actualizados: json, urllib, tarfile, zipfile, subprocess, sys, platform

### 2. Build Configuration
- **epub_to_pdf/epub_to_pdf.spec** - Configuración PyInstaller:
  - ✅ Fuentes embebidas desde `fonts/`
  - ✅ UPX compression habilitado
  - ✅ Exclusiones: matplotlib, numpy, scipy, pandas, PIL, tkinter
  - ✅ Modo onefile (ejecutable standalone)

### 3. Scripts Auxiliares
- **epub_to_pdf/scripts/download_tinytex.py**:
  - ✅ Descarga TinyTeX desde GitHub releases oficiales
  - ✅ Detección automática de plataforma
  - ✅ Soporte Windows, Linux, macOS
  - ✅ Usado por GitHub Actions workflow

- **epub_to_pdf/scripts/build_local.py**:
  - ✅ Testing local de builds PyInstaller
  - ✅ Limpieza automática de artifacts
  - ✅ Verificación de dependencias
  - ✅ Info de tamaño del ejecutable

### 4. CI/CD Pipeline
- **.github/workflows/release.yml** - GitHub Actions:
  - ✅ Trigger en tags `v*` (ej: v0.3.0)
  - ✅ Matrix build: ubuntu-20.04 + windows-latest
  - ✅ Python 3.11 con cache de pip
  - ✅ Build automatizado con PyInstaller
  - ✅ Descarga TinyTeX por plataforma
  - ✅ Creación de archives: .tar.gz (Linux), .zip (Windows)
  - ✅ GitHub Release automático con:
    - Ejecutables multiplataforma
    - TinyTeX opcional
    - Release notes generadas
  - ✅ Permisos: `contents: write`

### 5. Documentación
- **RELEASES.md**:
  - ✅ Guía de instalación por plataforma
  - ✅ Quick start para Windows y Linux
  - ✅ Instalación manual de TinyTeX
  - ✅ Añadir a PATH del sistema
  - ✅ Ejemplos de uso
  - ✅ Troubleshooting completo
  - ✅ Uso offline (air-gapped)
  - ✅ Requisitos de sistema

- **epub_to_pdf/README.md** - Actualizado:
  - ✅ Sección destacada de binarios precompilados
  - ✅ Links a releases
  - ✅ Separación clara: binarios vs código fuente

### 6. Project Configuration
- **epub_to_pdf/pyproject.toml**:
  - ✅ Version bumped: 0.2.1 → 0.3.0
  - ✅ Description actualizada
  - ✅ dev-dependencies añadidas: pyinstaller>=6.0

## Arquitectura del Sistema

```
Usuario descarga ejecutable (~10 MB)
         ↓
   Primera ejecución
         ↓
   ¿xelatex disponible?
         ↓ NO
   Descarga TinyTeX (~100 MB)
         ↓
   Instala en ~/.cache/epub2pdf/
         ↓
   Conversión EPUB → PDF
```

**Búsqueda de xelatex (prioridad):**
1. Cache local: `~/.cache/epub2pdf/tinytex/bin/`
2. Variable entorno: `$TINYTEX_HOME/bin/`
3. Sistema PATH: `which xelatex`
4. Descarga automática desde GitHub

## Tamaños Estimados

| Componente | Tamaño |
|------------|--------|
| Ejecutable Windows | ~8-12 MB |
| Ejecutable Linux | ~7-10 MB |
| TinyTeX-windows.zip | ~90-110 MB |
| TinyTeX-linux.tar.gz | ~80-100 MB |
| Fuentes (embebidas) | ~4 MB |
| **Total descarga usuario** | **~100-120 MB** (primera vez) |

## Testing Local

Antes de hacer push/release, puedes probar el build localmente:

```bash
# Navegar al directorio
cd epub_to_pdf

# Instalar dependencias de desarrollo
pip install -e ".[dev]"

# Build local
python scripts/build_local.py

# Ejecutable generado en: dist/epub2pdf (o dist/epub2pdf.exe)
```

## Crear Release

### Opción 1: Automático (Recomendado)

```bash
# 1. Commit cambios
git add .
git commit -m "feat: add automated release system with PyInstaller"

# 2. Crear tag de versión
git tag v0.3.0

# 3. Push con tags
git push origin main --tags
```

GitHub Actions se ejecutará automáticamente y publicará el release en ~10-15 minutos.

### Opción 2: Manual desde Web UI

1. Ve a GitHub → Releases → "Draft a new release"
2. Crea tag: `v0.3.0`
3. Título: `epub2pdf v0.3.0`
4. Descripción: (se puede dejar vacío, el workflow genera automáticamente)
5. Click "Publish release"

El workflow se ejecutará y añadirá los binarios automáticamente.

## Verificación Post-Release

Después de que el workflow complete:

1. ✅ Verificar que aparecen 4 assets en el release:
   - `epub2pdf-windows-x64.zip`
   - `epub2pdf-linux-x64.tar.gz`
   - `TinyTeX-1-windows.zip`
   - `TinyTeX-1-linux.tar.gz`

2. ✅ Descargar ejecutable para tu plataforma

3. ✅ Probar conversión básica:
   ```bash
   ./epub2pdf test.epub
   ```

4. ✅ Verificar descarga automática de TinyTeX (si no estaba instalado)

5. ✅ Verificar que segunda ejecución usa cache (sin descarga)

## Troubleshooting CI/CD

### Workflow falla en build
- Verificar que `epub_to_pdf.spec` existe
- Verificar que `fonts/` directory existe con archivos .ttf
- Revisar logs en GitHub Actions

### Workflow falla en descarga TinyTeX
- Verificar conectividad a GitHub API
- Verificar que script `scripts/download_tinytex.py` es ejecutable
- Timeout: aumentar timeout en workflow si necesario

### Release no se publica
- Verificar que tag comienza con `v` (ej: v0.3.0, no 0.3.0)
- Verificar permisos del repositorio: Settings → Actions → General → Workflow permissions → "Read and write"
- Verificar que `GITHUB_TOKEN` tiene permisos `contents: write`

## Próximas Mejoras (Opcional)

- [ ] Soporte para macOS (añadir a matrix)
- [ ] Cache de TinyTeX entre builds (actions/cache)
- [ ] Firma de código (code signing) para Windows
- [ ] Notarización para macOS
- [ ] Tests automatizados de conversión
- [ ] Changelog automatizado con commits convencionales

## Notas de Memoria

- TinyTeX NO se embebe en ejecutable (sería >200 MB)
- Descarga lazy mantiene ejecutable ligero (~10 MB)
- Cache en `~/.cache/` sigue estándar XDG
- Fix LD_LIBRARY_PATH esencial para Linux + PyInstaller
- UPX reduce tamaño ~30-40%
