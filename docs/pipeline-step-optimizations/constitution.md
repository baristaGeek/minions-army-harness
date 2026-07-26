# Step `constitution`

## Tiempo observado

Fuente actual: comentario de instrumentacion en [minions_army/core/runtime/orchestrator_runtime.py](/d:/source/enterprise/fork/minions-army/minions_army/core/runtime/orchestrator_runtime.py:427).

- `ne` (`config` no existe): `51787`, `61817`, `68664`, `64273` ms
- `e` (`config` ya existe): `32740`, `33592` ms

Resumen:

- `ne` promedio: ~61.5s
- `ne` rango: ~51.8s a ~68.7s
- `e` promedio: ~33.2s
- diferencia visible entre `ne` y `e`: ~28.4s menos cuando el archivo ya existe

## Lectura del comportamiento actual

Hoy el step sigue siendo completamente agentic:

- `OpenspecConstitutionStep` construye prompt
- resuelve sesion
- llama `run_agent_stage(...)`
- persiste el JSON de salida

Eso significa que incluso el camino `e`, donde el prompt dice "si ya existe una configuracion valida, corta enseguida", sigue pagando:

- arranque del agente
- parseo de un prompt largo
- chequeo inicial del repo
- decision del agente para confirmar que puede hacer skip
- emision del JSON final

En otras palabras: el prompt ya intenta optimizar, pero el runtime todavia no evita el costo base del agente.

## Que nos dice la diferencia entre `ne` y `e`

La diferencia entre `ne` y `e` es importante porque separa dos costos:

- costo fijo del enfoque agentic: alrededor de 30s+
- costo variable de exploracion y escritura cuando hay que configurar: alrededor de 20s a 35s extra

Interpretacion practica:

- `e` no es lento por trabajo real de repo, sino por overhead de agente
- `ne` es lento por overhead de agente mas discovery/adaptacion

Por eso, seguir puliendo solo el prompt probablemente ayude, pero no va a llevar este step a tiempos realmente bajos por si solo.

## Objetivo razonable

Separaria la meta por escenario:

- `e`: bajar de ~33s a <2s
- `ne`: bajar de ~61s a 5-12s en una primera iteracion
- `ne` ideal: <5s si casi todo el contexto se arma deterministicamente

## Propuestas nuevas

## Orden recomendado

Si el objetivo es reducir tiempo rapido con riesgo controlado:

1. Opcion A
2. Opcion B
3. Opcion C
4. Opcion D

Ese camino ataca primero el caso `e`, que hoy ya muestra una oportunidad clarisima.

Si el objetivo es optimizacion real del step y no solo pulido:

1. Opcion A
2. Skipped: base deterministica parcial
3. Skipped: step 100% deterministico

Ese camino ataca primero el costo fijo y despues el costo variable.

## Mi recomendacion

Haria esto:

1. Implementar short-circuit deterministico para `e`.
2. Agregar instrumentacion separada para `ready_check_ms`, `agent_launch_ms` y `files_inspected`.
3. Reescribir el prompt para reducir discovery en `ne`.
4. Si `ne` sigue arriba de ~15s, migrar a ruta deterministica parcial o completa.

La razon es simple:

- `e` ya no deberia costar ~33s
- esa mejora es relativamente segura
- despues de eso recien conviene discutir cuanto del camino `ne` debe seguir siendo agentic

## Cuando podria reducirse cada escenario

### `e`

Podria reducirse de inmediato si el skip deja de depender del agente.

No hace falta cambiar el prompt para capturar casi toda esa ganancia, pero si hace falta que el criterio de skip sea mas fuerte que "el archivo existe".

### `ne`

Podria reducirse un poco con mejor prompt y menos tools, pero la reduccion fuerte llegaria solo si:

- se preinyecta contexto, o
- se mueve parte de la generacion a Python, o
- se elimina por completo el agente para este step

## Instrumentacion recomendada

Agregaria logs separados para:

- `constitution.mode=agentic|skipped|deterministic|hybrid`
- `constitution.ready_check=true|false`
- `constitution.ready_check_ms=<n>`
- `constitution.agent_invoked=true|false`
- `constitution.files_inspected=<n>`
- `constitution.detected_context_count=<n>`
- `constitution.output_path=openspec/config.yaml`

## Meta actualizada

