"""Lee EN ESTE EQUIPO los modelos propios («Mis modelos») y los asuntos en trámite que Intrareg guarda en la carpeta del Registro del
usuario (subcarpeta «Intrareg», que escribe el navegador) o en los ficheros que exporta Intrareg cuando el navegador no puede usar
carpetas. Nada pasa por el servidor de Intrareg ni sale del equipo. Solo biblioteca estándar.

Dónde busca (la ruta que se le da puede ser cualquiera de estas):
  <carpeta del Registro>/Intrareg/u<cuenta>/{cuenta.json, modelos.json, en_tramite/<id>.json}   (la copia al día del navegador)
  «Mis modelos.json»                       (⬇ Exportar mis modelos)
  «<asiento>.calificar.json» o «Trabajos <fecha>.zip»   (Oficina › En trámite › ⬇ Exportar)

Uso:
  python leer_carpeta.py <ruta>                       resumen: cuentas, modelos y asuntos
  python leer_carpeta.py <ruta> --modelos             la lista de modelos (id, clase, título)
  python leer_carpeta.py <ruta> --modelo <id>         el texto de un modelo
  python leer_carpeta.py <ruta> --en-tramite          la lista de asuntos (número, estado, defectos con su código)
  python leer_carpeta.py <ruta> --asunto <id>         un asunto: número, estado, fechas y defectos
  python leer_carpeta.py <ruta> --nota <id> --salida <fichero.txt>
        escribe en ese fichero la nota del asunto (solo si se guardó «con los datos»): lleva datos personales, así que NO se imprime;
        anonimícela después con la skill «anonimizar» antes de leerla.
  --cuenta u<n>   si en la carpeta hay varias cuentas (la carpeta del Registro puede ser compartida), cuál.
Por la salida nunca van los datos del asiento ni el texto de la nota."""
import argparse
import json
import sys
import zipfile
from pathlib import Path

class Error(Exception):
    pass


def _json(p):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as e:
        raise Error(f'No se puede leer {Path(p).name}: {e}') from e


# ------------------------------------------------------------------ dónde está
def _cuentas(raiz):
    """Las subcarpetas de cuenta (con cuenta.json o modelos.json) bajo raiz, que puede ser la carpeta del Registro, su «Intrareg» o
    ya una cuenta."""
    raiz = Path(raiz)
    for cand in (raiz, raiz / 'Intrareg'):
        if (cand / 'modelos.json').is_file() or (cand / 'cuenta.json').is_file():
            return [cand]
        if cand.is_dir():
            cs = sorted(d for d in cand.iterdir() if d.is_dir() and ((d / 'cuenta.json').is_file() or (d / 'modelos.json').is_file()))
            if cs:
                return cs
    return []


def cargar(ruta, cuenta=None):
    """{'origen', 'cuenta', 'nombre', 'con_datos', 'modelos': [...], 'asuntos': [...]} de una carpeta o de un fichero exportado."""
    p = Path(ruta)
    if not p.exists():
        raise Error(f'No existe {p}.')
    if p.is_file():
        return _de_fichero(p)
    cs = _cuentas(p)
    if not cs:
        raise Error(f'En {p} no hay copia de Intrareg (falta la subcarpeta «Intrareg»). En Intrareg: Mis modelos › «💾 También en mi '
                    'ordenador», o exporte los modelos y lo que está en trámite.')
    if cuenta:
        cs = [c for c in cs if c.name == cuenta]
        if not cs:
            raise Error(f'No está la cuenta {cuenta}.')
    if len(cs) > 1:
        ls = ', '.join(f'{c.name} ({_json(c / "cuenta.json").get("nombre", "") if (c / "cuenta.json").is_file() else ""})' for c in cs)
        raise Error(f'Hay varias cuentas en la carpeta: {ls}. Indique cuál con --cuenta.')
    c = cs[0]
    info = _json(c / 'cuenta.json') if (c / 'cuenta.json').is_file() else {}
    mod = _json(c / 'modelos.json') if (c / 'modelos.json').is_file() else {}
    if mod and mod.get('formato') not in (None, 'intrareg.modelos'):
        raise Error('modelos.json no es de Intrareg.')
    asuntos = []
    d = c / 'en_tramite'
    if d.is_dir():
        for f in sorted(d.glob('*.json')):
            x = _json(f)
            if x.get('formato') == 'intrareg.en_tramite':
                asuntos.append(x)
    return {'origen': str(c), 'cuenta': c.name, 'nombre': info.get('nombre', ''), 'con_datos': bool(info.get('con_datos')),
            'actualizado': info.get('actualizado') or mod.get('actualizado', ''), 'modelos': mod.get('modelos') or [], 'asuntos': asuntos}


