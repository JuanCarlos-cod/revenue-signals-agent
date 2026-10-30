# Revenue Signals Agent — paquete de fuentes sintéticas

Este paquete contiene 18 fuentes ficticias (F01–F18) y un índice CSV. Ninguna fuente representa datos reales de Credicorp ni de sus clientes.

## Objetivo
Construir un prototipo que detecte señales con potencial económico, investigue relaciones entre fuentes, distinga hechos de hipótesis y produzca briefs con citas verificables.

## Requisitos mínimos
- Ingestar los 18 documentos sin editar su contenido.
- Presentar señales priorizadas y permitir investigar una señal seleccionada.
- Citar IDs de fuente y fragmentos que sustenten cada conclusión.
- Distinguir hechos confirmados, hipótesis y datos faltantes.
- Poder incorporar documentos adicionales durante una entrevista técnica.
- Producir un Opportunity Brief por cada señal priorizada.

## Entrega
Código o repositorio, README de ejecución, demo de hasta 5 minutos y breve explicación de decisiones técnicas. Dedicación objetivo: 4–6 horas; no se exige interfaz sofisticada ni multiagente.

## Uso de IA
Se permite cualquier stack; documentar modelos, dependencias, costos aproximados y qué tareas son determinísticas vs. agentic. No enviar información real/confidencial a servicios externos.

## Entrevista
45 minutos con incorporación de fuentes nuevas. Se evaluará capacidad de actualizar hallazgos ante evidencia adicional.

## Consulta adicional simulada (obligatoria, de alcance acotado)
Se incluye `herramientas/consultar_parametros.py` y una base local JSON con registros ficticios. Para al menos una señal, la solución debe decidir e invocar esta herramienta local con parámetros apropiados y registrar la consulta y su resultado. 
La herramienta funciona de manera independiente con Python 3, no requiere dependencias externas y puede invocarse mediante CLI, función Python o adaptador equivalente. No es necesario modificarla ni utilizar un framework específico. 
La herramienta NO resuelve el caso por sí sola. Se valorará el criterio de consulta, no la cantidad de llamadas.

## Trazabilidad de investigación
Además del Opportunity Brief, muestra para al menos una señal un registro breve de fuentes consultadas, consultas adicionales, resultados relevantes y aspectos no resueltos. No se solicitan razonamientos internos del modelo, sino un registro observable de acciones y evidencias.

## Límites del ejercicio
No se exige scraping, UI compleja, despliegue cloud, integraciones Teams, autenticación real ni multiagente. El agente puede ser un flujo simple con recuperación de documentos y una herramienta local. No debes revelar cadenas internas de razonamiento: basta un log de acciones observables.
