# Analisis de Duration Times del Pipeline

## Hallazgo principal

Los cuellos de botella reales no estan en `git` ni en el bootstrap; estan en la parte agentic y en la validacion duplicada. Viendo `minions_army/core/runtime/orchestrator_runtime.py`, las muestras apuntan a esto:

- `constitution`: ~52-62s
- `explore`: ~20-23s
- `propose`: ~51-67s
- `apply`: ~51s hasta ~808s
- `verify-build`: ~672s hasta ~777s
- `review-merge-deploy`: ~179s

El patron mas fuerte es que `apply` y `verify-build` son los pasos mas caros, y ademas hoy estan haciendo trabajo solapado. En la config activa, `.env` define `MINION_VERIFY_COMMAND=npm ci && npm run build`, mientras que el prompt de `apply` tambien obliga al agente a correr validacion antes de responder.

## Paso a paso

### `clone`, `checkout`, `git-config`, `commit`, `push`, `pr-create`

Los comandos son livianos:

- `git clone --branch ... --single-branch`
- `git checkout -b`
- `git config`
- `git add`
- `git commit`
- `git push`
- `gh pr create`

No vale la pena optimizarlos ahora. Su impacto total es marginal.

### `bootstrap`

Ejecuta `openspec init --tools claude --force`.

- ~6s es razonable.
- Mejora posible: pre-hornear esta inicializacion en la imagen o evitar re-init si el repo ya esta preparado.
- Ganancia esperada: baja.

### `constitution`

Corre como stage agentic con `claude -p ... --model ... --effort low --permission-mode bypassPermissions --output-format json --allowedTools Bash,Read,Edit,Write,Glob,Grep`.

El prompt pide:

- actualizar `config.yaml`
- leer `CONSTITUTION.md`
- preparar reglas

Para 50-60s, esta caro para una tarea casi deterministica.

Cambios recomendados:

- Sacarlo del agente y volverlo script deterministico en Python.
- Si debe seguir siendo agentic, reducir el prompt a "actualiza solo estos campos de `config.yaml`".
- Evitar exploracion libre del repo en este paso.

### `explore`

El prompt es breve y no escribe codigo.

- ~20s no es terrible, pero es overhead puro.
- Ya comparte sesion con `propose` y `apply`, lo cual ayuda.

Cambios recomendados:

- Hacerlo opcional segun la complejidad del request.
- Saltarlo en cambios pequenos y pasar directo a `propose` o `apply`.
- Si se mantiene, limitar explicitamente que archivos puede mirar.

### `propose`

Ejecuta `/opsx:propose` y genera artefactos OpenSpec.

- ~51-67s tambien esta alto.
- Si siempre implementas enseguida, este paso puede ser demasiado costoso para el valor que aporta.

Cambios recomendados:

- Fusionar `explore + propose` para requests simples.
- Permitir un modo "fast path" que vaya directo a `apply` cuando ya existe un cambio OpenSpec listo.
- Mantener `propose` solo cuando el cambio requiera artefactos nuevos de spec.

### `apply`

Es el cuello grande. Usa el mismo `claude -p` con herramientas amplias y ademas obliga a:

- implementar
- verificar cambios con `git status --short` y `git diff --stat`
- correr "the smallest relevant test, lint, or build check"

El rango ~51s a ~808s muestra alta variabilidad: el agente a veces resuelve rapido y a veces entra en loops de lectura, edicion, validacion y reintentos.

Cambios recomendados:

- Quitar del prompt de `apply` la obligacion de correr build/test si `verify-build` ya existe.
- Dejar en `apply` solo checks baratos: `git status --short`, `git diff --stat`, y quizas un test focalizado.
- Cambiar la instruccion de validacion por algo como: "no corras build completo; usa el check mas pequeno posible y deja el build final a `verify-build`".
- Restringir el espacio de busqueda del agente: darle archivos probables o paths candidatos.
- Si OpenSpec ya sabe que archivos tocar, inyectar esa lista al prompt.
- Considerar reducir herramientas permitidas si no necesita `Bash` amplio en todos los stages.

### `verify-build`

Ejecuta `bash -lc "npm ci && npm run build"` en `sample-app`.

- Este es probablemente el mayor costo fijo del pipeline.
- `npm ci` reinstala todo en cada corrida; en un entorno efimero eso pega muchisimo.
- Si `apply` ya corrio validacion parecida, aqui pagas doble.

Cambios recomendados:

- Mayor impacto: cambiar a `npm run build` si ya garantizas dependencias instaladas antes.
- Si necesitas instalacion limpia, usar cache de `node_modules` o del cache de npm entre ejecuciones.
- Como minimo: `npm ci --prefer-offline --no-audit --fund=false`.
- Si el objetivo es solo detectar rotura rapida, correr primero un gate mas barato: `npm run lint` o un test focalizado, y dejar `build` solo para PRs que pasaron.
- Si el repo no cambia dependencias casi nunca, preinstalar deps en la imagen base del minion.

### `review-merge-deploy`

Hace `gh pr diff <branch>`, luego inyecta el diff completo dentro del prompt del reviewer Claude.

- ~179s es consistente con pasarle un diff completo a otro agente y ademas permitirle volver a consultar `gh pr view/diff`.

Cambios recomendados:

- No incrustar el diff completo en el prompt; pasar resumen y dejar que el reviewer llame `gh pr diff` solo si lo necesita.
- Para cambios pequenos, usar un reviewer deterministico basado en reglas antes de invocar un LLM.
- Evaluar el engine `dspy` compilado si buscas latencia mas estable.

## Prioridad de optimizacion

1. Eliminar la validacion duplicada entre `apply` y `verify-build`.
2. Reducir o cachear `npm ci`.
3. Convertir `constitution` en paso deterministico.
4. Hacer `explore` y `propose` opcionales o fusionables.
5. Reducir el reviewer a diff bajo demanda, no diff embebido completo.

## Referencias revisadas

- `minions_army/core/runtime/orchestrator_runtime.py`
- `minions_army/application/services/orchestration_service.py`
- `minions_army/core/config/schema.py`
- `.env`
- `.env.example`
- `execution/prompts/openspec/constitution/prompt.md`
- `execution/prompts/openspec/explore/prompt.md`
- `execution/prompts/openspec/propose/prompt.md`
- `execution/prompts/openspec/apply/prompt.md`
- `execution/prompts/openspec/review/prompt.md`
