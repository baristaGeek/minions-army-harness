# Step `verify-build`

## Tiempo observado

- Rango observado: ~672s a ~777s
- Naturaleza del costo: shell + instalacion de dependencias + build completo

## Que hace hoy

Lee `MINION_VERIFY_COMMAND` y ejecuta:

`bash -lc "npm ci && npm run build"`

en el directorio configurado por `MINION_VERIFY_DIR`, hoy `sample-app`.

## Por que es el costo mas alto del pipeline

Este step tiene un costo fijo muy grande porque junta dos cosas caras:

- reinstalacion completa de dependencias
- build completo de una app Next.js

Ademas corre fuera del agente, por lo que no se beneficia de decisiones contextuales. Siempre paga
el costo completo.

## Analisis del comando actual

### Parte 1. `npm ci`

`npm ci` es correcto para reproducibilidad, pero es muy caro si se ejecuta en cada corrida efimera.

Costos tipicos:

- red
- descompresion
- escritura a disco
- lifecycle scripts
- reconstruccion de dependencias nativas si existen

### Parte 2. `npm run build`

En Next.js, `build` puede incluir:

- compilacion TypeScript
- bundling
- analisis de dependencias
- prerender
- validaciones del framework

Eso es util como gate fuerte, pero caro por naturaleza.

## Problema estructural

Este step actua como verificacion final, lo cual esta bien. El problema es que hoy ademas convive con
validacion dentro de `apply`. Entonces el pipeline paga:

- validacion interpretativa dentro del agente
- validacion mecanica fuerte fuera del agente

## Ideas de optimizacion

## Opcion A. Quitar `npm ci` de cada corrida

### Idea

Garantizar dependencias previamente y dejar `verify-build` como:

`npm run build`

### Ganancia esperada

- Muy alta

### Ventajas

- Elimina gran parte del costo fijo

### Riesgos

- Si las dependencias no estan correctamente instaladas, el build puede dar falsos negativos

### Cuando conviene

- Cuando la imagen del minion ya puede incluir dependencias
- Cuando puedes montar cache persistente

## Opcion B. Cachear npm y `node_modules`

### Idea

Persistir entre corridas:

- cache de npm
- `node_modules`
- cache de build si aplica

### Ganancia esperada

- Muy alta

### Ventajas

- Mantiene `npm ci` o flujo similar con mucho menor costo efectivo

### Riesgos

- Mayor complejidad operativa
- Posibles inconsistencias si el cache se invalida mal

## Opcion C. Reemplazar `npm ci` por una variante menos costosa

### Idea

Usar algo como:

`npm ci --prefer-offline --no-audit --fund=false`

### Ganancia esperada

- Media

### Ventajas

- Poco esfuerzo
- Reduce llamadas innecesarias y ruido

### Riesgos

- No resuelve el problema de fondo si todo sigue siendo efimero

## Opcion D. Introducir verificaciones escalonadas

### Idea

No correr siempre el build completo primero. Hacer una cascada:

1. check barato
2. check medio
3. build completo solo si pasa lo anterior

Por ejemplo:

1. `npm run lint`
2. test focalizado o typecheck
3. `npm run build`

### Ganancia esperada

- Alta cuando muchos cambios fallan pronto
- Menor cuando casi todo pasa

### Ventajas

- Detecta errores baratos antes del build

### Riesgos

- Aumenta complejidad del gate
- Si todo siempre pasa, el ahorro es menor

## Opcion E. Hacer gate basado en impacto del cambio

### Idea

Decidir el comando de verificacion segun que archivos cambiaron.

Ejemplos:

- solo docs: no build
- solo CSS/UI local: lint o test visual liviano
- backend sin tocar `sample-app`: no build de Next
- cambios en `sample-app`: build completo

### Ganancia esperada

- Muy alta si el pipeline procesa cambios heterogeneos

### Ventajas

- Evita builds innecesarios

### Riesgos

- Requiere reglas de impacto bien definidas
- Un mapa de impacto incompleto puede dejar pasar regresiones

## Opcion F. Pre-hornear deps en la imagen del minion

### Idea

Construir la imagen con las dependencias del proyecto ya resueltas para el lockfile esperado.

### Ganancia esperada

- Alta

### Ventajas

- Reduce mucho tiempo por corrida

### Riesgos

- La imagen se invalida cuando cambia `package-lock.json`
- Puede aumentar tiempo de build de la imagen

## Opcion G. Mover el build fuerte al sistema de CI

### Idea

Dejar en el minion solo checks rapidos y delegar `npm ci && npm run build` al PR check de GitHub
Actions.

### Ganancia esperada

- Muy alta en latencia del minion

### Ventajas

- El minion responde rapido
- El gate fuerte sigue existiendo

### Riesgos

- La seguridad del flujo cambia: la PR puede abrirse antes del build fuerte
- Requiere aceptar feedback asincrono

## Opcion H. Separar install y build como capas observables

### Idea

En vez de un solo comando, medir por separado:

- install time
- build time

### Ganancia esperada

- No reduce tiempo por si sola, pero destraba decisiones correctas

### Ventajas

- Permite saber donde esta el costo real

### Riesgos

- Ninguno importante

## Recomendacion priorizada para `verify-build`

1. Medir por separado instalacion y build.
2. Eliminar `npm ci` de la ruta caliente o cachearlo.
3. Usar gate por impacto del cambio.
4. Mantener build completo solo cuando el diff realmente toca `sample-app`.
5. Considerar mover el build fuerte a CI si el objetivo principal es latencia del minion.

## Senales a instrumentar

- tiempo de `npm ci`
- tiempo de `npm run build`
- hits y misses de cache
- archivos modificados en cada corrida
- porcentaje de corridas donde el build era innecesario

## Resultado objetivo razonable

- Meta conservadora: bajar a <300s
- Meta ideal: <60s cuando el cambio no requiere reinstalar deps ni build completo
