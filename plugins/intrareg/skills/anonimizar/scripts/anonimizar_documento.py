"""Anonimiza un documento EN ESTE EQUIPO con el anonimizador de Intrareg (anonimizar.py, el mismo del servidor), antes de que
Claude lo lea: nombres, DNI/NIE/CIF, domicilios, referencias catastrales, cuentas, correos y teléfonos pasan a etiquetas
([PERSONA-1], [DNI-1]…). Nada sale del equipo. Texto, Markdown y Word (.docx, con sus tablas, encabezados y pies) con la biblioteca
estándar; PDF con la primera biblioteca de uso habitual que tenga el equipo (pypdf, pdfplumber o pdfminer.six) o con «pdftotext»
(Poppler). Un PDF que es solo imagen (escaneado) no se inventa: se avisa de que hace falta OCR y sale con el código 2.

Uso:  python anonimizar_documento.py <documento.txt|.md|.docx|.pdf> [--salida carpeta] [--persona "Nombre Apellido" …]
Deja dos ficheros junto al documento (o en --salida):
  <nombre>.anonimizado.txt  el texto con etiquetas: es lo único que debe leer Claude;
  <nombre>.claves.json      la tabla etiqueta → dato original, para reponer los datos después en la nota (NO se lee ni se
                            envía: se queda en el equipo).
Varios documentos del mismo asunto (la escritura y la nota simple, el título y su certificación): pásalos juntos y la misma persona
lleva la misma etiqueta en todos (un solo <primero>.claves.json):
      python anonimizar_documento.py escritura.pdf nota_simple.pdf
Para reponer:  python anonimizar_documento.py --reponer nota.txt --claves <nombre>.claves.json  (escribe nota.repuesta.txt)
Por la salida solo dice dónde ha dejado los ficheros y cuántos datos ha cambiado, nunca los datos."""
import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from anonimizar import Anonimizador  # noqa: E402


class SinTexto(ValueError):
    """El PDF no tiene texto (es una imagen escaneada): hace falta reconocimiento de caracteres (OCR)."""


MIN_CARACTERES_PAGINA = 25     # menos que esto de media por página: el PDF es una imagen (o casi)


def _xml_docx(xml):
    xml = re.sub(r'</w:p>', '\n', xml)
    xml = re.sub(r'<w:(?:tab|br|cr)\b[^>]*/>', lambda m: '\t' if 'tab' in m.group(0) else '\n', xml)
    txt = re.sub(r'<[^>]+>', '', xml)
    return re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), txt.replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
                  .replace('&apos;', "'")).replace('&amp;', '&')


def leer_docx(p):
    """El texto de un .docx (cuerpo, con sus tablas, y encabezados y pies), sin programas añadidos."""
    with zipfile.ZipFile(p) as z:
        nombres = z.namelist()
        partes = ['word/document.xml'] + sorted(n for n in nombres if re.fullmatch(r'word/(?:header|footer)\d*\.xml', n))
        return '\n'.join(_xml_docx(z.read(n).decode('utf-8', 'replace')) for n in partes if n in nombres)


def leer_pdf(p):
    """El texto de un PDF con la primera biblioteca de uso habitual que haya en el equipo (pypdf, pdfplumber o pdfminer.six) o, si
    no, con «pdftotext» (Poppler). Todo en el equipo. Si el PDF no tiene texto (escaneado), SinTexto: hace falta OCR."""
    texto, paginas, usado = None, 0, ''
    try:
        from pypdf import PdfReader
    except ImportError:
        PdfReader = None
    if PdfReader:
        try:
            r = PdfReader(str(p))
            if r.is_encrypted and not r.decrypt(''):
                raise ValueError('El PDF está protegido con contraseña: ábralo y guárdelo sin protección.')
            hojas = [(pg.extract_text() or '') for pg in r.pages]
        except ValueError:
            raise
        except Exception as e:  # noqa: BLE001  (PDF dañado o de un formato que la biblioteca no entiende)
            raise ValueError(f'No se ha podido leer el PDF ({type(e).__name__}): ábralo y guárdelo de nuevo como PDF.') from e
        texto, paginas, usado = '\n\n'.join(hojas), len(hojas), 'pypdf'
    if texto is None:
        try:
            import pdfplumber
            with pdfplumber.open(str(p)) as pdf:
                hojas = [(pg.extract_text() or '') for pg in pdf.pages]
            texto, paginas, usado = '\n\n'.join(hojas), len(hojas), 'pdfplumber'
        except ImportError:
            pass
    if texto is None:
        try:
            from pdfminer.high_level import extract_text
            texto, usado = extract_text(str(p)) or '', 'pdfminer'
            paginas = max(1, texto.count('\f') + 1)
        except ImportError:
            pass
    if texto is None:
        import shutil
        import subprocess
        exe = shutil.which('pdftotext')
        if exe:
            r = subprocess.run([exe, '-layout', '-enc', 'UTF-8', str(p), '-'], capture_output=True, timeout=300)
            if r.returncode == 0:
                texto, usado = r.stdout.decode('utf-8', 'replace'), 'pdftotext'
                paginas = max(1, texto.count('\f') + 1)
    if texto is None:
        raise ValueError('Para leer un PDF en este equipo hace falta una biblioteca de Python de uso habitual: instale pypdf '
                         '(«python -m pip install pypdf») y vuelva a intentarlo. Nada se envía fuera.')
    util = len(re.sub(r'\s+', '', texto))
    if util < MIN_CARACTERES_PAGINA * max(1, paginas):
        raise SinTexto(f'El PDF ({paginas} página(s)) apenas tiene texto ({util} caracteres): es una imagen escaneada y hace falta '
                       'reconocimiento de caracteres (OCR). Páselo antes por un OCR (p. ej. «Guardar como PDF con texto» del escáner, '
                       'o el OCR de Intrareg en el navegador) y vuelva a anonimizarlo. No se ha leído nada.')
    return texto, usado


