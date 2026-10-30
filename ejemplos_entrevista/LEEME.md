# Documentos de ensayo para la entrevista

Estos documentos **no forman parte del paquete del reto**. Son ficticios y sirven para ensayar
cómo el agente actualiza sus hallazgos cuando llega evidencia nueva.

| Archivo | Qué prueba | Resultado esperado |
|---|---|---|
| `F19_confirmacion_tasa_web.md` | Una confirmación posterior de la hipótesis de S1 | S1 incorpora F19, la hipótesis de F01 pasa a «confirmada por F19» y el estado cambia a «Confirmada en fuente; impacto pendiente de cuantificar». Sigue sin cuantificarse. |
| `F20_comision_duplicada_app.md` | Un tema que no está en el catálogo | Aparece la señal emergente `E-F20`, separada de S4 aunque menciona una comisión. |

Para ensayar sin modificar `data/`:

```bash
python -m unittest discover -s tests -v
```

Para incorporarlos de verdad (quedan registrados en `data/fuentes_adicionales/`):

```bash
python -m revenue_agent agregar ejemplos_entrevista/F19_confirmacion_tasa_web.md
```
