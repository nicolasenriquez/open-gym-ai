---
type: Guide
title: Autoría y mantenimiento documental OKF
description: Cómo editar documentación, revisar propuestas y mantener índices sin escrituras innecesarias.
---
# Autoría y mantenimiento documental OKF

Para cambiar documentación, seguir `AGENTS.md` → [índice](../index.md) → documento pertinente. Consultar el [perfil local](../standards/okf-profile.md) para las reglas. La herramienta trabaja desde cualquier directorio; los comandos siguientes se muestran desde la raíz.

## Preparación

Instalar las dependencias de desarrollo raíz con `npm ci --ignore-scripts`, usando Node 22 o posterior. `js-yaml` lee metadatos; `markdown-it` distingue estructura Markdown de ejemplos; `github-slugger` calcula anclas. Son herramientas documentales, no dependencias de la aplicación.

```sh
node scripts/docs/okf.mjs check
node scripts/docs/okf.mjs check --json
node --test scripts/docs/okf.test.mjs
```

`check` solo lee: código 0 sin hallazgos requeridos, 1 con incumplimientos y 2 con error operativo. Los avisos históricos no bloquean. No cambia metadatos, fechas, índices ni verificación.

## Qué pertenece a docs/

Conservar conocimiento que ayude a usar, operar, mantener o evolucionar OpenGym:
guías vigentes, contratos, requisitos, decisiones y evidencia todavía necesaria.
Antes de crear una página, identificar su lector, la pregunta que resuelve y por qué
no basta actualizar una página existente. Cada regla tiene un único propietario.

Estos criterios editoriales también se aplican a los README y referencias de paquetes
fuera del bundle OKF. Un README orienta sobre el uso actual; no conserva permisos de
sesiones, contadores de tareas o la cronología RED/GREEN. Los checks estructurales no
sustituyen comprobar que sus comandos y afirmaciones siguen siendo válidos.

- Git, PR y releases conservan qué cambió; OpenSpec conserva el cambio seleccionado y sus tareas.
- Los pendientes van al tracker indicado en `.agents/docs/issue-tracker.md`, no a un informe perpetuo.
- Logs, capturas, exports sintéticos y resultados de ejecuciones quedan en temporales ignorados
  o artefactos de CI. `.playwright-cli/` es el destino del verificador web; eliminar sus
  artefactos al terminar su uso, sin tocar perfiles ni datos del usuario.
- Al cerrar un cambio, integrar lo útil en su documento propietario y retirar borradores
  y resultados sustituidos. No crear por rutina planes terminados, informes de cierre,
  `log.md` o carpetas de archivo dentro de `docs/`.
- Conservar investigación solo mientras sustente una decisión o una pregunta vigente;
  distinguir sus observaciones fechadas de requisitos y resultados actuales.

## Crear o editar

1. Elegir un propietario del conocimiento y revisar referencias entrantes. Editar allí el significado; los demás documentos enlazan a esa fuente.
2. Para un documento nuevo, escribir `type`, `title` y `description` en frontmatter. Conservar el idioma del contenido; no agregar pruebas o revisiones que no ocurrieron.
3. Si se crea una carpeta documental, declararla en `scripts/docs/okf.config.json` con `title`, `description` y propiedad explícita del índice (`owned: true` para generación). Título y descripción son cadenas de una línea; una configuración incompleta se rechaza. Los directorios de recursos exclusivos no necesitan índices.
4. Ejecutar `check`. La incorporación o cambio de título/descripción hará que el índice quede pendiente de regeneración.
5. Generar una propuesta en una ruta temporal **fuera del repositorio**, con carpeta padre existente. La ruta debe ser nueva; el comando no sobrescribe informes previos y comprueba el destino real, también a través de junctions. Cada comando admite únicamente sus opciones documentadas; repetir una opción es un error.

```text
node scripts/docs/okf.mjs plan --out <ruta-temporal-nueva.json>
node scripts/docs/okf.mjs apply --plan <ruta-del-plan-revisado.json>
node scripts/docs/okf.mjs check
```

