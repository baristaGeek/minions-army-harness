# Analisis Profundo de Steps Caros del Pipeline

Esta carpeta separa el analisis por cada step caro en tiempo del pipeline OpenSpec actual.

## Steps documentados

- [constitution.md](./constitution.md)
- [explore.md](./explore.md)
- [propose.md](./propose.md)
- [apply.md](./apply.md)
- [verify-build.md](./verify-build.md)
- [review-merge-deploy.md](./review-merge-deploy.md)

## Lectura rapida

Si el objetivo es ganar tiempo rapido con el menor riesgo, el mejor orden inicial es:

1. `verify-build`
2. `apply`
3. `constitution`
4. `propose`
5. `review-merge-deploy`
6. `explore`

## Hallazgos transversales

### 1. Hay duplicacion de trabajo

El pipeline hoy pide validacion dentro de `apply` y luego vuelve a ejecutar una validacion fuerte en
`verify-build`. Esa duplicacion es la oportunidad mas clara de ahorro.

### 2. Hay varios steps agentic donde el problema es casi deterministico

`constitution`, partes de `explore`, y parte de `propose` contienen trabajo que podria hacerse con
logica fija o con prompts mucho mas restringidos.

### 3. El costo no es solo ejecucion de comandos

En los steps agentic, mucho tiempo se va en:

- lectura de contexto
- busqueda de archivos
- planificacion interna del agente
- reintentos
- validacion defensiva
- produccion del JSON final

### 4. La variabilidad importa tanto como el promedio

`apply` no solo es caro; tambien es impredecible. Un step que a veces tarda 50s y a veces 800s
complica mucho la experiencia operativa, el throughput y la confianza en el pipeline.

## Referencias principales

- `minions_army/core/runtime/orchestrator_runtime.py`
- `minions_army/core/config/schema.py`
- `.env`
- `.env.example`
- `execution/prompts/openspec/constitution/prompt.md`
- `execution/prompts/openspec/explore/prompt.md`
- `execution/prompts/openspec/propose/prompt.md`
- `execution/prompts/openspec/apply/prompt.md`
- `execution/prompts/openspec/review/prompt.md`
