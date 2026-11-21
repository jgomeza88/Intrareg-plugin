# Intrareg para Claude (plugin)

Plugin de Intrareg para **Claude Cowork** (aplicación de escritorio de Claude) y **Claude Code**. Ayuda al Registrador de la Propiedad a
calificar con el Catálogo de defectos de Intrareg y la doctrina de la Dirección General de Seguridad Jurídica y Fe Pública, y deja la
nota de calificación como **borrador en Intrareg**, en su cuenta, para editarla allí (en Word solo si la pide).

El plugin **no lleva datos**: el Catálogo, la estadística de la DG, las resoluciones, la doctrina, los artículos, la Biblioteca y los
aranceles se consultan en vivo por el **conector de Intrareg** (`https://intrareg.com/w/mcp`, solo lectura), con la cuenta de
Intrareg del registrador.

Tampoco lleva escrito el método: de las skills de calificar, de la nota, del recurso, de las citas y del asistente, el plugin que se
instala trae solo el nombre, la descripción y la orden de pedir su texto a Intrareg (herramienta `instrucciones` del conector), que lo
da a quien tiene cuenta, una vez por tarea y con lo que esa tarea usa por debajo. En el equipo se quedan enteros el anonimizador, la
guarda de los datos, la lectura de sus modelos y las plantillas de Word con su programa.

## Qué trae

| | |
|---|---|
| `/intrareg:empezar` o `/intrareg:menu` | **Asistente**: menú numerado y, después, conversación como con un oficial del Registro (ver «Cómo empezar»). |
| `/intrareg:calificar <documento>` | Lee el documento, consulta Intrareg, propone la calificación y, si hay defectos, deja la nota como borrador en Intrareg (en Word, si lo pide). |
| `/intrareg:revisar-nota <nota>` | Revisa una nota contra el Catálogo y la estadística de la DG: riesgo de revocación de cada defecto, fundamentos y citas. |
| `/intrareg:defectos <documento>` | Solo la lista de posibles defectos, con su riesgo ante la DG. |
| `/intrareg:informe-recurso [recurso]` | Informe del registrador en defensa de la nota (art. 327 LH): doctrina a favor y en contra de cada defecto y el informe en Word. |
| `/intrareg:herencia`, `/intrareg:inmatriculacion`, `/intrareg:exceso-cabida` | Calificación de esos negocios: los candidatos del Catálogo para ese negocio, lo que hay que repasar y el riesgo de cada defecto ante la DG; en la inmatriculación y el exceso de cabida, también la calificación gráfica. |
| `/intrareg:novedades [periodo, materia]` | ¿Qué hay nuevo? Resoluciones de la DG, sentencias, consultas, aranceles y legislación de un periodo, por materia. |
| `/intrareg:plazos <presentación> [notificación]` | Plazos del asiento en días hábiles: calificación, caducidad, prórroga, sustitutoria y recurso. |
| `/intrareg:minuta <operación y valor>` | Minuta orientativa con la calculadora de aranceles de Intrareg. |
| `/intrareg:oposiciones [tema]` | Pregunta un tema de Registros o Notarías, corrige la exposición («cantar» el tema: dictado o voz de Claude, o lo grabado en Intrareg) y sugiere qué añadir. |
| `/intrareg:anonimizar <documento>` | Anonimiza el documento (PDF con texto, Word, texto) en su equipo con el anonimizador de Intrareg antes de que Claude lo lea (las claves se quedan en su equipo). Un PDF escaneado (solo imagen) necesita antes OCR: se avisa, no se inventa. |
| `/intrareg:mis-modelos [qué]` | Sus modelos propios y sus asuntos en trámite, leídos en su equipo de la carpeta del Registro (subcarpeta `Intrareg`) o de lo exportado, sin pasar por el servidor. |
| Skills de apoyo | `conector-intrareg` (herramientas y citas por fecha de firma), `calificar-documento` (el método), `redactar-nota-calificacion` (el modelo de la nota y la plantilla); `empezar`, con un guion por tarea. Su texto, del conector. |
| Plantillas (Word, solo si se pide) | `skills/redactar-nota-calificacion/assets/plantilla_nota_parcial.docx` (despacho con inscripción parcial, art. 19 bis LH: el modelo del Registro «Certificación de despacho con inscripción parcial», `--modelo parcial`) y `plantilla_nota.docx`, con los marcadores `{{REGISTRO}}`, `{{ASIENTO}}`, `{{DOCUMENTO}}`, `{{HECHOS}}`, `{{FUNDAMENTOS}}`, `{{SUBSANACION}}`, `{{PARTE_DISPOSITIVA}}`, `{{RECURSOS}}`, `{{FIRMA}}`…, que rellena `scripts/rellenar_nota.py`. |
| Conector | `.mcp.json`: el servidor MCP de Intrareg (HTTP, OAuth). Sin claves en el fichero. |
| Guarda de los datos | `hooks/`: Claude no puede leer, buscar ni copiar el fichero de claves del anonimizador (`*.claves.json`), y antes de abrir un PDF o un Word que no tiene al lado su versión anonimizada le pide confirmación. No depende de que Claude siga las instrucciones. |
| Segundo registrador | `agents/segundo-registrador.md`: la última revisión de la calificación la hace un agente aparte, que solo ve el documento anonimizado y los defectos propuestos, no el razonamiento previo; descarta lo que el documento no prueba o la DG revoca. |
| Casos de evaluación | `evals/` (no va en el plugin que se instala): los casos de la DG con documentos inventados y unos de comportamiento, para medir el plugin con `claude plugin eval` antes de cada versión (cuesta suscripción o API). Se rehacen con `herramientas/evals_plugin.py`. |

