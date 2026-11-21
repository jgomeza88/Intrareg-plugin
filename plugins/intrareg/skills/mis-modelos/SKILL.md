---
name: mis-modelos
description: "Lee en el equipo del registrador sus modelos propios de Intrareg («Mis modelos»: plantilla de la nota, informes, comunicaciones) y sus asuntos en trámite, de la carpeta del Registro donde Intrareg guarda una copia (subcarpeta «Intrareg») o de los ficheros que exporta, sin pasar por el servidor. Úsala cuando pidan «mis modelos», «mi plantilla de la nota», «lo que tengo en trámite» o «mis asuntos pendientes»."
argument-hint: "[qué: modelos, un modelo, en trámite o un asunto] [carpeta del Registro o fichero exportado]"
---

# Mis modelos y lo que tengo en trámite (en el equipo)

Lo que pide: $ARGUMENTS

Intrareg guarda los modelos propios y los asuntos en trámite en el navegador de cada uno y, si el registrador lo ha activado (Intrareg ›
Mis modelos › «💾 También en mi ordenador», o Calificación (Oficina) › En trámite › «💾 En mi ordenador»), una copia al día en la **misma carpeta del
Registro que usa Calificación**, en la subcarpeta `Intrareg/u<cuenta>/` (modelos.json y en_tramite/). Nada de esto está en el servidor:
el conector no lo ve (`mis_modelos` y `en_tramite` solo devuelven el enlace).

Solo donde puedas ejecutar programas en el equipo con acceso a esa carpeta (Cowork con la carpeta conectada, Claude Code). En el chat de
claude.ai no: allí, que abra Intrareg (Mis modelos o Calificación (Oficina) › En trámite).

1. Pregunte, si no lo ha dicho, dónde está la carpeta del Registro (la que eligió en Calificación › ⚙ › «📁 Carpetas compartidas»), o
   el fichero que exportó (Mis modelos.json, un .calificar.json o el ZIP de En trámite) si su navegador no puede usar carpetas.
2. Ejecute en su equipo:
   ```
   python "${CLAUDE_PLUGIN_ROOT}/skills/mis-modelos/scripts/leer_carpeta.py" "<carpeta o fichero>"
   ```
   (en Windows, «py -3» si «python» no responde) y, según lo que pida, con `--modelos`, `--modelo <id>`, `--en-tramite` o `--asunto <id>` (con varias cuentas en la carpeta,
   `--cuenta u<n>`). Lea **solo** lo que imprime el script; no abra los JSON de la carpeta.
3. Los asuntos llevan el número, el estado, las fechas y los defectos con su código del Catálogo: para revisarlos con la doctrina,
   use `ver_defectos`, `estadistica_defectos` y `no_defectos` del conector.
4. **La nota de un asunto** solo está si el registrador activó «con los datos». Lleva datos personales: el script no la imprime;
   escríbala a un fichero con `--nota <id> --salida <fichero.txt>`, anonimícela con la skill «anonimizar» y lea solo el
   `.anonimizado.txt`. Nunca abra los campos «trabajo» ni «nota» de los JSON.
5. Para redactar con un modelo propio (p. ej. su plantilla de la nota), léalo con `--modelo <id>` y respete sus huecos `[[…]]` y
   piezas `{{…}}`. Si la carpeta no tiene la copia, dígale cómo activarla (paso de arriba) o que exporte el fichero.
