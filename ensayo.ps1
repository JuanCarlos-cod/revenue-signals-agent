# Ensayo interactivo de la entrevista: incorpora documentos nuevos uno a uno y muestra que cambia.
# Uso:  powershell -ExecutionPolicy Bypass -File .\ensayo.ps1
# Al terminar deja data/ como estaba (borra data/fuentes_adicionales).

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$casos = @(
    @{ Archivo = "F19_confirmacion_tasa_web.md";  Espera = "S1 pasa a 'Confirmada'; la hipotesis de F01 queda 'confirmada por F19'. Sigue sin cifra." },
    @{ Archivo = "F21_muestra_ajustada_web.md";   Espera = "S1 suma hechos (la muestra ajustada) y un faltante (no validada con Finanzas)." },
    @{ Archivo = "F22_selector_en_produccion.md"; Espera = "S3: nueva contradiccion F22 -> F12. La herramienta es anterior a F22: no la valida, queda pendiente." },
    @{ Archivo = "F23_tarifa_estacionamiento.md"; Espera = "Se descarta como ruido aunque dice 'tarifa'." },
    @{ Archivo = "F24_comision_identificada.md";  Espera = "S4 suma hechos y sube de prioridad. La duda de F17 (codigo de la comision) queda 'resuelto por F24'." },
    @{ Archivo = "F20_comision_duplicada_app.md"; Espera = "Aparece la senal emergente E-F20, separada de S4." },
    @{ Archivo = "nota_sin_cabecera.md";          Espera = "Sin cabecera: recibe el siguiente ID libre y la fecha de hoy, y se asigna a S1." }
)

function Pausa($texto) { Read-Host "`n>> $texto (Enter para seguir)" | Out-Null }

if (Test-Path "data\fuentes_adicionales") { Remove-Item -Recurse -Force "data\fuentes_adicionales" }
Write-Host "`n=== Estado inicial (18 fuentes del reto) ===" -ForegroundColor Cyan
python -m revenue_agent analizar

foreach ($caso in $casos) {
    $ruta = "ejemplos_entrevista\$($caso.Archivo)"
    Pausa "Siguiente documento: $($caso.Archivo)"
    Write-Host "`n=== Documento nuevo: $($caso.Archivo) ===" -ForegroundColor Cyan
    Get-Content $ruta -Encoding UTF8 | Write-Host
    Write-Host "`nQue deberia pasar: $($caso.Espera)" -ForegroundColor Yellow
    Pausa "Predice tu respuesta y luego incorporalo"
    python -m revenue_agent agregar $ruta
}

Pausa "Fin del ensayo. Se restaurara el estado original"
Remove-Item -Recurse -Force "data\fuentes_adicionales"
python -m revenue_agent analizar | Out-Null
Remove-Item -ErrorAction SilentlyContinue "salidas\cambios.md", "salidas\estado_anterior.json"
Write-Host "`nListo: data/ y salidas/ vuelven al estado de las 18 fuentes originales." -ForegroundColor Green
