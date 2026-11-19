---
name: anonimizar
description: Anonimiza en el equipo del registrador, con el anonimizador de Intrareg, un documento con datos personales (escritura, mandamiento, recurso, nota) antes de leerlo, para que a Claude no le lleguen nombres, DNI, domicilios, referencias catastrales ni cuentas. Úsala siempre antes de leer un documento con datos (Cowork, Claude Code), y cuando digan «anonimízalo», «quítale los datos» o «sin datos personales».
argument-hint: "<documento: ruta del .pdf, .docx, .txt o .md>"
---

# Anonimizar en el equipo

Documento: $ARGUMENTS

Solo donde puedas ejecutar programas en el equipo del registrador (Cowork con acceso a su carpeta, Claude Code). En el chat de
claude.ai no: allí, que pegue el texto anonimizado desde Intrareg (✦ IA › cargar el documento › «texto anonimizado» › Copiar).

1. **No abras el documento antes.** Ejecuta, en su equipo:
   ```
   python "${CLAUDE_PLUGIN_ROOT}/skills/anonimizar/scripts/anonimizar_documento.py" "<documento>"
   ```
   (en Windows, «py -3» en lugar de «python» si no responde; si conoce los nombres de los intervinientes y los dice, añade `--persona "Nombre Apellido"` por cada uno: mejora el resultado).
   **Varios documentos del mismo asunto** (la escritura y su nota simple o certificación, el título y los documentos
   complementarios): pásalos **juntos en la misma orden**, uno detrás de otro; así la misma persona o finca lleva la misma etiqueta en
   todos y se puede comparar (el tracto: ¿el que vende es el titular inscrito?). Las claves quedan en `<primero>.claves.json`.
2. Lee **solo** `<nombre>.anonimizado.txt`. **Nunca** leas, copies ni envíes `<nombre>.claves.json`: guarda los datos reales y se
   queda en su equipo (la guarda del plugin lo impide aunque se intente).
3. Trabaja con las etiquetas ([PERSONA-1], [DNI-1], [DOMICILIO-1]…) como si fueran los datos; en la nota, déjalas tal cual.
4. Al terminar, si quiere la nota con los datos reales, repónlos en su equipo sin leerlos:
   ```
   python "${CLAUDE_PLUGIN_ROOT}/skills/anonimizar/scripts/anonimizar_documento.py" --reponer "<nota.txt>" --claves "<nombre>.claves.json"
   ```
   y dile dónde ha quedado el fichero (no lo abras).
5. **PDF**: el script saca el texto en el equipo con una biblioteca de uso habitual (pypdf, pdfplumber o pdfminer.six, o el programa
   «pdftotext»). Si dice que falta, propón instalar pypdf (`python -m pip install pypdf`, en su equipo y con su permiso) y repite.
   Si responde que el PDF **es solo imagen** (escaneado; sale con el código 2), **no inventes el contenido ni lo abras para leerlo**:
   dile que hace falta pasarlo antes por un OCR (el del escáner, o el anonimizador de Intrareg en el navegador, que lo reconoce) y
   que vuelva a pedirlo. Word (.docx) se lee siempre, con sus tablas, encabezados y pies.

El anonimizador es el mismo del servidor de Intrareg (`scripts/anonimizar.py`, con su diccionario de nombres en
`static/lib/nombres_es.json`); nada sale del equipo. Es automático: si ves en el texto anonimizado un dato que se le ha escapado,
no lo repitas y avisa en una línea.