def _de_trabajo(t):
    """Un trabajo exportado (.calificar.json) → el mismo resumen que en_tramite/<id>.json (con el trabajo entero aparte)."""
    D = t.get('datos') or {}
    return {'formato': 'intrareg.en_tramite', 'id': str(t.get('id') or ''), 'asiento': str(D.get('asiento') or ''),
            'anio': str(D.get('anio') or str(D.get('fecha_pres') or '')[:4]), 'entrada': str(D.get('entrada') or ''), 'nota_n': t.get('nota_n') or 1,
            'estado': str(t.get('estado') or ''), 'sentido': str(t.get('sentido') or ''), 'creado': str(t.get('creado') or ''),
            'actualizado': str(t.get('actualizado') or ''), 'con_datos': True, 'trabajo': t,
            'defectos': [{'numero': i + 1, 'codigo': str(d.get('cod') or ''), 'titulo': str(d.get('titulo') or ''), 'caracter': str(d.get('caracter') or '')}
                         for i, d in enumerate(t.get('defectos') or []) if isinstance(d, dict)]}


def _de_fichero(p):
    base = {'origen': str(p), 'cuenta': '', 'nombre': '', 'con_datos': False, 'actualizado': '', 'modelos': [], 'asuntos': []}
    if p.suffix.lower() == '.zip':
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if n.endswith('.calificar.json') or n.endswith('/trabajo.calificar.json'):
                    try:
                        base['asuntos'].append(_de_trabajo(json.loads(z.read(n).decode('utf-8-sig'))))
                    except ValueError:
                        continue
        base['con_datos'] = bool(base['asuntos'])
        return base
    d = _json(p)
    if isinstance(d, dict) and isinstance(d.get('propios'), dict):           # «Mis modelos.json»
        for k, l in d['propios'].items():
            for x in l if isinstance(l, list) else []:
                if isinstance(x, dict) and x.get('id'):
                    base['modelos'].append({'id': str(x['id']), 'clase': k, 'clase_nombre': k, 'titulo': str(x.get('titulo') or ''),
                                            'texto': str(x.get('texto') or '')})
        return base
    if isinstance(d, dict) and d.get('formato') == 'intrareg.modelos':
        base['modelos'] = d.get('modelos') or []
        return base
    if isinstance(d, dict) and d.get('formato') == 'intrareg.en_tramite':
        base['asuntos'] = [d]
        base['con_datos'] = bool(d.get('con_datos'))
        return base
    ts = d if isinstance(d, list) else [d]
    if all(isinstance(t, dict) and t.get('id') and isinstance(t.get('estado'), str) for t in ts):  # trabajos exportados
        base['asuntos'] = [_de_trabajo(t) for t in ts]
        base['con_datos'] = True
        return base
    raise Error(f'{p.name} no es un fichero de Intrareg (ni modelos ni trabajos).')


# ------------------------------------------------------------------ salida (sin datos personales)
def _numero(a):
    n = f"Asiento {a['asiento']}" + (f"/{a['anio']}" if a.get('anio') else '') if a.get('asiento') else (f"Entrada {a['entrada']}" if a.get('entrada') else 'Sin número')
    return n + (f" (nota {a['nota_n']})" if (a.get('nota_n') or 1) > 1 else '')


