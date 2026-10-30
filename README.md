# Revenue Signals Agent

Prototipo que lee comunicaciones internas (sintéticas), detecta señales con potencial económico,
conecta fuentes de distintas áreas, separa **hechos / hipótesis / datos faltantes**, consulta una
herramienta local cuando aporta evidencia y produce un **Opportunity Brief** por señal, con citas
literales verificadas y un registro de investigación observable.

## Ejecución

Requisitos: Python 3.10 o superior. El modo por defecto **no necesita instalar nada ni conexión a internet**.

```bash
python -m revenue_agent analizar
```

```bash
python -m revenue_agent investigar S1
```

```bash
python -m revenue_agent agregar ruta/al/documento_nuevo.md
```

```bash
python -m unittest discover -s tests -v
```

| Comando | Qué hace |
|---|---|
| `analizar` | Procesa todas las fuentes, prioriza las señales y escribe las salidas en `salidas/` |
| `investigar S1` | Muestra en pantalla el brief y el registro de investigación de una señal |
| `agregar archivo.md` | Copia el documento (sin editarlo) a `data/fuentes_adicionales/`, lo registra, vuelve a analizar todo y lista **qué cambió** |

Todos los comandos aceptan `--modo reglas` (por defecto) o `--modo llm` (ver más abajo).

**Otra forma de incorporar fuentes:** copiar el `.md` directamente en `data/fuentes/` y ejecutar
`analizar`. Aunque no figure en `indice_fuentes.csv`, se incorpora: toma el ID y la fecha de su
cabecera (o del nombre del archivo, como `F19.md`; si no hay, el siguiente ID libre y la fecha de hoy).
Se muestra un aviso y queda registrado en `trazabilidad/global.jsonl`.

También se puede añadir una fila a `indice_fuentes.csv`. La lectura del índice tolera los errores
habituales al editarlo a mano: guardado desde Excel (separador `;` y codificación de Windows), títulos
con comas sin comillas y rutas que no existen. En vez de detenerse, el agente muestra un aviso y sigue.

### Salidas

```
salidas/
  senales_priorizadas.md      Ranking, documentos descartados (con su cita) y cambios
  briefs/S1.md …              Un Opportunity Brief por señal
  trazabilidad/S1.md, .jsonl  Registro de acciones: fuentes, consultas, resultados, pendientes
  trazabilidad/global.jsonl   Ingesta (con sha256 de cada fuente) y descarte de ruido
  estado.json                 Estado resumido, base para detectar cambios
  cambios.md                  Diferencias frente al análisis anterior
```

## Estructura

```
data/                         Fuentes originales e índice (sin editar)
herramientas/
  consultar_parametros.py     Herramienta local del reto (original, sin modificar; la usa el agente)
  parametros_simulados.json   Base de la herramienta (original)
  consultar_parametros_pretty.py  Variante propia para consultas manuales (--pretty); el agente no la usa
config/catalogo_senales.json  Catálogo de dominio: temas, términos, impacto y política de consultas
revenue_agent/
  ingesta.py                  Lectura de índices y documentos; segmentación con posiciones exactas
  clasificador.py             Clasificación determinística de oraciones
  herramienta.py              Adaptador de consultar_parametros.py (subprocess) e interpretación
  llm.py                      Capa opcional con Claude (salida JSON con esquema, caché)
  pipeline.py                 Orquestación, contradicciones, prioridad y detección de cambios
  reporte.py                  Briefs, ranking y registros en Markdown/JSON
tests/                        Pruebas del comportamiento esperado
ejemplos_entrevista/          Documentos de ensayo (no son parte del paquete)
docs/                         Enunciado original y guía de recursos
```

## Cómo funciona

1. **Ingesta.** Lee `indice_fuentes.csv` y cada documento sin modificarlo, y registra su sha256.
   Divide el cuerpo en oraciones y guarda la posición exacta de cada una en el texto original.
2. **Clasificación.** Cada oración se etiqueta como hecho, confirmación, hipótesis, dato faltante,
   advertencia metodológica, corrección o negación de impacto.
3. **Filtrado de ruido.** Se descarta un documento que niega explícitamente el impacto y no contiene
   otras afirmaciones abiertas (F13–F16). Se cita la frase que lo justifica.
4. **Agrupación en señales.** Cada documento se asigna al tema del catálogo con más coincidencias de
   términos (fuertes = 2 puntos, débiles = 1; mínimo 2). Un documento con potencial económico que no
   encaja en ningún tema crea una **señal emergente** (`E-Fxx`).
5. **Actualización ante evidencia nueva.** Se compara cada fuente con las anteriores:
   - una **confirmación** posterior marca la hipótesis previa afín como «confirmada por Fxx»;
   - un hecho, confirmación o corrección posterior que responde a un **dato faltante** lo marca como
     «resuelto por Fxx» (cada oración resuelve como máximo una duda, la más específica);
   - una **corrección** que alude a una fuente anterior la contradice: si responde la duda que esa fuente
     dejaba abierta, sus hipótesis quedan «refutadas por Fxx»; si no, se enfrenta a la afirmación previa
     más afín. Prevalece la fuente posterior y la contradicción se reporta.
6. **Herramienta.** Para cada consulta configurada en el tema, el agente la ejecuta **solo si** una
   hipótesis, un dato faltante o una corrección contiene uno de sus disparadores. Registra el
   disparador, el comando, la respuesta completa y una interpretación acotada (nunca cuantifica).
