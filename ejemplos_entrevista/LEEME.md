# Documentos de ensayo para la entrevista

Estos documentos **no forman parte del paquete del reto**. Son ficticios y sirven para ensayar
cómo el agente actualiza sus hallazgos cuando llega evidencia nueva.

| Archivo | Qué prueba | Resultado esperado |
|---|---|---|
| `F19_confirmacion_tasa_web.md` | Confirmación posterior de una hipótesis | S1 pasa a «Confirmada en fuente; impacto pendiente de cuantificar» y la hipótesis de F01 queda «confirmada por F19». Sigue sin cifra. |
| `F20_comision_duplicada_app.md` | Tema fuera del catálogo | Aparece la señal emergente `E-F20`, separada de S4 aunque menciona una comisión. |
| `F21_muestra_ajustada_web.md` | Llega el dato que faltaba en F04 | S1 suma hechos y un nuevo faltante: la muestra no está validada con Finanzas. |
| `F22_selector_en_produccion.md` | Una fuente corrige a otra que ya corregía | Nueva contradicción F22 → F12. La herramienta (revisada el 17-sep) es anterior a F22, así que no la valida y queda pendiente. |
| `F23_tarifa_estacionamiento.md` | Ruido con una palabra económica | Se descarta como ruido aunque dice «tarifa». |
| `F19_aclaracion_captura_web.md` | Evidencia que **refuta** una hipótesis (texto con saltos de línea a mitad de frase) | Contradicción F19 → F01: la hipótesis de F01 queda «refutada por F19», su duda (¿producción o certificación?) queda «resuelto por F19», S1 baja de 5.0 a 3.75 y el estado pasa a «Hipótesis refutada en parte; por validar». La herramienta (06-sep) es anterior a F19 y no la valida. F04 sigue abierta. |
| `F24_comision_identificada.md` | Se resuelve un dato faltante | S4 suma hechos y sube de prioridad. La duda de F17 (el código de la comisión) queda «resuelto por F24»; las demás dudas de S4 siguen abiertas. |
| `nota_sin_cabecera.md` | Texto suelto sin cabecera | Recibe el siguiente ID libre y la fecha de hoy, y se asigna a S1. |

## Ensayo guiado

Incorpora los documentos uno a uno, muestra cada uno con lo que debería pasar, pausa para que
predigas el resultado y, al final, deja `data/` como estaba:

```bash
powershell -ExecutionPolicy Bypass -File .\ensayo.ps1
```

## Sin modificar `data/`

```bash
python -m unittest discover -s tests -v
```