def leer(ruta):
    p = Path(ruta)
    s = p.suffix.lower()
    if s in ('.txt', '.md', ''):
        return p.read_text(encoding='utf-8', errors='replace')
    if s == '.docx':
        return leer_docx(p)
    if s == '.pdf':
        return leer_pdf(p)[0]
    raise ValueError(f'No sé leer «{s}»: guárdelo como .pdf, .docx o .txt, o ábralo en Intrareg (✦ IA › cargar el documento › '
                     '«texto anonimizado» › Copiar) y pegue aquí el texto.')


def anonimizar(ruta, salida=None, personas=()):
    p = Path(ruta)
    d = Path(salida) if salida else p.parent
    d.mkdir(parents=True, exist_ok=True)
    a = Anonimizador()
    if personas:
        a.nombres(list(personas))
    texto = a.texto(leer(p))
    fa, fc = d / (p.stem + '.anonimizado.txt'), d / (p.stem + '.claves.json')
    fa.write_text(texto, encoding='utf-8')
    fc.write_text(json.dumps(a.originales, ensure_ascii=False, indent=1), encoding='utf-8')
    return fa, fc, len(a.originales)


def anonimizar_juntos(rutas, salida=None, personas=()):
    """Varios documentos con el mismo anonimizador: las mismas etiquetas para los mismos datos. → ([anonimizados], claves, n)"""
    rutas = [Path(r) for r in rutas]
    a = Anonimizador()
    if personas:
        a.nombres(list(personas))
    textos = [leer(p) for p in rutas]
    hechos = []
    for p, txt in zip(rutas, textos):
        d = Path(salida) if salida else p.parent
        d.mkdir(parents=True, exist_ok=True)
        fa = d / (p.stem + '.anonimizado.txt')
        fa.write_text(a.texto(txt), encoding='utf-8')
        hechos.append(fa)
    fc = (Path(salida) if salida else rutas[0].parent) / (rutas[0].stem + '.claves.json')
    fc.write_text(json.dumps(a.originales, ensure_ascii=False, indent=1), encoding='utf-8')
    return hechos, fc, len(a.originales)


def reponer(ruta, claves):
    tabla = json.loads(Path(claves).read_text(encoding='utf-8'))
    t = Path(ruta).read_text(encoding='utf-8')
    for etq in sorted(tabla, key=len, reverse=True):
        t = t.replace(etq, str(tabla[etq]))
    f = Path(ruta).with_name(Path(ruta).stem + '.repuesta' + Path(ruta).suffix)
    f.write_text(t, encoding='utf-8')
    return f


def main(argv=None):
    ap = argparse.ArgumentParser(description='Anonimiza un documento en este equipo (anonimizador de Intrareg).')
    ap.add_argument('documento', nargs='*')
    ap.add_argument('--salida')
    ap.add_argument('--persona', action='append', default=[])
    ap.add_argument('--reponer')
    ap.add_argument('--claves')
    x = ap.parse_args(argv)
    try:
        if x.reponer:
            print(f'Texto con los datos repuestos en {reponer(x.reponer, x.claves)} (no lo lea Claude).')
            return 0
        if not x.documento:
            ap.error('Falta el documento.')
        if len(x.documento) > 1:
            fas, fc, n = anonimizar_juntos(x.documento, x.salida, x.persona)
            print(f'Hecho: {n} datos cambiados por etiquetas, las mismas en los {len(fas)} documentos.')
            for fa in fas:
                print(f'Texto anonimizado (léalo): {fa}')
            print(f'Claves (no lo lea ni lo envíe): {fc}')
            return 0
        fa, fc, n = anonimizar(x.documento[0], x.salida, x.persona)
    except SinTexto as e:
        print(f'No se ha anonimizado: {e}')
        return 2
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
        print(f'No se ha podido anonimizar: {e}')
        return 1
    print(f'Hecho: {n} datos cambiados por etiquetas.\nTexto anonimizado (léalo): {fa}\nClaves (no lo lea ni lo envíe): {fc}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
