"""Rellena la plantilla de la nota de calificación (assets/plantilla_nota.docx) y deja la nota en Word.

Uso:
  python rellenar_nota.py --datos nota.json --salida "Nota de calificación.docx" [--plantilla plantilla_nota.docx]
  python rellenar_nota.py --modelo parcial --datos nota.json --salida "Nota de despacho parcial.docx"
  python rellenar_nota.py --marcadores [--modelo parcial]   # lista los marcadores de la plantilla y qué va en cada uno

Dos modelos: «general» (la nota de calificación negativa, assets/plantilla_nota.docx) y «parcial» (el despacho con inscripción
parcial del art. 19 bis LH: se inscribe lo no afectado y se suspende el resto, con el modelo del Registro «Certificación de despacho
con inscripción parcial», assets/plantilla_nota_parcial.docx).

Solo biblioteca estándar (zipfile y re): funciona en Cowork, en Claude Code y en el intérprete de ChatGPT sin instalar nada.
Todo se hace en el equipo del registrador: el script no abre la red.

nota.json: un objeto con las piezas de la nota (claves en minúsculas, ver MARCADORES). Los textos largos van con un salto de línea
entre párrafos («\\n»). Lo que falte se deja entre corchetes y en amarillo, para que el registrador lo complete en Word.

La forma (centrados, negritas, subrayados) se aplica como en el programa: apartados «I.- HECHOS» centrados en negrita y subrayados;
«Presentante:», «1.º Presentación.», «Alcance de la calificación.», «Primero. — …», «1.º SUSPENDER» y las
líneas «- …» de la parte dispositiva en negrita; «**así**» pone negrita a mano. El membrete, los márgenes y el pie (con
«Entrada N/AAAA» y el número de página) son los de la plantilla. La nota sale sin autor ni fechas en sus propiedades."""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PLANTILLA = AQUI.parent / 'assets' / 'plantilla_nota.docx'
PLANTILLA_PARCIAL = AQUI.parent / 'assets' / 'plantilla_nota_parcial.docx'

