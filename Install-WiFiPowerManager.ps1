#Requires -RunAsAdministrator

param (
    [Parameter(Mandatory=$true)]
    [string]$SSID,
    
    [Parameter(Mandatory=$false)]
    [int]$HomeMin = 0, # 0 = Nunca
    
    [Parameter(Mandatory=$false)]
    [int]$OfficeMin = 3
)

Write-Host "Iniciando configuración de WiFi Power Manager..." -ForegroundColor Cyan

# 1. Crear directorio de instalación en una ruta segura (Requiere Admin)
$installPath = "$env:ProgramData\WiFiPowerManager"
$scriptFile = "$installPath\wifi_logic.ps1"
$taskName = "WiFiPowerManagerTask"

if (!(Test-Path $installPath)) { 
    New-Item -ItemType Directory -Path $installPath | Out-Null 
}

# 2. Generar el script de lógica
$logicContent = @"
Start-Sleep -Seconds 5
`$ssid_target = "$SSID"
`$home_timeout = $HomeMin
`$office_timeout = $OfficeMin

# Extraer de forma exacta el nombre del SSID actual usando expresiones regulares
`$current_ssid = (netsh wlan show interfaces) | Select-String "^\s*SSID\s*:\s*(.*)" | ForEach-Object { `$_.Matches.Groups[1].Value.Trim() }

if (`$current_ssid -contains `$ssid_target) {
    powercfg /x monitor-timeout-ac `$home_timeout
    powercfg /x monitor-timeout-dc `$home_timeout
    powercfg /x standby-timeout-ac `$home_timeout
} else {
    powercfg /x monitor-timeout-ac `$office_timeout
    powercfg /x monitor-timeout-dc `$office_timeout
    powercfg /x standby-timeout-ac 10
}
"@

$logicContent | Out-File -FilePath $scriptFile -Encoding utf8 -Force

# 3. Preparar la Acción y Ajustes de la Tarea Programada
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptFile`""
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$trigger = New-ScheduledTaskTrigger -AtLogOn

# Crear un objeto temporal de la tarea para extraer su XML
$tempTask = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings

# 4. Inyectar el Trigger de Evento de Red de forma estructurada en el XML
$xml = [xml]($tempTask | Export-ScheduledTask)
$xmlNS = $xml.DocumentElement.NamespaceURI

# Crear nodos XML para el evento
$eventTrigger = $xml.CreateElement("EventTrigger", $xmlNS)
$enabled = $xml.CreateElement("Enabled", $xmlNS)
$enabled.InnerText = "true"
$subscription = $xml.CreateElement("Subscription", $xmlNS)
$subscription.InnerText = "<QueryList><Query Id='0' Path='Microsoft-Windows-NetworkProfile/Operational'><Select Path='Microsoft-Windows-NetworkProfile/Operational'>*[System[(EventID=10000)]]</Select></Query></QueryList>"

# Acoplar los nodos al documento
$eventTrigger.AppendChild($enabled) | Out-Null
$eventTrigger.AppendChild($subscription) | Out-Null
$xml.Task.Triggers.AppendChild($eventTrigger) | Out-Null

# 5. Registrar la tarea final con el XML modificado y privilegios de SYSTEM
Register-ScheduledTask -Xml $xml.OuterXml -TaskName $taskName -User "SYSTEM" -Force | Out-Null

Write-Host "Configuración completada con éxito para la red: $SSID" -ForegroundColor Green
