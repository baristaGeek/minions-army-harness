# Pipeline Step Timings

## Objetivo

Este documento lista los steps del pipeline y los tiempos observados que hoy estan anotados en el runtime.

Cuando un step todavia no tiene datos suficientes, se deja explicitamente como pendiente.

Fuente principal:

- [minions_army/core/runtime/orchestrator_runtime.py](/d:/source/enterprise/fork/minions-army/minions_army/core/runtime/orchestrator_runtime.py)

## Steps comunes

| Step | Scope | Tiempos observados |
| --- | --- | --- |
| `initialize-workspace` | Comun | `0` ms |
| `clone` | Comun | `3091`, `3245` ms |
| `checkout` | Comun | `102`, `4` ms |
| `git-config` | Comun | `7`, `8` ms |
| `constitution-prepare` | Comun | `4`, `4` ms |
| `bootstrap` | Comun | `6216` ms |
| `verify-build` | Comun | `776796`, `672026`, `815751`, `846240` ms |
| `commit` | Comun | `372`, `398` ms |
| `push` | Comun | `2039`, `2751`, `2688` ms |
| `pr-create` | Comun | `5395`, `6458` ms |
| `review-merge-deploy` | Comun | `178742` ms |

## Steps OpenSpec

| Step | Scope | Tiempos observados |
| --- | --- | --- |
| `openspec-constitution` | OpenSpec | `ne`: `51787`, `61817`, `68664`, `64273`, `57480`, `43751` ms; `e`: `32740`, `33592` ms |
| `openspec-explore` | OpenSpec | `22706`, `19678`, `31093`, `32539`, `30652`, `20017` ms |
| `openspec-propose` | OpenSpec | `51068`, `66657`, `73684`, `72928`, `71948`, `64567` `60758` ms |
| `openspec-apply` | OpenSpec | `807967`, `51283`, `469739`, `287900`, `463351` ms |

## Steps Speckit

| Step | Scope | Tiempos observados |
| --- | --- | --- |
| `speckit-constitution` | Speckit | Sin datos todavia |
| `speckit-specification` | Speckit | Sin datos todavia |
| `speckit-planner` | Speckit | Sin datos todavia |
| `speckit-tasks` | Speckit | Sin datos todavia |
| `speckit-implementation` | Speckit | Sin datos todavia |

## Notas

- `ne` en `openspec-constitution` significa que el config no existe.
- `e` en `openspec-constitution` significa que el config ya existe.
- Este documento refleja tiempos manualmente anotados en comentarios del runtime, no una serie historica consolidada.
- Si mas adelante se agrega instrumentacion formal, este archivo deberia pasar a usar datos agregados desde logs o metricas persistidas.
