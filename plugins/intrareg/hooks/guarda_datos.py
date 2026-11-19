"""Guarda de los datos personales del plugin de Intrareg (hook PreToolUse de Claude Code y Cowork).

Lo que hace, sin depender de que Claude siga las instrucciones de las skills:
- Las claves del anonimizador (<documento>.claves.json guardan los datos reales): ninguna herramienta las lee, las busca ni las
  copia. La única orden que puede nombrarlas es la del propio anonimizador al reponer los datos (anonimizar_documento.py --reponer),
  que las usa en el equipo sin enseñarlas.
- Un documento de oficina o PDF (escritura, mandamiento, recurso…) que no tiene al lado su «.anonimizado.txt»: antes de leerlo con
  Read se pregunta al registrador (sugiere /intrareg:anonimizar). Si dice que sí (una resolución publicada, un modelo sin datos), se
  lee; la decisión es suya.

Solo biblioteca estándar. Lee de la entrada estándar el JSON del hook y, si tiene algo que decir, escribe en la salida estándar la
decisión (deny / ask) con su motivo. Ante cualquier fallo propio no bloquea nada: no puede dejar al registrador sin herramientas."""
import json
import re
import sys
from pathlib import Path

CLAVES = re.compile(r'\.claves\.json\b', re.I)
REPONER = re.compile(r'anonimizar_documento\.py["\']?\s.*--reponer', re.S)
DOCUMENTOS = ('.pdf', '.docx', '.doc', '.odt', '.rtf')

MOTIVO_CLAVES = ('Ese fichero guarda los datos reales que quitó el anonimizador de Intrareg y no se lee, no se busca ni se copia. '
                 'Para devolver los datos a la nota, la orden de la skill «anonimizar» con --reponer, sin abrirlo.')
MOTIVO_DOCUMENTO = ('Este documento no tiene al lado su versión anonimizada ({nombre}.anonimizado.txt). Lo recomendable es '
                    '/intrareg:anonimizar «{ruta}» y trabajar con el texto anonimizado. ¿Lo leo tal cual? (Sí, si no lleva datos '
                    'personales: una resolución publicada, un modelo en blanco…)')


def decidir(entrada):
    """(decisión, motivo) o None para dejar seguir. decisión: «deny» o «ask»."""
    herr = str(entrada.get('tool_name') or '')
    ti = entrada.get('tool_input') or {}
    if not isinstance(ti, dict):
        return None
    textos = [str(v) for k, v in ti.items() if k in ('file_path', 'path', 'pattern', 'glob', 'command', 'notebook_path')]
    if herr == 'Bash':
        orden = str(ti.get('command') or '')
        if CLAVES.search(orden) and not REPONER.search(orden):
            return 'deny', MOTIVO_CLAVES
        return None
    if any(CLAVES.search(t) for t in textos):
        return 'deny', MOTIVO_CLAVES
    if herr == 'Read':
        ruta = str(ti.get('file_path') or '')
        p = Path(ruta)
        if p.suffix.lower() in DOCUMENTOS:
            hermano = p.with_name(p.stem + '.anonimizado.txt')
            try:
                hay = hermano.is_file()
            except OSError:
                hay = False
            if not hay:
                return 'ask', MOTIVO_DOCUMENTO.format(nombre=p.stem, ruta=ruta)
    return None


def main():
    try:
        entrada = json.loads(sys.stdin.read() or '{}')
        d = decidir(entrada if isinstance(entrada, dict) else {})
    except Exception:  # noqa: BLE001  (la guarda nunca bloquea por un fallo suyo)
        return 0
    if d:
        decision, motivo = d
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': decision,
                                                 'permissionDecisionReason': motivo}}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