# marcador → (clave del JSON, qué va, ejemplo si falta)
MARCADORES = {
    'REGISTRO': ('registro', 'Nombre oficial del Registro: «Registro de la Propiedad de Arenas de San Pedro»', '[Registro de la Propiedad de …]'),
    'REGISTRADOR': ('registrador', 'Nombre y apellidos del registrador', '[nombre del Registrador]'),
    'REGISTRADOR_DE': ('registrador_de', '«Registrador de la Propiedad de … y su distrito hipotecario»', '[Registrador de la Propiedad de … y su distrito hipotecario]'),
    'TRATAMIENTO': ('tratamiento', '«DON» o «DOÑA» (de serie, DON)', 'DON'),
    'ASIENTO': ('asiento', 'Entrada, asiento y Diario, y presentación (una línea cada uno: «ENTRADA Nº: … DEL AÑO: …», «Asiento Nº: …  Diario: …», «Presentado el … a las …»)',
                'ENTRADA Nº: [n.º] DEL AÑO: [año]\nAsiento Nº: [n.º]  Diario: [año]\nPresentado el [fecha] a las [hora]'),
    'DOCUMENTO': ('documento', 'Presentante, interesados, naturaleza, objeto, n.º de documento y autorizante (una línea cada uno: «Presentante: …»)',
                  'Presentante: [presentante]\nInteresados: [interesados]\nNaturaleza: [Documento notarial]\nObjeto: [objeto]\nNº Documento: [n.º] de [fecha]\nNotario: [Notario de …, don …]'),
    'HECHOS': ('hechos', '«1.º Presentación. …» y «2.º Análisis del documento. …» con un apartado por defecto (2.1, 2.2…)', '[Hechos]'),
    'FUNDAMENTOS': ('fundamentos', '«Vistos …», «Alcance de la calificación. …» y un fundamento por defecto desde «Primero. — Título»', '[Fundamentos de derecho]'),
    'SUBSANACION': ('subsanacion', 'Forma de subsanación, sin el título (lo pone el script). Vacío si todos los defectos son insubsanables', ''),
    'ADVERTENCIA': ('advertencia', 'Cláusulas y pactos que no se harán constar, sin el título. Vacío si no hay', ''),
    'PARTE_DISPOSITIVA': ('parte_dispositiva', '«1.º SUSPENDER / DENEGAR …», las líneas «- …» de cada defecto, la anotación preventiva, la prórroga y NOTIFICAR', '[Parte dispositiva]'),
    'TRIBUNAL': ('tribunal', 'Tribunal de la capital de la provincia para impugnar la calificación (art. 328 LH)', '[Tribunal de Instancia de …, Sección Civil]'),
    'RECURSOS': ('recursos', 'Régimen de recursos (de serie, el texto fijo del modelo general, con el tribunal)', None),
    'FIRMA': ('firma', 'Lugar y fecha de firma (de serie: «En [lugar] a fecha de firma.»)', None),
    'LUGAR': ('lugar', 'Municipio del Registro (para la firma)', '[lugar]'),
    'ENTRADA': ('entrada', 'Número de entrada (pie de página)', '[n.º]'),
    'ANIO': ('anio', 'Año de la entrada (pie de página)', '[año]'),
}
# El despacho con inscripción parcial (modelo del Registro «Certificación de despacho con inscripción parcial»): sus [[HUECOS]],
# en minúsculas en el JSON. Lo que no se dé queda entre corchetes.
MARCADORES_PARCIAL = {
    'REGISTRADOR': ('registrador', 'Nombre del registrador (sale en mayúsculas)'),
    'REGISTRO': ('registro', 'El Registro: «Registro de la Propiedad de …» o solo el lugar (sale en mayúsculas, tras «REGISTRO DE LA PROPIEDAD DE»)'),
    'PROTOCOLO': ('protocolo', 'Número de protocolo (n.º/año)'), 'FECHA_ESCRITURA': ('fecha_escritura', 'Fecha de la escritura, en letra'),
    'RESIDENCIA': ('residencia', 'Residencia del Notario'), 'NOTARIO': ('notario', 'Notario autorizante'),
    'ASIENTO': ('asiento', 'Número del asiento de presentación'), 'DIARIO': ('diario', 'Libro Diario'),
    'ENTRADA': ('entrada', 'Número de entrada'), 'OPERACION': ('operacion', 'Título u operación (p. ej. COMPRAVENTA)'),
    'INCIDENCIAS': ('incidencias', 'Incidencias del procedimiento (p. ej. «PRESENTADO 03/03»)'),
    'FECHA_PRESENTACION': ('fecha_presentacion', 'Fecha de presentación, en letra'),
    'DOCUMENTO': ('documento', 'El documento presentado («escritura autorizada el … por el Notario de …»)'),
    'ADJUDICACION': ('inscrito', 'Lo que se inscribe (operación y derecho, p. ej. «el pleno dominio de [PERSONA-1]»)'),
    'TITULO': ('titulo', 'Título de la adquisición (compraventa, herencia…)'), 'CARACTER': ('caracter', 'Carácter (privativo, ganancial…)'),
    'FINCAS_INSCRITAS': ('fincas_inscritas', 'Las fincas en que se ha inscrito, con su inscripción y CRU'),
    'NOTAS_EXTENDIDAS': ('notas_extendidas', 'Notas extendidas al margen, si las hay (puede ir vacío)'),
    'HECHOS': ('hechos', 'Los hechos de lo que se suspende: «1º.- …» uno por defecto'),
    'FUNDAMENTOS': ('fundamentos', 'Los fundamentos de lo que se suspende: «1º.- …» uno por defecto, y los Vistos'),
    'DEFECTOS': ('defectos', 'Los defectos de lo suspendido, una línea «- …» cada uno'),
    'CAPITAL_PROVINCIA': ('capital_provincia', 'Capital de la provincia (para la impugnación judicial)'),
    'LUGAR': ('lugar', 'Municipio del Registro (para la firma)'), 'FECHA': ('fecha', 'Fecha de la firma (de serie «fecha de firma»)'),
    'ANIO': ('anio', 'Año de la entrada (pie de página)'),
}
VACIOS_PARCIAL = ('NOTAS_EXTENDIDAS',)
# Los que la plantilla escribe sola a partir de los demás
DERIVADOS = ('REGISTRO_MAYUS', 'REGISTRADOR_MAYUS', 'NUM_DISPOSITIVA', 'NUM_RECURSOS')

