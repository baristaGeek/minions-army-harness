# Step `propose`

## Tiempo observado

- Rango observado: ~51s a ~67s
- Naturaleza del costo: agentic con generacion de artefactos OpenSpec

## Que hace hoy

Ejecuta el comando `/opsx:propose` a traves del agente y debe:

- crear o actualizar artefactos de propuesta OpenSpec
- mantenerse alineado al request
- no implementar todavia
- seguir la constitucion

## Interpretacion del costo

Este step no es tan caro como `apply` o `verify-build`, pero si es costoso para un paso cuyo valor
solo se materializa si realmente necesitas el ciclo completo de propuesta antes de implementar.

Si el pipeline siempre va a `apply` de inmediato, `propose` puede convertirse en costo estructural.

## Por que tarda

### Generar artefactos es mas que escribir un archivo

Un agente no solo escribe. Tambien:

- descubre si ya existe un cambio relacionado
- decide naming y scope
- revisa consistencia con OpenSpec
- produce resumen y plan

### Hay posible solapamiento con `explore`

Si `explore` ya identifico contexto del cambio, `propose` puede estar repitiendo parte del discovery.

### Hay posible solapamiento con `apply`

Si `apply` luego vuelve a leer artefactos, revisar scope y reentender el cambio, el pipeline paga
tres veces por comprender el mismo request:

- en `explore`
- en `propose`
- en `apply`

## Hipotesis de cuellos de botella

### Hipotesis 1. Demasiada libertad para decidir estructura del cambio

OpenSpec suele implicar decisiones sobre:

- carpeta del cambio
- nombre de la propuesta
- artefactos requeridos
- amplitud del alcance

Esa libertad cuesta tiempo.

### Hipotesis 2. El agente revisa demasiado el estado previo

Si intenta ser cuidadoso, puede mirar cambios existentes, specs archivadas y docs para evitar drift.

### Hipotesis 3. El prompt no le da un criterio de salida lo bastante agresivo

Puede seguir refinando plan y artefactos aunque ya alcanzo un resultado suficiente.

## Ideas de optimizacion

## Opcion A. Saltar `propose` cuando ya existe un cambio OpenSpec aplicable

### Idea

Antes de correrlo, detectar si ya existe:

- un cambio activo alineado al request
- tareas ya creadas
- specs suficientes para pasar directo a `apply`

### Ganancia esperada

- Alta para iteraciones sobre cambios en progreso

### Ventajas

- Elimina trabajo repetido

### Riesgos

- La deteccion debe ser confiable

## Opcion B. Fusionar `explore` y `propose`

### Idea

Permitir que un solo stage haga:

- discovery minima
- generacion de propuesta

### Ganancia esperada

- Media a alta

### Ventajas

- Menos serializacion entre steps
- Menos relectura de contexto

### Riesgos

- Prompt mas grande
- Responsabilidad menos separada

## Opcion C. Parametrizar naming y estructura de propuesta

### Idea

Resolver deterministicamente por codigo:

- nombre del cambio
- ubicacion del cambio
- plantilla base

Y dejar al agente solo llenar contenido.

### Ganancia esperada

- Media

### Ventajas

- Menos decisiones abiertas
- Menos drift entre corridas

### Riesgos

- Menor flexibilidad para casos especiales

## Opcion D. Limitar el trabajo de revision historica

### Idea

En vez de dejar discovery libre, pasarle al agente una lista concreta de fuentes permitidas:

- cambio activo similar, si existe
- `openspec/config.yaml`
- `README.md`
- `docs/ARCHITECTURE.md`

### Ganancia esperada

- Media

### Ventajas

- Menos lectura lateral

### Riesgos

- Puede omitir contexto util en casos complejos

## Opcion E. Hacer `propose` incremental

### Idea

Si ya hay propuesta parcial, actualizar solo archivos faltantes o secciones faltantes en lugar de
rehacer el cambio completo.

### Ganancia esperada

- Alta en flujos iterativos

### Ventajas

- Menos trabajo del agente
- Menos churn en archivos OpenSpec

### Riesgos

- Requiere deteccion fina de artefactos existentes

## Opcion F. Convertir parte de la propuesta en plantillas deterministicas

### Idea

Usar templates para:

- estructura de `proposal.md`
- secciones por defecto
- checklist o tareas base

Y reservar al agente solo el contenido especifico del request.

### Ganancia esperada

- Media

### Ventajas

- Menos deliberacion
- Salida mas consistente

### Riesgos

- Plantillas demasiado rigidas si el dominio cambia mucho

## Recomendacion priorizada para `propose`

1. Agregar fast-path cuando ya exista un cambio OpenSpec utilizable.
2. Fusionarlo con `explore` en requests simples.
3. Determinizar naming y estructura.
4. Hacer actualizacion incremental de propuestas existentes.

## Senales a instrumentar

- si creo un cambio nuevo o reutilizo uno existente
- cuantos archivos OpenSpec toco
- si leyo cambios archivados o activos
- correlacion entre `propose` y retrabajo posterior en `apply`

## Resultado objetivo razonable

- Meta conservadora: bajar a <30s
- Meta ideal: <10s cuando el cambio ya existe o la propuesta es simple
