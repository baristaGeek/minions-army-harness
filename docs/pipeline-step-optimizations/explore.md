# Step `explore`

## Tiempo observado

- Rango observado: ~20s a ~23s
- Naturaleza del costo: agentic de discovery

## Que hace hoy

Ejecuta el stage OpenSpec de exploracion con sesion compartida para los siguientes steps
`propose` y `apply`.

El prompt le pide:

- usar `openspec-explore`
- inspeccionar el estado del repositorio
- identificar contexto del cambio OpenSpec
- no escribir implementacion

## Lectura operativa

No es el step mas caro en terminos absolutos, pero si es un step con dos caracteristicas:

- agrega overhead fijo a todas las corridas
- su valor depende mucho del tipo de request

En cambios pequenos, ese overhead probablemente no compensa.

## Por que tarda

### El trabajo es discovery puro

Todo el tiempo se va en leer, entender y resumir. No produce valor directo en el repo ni valida un
artefacto final.

### Tiene incentivo a sobreexplorar

La instruccion "inspect the repository state" es abierta. Un agente conservador puede:

- abrir varios archivos
- revisar cambios OpenSpec previos
- inferir arquitectura
- confirmar restricciones

Eso es razonable, pero caro si el cambio es simple.

### El beneficio es indirecto

Este step solo vale si reduce tiempo o errores en `propose` y `apply`. Si no lo hace, es overhead.

## Hipotesis de valor versus costo

### Cuando probablemente si vale la pena

- requests ambiguos
- cambios cross-cutting
- repos con multiples areas posibles
- cambios donde OpenSpec existente no esta claro

### Cuando probablemente no vale la pena

- cambios muy localizados
- cambios cosmeticos
- requests con archivo/feature target evidente
- repos donde la estructura es estable y conocida

## Ideas de optimizacion

## Opcion A. Hacer `explore` condicional

### Idea

Antes de ejecutarlo, clasificar el request:

- simple
- medio
- complejo

Y correr `explore` solo para `medio` y `complejo`.

### Ganancia esperada

- Alta a nivel pipeline completo
- Baja a nivel step individual, porque el ahorro viene de omitirlo

### Ventajas

- Quita overhead fijo
- Mantiene discovery cuando realmente hace falta

### Riesgos

- Necesita una heuristica inicial buena
- Si clasificas mal, `apply` puede tardar mas o equivocarse

## Opcion B. Fusionar `explore` con `propose`

### Idea

Hacer que `propose` absorba una discovery minima y produzca directamente los artefactos.

### Ganancia esperada

- Media a alta
- Evita un proceso agentic separado

### Ventajas

- Menos arranques de agente
- Menos serializacion JSON intermedia
- Menos repeticion de contexto

### Riesgos

- `propose` se vuelve mas pesado
- Puede empeorar claridad de responsabilidades

## Opcion C. Prescribir un presupuesto de exploracion

### Idea

Cambiar el prompt para limitar la exploracion. Por ejemplo:

- leer maximo cierto numero de archivos
- priorizar `openspec/`, `README`, `docs/ARCHITECTURE.md`, `package.json`, `pyproject.toml`
- detenerse cuando ya tenga contexto suficiente

### Ganancia esperada

- Media

### Ventajas

- Reduce deriva del agente
- Conserva el step

### Riesgos

- Puede faltar contexto para casos raros

## Opcion D. Reusar un resumen de repo ya computado

### Idea

Generar una vez por corrida un "repo context snapshot" deterministico y compartirlo a varios steps.

### Ganancia esperada

- Media
- Tambien puede beneficiar `constitution`, `propose` y `apply`

### Ventajas

- Menos lecturas repetidas
- Menos exploracion ad hoc

### Riesgos

- El snapshot puede quedarse corto o volverse obsoleto si el repo cambia durante la corrida

## Opcion E. Reemplazarlo por heuristicas fijas para cambios simples

### Idea

Si el request menciona claramente:

- una pagina
- un archivo
- un modulo
- un endpoint

omitir `explore` y construir contexto con reglas simples.

### Ganancia esperada

- Alta en requests frecuentes y pequenos

### Riesgos

- Requiere parser o heuristicas de request

## Recomendacion priorizada para `explore`

1. Volverlo condicional.
2. Fusionarlo con `propose` para casos simples.
3. Limitar el presupuesto de lectura del agente.
4. Compartir un snapshot de contexto de repo entre steps.

## Senales a instrumentar

- cantidad de archivos abiertos
- tiempo de agente
- correlacion entre correr `explore` y reducir tiempo de `apply`
- tasa de errores de `apply` con y sin `explore`

## Resultado objetivo razonable

- Meta conservadora: que solo corra cuando su valor esperado sea alto
- Meta ideal: ahorro neto de >20s en promedio por corrida