Todo son skills (`skills/<nombre>/SKILL.md`, el formato vigente de los plugins de Claude; ya no hay carpeta `commands/`): cada
orden es la skill del mismo nombre, que se lanza con `/intrareg:<nombre>` y, si se escribe algo detrás, lo recibe como
`$ARGUMENTS`. Las órdenes también se pueden pedir con palabras («califica esta escritura», «haz la nota»): las skills se activan
solas, salvo `menu`, que solo se lanza a mano (`disable-model-invocation`) porque es otro nombre de `empezar`. En el chat de
claude.ai las skills se eligen con `/` o se activan solas.

## Cómo empezar

Escriba **«hola»** (o «menú», o `/intrareg:empezar`) y Claude contesta con el menú:

```
### ⚖️ Intrareg › Menú
¿Qué quiere hacer?
1. Redactar una nota de calificación
2. Buscar un defecto en el Catálogo
3. Resoluciones de la DG o sentencias sobre un tema
4. Artículo vigente
5. Aranceles / honorarios
6. Consulta (una pregunta libre)
```

Conteste con el número. A partir de ahí es una conversación normal, como con un oficial del Registro: primero se habla de lo
presentado y de las cuestiones dudosas, se repasan los defectos del Catálogo y la doctrina de la DG, y Claude le entrega el
**documento de defectos** (cada defecto con su código y enlace a la ficha en Intrareg). Solo al final, si quiere la nota, se pasa a
los datos: mejor rellenarlos en Intrareg (Calificación (Oficina) › Nuevo); si no, anonimizados o entre corchetes. «menú» vuelve al menú.

Ejemplo:

> **Usted**: 1
> **Claude**: ¿Qué le han presentado? Con el tipo de documento y el negocio me basta para empezar, sin nombres ni datos.
> **Usted**: Una compraventa en escritura; vende un señor casado.
> **Claude**: Veo dos cuestiones que conviene mirar: la vivienda familiar (C-0101-1.05-02, subsanable; la DG lo viene confirmando)
> y el régimen económico del vendedor. ¿Consta en la escritura la manifestación sobre la vivienda?

**Los enlaces van a Intrareg.** Cada resolución lleva a su voz del Fichero único con la resolución señalada (`#fichero/res:…`; si
aún no tiene voz, a su ficha) y cada artículo a su ventana con el texto consolidado (`#fichero/art:…`); el BOE, solo si lo pide. El
conector devuelve ya cada cita enlazada.

