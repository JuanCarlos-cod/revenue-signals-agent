# Guía de recursos del reto

Resumen de estudio de los recursos entregados en `Revenue_Signals_Paquete_Candidatos_v3`.
Los archivos originales se copiaron **sin modificaciones** (verificado por checksum MD5).

## 1. Necesidad de negocio

Detectar temprano, a partir de comunicaciones internas dispersas (Teams, correos, actas, fichas,
políticas), dónde el banco podría estar **perdiendo o dejando de ganar ingresos**, sin generar falsas
alarmas. El agente debe conectar fuentes de distintas áreas, separar **hechos / hipótesis / datos
faltantes**, verificar con la herramienta cuando aporte, y producir un **Opportunity Brief** por señal
con citas verificables (ID de fuente + fragmento literal).

## 2. Mapa de fuentes (`data/fuentes/`)

| Señal | Fuentes | Tema | Clave |
|---|---|---|---|
| **S1** | F01–F04 | Tasa de desgravamen en Web: el sistema espera **anual**, se sospecha que se cargó la **mensual** | Mayor impacto potencial (~1/12 de la prima). Sin confirmación en producción; F04 sin ajustar por saldo y con adjunto faltante |
| **S2** | F05–F07 | Ampliar la exoneración de membresía de tarjeta | Trade-off retención vs. ingreso; criterio sin aprobar |
| **S3** | F08–F12 | Selector de día de pago en Banca Web | **Contradicción:** F11 dice "habilitado"; F12 (posterior, de Canales) corrige: solo maqueta |
| **S4** | F17–F18 | Depurar el tarifario de Banca Mayorista | Riesgo de eliminar comisiones poco usadas pero materiales; falta conciliación contable |
| Ruido | F13–F16 | Dashboard, RR. HH., servidores de pruebas, manual de marca | Mencionan "tarifas/cobros" **para negar** el impacto: trampa de palabras clave |

## 3. Índice (`data/indice_fuentes.csv`)

Columnas: `id, fecha, tipo, area, titulo, archivo`. La ruta `archivo` (`fuentes/F01.md`) es relativa
a la carpeta `data/`. Fechas del 03-sep al 23-sep-2026: sirven para ordenar los hechos y resolver
contradicciones. El `tipo` indica el peso de la evidencia (Ficha técnica / Política > Acta / Correo > Teams).

## 4. Herramienta (`herramientas/`)

```bash
python herramientas/consultar_parametros.py "Credito Flexible" Web rate_input
```

- 3 argumentos obligatorios: `PRODUCTO CANAL PARAMETRO`. Si faltan, devuelve `{"error": ...}` con código de salida 2.
- Coincidencia **exacta** sin distinguir mayúsculas; **las tildes sí importan** ("Crédito" no coincide).
- Sin coincidencias devuelve `encontrado: false` con código de salida 0: revisar el campo, no el código de salida.
- Siempre incluye la advertencia: *"contrastar con fuentes y no inferir leakage cuantificado"*.
- No se puede importar como función (se ejecuta al cargarse): invocarla con `subprocess`.
- `herramientas/consultar_parametros_pretty.py` es una variante propia (no del paquete) con `--pretty`
  para leer resultados en la terminal. El agente usa siempre la original.
- En Windows, usar `PYTHONIOENCODING=utf-8` para que las tildes de la salida no se corrompan.

### Registros (`parametros_simulados.json`)

| Producto / Canal / Parámetro | Esperado | Configurado | Estado | Revisión | Uso |
|---|---|---|---|---|---|
| Credito Flexible / Web / rate_input | anual | pendiente_de_validar | sin_confirmacion | 2026-09-06 | S1: hipótesis abierta |
| Credito Flexible / Sucursal / rate_input | anual | anual | vigente | 2026-09-06 | S1: línea base (pedido por F03) |
| Tarjeta TC / general / exoneracion_membresia | regla_por_segmento | segun_politica_vigente | vigente | 2026-09-15 | S2: la regla actual sigue igual |
| Credito Flexible / Web / selector_dia_pago | opciones | maqueta | no_desplegado | 2026-09-17 | S3: confirma F12 |

No hay registros para S4, ni valores numéricos de tasas o montos: la herramienta **no resuelve el
caso**; aporta contraste.

## 5. Qué pide el reto (`docs/README_reto.md`)

- Ingestar las 18 fuentes sin editarlas.
- Priorizar las señales y permitir investigar una seleccionada.
- Citar el ID y el fragmento de cada conclusión.
- Distinguir hechos, hipótesis y datos faltantes.
- Incorporar documentos nuevos en vivo durante la entrevista.
- Generar un Opportunity Brief por cada señal priorizada.
- Invocar la herramienta en al menos una señal, con criterio, y registrar la consulta y su resultado.
- Dejar un log de trazabilidad para al menos una señal: fuentes, consultas, resultados y aspectos no resueltos.
- Entregar el código, un README de ejecución, una demo de ≤5 minutos y las decisiones técnicas
  (modelos, costos, qué es determinístico y qué es agéntico).

## 6. Trampas a evitar

1. Cuantificar o confirmar una fuga sin evidencia (S1).
2. Aceptar comparaciones no ajustadas por saldo, fecha o elegibilidad (F01, F04).
3. Confundir certificación o una demo con producción (F01, F03, F11).
4. Ocultar contradicciones en lugar de resolverlas y reportarlas (F11 vs. F12).
5. Clasificar como señal un documento que niega el impacto (F13–F16).
6. Llamar a la herramienta sin propósito (S4).
7. Generalizar desde muestras pequeñas (F10).
8. Asumir que una comisión poco usada es obsoleta (F17, F18).
