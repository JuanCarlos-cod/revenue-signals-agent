# Comprobacion automatica del proyecto (sin pausas). Ideal antes de la demo o la entrevista.
# Uso:  powershell -ExecutionPolicy Bypass -File .\probar.ps1
# Al terminar deja data/ y salidas/ en el estado de las 18 fuentes originales.

Set-Location $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$resultados = @()

function Comprobar($nombre, [scriptblock]$prueba) {
    try {
        $ok = & $prueba
    } catch {
        $ok = $false
    }
    $script:resultados += [pscustomobject]@{ Prueba = $nombre; Resultado = $(if ($ok) { "OK" } else { "FALLA" }) }
    $color = if ($ok) { "Green" } else { "Red" }
    Write-Host ("  [{0}] {1}" -f $(if ($ok) { "OK" } else { "FALLA" }), $nombre) -ForegroundColor $color
}

function Limpiar {
    if (Test-Path "data\fuentes_adicionales") { Remove-Item -Recurse -Force "data\fuentes_adicionales" }
}

Write-Host "`n=== 1. Entorno ===" -ForegroundColor Cyan
Comprobar "Python 3.10 o superior" {
    $v = (python -c "import sys; print(sys.version_info >= (3, 10))") 2>$null
    $v -eq "True"
}
Comprobar "Las 18 fuentes estan en data/fuentes" { (Get-ChildItem "data\fuentes\F*.md").Count -eq 18 }

Write-Host "`n=== 2. Herramienta local ===" -ForegroundColor Cyan
$web = python herramientas\consultar_parametros.py "Credito Flexible" Web rate_input | ConvertFrom-Json
Comprobar "Web / rate_input = pendiente_de_validar" { $web.registros[0].valor_configurado -eq "pendiente_de_validar" }
$suc = python herramientas\consultar_parametros.py "Credito Flexible" Sucursal rate_input | ConvertFrom-Json
Comprobar "Sucursal / rate_input = anual y vigente" { $suc.registros[0].valor_configurado -eq "anual" -and $suc.registros[0].estado_produccion -eq "vigente" }
$sinArgs = python herramientas\consultar_parametros.py 2>$null | ConvertFrom-Json
Comprobar "Sin argumentos devuelve error controlado" { [bool]$sinArgs.error }

Write-Host "`n=== 3. Pruebas automaticas ===" -ForegroundColor Cyan
$salidaTests = python -m unittest discover -s tests 2>&1 | Out-String
Comprobar "Pruebas unitarias (python -m unittest)" { $salidaTests -match "OK" -and $salidaTests -notmatch "FAILED" }

Write-Host "`n=== 4. Analisis de las 18 fuentes ===" -ForegroundColor Cyan
Limpiar
python -m revenue_agent analizar | Out-Null
$estado = Get-Content "salidas\estado.json" -Encoding UTF8 -Raw | ConvertFrom-Json
$orden = ($estado.senales.PSObject.Properties | Sort-Object { $_.Value.rank } | ForEach-Object { $_.Name }) -join ","
Comprobar "Orden de senales S1,S4,S2,S3 (obtenido: $orden)" { $orden -eq "S1,S4,S2,S3" }
Comprobar "Ruido descartado: F13, F14, F15, F16" { ($estado.descartados -join ",") -eq "F13,F14,F15,F16" }
Comprobar "S1 queda 'Por validar' (no confirma sin evidencia)" { $estado.senales.S1.estado -eq "Por validar" }
Comprobar "S1 consulta Web y Sucursal" { $estado.senales.S1.consultas."Web/rate_input" -eq "no_verificado" -and $estado.senales.S1.consultas."Sucursal/rate_input" -eq "conforme" }
Comprobar "S4 no consulta la herramienta" { @($estado.senales.S4.consultas.PSObject.Properties).Count -eq 0 }
Comprobar "S3 resuelve la contradiccion F12 -> F11" { ($estado.senales.S3.contradicciones -join ";") -match "^F12.F11$" }
Comprobar "Se generaron 4 briefs y sus registros" {
    (Get-ChildItem "salidas\briefs\*.md").Count -eq 4 -and (Get-ChildItem "salidas\trazabilidad\S*.md").Count -eq 4
}

Write-Host "`n=== 5. Evidencia nueva (simulacion de entrevista) ===" -ForegroundColor Cyan
$cambios = python -m revenue_agent agregar "ejemplos_entrevista\F19_confirmacion_tasa_web.md" | Out-String
Comprobar "F19 confirma la hipotesis de S1" { $cambios -match "confirmada por F19" }
$cambios = python -m revenue_agent agregar "ejemplos_entrevista\F23_tarifa_estacionamiento.md" | Out-String
Comprobar "F23 se descarta como ruido" { $cambios -match "F23 se descart" }
$cambios = python -m revenue_agent agregar "ejemplos_entrevista\F20_comision_duplicada_app.md" | Out-String
Comprobar "F20 crea la senal emergente E-F20" { $cambios -match "Nueva se.al E-F20" }

Write-Host "`n=== 6. Restaurar estado original ===" -ForegroundColor Cyan
Limpiar
python -m revenue_agent analizar | Out-Null
Remove-Item -ErrorAction SilentlyContinue "salidas\cambios.md", "salidas\estado_anterior.json"
Comprobar "data/ vuelve a tener solo las 18 fuentes" { -not (Test-Path "data\fuentes_adicionales") }

$fallas = @($resultados | Where-Object { $_.Resultado -eq "FALLA" })
Write-Host ""
if ($fallas.Count -eq 0) {
    Write-Host "RESULTADO: $($resultados.Count) de $($resultados.Count) comprobaciones OK" -ForegroundColor Green
    exit 0
}
Write-Host "RESULTADO: $($fallas.Count) de $($resultados.Count) comprobaciones FALLARON:" -ForegroundColor Red
$fallas | ForEach-Object { Write-Host "  - $($_.Prueba)" -ForegroundColor Red }
exit 1