7. **Priorización.** `prioridad = impacto × confianza`, donde
   `confianza = (0,5 + 0,1 × evidencia) × (1 − 0,5 × hipótesis refutadas / hipótesis)` y
   `evidencia = 1 + 0,5·hechos + 0,5·fuentes + 1,5·confirmaciones + 0,5·consultas con registro` (máximo 5).
   Una señal cuyas hipótesis caen pierde prioridad; si caen todas, la confianza se reduce a la mitad.
8. **Salidas.** Brief, registro de investigación y comparación con el estado anterior.

### Resultado sobre el paquete

| # | Señal | Prioridad | Estado | Herramienta |
|---|---|---|---|---|
| 1 | S1 Tasa de desgravamen Web (F01–F04) | 5.0 | Por validar | Web `no_verificado` y Sucursal `conforme`: la duda queda acotada a Web |
| 2 | S4 Tarifario Mayorista (F17–F18) | 2.8 | Por validar | No se consulta: la base no tiene registros aplicables |
| 3 | S2 Exoneración de membresía (F05–F07) | 2.55 | Por validar | No se consulta: ninguna hipótesis la justifica |
| 4 | S3 Día de pago (F08–F12) | 1.5 | Hipótesis refutada en parte (F11, por F12) · contradicción resuelta | `no_desplegado`: respalda a F12 |
| — | F13–F16 | — | Descartados con cita | — |

## Decisiones técnicas

- **Híbrido, con lo crítico determinístico.** Las citas, la decisión de consultar la herramienta, la
  priorización y la detección de cambios no dependen del modelo. Son reproducibles y auditables.
- **Citas verificables por construcción.** En modo reglas, cada cita es una oración del original con
  sus posiciones exactas. En modo LLM, toda cita se busca literalmente en la fuente y, si no aparece,
  se descarta y se registra. El pipeline comprueba `texto[inicio:fin] == cita` en ambos modos.
- **Catálogo de dominio explícito.** Los temas, el impacto (1–5, con justificación) y la política de
  consultas viven en `config/catalogo_senales.json`. El impacto es un juicio de negocio, así que se
  declara en lugar de esconderlo en un modelo. Los temas no catalogados aparecen como señales emergentes.
- **Herramienta sin modificar.** El script se ejecuta todo al importarse y llama a `sys.exit`, así que
  se invoca con `subprocess`, con `PYTHONIOENCODING=utf-8` (necesario en Windows) y quitando las tildes
  de los argumentos, porque la base usa «Credito» sin tilde. Para revisiones manuales durante la demo
  existe una variante aparte, `consultar_parametros_pretty.py`, con el mismo JSON y la opción `--pretty`:

  ```bash
  python herramientas/consultar_parametros_pretty.py "Credito Flexible" Web rate_input --pretty
  ```
- **Sin cuantificación.** Ninguna fuente aporta montos y la propia herramienta advierte que no se infiera
  la fuga. El impacto se describe de forma cualitativa.
- **Actualización ante evidencia nueva.** `agregar` vuelve a analizar todo el corpus (con 20 documentos
  tarda menos de un segundo) y compara con `estado.json`: nuevas fuentes, cambios de estado y de
  prioridad, hipótesis confirmadas o superadas y nuevas señales.

### Qué es determinístico y qué es agéntico

| Tarea | Modo `reglas` | Modo `llm` |
|---|---|---|
| Ingesta, segmentación y hash | Determinístico | Determinístico |
| Clasificar afirmaciones | Reglas lingüísticas | **Claude**, con citas validadas literalmente |
| Asignar tema / detectar señal nueva | Términos del catálogo | **Claude** (tema existente, NUEVO o NINGUNO) |
| Decidir e invocar la herramienta | Política explícita con disparadores | Igual (determinístico) |
| Contradicciones, confirmaciones y prioridad | Determinístico | Determinístico |
| Resumen y próximos pasos del brief | Plantilla | **Claude**, rechazado si cita IDs ajenos a la señal |
| Detección de cambios | Determinístico | Determinístico |

### Modo LLM (opcional)

```bash
pip install -r requirements.txt
```

```bash
python -m revenue_agent analizar --modo llm
```

- Modelo: `claude-opus-5-5` (se cambia con la variable `REVENUE_AGENT_MODEL`), con esfuerzo `low` y
  salida JSON restringida por esquema. Usa los fallbacks del servidor ante rechazos por políticas.
- Credenciales: `ANTHROPIC_API_KEY` o un perfil de `ant auth login`.
- Las respuestas se guardan en caché (`salidas/cache_llm/`) por contenido: volver a analizar sin
  cambios cuesta cero, y al agregar un documento solo se procesa ese documento y los briefs.
- Costo aproximado de un análisis completo sin caché: unas 22 llamadas, ~25k tokens de entrada y
  ~12k de salida, del orden de **0,35 USD** a 4/20 USD por millón de tokens. Es una estimación: el
  modo LLM no se ha ejecutado contra la API en este entorno.
- Si el SDK o las credenciales no están disponibles, el análisis continúa en modo reglas y lo deja
  registrado en `trazabilidad/global.jsonl` y en el encabezado del ranking.
- Las fuentes del reto son sintéticas. Con datos reales se usaría un despliegue privado (por ejemplo
  Bedrock o Vertex en la nube del banco) o solo el modo reglas.

## Limitaciones conocidas

- Las reglas lingüísticas y los términos del catálogo están calibrados sobre este corpus. Redacciones
  muy distintas pueden clasificarse mal; para eso existe el modo LLM.
- El impacto de las señales emergentes se fija en 3 («por evaluar») en modo reglas.
- La detección de contradicciones cubre correcciones explícitas a fuentes anteriores, no
  contradicciones implícitas entre hechos.
