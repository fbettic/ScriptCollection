
para instalar las extensiones de vs code
cat extensions-list.txt | xargs -n 1 code --install-extension


##Install-WiFiPowerManager.ps1
Este script configura una Tarea Programada que ajusta automáticamente el tiempo de bloqueo de pantalla según tu red Wi-Fi. Si detecta el SSID elegido, aplica una configuración de "Hogar" (ej. nunca bloquearse); si estás en otra red, aplica la de "Oficina". Se ejecuta de forma invisible con privilegios de sistema cada vez que inicias sesión o cambias de red.

Para ejecutarlo directamente desde la web sin descargar el archivo, abre PowerShell como Administrador y pega este comando (ajustando tu red y minutos):

```PowerShell
$url = "https://raw.githubusercontent.com/fbettic/ScriptCollection/refs/heads/main/Install-WiFiPowerManager.ps1"
Invoke-Command -ScriptBlock ([ScriptBlock]::Create((Invoke-RestMethod -Uri $url))) -Ar 
```

---