- meta inmediata para `e`: <2s
- meta incremental para `ne`: <20s
- meta buena para `ne`: <10s
- meta ideal para `ne`: <5s con ruta deterministica

## Opciones implementadas

## Opcion A. Short-circuit deterministico antes de invocar al agente

### Estado

Implementada en el runtime del step `OpenspecConstitutionStep`.

### Que hace

Antes de invocar al agente, el step ahora ejecuta un ready check local sobre `openspec/config.yaml`.

Si el archivo parece realmente preparado:

- no se llama al agente
- no se abre sesion
- no se renderiza el prompt completo
- se persiste un output JSON de `skipped`

Si el archivo no pasa el check:

- el flujo sigue por el camino agentic actual

### Que no hace

No usa un chequeo de solo existencia del archivo.

`openspec/config.yaml` puede existir y aun asi no estar listo para skip. Por ejemplo, puede estar:

- vacio
- con contenido default de inicializacion
- con YAML valido pero sin adaptacion real al repositorio
- escrito a medias por una corrida fallida o interrumpida
- sin referencia efectiva a `CONSTITUTION.md`

Por eso, `exists(config)` solo sirve como señal inicial, no como criterio final de "already configured".

### Criterio implementado

La decision efectiva es mas cercana a:

- `is_prepared_config(config)`

Hoy el ready check implementado valida de forma conservadora que:

- el archivo exista
- tenga contenido no vacio
- no parezca un default trivial
- tenga suficientes lineas sustantivas
- contenga señales de adaptacion a constitucion y contexto repositorio-especifico

### Impacto esperado

- `e`: deberia capturar casi toda la ganancia
- `ne`: no cambia materialmente

### Riesgo residual

El criterio actual esta diseñado para evitar falsos positivos, asi que puede producir falsos negativos.

Eso significa:

- a veces correra el agente aunque el archivo ya este bien
- pero no deberia saltarse el step ante un config dudoso o incompleto

## Opcion B. Precomputar contexto minimo y pasarlo al prompt

### Estado

Implementada en el runtime del step `OpenspecConstitutionStep` y en los prompts `prompt.md` y `prompt_slim.md`.

### Que hace

Antes de invocar al agente, el step ahora construye un bloque de contexto precomputado y lo inyecta en el prompt final.

Ese bloque incluye:

- path del config target
- path del `CONSTITUTION.md`
- lenguajes detectados por manifests
- frameworks detectables por estructura
- tools detectables por archivos de configuracion
- componentes candidatos
- paths relevantes del repo

### Cambio de comportamiento esperado

El prompt ahora instruye al agente a:

- leer primero ese contexto precomputado
- tratarlo como evidencia inicial del repositorio
- no hacer discovery adicional si ese contexto ya es suficiente
- abrir mas archivos solo cuando el contexto precomputado sea insuficiente, incompleto o contradictorio

### Cuando reduce tiempo

Reduce sobre todo en `ne`, cuando el agente necesita decidir que mirar.

En `e` el beneficio es menor porque el mayor ahorro ya viene de la Opcion A.

### Impacto esperado

- `ne`: ahorro moderado
- `e`: ahorro bajo o marginal

### Riesgo residual

El principal riesgo es pasar contexto incompleto o demasiado simplificado.

Para mitigarlo, la implementacion actual:

- solo inyecta hechos baratos y detectables
- no intenta describir negocio ni arquitectura profunda
- deja al agente la opcion de abrir mas archivos cuando ese contexto no alcance

## Opcion C. Reescribir el prompt para que sea realmente de dos caminos

### Estado

Implementada en `prompt.md` y `prompt_slim.md` para `openspec-constitution`.

### Que hace

Los prompts ahora dejan explicito que este step tiene solo dos caminos validos:

1. `skip` inmediato cuando el config ya es valido
2. configuracion minima cuando el config no existe o esta incompleto

Ademas:

- priorizan el contexto precomputado antes de abrir archivos
- priorizan manifests y metadata antes que source code
- remarcan que source inspection es fallback, no default
- bajan el presupuesto de exploracion para repos simples
- refuerzan que no se deben reconfirmar hechos ya establecidos

### Cambio de comportamiento esperado

El agente deberia:

- salir antes en el camino `e`
- hacer menos discovery lateral en `ne`
- usar menos archivos para llegar a una configuracion suficiente