RECURSOS = (
    'Contra la presente calificación negativa podrán los interesados, a su elección:\n'
    'a) Solicitar la calificación del registrador sustituto que corresponda conforme al cuadro de sustituciones, del que puede informarse en este Registro, dentro de los quince días siguientes a la notificación y durante la vigencia del asiento de presentación, aportando testimonio íntegro del título y de la documentación complementaria (artículos 19 bis y 275 bis de la Ley Hipotecaria y Real Decreto 1039/2003, de 1 de agosto).\n'
    'b) Interponer recurso gubernativo ante la Dirección General de Seguridad Jurídica y Fe Pública en el plazo de un mes desde la notificación, mediante escrito dirigido a dicho Centro Directivo y presentado en este Registro, en cualquier otro Registro de la Propiedad o en cualquiera de los lugares previstos en el artículo 16.4 de la Ley 39/2015, incluido el registro electrónico de cualquier Administración, acompañando el título objeto de la calificación, en original o por testimonio, y una copia de esta nota, con los requisitos de los artículos 324 a 327 de la Ley Hipotecaria. La Dirección General deberá resolver y notificar en el plazo de tres meses desde la entrada del recurso en este Registro; transcurrido dicho plazo sin resolución expresa, el recurso se entenderá desestimado, quedando expedita la vía jurisdiccional (artículo 327 de la Ley Hipotecaria).\n'
    'c) Impugnar directamente la calificación ante los órganos del orden jurisdiccional civil de la capital de la provincia en que radican los inmuebles —{tribunal}—, por los trámites del juicio verbal, en el plazo de dos meses desde la notificación (artículo 328 de la Ley Hipotecaria).\n'
    'Están legitimadas para recurrir las personas a que se refiere el artículo 325 de la Ley Hipotecaria. Todo ello sin perjuicio de que el interesado ejercite cualquier otro medio de impugnación que entienda procedente (artículo 19 bis, párrafo segundo, de la Ley Hipotecaria).')
TITULO_SUBSANACION = 'III.- FORMA DE SUBSANACIÓN.'
TITULO_ADVERTENCIA = 'ADVERTENCIA SOBRE CLÁUSULAS Y PACTOS QUE NO SE HARÁN CONSTAR'

# ------------------------------------------------------------------ la forma de cada párrafo
_ETIQUETAS = re.compile(r'^(Presentante:|Interesados:|Naturaleza:|Objeto:|Nº Documento:|Notario:|Juzgado/Tribunal:|Adminis\./Ayunt\.:|'
                        r'Solicitante:|Documento:)')
_ORDINAL = re.compile(r'^(\d\.º (?:SUSPENDER|DENEGAR|NOTIFICAR)|\d\.º(?= (?:No se practica|Queda prorrogado))|\d\.º [A-ZÁÉÍÓÚ][a-záéíóúñ ]{2,40}[.:]|'
                      r'\d+\.\d+\.|(?:Primero\. )?Alcance de la calificación\.|Vistos|\d+\.º [A-ZÁÉÍÓÚ][^.]{2,80}\.)(?=\s)')
_DEFECTO = re.compile(r'^(?:[A-ZÁÉÍÓ][a-záéíóúñ]+|\d+\.º)\. — .{1,300}$')


