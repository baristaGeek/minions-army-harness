# Step `apply`

## Tiempo observado

- Rango observado: ~51s a ~808s
- Naturaleza del costo: agentic de implementacion con alta variabilidad

## Que hace hoy

Ejecuta `/opsx:apply` mediante el agente y el prompt le exige:

- implementar solo lo definido por OpenSpec
- hacer los cambios directamente
- seguir la constitucion
- verificar que hubo cambios con `git status --short`
- verificar el diff con `git diff --stat`
- correr la validacion mas pequena relevante
- devolver JSON con resumen, validacion, commit y PR

## Por que es el step mas delicado

No solo es caro. Tambien es el menos predecible. Ese rango de ~51s a ~808s indica que el problema
no es solo "el trabajo tarda", sino que el comportamiento del agente cambia mucho segun:

- ambiguedad del request
- facilidad para encontrar archivos
- necesidad de corregir errores
- validaciones ejecutadas
- loops de edicion y reintento

## Descomposicion del costo

### 1. Discovery tecnico antes de tocar codigo

Aunque `explore` y `propose` ya corrieron, `apply` probablemente vuelve a:

- ubicar archivos
- releer contexto
- confirmar arquitectura
- revalidar que el cambio pedido coincide con la spec

### 2. Edicion del codigo

Esto puede ser rapido si el target es obvio, o muy lento si el agente prueba varios caminos.

### 3. Validacion interna del agente

El prompt empuja al agente a ejecutar checks reales antes de terminar. Ese comportamiento es bueno
para calidad, pero caro para latencia.

### 4. Correccion tras fallos de validacion

Si el primer intento rompe build, lint o tipado, el agente puede entrar en ciclos:

1. cambiar codigo
2. correr check
3. leer error
4. corregir
5. volver a correr check

Ese loop explica gran parte de la cola larga.

## Factor mas importante: validacion duplicada

En tu configuracion actual, `apply` valida por prompt y `verify-build` ejecuta ademas
`npm ci && npm run build`. Eso significa que la implementacion puede estar pagando build o tests
dos veces:

- una dentro del agente
- otra fuera del agente

Esta es la principal razon para atacar `apply` junto con `verify-build`.

## Hipotesis de cuellos de botella

### Hipotesis 1. El agente tiene demasiado espacio de busqueda

Con herramientas amplias y sin target files explicitados, puede leer mucho antes de editar.

### Hipotesis 2. La salida requerida es demasiado grande para un step de implementacion

Ademas de implementar, debe producir:

- resumen
- plan
- acciones
- validacion
- riesgos
- commit message
- pr title
- pr body

No es el costo principal, pero suma deliberacion.

### Hipotesis 3. El prompt incentiva checks caros aun cuando ya existe `verify-build`

La frase "run the smallest relevant test, lint, or build check" permite que el agente elija build
completo si lo considera prudente.

### Hipotesis 4. El uso de OpenSpec no acota lo suficiente que archivos tocar

Si el agente no recibe una lista de archivos o areas candidatas, sigue haciendo discovery incluso
despues de la propuesta.

## Ideas de optimizacion

## Opcion A. Separar implementacion de validacion fuerte

### Idea

Reescribir el prompt para que `apply` haga solo:

- implementar
- verificar que hay cambios
- correr checks baratos y focalizados

Y dejar la validacion fuerte para `verify-build`.

### Ganancia esperada

- Muy alta

### Ventajas

- Menos loops dentro del agente
- Menor tiempo promedio
- Menor variabilidad

### Riesgos

- Puede bajar la tasa de acierto en primer build si el check focalizado fue insuficiente

### Recomendacion

Es la optimizacion de mayor impacto dentro del propio `apply`.

## Opcion B. Inyectar archivos candidatos al prompt

### Idea

Pasar al stage una lista de:

- archivos probables
- modulos relacionados
- artefactos OpenSpec relevantes

### Ganancia esperada

- Alta

### Ventajas

- Menos lectura lateral
- Menos exploracion libre

### Riesgos

- Si la lista esta mal, el agente puede quedarse corto

## Opcion C. Introducir un modo `fast_apply`

### Idea

Para cambios simples, usar un prompt especial mas corto que:

- prohiba exploracion extensa
- limite numero de archivos
- permita solo validacion minima

### Ganancia esperada

- Alta en cambios pequenos

### Ventajas

- Excelente ROI si la mayoria de requests son simples

### Riesgos

- Necesita clasificacion previa del request

## Opcion D. Reducir herramientas permitidas por stage

### Idea

No todos los `apply` necesitan `Bash` abierto. Podrias tener dos perfiles:

- `apply-lite`: `Read,Edit,Write,Glob,Grep`
- `apply-full`: agrega `Bash`

### Ganancia esperada

- Baja a media

### Ventajas

- Menos ramas de decision
- Menos probabilidad de checks caros ad hoc

### Riesgos

- Algunos cambios realmente requieren tooling shell

## Opcion E. Limitar reintentos de validacion

### Idea

Indicar en el prompt que:

- haga un solo check focalizado
- si falla, corrija una vez
- no entre en loops largos

### Ganancia esperada

- Alta para la cola larga

### Ventajas

- Baja el worst-case

### Riesgos

- Algunas corridas terminaran antes con riesgo pendiente en vez de auto-repararse

## Opcion F. Reducir el payload de salida

### Idea

Quitar de `apply` campos no estrictamente necesarios y derivarlos luego en Python si hace falta.

Por ejemplo:

- `pr_body` podria construirse automaticamente a partir de otros campos
- parte del `plan` podria omitirse

### Ganancia esperada

- Baja

### Ventajas

- Menos trabajo cognitivo al final del stage

### Riesgos

- Ganancia pequena comparada con validacion y discovery

## Opcion G. Reusar mejor la sesion compartida

### Idea

Ya existe sesion compartida entre `explore`, `propose` y `apply`. Conviene medir si realmente el
agente esta reutilizando contexto de forma util o si igual reexplora. Si no hay beneficio claro,
hay que cambiar el prompt para hacer referencia explicita a lo ya decidido.

### Ganancia esperada

- Media

### Ventajas

- Aprovecha una capacidad ya implementada

### Riesgos

- La mejora depende del comportamiento del CLI, no solo del prompt

## Opcion H. Prevalidacion deterministica de paths y herramientas

### Idea

Antes de `apply`, resolver:

- si el repo es Node, Python, o mixto
- donde estan los tests
- cual es el comando de validacion barata

Y pasarselo resuelto al prompt.

### Ganancia esperada

- Media

### Ventajas

- Reduce improvisacion del agente

### Riesgos

- Necesita heuristicas robustas por stack

## Recomendacion priorizada para `apply`

1. Sacar del prompt la validacion pesada y dejar solo checks baratos.
2. Inyectar archivos target o snapshot de contexto.
3. Crear un modo `fast_apply` para cambios simples.
4. Limitar loops de reintento.
5. Simplificar el payload JSON final.

## Senales a instrumentar

- tiempo total del agente
- cantidad de archivos leidos y editados
- comandos shell ejecutados por el agente
- numero de ciclos edit-check-fix
- si corrio build, lint o test
- porcentaje de corridas que entran a la cola larga

## Resultado objetivo razonable

- Meta conservadora: bajar la mediana por debajo de 120s
- Meta ideal: mantener la mayoria de corridas simples por debajo de 60s y cortar la cola larga
