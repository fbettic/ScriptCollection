# Pre-Release Checklist

## ✅ Verificación de Archivos

- [x] epub_to_pdf/epub_to_pdf.py - refactorizado con descarga lazy
- [x] epub_to_pdf/epub_to_pdf.spec - configuración PyInstaller
- [x] epub_to_pdf/scripts/download_tinytex.py - script auxiliar descarga
- [x] epub_to_pdf/scripts/build_local.py - script testing local
- [x] .github/workflows/release.yml - workflow CI/CD
- [x] epub_to_pdf/pyproject.toml - actualizado a v0.3.0
- [x] RELEASES.md - documentación instalación binarios
- [x] epub_to_pdf/README.md - actualizado con sección binarios
- [x] epub_to_pdf/fonts/ - contiene 5 archivos .ttf

## 🔧 Testing Local (Opcional pero Recomendado)

```bash
# 1. Navegar al directorio
cd epub_to_pdf

# 2. Instalar dependencias dev
pip install pyinstaller pypandoc

# 3. Build local
python scripts/build_local.py

# 4. Probar ejecutable generado
cd dist
./epub2pdf "path/to/test.epub"  # Linux
.\epub2pdf.exe "path\to\test.epub"  # Windows
```

## 📦 Crear Release

### Paso 1: Commit y Push

```bash
git add .
git commit -m "feat: add automated multi-platform release system

- Refactor epub_to_pdf.py with lazy TinyTeX download
- Add PyInstaller .spec configuration  
- Create GitHub Actions workflow for Windows + Linux
- Add release documentation and installation guides
- Bundle fonts, auto-provision TinyTeX on first run"

git push origin main
```

### Paso 2: Crear Tag

```bash
# Crear tag de versión
git tag v0.3.0 -m "Release v0.3.0: Standalone executables"

# Push tag
git push origin v0.3.0
```

### Paso 3: Monitorear Workflow

1. Ve a: https://github.com/fbettic/ScriptCollection/actions
2. Deberías ver workflow "Build and Release" ejecutándose
3. Espera ~10-15 minutos para completar
4. Revisa logs si hay errores

### Paso 4: Verificar Release

1. Ve a: https://github.com/fbettic/ScriptCollection/releases
2. Verifica que release v0.3.0 aparece con 4 assets:
   - ✅ epub2pdf-windows-x64.zip
   - ✅ epub2pdf-linux-x64.tar.gz  
   - ✅ TinyTeX-*-windows.zip
   - ✅ TinyTeX-*-linux.tar.gz

## 🧪 Testing Post-Release

### Windows
```powershell
# Descargar epub2pdf-windows-x64.zip
# Extraer
# Ejecutar:
.\epub2pdf.exe test.epub

# Primera ejecución debería:
# - Descargar TinyTeX automáticamente (~100 MB)
# - Instalar en %LOCALAPPDATA%\epub2pdf\tinytex
# - Generar test.pdf exitosamente

# Segunda ejecución debería:
# - Usar TinyTeX del cache (sin descarga)
# - Ser más rápida
```

### Linux
```bash
# Descargar epub2pdf-linux-x64.tar.gz
tar -xzf epub2pdf-linux-x64.tar.gz
chmod +x epub2pdf
./epub2pdf test.epub

# Primera ejecución debería:
# - Descargar TinyTeX automáticamente (~100 MB)
# - Instalar en ~/.cache/epub2pdf/tinytex
# - Generar test.pdf exitosamente

# Segunda ejecución debería:
# - Usar TinyTeX del cache (sin descarga)
# - Ser más rápida
```

## 🐛 Si Algo Falla

### Workflow no se ejecuta
- Verifica que el tag comience con 'v': `v0.3.0` ✅ (no `0.3.0` ❌)
- Verifica GitHub Actions está habilitado en el repo
- Revisa la pestaña Actions por errores

### Build falla
- Revisa logs detallados en GitHub Actions
- Verifica que todos los archivos fueron committed
- Prueba build local primero: `python scripts/build_local.py`

### Release no tiene binarios
- Verifica permisos del workflow:
  - Settings → Actions → General → Workflow permissions
  - Selecciona "Read and write permissions"
  - Save

### Ejecutable no funciona
- Verifica que descargaste el archivo correcto para tu plataforma
- En Linux: asegúrate de dar permisos de ejecución `chmod +x epub2pdf`
- Verifica que tienes conexión a internet para descarga de TinyTeX

## 📝 Después del Release

1. Actualiza el README principal si necesario
2. Anuncia el release (opcional):
   - GitHub Discussions
   - Redes sociales
   - Blog personal

3. Monitorea issues por problemas de usuarios

4. Planifica próxima versión:
   - Soporte macOS
   - Tests automatizados
   - Mejoras de rendimiento

## 🎉 ¡Listo!

Tu sistema de releases está completamente configurado. Cada vez que crees un nuevo tag `v*`, GitHub Actions:
1. Compilará ejecutables para Windows y Linux
2. Descargará TinyTeX apropiado
3. Creará un release con todos los binarios
4. Generará release notes automáticamente

¡No más builds manuales! 🚀