def _xml(s):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def _runs(texto, negrita=False, subrayado=False):
    """Los «runs» de un texto: «**negrita**» a mano y los [huecos] y {{MARCADORES}} en amarillo."""
    out = []
    for i, trozo in enumerate(re.split(r'\*\*(.+?)\*\*', texto)):
        b = negrita or i % 2 == 1
        for s in re.split(r'(\[[^\]\n]{1,200}\]|\{\{[A-Z_]+\}\})', trozo):
            if not s:
                continue
            hl = bool(re.fullmatch(r'\[[^\]]+\]|\{\{[A-Z_]+\}\}', s))
            out.append('<w:r><w:rPr>' + ('<w:b/>' if b else '') + '<w:noProof/>' + ('<w:u w:val="single"/>' if subrayado else '')
                       + ('<w:highlight w:val="yellow"/>' if hl else '') + f'</w:rPr><w:t xml:space="preserve">{_xml(s)}</w:t></w:r>')
    return ''.join(out)


def parrafo(linea, en_acuerdo=False):
    """Una línea de la nota → <w:p> con la forma del modelo general."""
    x = linea.strip()
    jc, cuerpo = 'both', None
    if not x:
        cuerpo = ''
    elif (re.fullmatch(r'[IVX]+\.-\s.+|ADVERTENCIA SOBRE CLÁUSULAS.*|\{\{NUM_[A-Z]+\}\}\.-\s.+', x) and x == x.upper()):
        jc, cuerpo = 'center', _runs(x, True, True)
    elif re.match(r'^(?:REGISTRO\b|NOTA DE CALIFICACI[ÓO]N|\{\{REGISTRO_MAYUS\}\})', x) and x == x.upper():
        jc, cuerpo = 'center', _runs(x, True)
    elif re.fullmatch(r'_{5,}', x) or re.match(r'^(?:ENTRADA Nº:|Asiento Nº:|Presentado el)', x):
        jc, cuerpo = 'center', _runs(x)
    elif _ETIQUETAS.match(x) and len(x) < 300:
        m = _ETIQUETAS.match(x)
        cuerpo = _runs(m.group(1), True) + _runs(x[len(m.group(1)):])
    elif _DEFECTO.match(x) or (en_acuerdo and x.startswith('- ')):
        cuerpo = _runs(x, True)
    else:
        m = _ORDINAL.match(x)
        if m:
            resto = x[len(m.group(1)):]
            cuerpo = _runs(m.group(1), True) + ''.join(_runs(t, t == 'DENEGAR') for t in re.split(r'(\bDENEGAR\b)', resto))
        else:
            cuerpo = _runs(x)
    return f'<w:p><w:pPr><w:jc w:val="{jc}"/><w:rPr><w:noProof/></w:rPr></w:pPr>{cuerpo}</w:p>'


def parrafos(lineas):
    out, en_acuerdo = [], False
    for linea in lineas:
        x = linea.strip()
        if re.fullmatch(r'(?:[IVX]+|\{\{NUM_[A-Z]+\}\})\.-\s.+', x):
            en_acuerdo = 'PARTE DISPOSITIVA' in x
        out.append(parrafo(linea, en_acuerdo))
    return ''.join(out)


# ------------------------------------------------------------------ el documento
def _parrafos_de(cuerpo):
    """Los <w:p> de primer nivel del cuerpo, con lo que haya entre ellos (tablas, sectPr): [(es_parrafo, xml)]."""
    trozos, pos, prof, ini = [], 0, 0, None
    for m in re.finditer(r'<w:p(?=[ >/])[^>]*?/>|<w:p(?=[ >])[^>]*>|</w:p>', cuerpo):
        t = m.group(0)
        if t.endswith('/>') and t.startswith('<w:p'):
            if prof == 0:
                if m.start() > pos:
                    trozos.append((False, cuerpo[pos:m.start()]))
                trozos.append((True, t))
                pos = m.end()
            continue
        if t.startswith('<w:p'):
            if prof == 0:
                if m.start() > pos:
                    trozos.append((False, cuerpo[pos:m.start()]))
                ini = m.start()
            prof += 1
        else:
            prof -= 1
            if prof == 0:
                trozos.append((True, cuerpo[ini:m.end()]))
                pos = m.end()
    if pos < len(cuerpo):
        trozos.append((False, cuerpo[pos:]))
    return trozos


