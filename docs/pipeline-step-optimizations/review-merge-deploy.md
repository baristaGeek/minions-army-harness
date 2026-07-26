# Step `review-merge-deploy`

## Tiempo observado

- Rango observado: ~179s
- Naturaleza del costo: fetch de diff + re-razonamiento agentic + posible merge/deploy

## Que hace hoy

Si el reviewer esta habilitado:

1. ejecuta `gh pr diff <branch>`
2. incrusta el diff completo en el prompt del reviewer
3. corre otro `claude -p`
4. si aprueba, hace merge
5. opcionalmente despliega

## Por que es caro

### Paga por otro ciclo completo de agente

Aunque el diff ya existe y el cambio fue generado por otro agente del mismo pipeline, aqui se abre un
segundo proceso cognitivo costoso.

### El prompt lleva el diff completo embebido

Eso aumenta:

- el tamano del prompt
- el tiempo de parseo
- la carga de razonamiento

### Ademas se permite volver a pedir contexto

El reviewer puede correr `gh pr view` y `gh pr diff` otra vez. Eso es bueno para rigor, pero puede
repetir trabajo ya hecho.

## Donde puede estar el costo

### 1. Fetch del diff

Costo generalmente moderado, salvo PRs grandes.

### 2. Tamanio del prompt

Mientras mas grande el diff, mas caro y mas lento el reviewer.

### 3. Lectura adicional de archivos o metadata

El reviewer puede abrir archivos para confirmar sospechas.

### 4. Acciones posteriores

Merge y deploy suman tiempo, aunque el grueso parece estar en el reviewer.

## Ideas de optimizacion

## Opcion A. No inyectar el diff completo en el prompt

### Idea

Pasar al reviewer:

- objetivo del request
- branch
- resumen de cambios

Y dejar que solo use `gh pr diff` si necesita profundizar.

### Ganancia esperada

- Alta

### Ventajas

- Prompt mucho mas chico
- Menos costo base fijo

### Riesgos

- El reviewer puede necesitar hacer un fetch adicional

## Opcion B. Usar un reviewer por capas

### Idea

Primero aplicar reglas deterministicas:

- buscar secretos
- detectar comandos destructivos
- revisar archivos sensibles

Y solo si ese gate pasa o detecta ambiguedad invocar LLM.

### Ganancia esperada

- Alta

### Ventajas

- Muchos casos se resuelven sin agente
- Menor costo y latencia

### Riesgos

- Las reglas deterministicas no reemplazan juicio semantico completo

## Opcion C. Activar reviewer solo para cambios de mayor riesgo

### Idea

No todos los PR necesitan un reviewer agentic. Usarlo solo si:

- toca migraciones
- toca auth
- toca despliegue
- toca infraestructura
- cambia muchos archivos

### Ganancia esperada

- Muy alta a nivel pipeline global

### Ventajas

- Excelente ahorro

### Riesgos

- Algunos cambios medianos podrian merecer review y no recibirlo

## Opcion D. Usar el engine DSPy compilado

### Idea

Comparar `claude_cli` contra `dspy` con programa compilado y optimizado.

### Ganancia esperada

- Media

### Ventajas

- Latencia potencialmente mas estable
- Menor dependencia del comportamiento agentic libre

### Riesgos

- Debe medirse calidad real del veredicto

## Opcion E. Reducir el scope de herramientas del reviewer

### Idea

Si el diff ya se paso por otro canal, el reviewer podria tener:

- solo `Read`
- solo `Grep`
- `gh pr diff` bajo demanda

### Ganancia esperada

- Baja a media

### Ventajas

- Menos exploracion incidental

### Riesgos

- Puede quedarse corto en investigaciones profundas

## Opcion F. Separar review de merge y deploy

### Idea

Medir por separado:

- review time
- merge time
- deploy time

### Ganancia esperada

- No reduce tiempo por si sola, pero mejora decisiones

### Ventajas

- Evita culpar al reviewer por costo que viene del deploy

### Riesgos

- Ninguno importante

## Opcion G. Resumir el diff antes del reviewer

### Idea

En vez de pasar diff completo, pasar:

- archivos tocados
- diff stat
- snippets de alto riesgo

### Ganancia esperada

- Media a alta

### Ventajas

- Mejor relacion senal/ruido

### Riesgos

- Un resumen malo puede ocultar un problema real

## Recomendacion priorizada para `review-merge-deploy`

1. Separar metricas de review, merge y deploy.
2. Quitar el diff completo del prompt base.
3. Introducir un gate deterministico previo al LLM.
4. Hacer reviewer condicional por riesgo del cambio.
5. Evaluar DSPy compilado frente a Claude CLI.

## Senales a instrumentar

- diff size
- tiempo de `gh pr diff`
- tiempo del reviewer LLM
- archivos leidos por el reviewer
- tiempo de merge
- tiempo de deploy

## Resultado objetivo razonable

- Meta conservadora: bajar review agentic a <90s
- Meta ideal: omitirlo en gran parte de los cambios de bajo riesgo