def _defectos(a):
    return [f"  {d.get('numero')}. {d.get('codigo') or '(sin código)'} · {d.get('titulo') or ''}" + (f" ({d['caracter']})" if d.get('caracter') else '')
            for d in a.get('defectos') or []]


def resumen(r):
    ls = [f"# Intrareg en el equipo: {r['origen']}" + (f" · cuenta {r['cuenta']}" if r['cuenta'] else '')
          + (f" · al día a {r['actualizado'][:16].replace('T', ' ')}" if r.get('actualizado') else '')]
    ls.append(f"Modelos propios: {len(r['modelos'])}")
    ls += [f"- {m.get('id')} · {m.get('clase_nombre') or m.get('clase')} · {m.get('titulo') or '(sin título)'}" for m in r['modelos']]
    ls.append(f"Asuntos en trámite: {len(r['asuntos'])}" + (' (guardados con los datos: no los imprima; para la nota, --nota)' if r['con_datos'] else ''))
    for a in r['asuntos']:
        ls.append(f"- {a.get('id')} · {_numero(a)} · {a.get('estado') or ''} · {len(a.get('defectos') or [])} defecto(s)")
    return '\n'.join(ls)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Lee en este equipo los modelos y los asuntos en trámite que guarda Intrareg.')
    ap.add_argument('ruta')
    ap.add_argument('--cuenta')
    ap.add_argument('--modelos', action='store_true')
    ap.add_argument('--modelo')
    ap.add_argument('--en-tramite', action='store_true')
    ap.add_argument('--asunto')
    ap.add_argument('--nota')
    ap.add_argument('--salida')
    x = ap.parse_args(argv)
    try:
        r = cargar(x.ruta, x.cuenta)
        if x.modelo:
            m = next((m for m in r['modelos'] if str(m.get('id')) == x.modelo), None)
            if not m:
                raise Error(f'No hay ningún modelo con el id {x.modelo} (véalos con --modelos).')
            print(f"# {m.get('clase_nombre') or m.get('clase')} · {m.get('titulo') or ''}\n\n{m.get('texto') or ''}")
        elif x.modelos:
            print('\n'.join(f"- {m.get('id')} · {m.get('clase_nombre') or m.get('clase')} · {m.get('titulo') or '(sin título)'}" for m in r['modelos'])
                  or 'No hay modelos propios.')
        elif x.asunto or x.nota:
            i = x.asunto or x.nota
            a = next((a for a in r['asuntos'] if str(a.get('id')) == i), None)
            if not a:
                raise Error(f'No hay ningún asunto con el id {i} (véalos con --en-tramite).')
            if x.nota:
                nota = a.get('nota') or ''
                if not nota:
                    raise Error('Ese asunto no tiene la nota en la carpeta: en Intrareg, active «Con los datos del asiento y la nota».')
                if not x.salida:
                    raise Error('La nota lleva datos personales: indique --salida <fichero.txt> (no se imprime).')
                Path(x.salida).write_text(nota, encoding='utf-8')
                print(f'Nota escrita en {x.salida} (lleva datos personales: anonimícela antes de leerla).')
            else:
                print('\n'.join([f"# {_numero(a)} · {a.get('estado') or ''}" + (f" · {a['sentido']}" if a.get('sentido') else ''),
                                 f"id {a.get('id')} · creado {a.get('creado') or '—'} · actualizado {a.get('actualizado') or '—'}",
                                 'Defectos:'] + (_defectos(a) or ['  (ninguno)'])))
        elif x.en_tramite:
            print('\n'.join(f"- {a.get('id')} · {_numero(a)} · {a.get('estado') or ''}\n" + '\n'.join(_defectos(a)) for a in r['asuntos'])
                  or 'No hay asuntos en trámite.')
        else:
            print(resumen(r))
    except Error as e:
        print(f'No se ha podido leer: {e}')
        return 1
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