**Con el navegador.** En la aplicación de escritorio de Claude, si la conversación tiene el **navegador integrado** (el panel de la
derecha), Claude **abre Intrareg ahí desde la primera respuesta, sin preguntar**, y lleva allí cada enlace que le dé —la resolución en
su voz, el artículo, la ficha del defecto, el borrador de la nota— (si Intrareg pide entrar, entra usted; la sesión se queda en ese
panel). Si solo tiene la extensión **Claude in Chrome**, lo mismo en una pestaña de su Chrome. Sin navegador, Claude le da los
enlaces. **Lo que no depende del plugin**: un enlace escrito en un mensaje lo abre la aplicación de Claude a su manera (en el
escritorio, en el navegador del sistema); por eso Claude lo abre con sus herramientas. Sin preguntar, solo abre intrareg.com; las
contraseñas y los datos los escribe usted, y nada se guarda ni se envía sin que lo diga.

**También con lo de fuera de Intrareg.** Claude usa además la legislación, la jurisprudencia y la doctrina que conozca o encuentre con
la búsqueda web (si la tiene; solo con términos jurídicos, nunca con datos del documento), siempre con la **fuente concreta** (norma y
artículo, resolución por su fecha de firma, sentencia con su ROJ o ECLI, autor y obra) y su enlace si lo hay. Va **marcada «fuera de
Intrareg»**, contrastada con lo que dice Intrareg (herramienta `contrastar_fuente`) y, si no se puede verificar, se lo dice.

**La nota, en Intrareg.** Con los defectos decididos, Claude deja la nota como **borrador en su cuenta de Intrareg** (herramienta
`borrador_nota`: hechos, defectos del Catálogo con su código, fundamentos y datos del asiento, seudonimizados) y le da el enlace; al
abrirlo es un asunto de Calificación, igual que «Nueva calificación», que completa y edita allí (el servidor lo borra al abrirlo; sin
abrir, caduca en 7 días; como mucho 10 por hora). Si se inscribe una parte y se suspende el resto (art. 19 bis LH), sale con el modelo
del Registro **«Certificación de despacho con inscripción parcial»** (su versión propia, si la tiene). La nota en Word, solo si la pide.

Claude no habla primero: el menú sale con el **primer mensaje** de cada conversación. Para que salga siempre, sin pedirlo, cree en
Claude un **Proyecto «Intrareg»** y pegue en sus instrucciones el texto de `instrucciones_proyecto.md` (Proyectos › Nuevo proyecto ›
Instrucciones del proyecto): todas las conversaciones de ese proyecto empiezan con el menú. Sirve también en claude.ai con solo el
conector (sin el plugin).

## Instalarlo

Hace falta una cuenta de Intrareg de **registrador verificado**. La primera vez, Claude pide **iniciar sesión en Intrareg** para
autorizar el acceso de solo lectura del conector.

Se instala desde su repositorio público, `jgomeza88/intrareg-plugin`, sin descargar nada de Intrareg.

### Cowork (aplicación de escritorio de Claude)
1. Personalizar › Plugins › Añadir marketplace, y escriba `jgomeza88/intrareg-plugin`.
2. Instale «Intrareg» de ese marketplace.
3. En el plugin, pestaña Conectores: «Conectar» en Intrareg, entre con su cuenta y permita el acceso de solo lectura.
4. En una tarea de Cowork con acceso a la carpeta de sus documentos: `/intrareg:calificar escritura.pdf`.

### Claude Code
```
/plugin marketplace add jgomeza88/intrareg-plugin
/plugin install intrareg@intrareg
```
Para que se ponga al día solo: `/plugin` › Marketplaces › intrareg › Enable auto-update. Después, `/mcp` › intrareg › Autenticar, y
entre con su cuenta de Intrareg.

### Qué ejecuta en su equipo y qué envía
- Solo se conecta a `https://intrareg.com` (el conector, con OAuth) y, si usted lo pide, Claude abre intrareg.com en su navegador.
- La guarda de los datos (`hooks/guarda_datos.py`) se ejecuta con Python antes de cada lectura de ficheros: no envía nada; solo
  bloquea el fichero de claves del anonimizador y pide confirmación antes de leer un documento sin anonimizar.
- Los scripts (`anonimizar.py`, `anonimizar_documento.py`, `leer_carpeta.py`, `rellenar_nota.py`, `informe_docx.py`) trabajan con
  ficheros de su equipo y no se conectan a nada (para leer un PDF, `anonimizar_documento.py` usa `pdftotext` si está instalado).

## Lo que trae el conector (y lo que no)

- **Los candidatos de una vez** (`candidatos_defectos`): con el negocio, la clase de documento y unos términos jurídicos (nunca el
  documento), los defectos que pueden venir al caso, como los prepara Intrareg para su propia calificación.