6. Leer `changes` antes de aplicar. Cada entrada contiene ruta, hash anterior, resultado y motivo. La herramienta solo añade metadatos explícitos o regenera índices declarados; la prosa se modifica manualmente.
7. Crear una segunda propuesta: debe contener `changes: []`. Aplicarla debe indicar `written: 0`, sin modificar mtimes. Revisar el diff, incluidos archivos nuevos.

Para una conversión de un concepto sin frontmatter, `plan` admite `--metadata <archivo.json>`: un objeto de rutas relativas a la raíz cuyos valores son los metadatos revisados. Ese archivo es una propuesta temporal, no una segunda fuente permanente de títulos. El comando rechaza reemplazar frontmatter existente y conserva el cuerpo byte por byte.

## Mover, deprecar o reducir duplicaciones

Buscar con `rg` enlaces entrantes antes de mover una página o cambiar un encabezado. Actualizar enlaces activos y regenerar índices. Mantener las URL existentes cuando sea posible. Retirar prosa solo con propietario, evidencia y sustitución identificados; el script no decide qué requisito sobra.

La evidencia protegida se consulta en su contexto temporal. Para corregirla, publicar
una nota claramente separada; el manifiesto no se regenera automáticamente. Para
retirarla o trasladarla, seguir el criterio del perfil: revisar consumidores, preservar
conocimiento necesario y actualizar explícitamente manifiesto y configuración en el
mismo cambio. El generador no borra ni mueve archivos.

Antes de una retirada amplia, respaldar fuera del repositorio también los archivos sin
seguimiento y cambios locales. En el diff/PR explicar qué se retira y dónde queda lo
útil; no añadir otro informe permanente de la limpieza. Comprobar enlaces entrantes
fuera de `docs/`, incluidos skills y OpenSpec. Retirar entradas de carpetas eliminadas
en `okf.config.json`, regenerar índices y ejecutar `check` y la suite de la herramienta.
Una segunda propuesta debe quedar vacía.

## Concurrencia y recuperación

Un plan queda invalidado si cambian documentos, inventario o política. Crear otra propuesta después de integrar el cambio concurrente; no forzar la anterior. Aplicar de nuevo una propuesta ya aplicada es una operación sin escrituras cuando todo coincide con su resultado.

`apply` usa `scripts/docs/.okf.lock`. Ante un cierre abrupto, comprobar que no hay una ejecución activa antes de retirar **ese archivo de bloqueo concreto**. Un bloqueo inesperado es motivo para investigar, no para matar otros procesos.

Antes de escribir se prepara un journal y copias en el directorio temporal del sistema; ante un fallo la ruta aparece en el error. Los journals exitosos también quedan disponibles durante la vida de ese almacenamiento temporal. Una escritura es atómica por archivo, no por toda la carpeta. Un fallo controlado intenta revertir únicamente los resultados propios que siguen coincidiendo con el hash de salida; conserva ediciones concurrentes.

Tras una interrupción abrupta, leer `journal.json`: comparar cada ruta con `before` y `after`; restaurar el `.before` solo si el archivo actual coincide con `after`. Si `before` era null, el archivo fue creado por esa aplicación: retirarlo solo si aún coincide con `after`. Si ningún hash coincide, conservar el archivo y resolver manualmente. Después ejecutar `check` y crear una propuesta nueva. Nunca usar reset global ni restaurar todo el árbol.

Para operaciones grandes, conservar además una copia fuera del repositorio: los temporales pueden ser limpiados por el sistema. La copia debe incluir un manifiesto de rutas y hashes para comprobar qué se preservó; no depender solo de Git para recuperar trabajo local.

## Actualizar el estándar

Cambiar el pin oficial explícitamente, revisar la diferencia normativa y adaptar perfil, herramienta y fixtures. Las ejecuciones ordinarias son offline y no siguen automáticamente una rama remota. El job `documentation` de `.github/workflows/test.yml` ejecuta `check` y la suite de la herramienta; no publica ni despliega.