### Cuando reduce tiempo

Principalmente en `ne`.

En `e` ayuda menos que la Opcion A, pero deja el comportamiento mas consistente con el short-circuit y el contexto precomputado ya implementados.

### Impacto esperado

- `ne`: ahorro moderado
- `e`: ahorro bajo

### Riesgo residual

El riesgo principal es que el prompt quede demasiado rigido para repos poco convencionales.

La mitigacion actual es que todavia permite discovery adicional cuando:

- el contexto precomputado no alcanza
- la metadata es insuficiente
- hay contradicciones o tecnologias poco familiares

## Opcion D. Reducir herramientas permitidas para este stage

### Estado

Implementada unicamente para `openspec-constitution`.

### Que hace

Este step ya no usa el mismo set de herramientas amplio que otros stages agentic.

Para `openspec-constitution`, el runtime ahora pasa:

- `Read`
- `Edit`
- `Write`
- `Glob`
- `Grep`

Y deja afuera `Bash`.

### Cambio de comportamiento esperado

La idea es achicar el arbol de decisiones del agente en este step y reducir exploracion lateral innecesaria.

### Cuando reduce tiempo

Reduce principalmente en `ne`.

En `e` el efecto es menor porque el mayor ahorro ya viene del short-circuit.

### Impacto esperado

- `ne`: ahorro bajo a moderado
- `e`: ahorro bajo

### Riesgo residual

Si algun repo raro necesitara discovery mas libre por shell, este set puede quedarse corto.

La mitigacion actual es mantener `Glob` y `Grep`, que todavia permiten localizar archivos relevantes sin abrir `Bash`.

## Skipped

## Opcion E. Base deterministica parcial para `openspec/config.yaml`

### Motivo del cambio de categoria

Esto no se comporta tanto como una opcion independiente, sino como una posible etapa intermedia o complemento entre las opciones ya definidas.

Por eso no conviene listarla al mismo nivel que las demas opciones principales.

### Idea

No hace falta que el agente construya todo desde cero. El runtime puede crear o normalizar una base estable y dejar al agente solo la adaptacion final.

### Parte deterministica

El runtime podria:

- crear `openspec/config.yaml` si no existe
- completar campos base y estructura esperada
- insertar una referencia canonica a `CONSTITUTION.md`
- dejar placeholders o bloques reservados para contexto repo-especifico

### Parte agentic

El agente solo:

- valida la base
- adapta reglas por stack
- completa componentes relevantes

### Cuando reduce tiempo

Reduce principalmente en `ne`.

Puede bajar algo en `e` si el ready check usa esa misma estructura para hacer skip confiable.

### Impacto esperado

- `ne`: ahorro alto, posiblemente llevarlo a ~10-20s sin eliminar del todo el agente
- `e`: mejora indirecta si se combina con Opcion A

### Riesgo

Acoplar el runtime a la estructura de `config.yaml`.

### Mitigacion

Mantener la parte deterministica limitada a estructura base estable, no a todo el contenido semantico.

## Opcion F. Reemplazar `constitution` por un step 100% deterministico

### Motivo del cambio de categoria

Esta opcion tambien queda mejor como item de `Skipped` que como opcion activa principal.

Es una direccion estructural de mayor alcance, no una mejora incremental inmediata como las otras opciones.

### Idea

Si el objetivo es bajar tiempo de verdad, este es el cambio estructural.

El runtime:

- lee `CONSTITUTION.md`
- detecta stack con heuristicas fijas
- detecta componentes por estructura y manifests
- genera `openspec/config.yaml`
- valida el YAML
- emite el mismo JSON final del contrato

### Cuando reduce tiempo

Reduce fuertemente tanto `ne` como `e`.

### Impacto esperado

- `e`: practicamente resuelto junto con skip
- `ne`: podria bajar de ~61s a pocos segundos

### Por que tiene sentido

La diferencia `ne` vs `e` muestra que el trabajo "inteligente" que queda en `ne` no parece justificar 60s. Gran parte del costo es de forma, no de contenido.

### Riesgo

Hay que definir con precision que partes del `config.yaml` son realmente derivables de forma estable.

### Mitigacion

- cubrir con tests varios formatos de repo
- hacer updates no destructivos
- dejar fallback agentic solo para casos no soportados en una primera etapa
