---
name: menu
description: Abre el asistente guiado de Intrareg — menú numerado (nota de calificación, defectos del Catálogo, resoluciones, artículos, aranceles, consulta); después, conversación como con un oficial del Registro.
argument-hint: "[número de opción o lo que quiere hacer]"
disable-model-invocation: true
---

`/intrareg:menu` es otro nombre de `/intrareg:empezar`. Abre el asistente de Intrareg con la skill «empezar» y sigue sus reglas (el menú y, después,
conversación normal).

- Sin nada más: muestra el menú (`### ⚖️ Intrareg › Menú`).
- Con algo: $ARGUMENTS — si es un número del 1 al 6, entra en esa tarea; si es una petición, entra en esa tarea
  sin preguntar lo ya dicho.
