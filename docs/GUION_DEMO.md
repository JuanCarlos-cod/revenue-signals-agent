# Guion de demo (5 minutos) y preparación de la entrevista

## Antes de empezar

```bash
python -m revenue_agent analizar
```

Ten abiertos en VS Code `salidas/briefs/S1.md`, `salidas/trazabilidad/S1.md` y `salidas/briefs/S3.md`.
Si ya ensayaste con `agregar`, deja `data/` como estaba borrando `data/fuentes_adicionales/` y vuelve a
ejecutar `analizar`.

---

## Demo

### 0:00 – 0:40 · El problema

> "Hay información con impacto económico repartida en chats, correos y actas de distintas áreas.
> El riesgo es doble: no ver una fuga real o sobrerreaccionar ante un rumor. El agente conecta las
> fuentes y separa lo que se sabe de lo que se sospecha y de lo que falta, citando siempre el texto."

### 0:40 – 1:40 · Ranking

```bash
python -m revenue_agent analizar
```

- Hay 4 señales y 4 documentos descartados. Abre `salidas/senales_priorizadas.md`: cada descarte trae
  la frase que lo justifica («No cambia ninguna tarifa…»).
- La fórmula de prioridad es visible: impacto × confianza. S3 tiene mucha evidencia pero poco impacto,
  por eso queda última.

### 1:40 – 3:10 · Investigar S1

```bash
python -m revenue_agent investigar S1
```

- **Hechos:** el sistema espera una tasa anual [F01, F02, F03].
- **Hipótesis:** «parece coincidir con el valor mensual» [F01].
- **Faltantes:** el entorno (producción o certificación), el adjunto de F04 y una muestra con igual saldo.
- **Herramienta:** el agente decide consultar Web porque F01 menciona «tasa registrada», y Sucursal
  porque F01 menciona copiar configuraciones «entre canales». Web está sin validar y Sucursal conforme:
  la duda se acota a Web, pero no se prueba el defecto.
- **Sin cifras:** ni las fuentes ni la herramienta lo permiten.
- Abre `salidas/trazabilidad/S1.md`: el registro paso a paso con el comando exacto y el JSON completo.

### 3:10 – 3:50 · Contradicción (S3)

En `salidas/briefs/S3.md`, sección «Contradicciones»: F11 decía «habilitado» y F12 lo corrige.
Prevalece F12 y la herramienta (`maqueta / no_desplegado`) la respalda.

### 3:50 – 4:40 · Evidencia nueva

```bash
python -m revenue_agent agregar ejemplos_entrevista/F19_confirmacion_tasa_web.md
```

El agente lista lo que cambió: S1 incorpora F19, la hipótesis de F01 pasa a «confirmada por F19» y el
estado cambia a «Confirmada; impacto pendiente de cuantificar». Sigue sin poner una cifra.

### 4:40 – 5:00 · Cierre

> "Lo crítico es determinístico: citas, decisión de consultar, prioridad y cambios. El LLM es opcional,
> solo clasifica y redacta, y todo lo que devuelve se valida contra las fuentes."

---

## En la entrevista: qué hacer cuando te den un documento nuevo

1. Guárdalo como `.md` (con o sin cabecera `**ID:**`, `**Fecha:**`…; si no la tiene, el agente asigna
   el siguiente ID y la fecha de hoy).
2. Ejecuta `python -m revenue_agent agregar ruta/al/archivo.md`. Si el evaluador prefiere copiarlo
   directamente en `data/fuentes/`, también sirve: ejecuta `python -m revenue_agent analizar` y el
   agente lo incorpora con un aviso, aunque no esté en el índice.
3. Lee la lista de cambios en voz alta y abre el brief afectado.

| Si el documento… | El agente debería… |
|---|---|
| Confirma una hipótesis | Marcarla «confirmada por Fxx» y cambiar el estado de la señal |
| Corrige una fuente anterior («el acta anterior…») | Registrar una contradicción y dar por buena la fuente posterior |
| Trae un dato que faltaba (por ejemplo, el adjunto de F04) | Sumar hechos; el faltante original sigue listado y lo explicas tú |
| Habla de un tema nuevo con potencial económico | Crear una señal emergente `E-Fxx` |
| No tiene impacto | Descartarlo con su cita |

**Si algo sale distinto de lo esperado** (por ejemplo, un documento que no se asigna al tema correcto):
dilo abiertamente. El motivo está en el registro (`asignar_fuente` muestra los términos). La corrección
es explícita: añadir el término a `config/catalogo_senales.json` y volver a ejecutar. Es mejor mostrarlo
que esconderlo; es justo lo que demuestra que el sistema es auditable.

---

## Preguntas probables

**¿Por qué no usaste solo un LLM?**
Porque lo que evalúan es la disciplina con la evidencia. Las citas, la decisión de usar la herramienta
y la prioridad tienen que ser reproducibles. El LLM aporta flexibilidad para clasificar redacciones
nuevas, pero siempre bajo validación.

**¿Cómo evitas citas inventadas?**
En modo reglas, cada cita es una oración del original con su posición exacta. En modo LLM, la cita se
busca literalmente en la fuente y, si no aparece, se descarta y se registra. El pipeline comprueba
`texto[inicio:fin] == cita` siempre.

**¿Por qué consultaste la herramienta en S1 y no en S4?**
En S1 hay hipótesis y faltantes sobre un parámetro que la herramienta tiene (y F03 pide contrastar
canales). En S4 la base no tiene registros de tarifas mayoristas: consultar no aportaría nada, y queda
registrado así. En S2 el disparador no se activó porque nadie dice que la regla nueva ya se cargó.

**¿Por qué S4 está por encima de S2 y S3?**
Por impacto: retirar comisiones sin conciliar puede eliminar ingresos que no se recuperan. Es un juicio
de negocio, declarado y justificado en el catálogo, no oculto en un modelo.

**¿El impacto 1–5 no es arbitrario?**
Es un supuesto explícito y editable, con su justificación escrita. La alternativa (que lo decida el
modelo) sería igual de subjetiva y menos auditable. Con más tiempo lo calibraría con datos de volumen.

**¿Por qué no cuantificas la pérdida de S1?**
No hay montos en las fuentes, la comparación de F04 no está ajustada por saldo y la herramienta advierte
explícitamente que no se infiera. Sí explico el mecanismo: el valor quedaría cerca de 1/12 de la prima.

**¿Qué pasaría con datos reales?**
El modo reglas no envía nada fuera. Para el modo LLM usaría un despliegue privado (Bedrock o Vertex en
la nube del banco) o anonimizaría antes.

**¿Qué harías con más tiempo?**
Un conjunto de evaluación con documentos nuevos redactados de formas distintas, para medir el modo
reglas frente al modo LLM; detección de contradicciones implícitas entre hechos; y una interfaz simple.

**Limitaciones que conviene decir tú antes de que te las pregunten**
- Las reglas están calibradas sobre este corpus; redacciones muy distintas pueden fallar.
- El modo LLM no se ha ejecutado contra la API en este entorno.
- Solo se detectan contradicciones explícitas («corregir el acta anterior»).