def _texto(p):
    return ''.join(re.findall(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>', p)).replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')


def _valores(datos):
    """Los valores de cada marcador, con los de serie y los derivados; y la lista de los que faltan."""
    v, faltan = {}, []
    for m, (k, _que, falta) in MARCADORES.items():
        x = datos.get(k)
        x = '' if x is None else str(x).strip()
        if not x and falta:
            x = falta
            if k != 'tratamiento':
                faltan.append(k)
        v[m] = x
    v['TRATAMIENTO'] = (v['TRATAMIENTO'] or 'DON').upper()
    v['REGISTRO_MAYUS'] = v['REGISTRO'].upper() if not v['REGISTRO'].startswith('[') else v['REGISTRO']
    v['REGISTRADOR_MAYUS'] = v['REGISTRADOR'].upper() if not v['REGISTRADOR'].startswith('[') else v['REGISTRADOR']
    sub = bool(v['SUBSANACION'])
    v['NUM_DISPOSITIVA'], v['NUM_RECURSOS'] = ('IV', 'V') if sub else ('III', 'IV')
    if not v['RECURSOS']:
        v['RECURSOS'] = RECURSOS.format(tribunal=v['TRIBUNAL'])
    if not v['FIRMA']:
        v['FIRMA'] = f'En {v["LUGAR"]} a fecha de firma.'
    return v, faltan


def _valores_parcial(datos):
    """Los valores del modelo de despacho parcial y los que faltan."""
    v, faltan = {}, []
    for m, (k, _que) in MARCADORES_PARCIAL.items():
        x = datos.get(k)
        x = '' if x is None else str(x).strip()
        if not x and m not in VACIOS_PARCIAL:
            x = '[' + k.replace('_', ' ') + ']'
            faltan.append(k)
        v[m] = x
    if not v['REGISTRADOR'].startswith('['):
        v['REGISTRADOR'] = v['REGISTRADOR'].upper()
    if not v['REGISTRO'].startswith('['):
        v['REGISTRO'] = re.sub(r'^\s*Registro\s+de\s+la\s+Propiedad\s+(?:n[º.°]*\s*\d+\s+)?de\s+', '', v['REGISTRO'], flags=re.I).upper()
    if v['FECHA'].startswith('['):
        v['FECHA'] = 'fecha de firma'
        faltan.remove('fecha')
    return v, faltan


def _poner(texto, v):
    return re.sub(r'\{\{([A-Z_]+)\}\}', lambda m: v.get(m.group(1), m.group(0)), texto)


def rellenar(plantilla, datos, salida, modelo='general'):
    """Escribe la nota en «salida». → lista de claves que faltaban (quedan entre corchetes)."""
    v, faltan = _valores_parcial(datos) if modelo == 'parcial' else _valores(datos)
    with zipfile.ZipFile(plantilla) as z:
        partes = {n: z.read(n) for n in z.namelist()}
    doc = partes['word/document.xml'].decode('utf-8')
    a, b = doc.index('<w:body>') + len('<w:body>'), doc.index('</w:body>')
    trozos = _parrafos_de(doc[a:b])
    lineas, nuevo, hecho = [], [], False

    def volcar():
        if lineas:
            nuevo.append(parrafos(lineas))
            lineas.clear()
    saltar_vacio = False
    for es_p, x in trozos:
        if not es_p or '<w:drawing' in x or '<w:pict' in x or '<w:sectPr' in x:
            volcar()
            nuevo.append(x)
            continue
        t = _texto(x).strip()
        if saltar_vacio and not t:
            saltar_vacio = False
            continue
        saltar_vacio = False
        bloque = re.fullmatch(r'\{\{([A-Z_]+)\}\}', t)
        if bloque:
            m = bloque.group(1)
            val = v.get(m, '')
            if m == 'SUBSANACION' and val:
                val = TITULO_SUBSANACION + '\n\n' + val
            if m == 'ADVERTENCIA' and val:
                val = TITULO_ADVERTENCIA + '\n\n' + val
            if not val:
                saltar_vacio = True
                continue
            lineas.extend(re.sub(r'\n{3,}', '\n\n', val.replace('\r\n', '\n')).split('\n'))
            hecho = True
            continue
        linea = _poner(t, v)
        if v.get('TRATAMIENTO') == 'DOÑA':
            linea = linea.replace('Registrador titular del', 'Registradora titular del')
        lineas.extend(linea.split('\n'))
    volcar()
    if not hecho:
        raise SystemExit('La plantilla no tiene los marcadores de la nota ({{HECHOS}}, {{FUNDAMENTOS}}…).')
    partes['word/document.xml'] = (doc[:a] + ''.join(nuevo) + doc[b:]).encode('utf-8')
    for n in [n for n in partes if re.fullmatch(r'word/(?:footer|header)\d*\.xml', n)]:
        partes[n] = _poner(partes[n].decode('utf-8'), {k: _xml(x) for k, x in v.items()}).encode('utf-8')
    partes['docProps/core.xml'] = core_limpio('Nota de calificación').encode('utf-8')
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in (['[Content_Types].xml'] + [n for n in partes if n != '[Content_Types].xml']):
            z.writestr(zipfile.ZipInfo(n, (1980, 1, 1, 0, 0, 0)), partes[n], zipfile.ZIP_DEFLATED)
    return faltan


def core_limpio(titulo):
    """Propiedades del documento sin autor, sin «modificado por» y sin fechas."""
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
            f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>{_xml(titulo)}</dc:title></cp:coreProperties>')


def main():
    ap = argparse.ArgumentParser(description='Rellena la plantilla de la nota de calificación.')
    ap.add_argument('--datos', help='JSON con las piezas de la nota')
    ap.add_argument('--salida', help='La nota en Word (.docx)')
    ap.add_argument('--plantilla', help='Otra plantilla (de serie, la del modelo)')
    ap.add_argument('--modelo', choices=('general', 'parcial'), default='general',
                    help='general: nota de calificación negativa; parcial: despacho con inscripción parcial (art. 19 bis LH)')
    ap.add_argument('--marcadores', action='store_true', help='Lista los marcadores y sale')
    a = ap.parse_args()
    if a.marcadores or not (a.datos and a.salida):
        print('Marcadores de la plantilla (clave del JSON: qué va):')
        if a.modelo == 'parcial':
            for m, (k, que) in MARCADORES_PARCIAL.items():
                print(f'  {{{{{m}}}}}  {k}: {que}')
            return 0 if a.marcadores else 2
        for m, (k, que, _f) in MARCADORES.items():
            print(f'  {{{{{m}}}}}  {k}: {que}')
        print('  Se calculan solos: ' + ', '.join('{{' + d + '}}' for d in DERIVADOS))
        return 0 if a.marcadores else 2
    datos = json.loads(Path(a.datos).read_text(encoding='utf-8'))
    if not isinstance(datos, dict):
        raise SystemExit('El JSON ha de ser un objeto con las piezas de la nota.')
    plantilla = a.plantilla or str(PLANTILLA_PARCIAL if a.modelo == 'parcial' else PLANTILLA)
    faltan = rellenar(plantilla, datos, a.salida, a.modelo)
    print(f'Nota escrita: {a.salida}')
    if faltan:
        print('Quedan entre corchetes (en amarillo) para completar en Word: ' + ', '.join(faltan))
    return 0


if __name__ == '__main__':
    sys.exit(main())