- **Solo lo que sirve fuera de Intrareg**: las herramientas de la pantalla de Intrareg (cambiar la nota, ir a otra pantalla…) no se
  ofrecen al asistente, que no ve esa pantalla.
- **Las órdenes sin plugin**: quien solo tiene el conector (claude.ai en la web o en el móvil) tiene también como indicaciones del
  conector `defectos`, `revisar-nota`, `informe-recurso`, `novedades`, `plazos` y `minuta`, además de `calificar` y `empezar`.

- **Datos de su cuenta para la nota** (`mi_registro`): Registro, su nombre, «Registrador de la Propiedad de … y su distrito
  hipotecario», lugar de la firma y tribunal; solo los de la cuenta conectada.
- **Plazos, minuta, novedades, oposiciones y Catastro** (ficha, afecciones y colindantes), de solo lectura. El Catastro se consulta en
  el momento con la referencia catastral que usted dé (sale de su equipo hacia Intrareg y el Catastro): Claude le pide permiso antes.
- **Vistas dentro de la conversación** (en pruebas: el administrador con el ajuste `mcp_vistas`; para todos cuando se publiquen en Administración › Funciones en pruebas): la ficha del defecto, la
  estadística confirma/revoca de un defecto con sus resoluciones, la lista de resoluciones con su resultado y la nota en curso
  (seudonimizada) con sus defectos enlazados. Sin nada externo: los enlaces abren Intrareg.
- **Contrastar lo de fuera** (`contrastar_fuente`): una norma, una resolución, una sentencia (con su ROJ o ECLI) o una obra de
  doctrina que Claude trae de fuera sale marcada «fuera de Intrareg», con su fuente, y con el enlace a Intrareg si Intrareg la tiene;
  si no, «no verificada en Intrareg».
- **Borradores de nota** (`borrador_nota`): solo en la cuenta conectada, sin datos personales (se rechazan nombres y DNI), con tope
  por hora; se apagan con el ajuste `mcp_borradores`.
- **Escribir en Intrareg** (de momento, solo el administrador): enviar sugerencias al Catálogo y guardar la corrección de una
  exposición en el seguimiento del alumno. Hace falta marcar «Permitir también escribir» al conectar (con el doble factor) y
  confirmar cada envío o guardado.
- **Sus modelos y lo que tiene en trámite** no están en el servidor: viven en su navegador y, si lo activa (Intrareg › Mis modelos ›
  «💾 También en mi ordenador», o Calificación (Oficina) › En trámite › «💾 En mi ordenador»), en una copia al día dentro de **la misma carpeta del
  Registro que usa Calificación** (la elegida en Calificación › ⚙ › «📁 Carpetas compartidas»), en `Intrareg/u<cuenta>/`:
  `modelos.json` y `en_tramite/<id>.json` (número, estado y defectos; los datos y la nota solo si activa «con los datos»). La skill
  `mis-modelos` los lee de esa carpeta en su equipo (Cowork con la carpeta conectada, o Claude Code); sin carpeta (Firefox, Safari,
  móvil), lee también `Mis modelos.json` y lo exportado de En trámite.
## Privacidad

- **El documento no va a Intrareg.** Claude lo lee en su equipo; al conector solo van términos jurídicos cortos («vivienda familiar
  consentimiento cónyuge»), y el conector **rechaza** cualquier búsqueda que lleve nombres, DNI, domicilios u otros datos personales.
- El documento lo trata Anthropic según el plan de Claude del registrador. **Con documentos reales, use un plan de empresa** (Team o
  Enterprise: sin entrenamiento con sus datos y con acuerdo de tratamiento).
- **La búsqueda en internet, solo con términos jurídicos**: Claude la usa para la legislación, la jurisprudencia o la doctrina de
  fuera de Intrareg, nunca con el documento ni con datos del caso. Si prefiere no arriesgar, desactívela en las tareas con documentos.
- El borrador de la nota va seudonimizado y se borra del servidor al abrirlo; la nota en Word (si la pide) se escribe en su carpeta,
  sin autor ni metadatos en sus propiedades.
- Las conexiones del conector se ven y se retiran en Intrareg › Mi cuenta › ✦ IA.

La calificación la decide y la firma el registrador: el plugin prepara una propuesta con sus fuentes.
