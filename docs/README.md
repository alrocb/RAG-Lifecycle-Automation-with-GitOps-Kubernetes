# Documentación del proyecto

Esta carpeta recoge todo lo que se ha hecho en el TFM, por qué se ha hecho así y qué se ha medido, a medida que se implementa. Es la fuente para redactar la memoria: cada decisión tiene su justificación y cada cifra, su fecha y sus condiciones.

| Documento | Qué contiene | Para qué apartado de la memoria |
| --- | --- | --- |
| [acceso.md](acceso.md) | Qué es cada dirección web, cómo entrar y qué se puede hacer | 4.2, anexos |
| [argocd.md](argocd.md) | Argo CD a fondo: qué es, cómo funciona, cómo se usa aquí y qué se puede hacer desde su web | 2 (estado del arte), 4.2 |
| [ficheros.md](ficheros.md) | Qué contiene cada fichero del repositorio, qué hace y por qué existe | 4.2, anexos |
| [arquitectura.md](arquitectura.md) | Componentes del sistema, cómo se relacionan y los flujos principales, con diagramas | 4.2 (OE2) |
| [decisiones.md](decisiones.md) | Registro de decisiones de diseño (ADR): contexto, decisión, alternativas y justificación | 4.1.3, 4.2 |
| [proceso.md](proceso.md) | Bitácora por fases: qué se hizo, en qué orden, qué problemas aparecieron y cómo se resolvieron | 4.2, 4.1.5 (riesgos) |
| [mediciones.md](mediciones.md) | Todas las cifras medidas, con fecha, entorno y método | 4.2.6, 4.3 (evaluación) |
| [operacion.md](operacion.md) | Procedimiento para levantar, usar y destruir el entorno | 4.2, anexos |

## Convenciones

- **Fechas**: las de cada sesión de trabajo (2026). Las mediciones indican siempre dónde se tomaron: el equipo de desarrollo (Windows 11, Docker Desktop, 6 núcleos asignados) o la máquina de AWS (t3.large, 2 vCPU, 8 GB).
- **Referencias a objetivos y requisitos**: OE1–OE8, RF1–RF5 y RNF1–RNF6 son los de la memoria (capítulos 3 y 4.1.2).
- **Diagramas**: en Mermaid; GitHub los muestra dibujados. Las versiones pulidas para la memoria están en el documento del apartado 4.2.
- **Simplicidad**: se elige siempre la solución más simple que cumpla el requisito, y todo lo que se añade queda explicado aquí.
- **Estado**: fases 2 a 5 implementadas y desplegadas en AWS. Las fases 6 (observabilidad) y 7 (evaluación) se documentarán aquí cuando se hagan.
