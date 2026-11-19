"""Deja el informe del registrador en defensa de la nota (art. 327 LH) en Word (.docx), con una plantilla propia escrita aquí
mismo (Times New Roman 12, márgenes de 3 cm, título centrado y párrafos justificados). Solo biblioteca estándar.

Uso:  python informe_docx.py --datos informe.json --salida "Informe recurso.docx"
informe.json: {"registro": "Registro de la Propiedad de …", "titulo": "INFORME DEL REGISTRADOR", "encabezado": "…",
               "secciones": [{"titulo": "I. ANTECEDENTES DE HECHO", "texto": "…"}], "firma": "En … a fecha de firma."}
Lo que va entre corchetes sale resaltado en amarillo (para completar); **así**, en negrita. Sin autor ni fechas en las propiedades."""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                 '<Default Extension="xml" ContentType="application/xml"/>'
                 '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                 '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                 '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
                 '</Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '</Relationships>')
DOC_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>')
CORE = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Informe del registrador</dc:title></cp:coreProperties>')
STYLES = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr>'
          '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/><w:sz w:val="24"/><w:lang w:val="es-ES"/>'
          '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="300" w:lineRule="auto"/><w:jc w:val="both"/>'
          '</w:pPr></w:pPrDefault></w:docDefaults></w:styles>')


def _runs(texto, negrita=False):
    """Trozos con **negrita** y [corchetes] resaltados."""
    out = []
    for parte in re.split(r'(\*\*[^*]+\*\*|\[[^\]]*\])', texto):
        if not parte:
            continue
        b = negrita or (parte.startswith('**') and parte.endswith('**'))
        t = parte[2:-2] if parte.startswith('**') and parte.endswith('**') else parte
        rpr = ('<w:b/>' if b else '') + ('<w:highlight w:val="yellow"/>' if t.startswith('[') else '')
        out.append(f'<w:r>{"<w:rPr>" + rpr + "</w:rPr>" if rpr else ""}<w:t xml:space="preserve">{escape(t)}</w:t></w:r>')
    return ''.join(out)


def _p(texto, centrado=False, negrita=False, sangria=True):
    ppr = '<w:pPr>' + ('<w:jc w:val="center"/>' if centrado else (f'<w:ind w:firstLine="709"/>' if sangria else '')) + '</w:pPr>'
    return f'<w:p>{ppr}{_runs(texto, negrita)}</w:p>'


def documento(d):
    cuerpo = [_p(str(d.get('titulo') or 'INFORME DEL REGISTRADOR'), centrado=True, negrita=True)]
    if d.get('registro'):
        cuerpo.append(_p(str(d['registro']).upper(), centrado=True, negrita=True))
    for par in str(d.get('encabezado') or '').split('\n'):
        if par.strip():
            cuerpo.append(_p(par.strip()))
    for s in d.get('secciones') or []:
        if s.get('titulo'):
            cuerpo.append(_p(str(s['titulo']), negrita=True, sangria=False))
        for par in str(s.get('texto') or '').split('\n'):
            if par.strip():
                cuerpo.append(_p(par.strip()))
    cuerpo.append(_p(str(d.get('firma') or 'En [lugar] a fecha de firma.'), sangria=False))
    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1701" w:right="1701" w:bottom="1418" w:left="1701" '
            'w:header="709" w:footer="709" w:gutter="0"/></w:sectPr>')
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>'
            + ''.join(cuerpo) + sect + '</w:body></w:document>')


def escribir(d, salida):
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as z:
        for nombre, txt in (('[Content_Types].xml', CONTENT_TYPES), ('_rels/.rels', RELS), ('word/_rels/document.xml.rels', DOC_RELS),
                            ('word/styles.xml', STYLES), ('docProps/core.xml', CORE), ('word/document.xml', documento(d))):
            zi = zipfile.ZipInfo(nombre, (1980, 1, 1, 0, 0, 0))
            z.writestr(zi, txt.encode('utf-8'), zipfile.ZIP_DEFLATED)
    return salida


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--datos', required=True)
    ap.add_argument('--salida', required=True)
    a = ap.parse_args(argv)
    d = json.loads(Path(a.datos).read_text(encoding='utf-8'))
    f = escribir(d, a.salida)
    print(f'Informe en {f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
