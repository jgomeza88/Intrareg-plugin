# -*- coding: utf-8 -*-
"""Anonimización del texto de los PDF antes de guardarlos o enviarlos a la IA.

Sustituye de forma consistente (la misma persona recibe siempre la misma etiqueta):
- DNI / NIE / NIF / CIF, pasaportes con formato habitual → [NIF-1], [NIF-2]…
- nombres de los comparecientes, representados y titulares registrales que reconoce el lector (y cualquier otro
  nombre precedido de DON/DOÑA) → [PERSONA-1], [PERSONA-2]…; las entidades reconocidas → [ENTIDAD-1]…
- correos electrónicos, teléfonos, IBAN / cuentas bancarias, tarjetas
- domicilios de las personas («con domicilio en …», «vecino de …, calle …») → [DOMICILIO]
- referencia catastral → [REFCAT-n]; IDUFIR/CRU → [IDUFIR-n]; número de finca registral → [FINCA-n]; matrículas → [MATRICULA-n]; fecha de nacimiento → [NACIMIENTO-n];
  personas de la filiación («hijo de…»), de los linderos, «a favor de», «propiedad de», «titular…», los bloques de nombres en
  mayúsculas de la comparecencia y los nombres que reconoce el diccionario (static/lib/nombres_es.json) → [PERSONA-n]
El municipio, el tomo, libro y folio, el Notario, las fechas (salvo la de nacimiento), los precios y las cláusulas se conservan (hacen falta
para calificar). Es seudonimización, no anonimización: las etiquetas se reponen en el navegador.
El resultado se guarda como PDF de solo texto (sin la maquetación original) con `escribir_pdf`."""
import re
import zlib

_DNI = r'\b(?:\d{2}\.?\d{3}\.?\d{3}\s?-?\s?[A-Za-z]|\d\.?\d{3}\.?\d{3}\s?-?\s?[A-Z])\b'   # también los DNI de 7 cifras
_NIE = r'\b[XYZxyz]\s?-?\s?\d{7}\s?-?\s?[A-Za-z]\b'
_CIF = r'\b[ABCDEFGHJKLMNPQRSUVWabcdefghjklmnpqrsuvw]\s?-?\s?\d{7}\s?-?\s?[0-9A-Ja-j]\b'
# el número del pasaporte lleva al menos una cifra («pasaporte vigente» no es un número)
_PASAPORTE = r'\b(?:pasaporte|passport)\s+(?:n(?:\.º|º|úmero)?\s*)?((?=[A-Z]*\d)[A-Z0-9]{6,12})\b'
_ID_OCR = r'(?:D\.?\s?N\.?\s?I\.?|N\.?\s?I\.?\s?[EF]\.?|documento\s+nacional\s+de\s+identidad|carta\s+de\s+identidad|documento\s+de\s+identidad)[^\w\[]{0,10}(?:n[úu]mero|n[úu]m\.?|n\.?º|nº)?[^\w\[]{0,10}([A-Z]?\s?\d{1,2}\.\d{3}\.\d{3}\s?-?\s?[A-Za-z]?|[A-Z]?\s?\d{6,9}\s?-?\s?[A-Za-z]?)(?![\w])'
_EMAIL = r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+'
# el correo escrito «juan.perez (arroba) gmail.com» para que no lo lean los robots
_EMAIL_OFUSCADO = (r'(?i)[\w.+-]+\s*(?:\(arroba\)|\[arroba\]|\(at\)|\[at\]|\s(?:arroba|at)\s)\s*[\w-]+'
                   r'(?:\s*(?:\.|\(punto\)|\[punto\]|\s(?:punto|dot)\s)\s*[\w-]+)+')
# móviles «655 123 456», fijos «91 555 55 55», «+34 600123456»; no cantidades («1.234.567.890», «600.000», «123456789,50»)
_TEL = r'(?<![\d/])(?<![\d][.,])(?:\+34\s?)?(?:[6789]\d{2}[\s-]?\d{3}[\s-]?\d{3}|9\d[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}|[6789]\d{8})(?![\d/])(?![.,]\d)'
# teléfonos extranjeros («+33 6 12 34 56 78») y los españoles por pares con guiones o puntos («655-12-34-56»)
_TEL_INT = r'(?<![\w+])\+(?!34)\d{1,3}(?:[\s.-]?\d){6,12}(?!\d)'
_TEL_PARES = r'(?<![\d/])(?:\+34[\s.-]?)?[6789]\d{2}[\s.-]\d{2}[\s.-]\d{2}[\s.-]\d{2}(?![\d/])'
_IBAN = r'\b[A-Z]{2}\d{2}(?:[\s-]?[0-9A-Z]{4}){4,7}\b'
# código cuenta cliente de 20 cifras (entidad, oficina, control y cuenta: «2100 0418 45 0200051332»)
_CCC = r'(?<![\d])\d{4}[\s-]?\d{4}[\s-]?\d{2}[\s-]?\d{10}(?!\d)'
# número de afiliación a la Seguridad Social («28/12345678/90») y, tras su nombre, también sin separadores
_NAF = r'(?<![\d/])\d{2}[/-]\d{7,8}[/-]\d{2}(?![\d/])'
_NAF_CTX = r'(?i:seguridad\s+social|n\.?\s?a\.?\s?f\.?|afiliaci[oó]n)[^\d\[\n]{0,40}(\d{10,12})(?!\d)'
_TARJETA = r'\b(?:\d{4}[\s-]){3}\d{4}\b'
# también «señor/señora» sin abreviar, los tratamientos catalanes y extranjeros y la antefirma («Fdo.: …»)
_TRAT_OTROS = (r'|[Ss]eñor(?:es|as?)?|SEÑOR(?:ES|AS?)?|[Ss]enyor(?:a|es)?|SENYOR(?:A|ES)?|Mr\.?|Mrs\.?|Ms\.?|Miss|Sir|Mme\.?|Herr|Frau'
               r'|Fdo\.?\s*:|FDO\.?\s*:|Firmado\s*:|FIRMADO\s*:)')
_TRAT = r'(?<![\w])(?:DON|DOÑA|Don|Doña|don|doña|D\.ª|Dª|D\.a\.?|Dña\.?|Sr\.|Sra\.|Sres\.|D\.' + _TRAT_OTROS
_TRAT_1 = r'(?<![\w])(?:DON|DOÑA|Don|Doña|don|doña|D\.ª|Dª|Dña\.?|Sr\.|Sra\.' + _TRAT_OTROS     # admiten un nombre de una sola palabra («don Pedro»); «D.» no («R.D. Legislativo»)
# palabra de nombre propio (inicial mayúscula); nunca un tratamiento, una sigla de identificador, un cargo o una palabra común
# que suela seguir al nombre sin coma («Don Pedro López Vende», «DOÑA ANA RUIZ MAYOR DE EDAD»)
_NO_NOMBRE = (r'(?i:DON|DOÑA|NIF|DNI|NIE|CIF|Notari[oa]|Registrador[a]?|Letrad[oa]|Abogad[oa]|Procurador[a]?|Secretari[oa]|Juez|Magistrad[oa]|'
              r'Alcalde|Alcaldesa|Presidente|Presidenta|Administrador[a]?|Apoderad[oa]|Consejer[oa]|Director[a]?|Gerente|Vende|Compra|Dona|'
              r'Comparecen?|Comparecientes?|Manifiestan?|Otorgan?|Exponen?|Declaran?|Intervienen?|Act[úu]an?|Aceptan?|Adquieren?|Transmiten?|Hipoteca|Constituyen?|'
              r'Mayor|Mayores|Casad[oa]s?|Solter[oa]s?|Viud[oa]s?|Divorciad[oa]s?|Vecin[oa]s?|Titular|Propietari[oa]|Y|E|O|U|A|El|La|Los|Las|En|Con|Por|Para|Que|Quien|Quienes|Como|Su|Sus)')
# «(?![\w'’])» y no «\b»: en «O'Connor» la O no es la conjunción
_W = rf"(?!{_NO_NOMBRE}(?![\w'’]))[A-ZÁÉÍÓÚÑÜ][A-Za-zÁÉÍÓÚÑÜáéíóúñüàèòïç'’\-]+"
_WM = rf"(?!{_NO_NOMBRE}(?![\w'’]))[A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜÀÈÒÏÇ'’\-]+"
# la «i» une los apellidos catalanes («Puigdemont i Casamajó»)
_NOMBRE = rf"({_W}(?:[ \-]+(?:(?:de|del|de la|de los|de las|y|i|DE|DEL|DE LA|DE LOS|DE LAS|Y|I)[ \-]+)?{_W}){{1,8}})"
_NOMBRE_MAYUS = rf"({_WM}(?:[ \-]+(?:(?:DE|DEL|DE LA|DE LOS|DE LAS|Y)[ \-]+)?{_WM}){{1,8}}(?:,\s*{_WM}(?:[ \-]+{_WM})?)?)(?=\s*(?:[,.;:)\]»”\"\n]|$|\d|[a-záéíóúñü]|(?:NIF|DNI|CIF|NIE)\b))"
# «vecino de Madrid, con domicilio en …»: la vecindad es el municipio (se conserva) y lo que se tapa es el domicilio
_DOMICILIO = (r'(?i)(con\s+domic\s*ilio\s+(?:a\s+(?:estos\s+)?efectos\s+(?:de\s+notificaciones\s+)?)?en|vecin[oa]s?\s+de(?![^,;\n]{2,40},\s*(?:y\s+)?(?:con\s+)?domicil)|domiciliad[oa]s?\s+en|y\s+domicilio\s+en|domicilio\s*:)'
              r'(?!\s+(?:\[[A-Z]|⟦))'   # si detrás ya hay una etiqueta del navegador ([DOMICILIO-1]) o su resguardo, no se toca
              r'\s+[^\n;”"]{5,160}?(?=\.(?:\s+(?-i:[A-ZÁÉÍÓÚÑ¿¡«“"])|\s*$)|[;”"\n]|,?\s+(?:y\s+)?(?:con\s+)?(?:D\.?N\.?I|N\.?I\.?F|N\.?I\.?E|C\.?I\.?F|pasaporte|provist[oa]s?|titular(?:es)?|de\s+nacionalidad|mayor(?:es)?\s+de\s+edad|inscrita|constituida|casad[oa]s?|solter[oa]s?|viud[oa]s?|divorciad[oa]s?|representad[oa]s?|actuando|en\s+nombre|(?-i:D\.\s|Don|Doña|DON|DOÑA|Dña\.))\b)')
# la dirección con su número, piso y puerta y, si va detrás, el código postal («Avda. de la Constitución, 14, 28001»), aunque no la
# anuncie «con domicilio en»; «plaza de garaje» es un elemento de la finca, no una dirección
_VIA = (r'(?:calle|c/|avda\.?|avenida|av\.|plaza|plza\.?|pza\.?|paseo|pso\.?|camino|carrer|rúa|rua|ronda|traves[ií]a|glorieta|carretera|'
        r'ctra\.?|urbanizaci[oó]n|urb\.?|pasaje|callej[oó]n|cuesta|alameda|rambla)')
_PISO = (r'(?:,?\s*(?:(?:piso|planta|escalera|esc\.|portal|bloque|puerta|pta\.)\s*)?(?:\d{1,2}\s*[º°ª]\.?|\d{1,2}\s*(?-i:[A-H])\b|'
         r'bajo|bj\.|[áa]tico|entresuelo|entlo\.|principal|pral\.|(?-i:[A-H])\b|izda\.?|izq(?:uierda|da)?\.?|dcha\.?|derecha|centro)){0,4}')
_DIRECCION_NUM = (rf'(?i)\b{_VIA}(?:\s+|(?<=[/.])\s*)(?!de\s+(?:garaje|aparcamiento))(?!(?:n[º°o]\.?|n[uú]m(?:ero)?\.?)\s*\d)(?!\[[A-Z]|⟦)[^\n;,\d“”"\[]{{2,60}}?,?\s*'
                  rf'(?:n[º°o]\.?\s*|n[uú]m(?:ero)?\.?\s*)?(?:\d{{1,4}}(?![\d.,]?\d|\s*(?:%|por\s+ciento|euros|€|m2|m²|metros))(?:\s?(?-i:[A-Z])\b)?|s/n){_PISO}(?:,?\s*\d{{5}}(?!\d))?')
# también calles, plazas, C.P. y similares (datos por los que se identifica a las personas); «número» o «nº» solos no anuncian una
# dirección: «finca registral número 12345», «D.N.I. número…»
_DIRECCION = (r'(?i)\b((?:calle|c/|avda\.?|avenida|plaza|plza\.?|paseo|pso\.?|camino|carrer|rúa|rua|urbanizaci[oó]n|urb\.?|'
              r'polígono|poligono|bloque|portal)\s+(?!de\s+(?:garaje|aparcamiento))(?!\[[A-Z]|⟦)[^\n;”"]{3,120}?)'   # sin tocar etiquetas
              r'(?=\.(?:\s|$)|[;”"\n]|,?\s+(?:con\s+)?(?:D\.?N\.?I|N\.?I\.?F|N\.?I\.?E|provist|titular|de\s+nacionalidad|mayor|casad|solter|viud|divorciad|c\.?p\.?|c[oó]digo\s+postal)\b)')
_CP = r'(?i)\b(?:C\.?\s*P\.?|código\s+postal)\s*:?\s*\d{5}\b'
# el código postal suelto, junto al municipio («Madrid 28001», «28001 Madrid»); lo que decide si lo es se mira en _cp_suelto()
_CP_SUELTO = r'(?<![\w/.,\[-])((?:0[1-9]|[1-4]\d|5[0-2])\d{3})(?![\w/\-%]|[.,]\d)'
_NO_ANTES_CP = {'finca', 'fincas', 'tomo', 'libro', 'folio', 'protocolo', 'numero', 'inscripcion', 'asiento', 'ley', 'decreto', 'articulo',
                'expediente', 'entrada', 'diario', 'ano', 'euros', 'euro', 'pesetas', 'pagina', 'boe', 'resolucion', 'sentencia', 'nota',
                'referencia', 'parcela', 'poligono', 'precio', 'importe', 'total', 'cantidad', 'capital', 'valor', 'suma', 'cuota', 'recurso',
                'procedimiento', 'autos', 'orden', 'circular', 'instruccion', 'consulta', 'codigo', 'cuenta', 'lote', 'registro', 'nif', 'cif'}
# la razón social de una sociedad mercantil («Construcciones Ruiz, S.L.»): con ella se llega a sus socios y administradores
_RAZON = (r"(?<![\w\[])((?:[A-ZÁÉÍÓÚÑÜ][\w&'’.\-]*)(?:[ ]+(?:(?:de|del|de la|de los|y|e|&|DE|DEL|DE LA|DE LOS|Y)[ ]+)?[A-ZÁÉÍÓÚÑÜ0-9][\w&'’.\-]*){0,5})"
          r",?[ ]+(?=(?:S\.\s?[AL]\.(?:\s?U\.)?|S\.\s?L\.\s?P\.|S\.\s?Coop\.?|S\.\s?C\.|C\.\s?B\.|SLU|SAU|SLP|SL|SA)(?![\w]))")
_RAZON_FUERA = {'la', 'el', 'los', 'las', 'en', 'con', 'por', 'de', 'del', 'y', 'a', 'que', 'mercantil', 'entidad', 'sociedad', 'compania',
                'empresa', 'vende', 'compra', 'representacion', 'nombre', 'denominada', 'denominacion'}
# los bancos y las grandes empresas se conservan (se ve quién es el acreedor, el suministrador…)
_RAZON_PUBLICA = {'banco', 'banca', 'bankia', 'caixabank', 'caja', 'caixa', 'santander', 'sabadell', 'bbva', 'unicaja', 'ibercaja', 'kutxabank',
                  'bankinter', 'abanca', 'cajamar', 'sareb', 'openbank', 'liberbank', 'cajasur', 'deutsche', 'popular', 'iberdrola', 'endesa',
                  'naturgy', 'telefonica', 'adif', 'renfe', 'correos', 'repsol', 'cepsa', 'mapfre', 'targobank'}
# matrícula provincial antigua sin la palabra «matrícula» («M-1234-AB»): siglas de provincia y guiones obligatorios
_MATRICULA_ANT = (r'(?<![\w\-])(?:A|AB|AL|AV|B|BA|BI|BU|C|CA|CC|CE|CO|CR|CS|CU|GC|GE|GI|GR|GU|H|HU|IB|J|L|LE|LO|LU|M|MA|ML|MU|NA|O|OR|OU|'
                  r'P|PM|PO|S|SA|SE|SG|SO|SS|T|TE|TF|TO|V|VA|VI|Z|ZA)-\d{4}-[A-Z]{1,2}(?![\w\-])')

# Con la referencia catastral, el IDUFIR/CRU o una matrícula se llega al titular (Catastro, Registro, DGT): son datos
# personales y se sustituyen por etiquetas que el navegador repone al volver la respuesta.
# Referencia catastral de 20 caracteres: urbana (7 cifras, 2 letras, 4 cifras, letra, 4 cifras, 2 letras) y rústica (provincia y municipio,
# sector, polígono, parcela, 4 cifras y 2 letras); con espacios o sin ellos, y también con un espacio, punto o guion suelto entre
# cualquiera de sus grupos («28 079 A 001 00001 0000 XY», «1234567-VK-4713-S»): mal escrita sigue llevando al titular.
_RC = r'[ \u00a0.\-]?'
_REFCAT = (rf'(?<![A-Za-z0-9])(?:\d{{7}}{_RC}[A-Z]{{2}}{_RC}\d{{4}}{_RC}[A-Z]{_RC}\d{{4}}{_RC}[A-Z]{{2}}'
           rf'|\d{{2}}{_RC}\d{{3}}{_RC}[A-Z]{_RC}\d{{3}}{_RC}\d{{5}}{_RC}\d{{4}}{_RC}[A-Z]{{2}})(?![A-Za-z0-9])')
# la de 14 caracteres (solo la parcela), solo tras «referencia catastral»
_REFCAT_CTX = (r'(?i:referencias?\s+catastral(?:es)?|ref\.?\s*catastral|ref\.?\s*cat\.)[^0-9\[\n]{0,30}?'
               rf'((?-i:\d{{7}}{_RC}[A-Z]{{2}}{_RC}\d{{4}}{_RC}[A-Z]|\d{{2}}{_RC}\d{{3}}{_RC}[A-Z]{_RC}\d{{3}}{_RC}\d{{5}}))(?![A-Za-z0-9])')
# IDUFIR / CRU: 14 cifras tras «IDUFIR», «CRU» o «código registral (único)»
_IDUFIR = (r'(?:\b(?:IDUFIR|Idufir|idufir|CRU)\b|C\.R\.U\.?|I\.D\.U\.F\.I\.R\.?|(?i:c[óo]digo\s+registral(?:\s+[úu]nico)?))'
           r'[^0-9\[\n]{0,30}?(\d{14})(?!\d)')
# Número de finca registral: con él y el Registro se llega al titular. Tras «finca (registral) (número|nº)», «FINCA DE <municipio> Nº»,
# «la registral nº» o «nº de finca», y la lista tras «fincas» («fincas 12, 13 y 14»); no una superficie, un importe ni un porcentaje
# («finca de 500 metros»). Igual que _FINCA_UNA y _FINCA_VARIAS de fuente_js/01_base.js.
_FINCA_NUM = r'(?:\d{1,3}(?:\.\d{3})+|\d{1,7})(?![\d.,]?\d|\s*(?:%|por\s+ciento|m2|m²|metros|hect|[áa]reas|euros|€|ha\b))'
_FINCA_NO = r'(?:n[úu]mero|n[úu]m\.|n\.?\s?[º°o]\.?)'
_FINCA_UNA = (r'(?i)((?<![A-Za-zÁÉÍÓÚÜÑáéíóúüñ])(?:finca(?:\s+(?:registral|' + _FINCA_NO + r'))*\s*:?\s*|finca\s+de\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ ]{2,40}?\s+'
              + _FINCA_NO + r'\s*:?\s*|registral\s+' + _FINCA_NO + r'\s*:?\s*|' + _FINCA_NO + r'\s+de\s+finca(?:\s+registral)?\s*:?\s*))(' + _FINCA_NUM + ')')
_FINCA_VARIAS = (r'(?i)((?<![A-Za-zÁÉÍÓÚÜÑáéíóúüñ])fincas(?:\s+(?:registrales|' + _FINCA_NO + r'|n[úu]meros))*\s*:?\s*)(' + _FINCA_NUM
                 + r'(?:\s*(?:,|\by\b|\be\b)\s*' + _FINCA_NUM + r')*)')
# matrículas: la actual (4 cifras y 3 consonantes) y, tras «matrícula», también la provincial antigua («M-1234-AB»)
_MATRICULA = r'(?<![\w\-])\d{4}[\s-]?[BCDFGHJKLMNPRSTVWXYZ]{3}(?![\w\-])'
_MATRICULA_CTX = r'(?i:matr[íi]cula)[^\w\[\n]{0,15}(?:(?i:n[úu]mero|n\.?º)\s*)?((?-i:[A-Z]{1,2}[\s-]?\d{4}[\s-]?[A-Z]{1,3}))(?![\w])'
# fecha de nacimiento («nacido el 12 de mayo de 1970», «nacida en Soria el día doce de mayo de mil novecientos setenta»)
_NUM_PAL = (r'(?:y|un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|diecis[ée]is|diecisiete|'
            r'dieciocho|diecinueve|veinte|veinti[a-záéíóúñ]+|treinta|cuarenta|cincuenta|sesenta|setenta|ochenta|noventa|cien|ciento|'
            r'doscientos|trescientos|cuatrocientos|quinientos|seiscientos|setecientos|ochocientos|novecientos|mil)')
_MES = r'(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|se?tiembre|octubre|noviembre|diciembre)'
_FECHA = (rf'(?:\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}|(?:\d{{1,2}}|primero|{_NUM_PAL}(?:\s+y\s+{_NUM_PAL})?)\s+de\s+{_MES}\s+'
          rf'(?:de|del)\s+(?:\d{{4}}|mil(?:\s+{_NUM_PAL})*))')
_NACIMIENTO = (rf'(?i)(?:nacid[oa]s?\s+(?:en\s+[^,;\n\d]{{2,40}}?\s+)?(?:el\s+)?(?:d[ií]a\s+)?|fecha\s+de\s+nacimiento\s*:?\s*(?:el\s+)?|'
               rf'nacimiento\s*:\s*)({_FECHA})')
# personas tras «hijo de», «a favor de», «propiedad de», «titular…» y en los linderos («linda… con finca de X», «con la de Y»)
_PERS_PAL = rf"(?:{_W})"
_PERS_SEQ = rf"{_PERS_PAL}(?:[ ]+(?:(?:de|del|de la|de los|de las|DE|DEL|DE LA|DE LOS|DE LAS)[ ]+)?{_PERS_PAL}){{0,6}}"
_PERS_TRAT = r'(?:(?:don|doña|DON|DOÑA|Don|Doña|D\.ª|Dª|Dña\.?|D\.)\s+)?'
_FILIACION = rf'(?<![\w])(?i:hij[oa]s?\s+(?:leg[íi]tim[oa]s?\s+)?de)\s+{_PERS_TRAT}({_PERS_SEQ}(?:\s*(?:,|\by\b|\be\b)\s*(?:(?i:de)\s+)?{_PERS_TRAT}{_PERS_SEQ})*)'
_A_FAVOR = (rf'(?<![\w])(?i:a\s+favor\s+de|propiedad\s+de|a\s+nombre\s+de|pertenecen?\s+a|adquirid[oa]s?\s+por|'
            rf'titular(?:es)?(?:\s+registral(?:es)?)?(?:\s+(?:es|son|actual(?:es)?))?\s*:?)\s+{_PERS_TRAT}'
            rf'({_PERS_SEQ}(?:\s*(?:,|\by\b|\be\b)\s*{_PERS_TRAT}{_PERS_SEQ})*)')
_LINDA = r'(?i)\blind(?:a|an|ando|ero|eros)\b[^\n]{0,700}?(?=\.\s*(?:\n|(?-i:[A-ZÁÉÍÓÚÑ]{2,}|Inscrit|Referencia|Título|Cargas|Libre|Le\s+pertenece))|\n\s*\n|$)'
_LINDA_CON = (rf'(?<![\w])(con\s+(?:(?:la|una|las)\s+)?(?:(?:finca|fincas|parcela|casa|solar|vivienda|tierras?|terrenos?|propiedad|edificio|nave|local|piso|huerta|era|corral|resto)'
              rf'(?:\s+(?:propiedad|registral|catastral|matriz))?\s+(?:de\s+|propiedad\s+de\s+)|(?:la|las|el|los)\s+de\s+|propiedad\s+de\s+|herederos\s+de\s+)?)'
              rf'{_PERS_TRAT}({_PERS_SEQ})')
# lo que no es una persona aunque empiece por mayúscula (linderos, organismos, entidades)
_NO_PERSONA = {'banco', 'caja', 'caixa', 'ayuntamiento', 'estado', 'hacienda', 'comunidad', 'junta', 'generalitat', 'diputación', 'diputacion',
               'consejería', 'consejeria', 'ministerio', 'tesorería', 'tesoreria', 'agencia', 'seguridad', 'sociedad', 'fundación', 'fundacion',
               'asociación', 'asociacion', 'iglesia', 'obispado', 'diócesis', 'diocesis', 'cooperativa', 'entidad', 'instituto', 'registro',
               'notaría', 'notaria', 'juzgado', 'tribunal', 'administración', 'administracion', 'dirección', 'direccion', 'gobierno', 'cabildo',
               'consell', 'xunta', 'mancomunidad', 'confederación', 'confederacion', 'calle', 'camino', 'carretera', 'río', 'rio', 'arroyo',
               'acequia', 'barranco', 'senda', 'vereda', 'cañada', 'vía', 'via', 'monte', 'término', 'termino', 'zona', 'resto', 'elementos',
               'finca', 'fincas', 'parcela', 'solar', 'vivienda', 'local', 'piso', 'patio', 'plaza', 'avenida', 'paseo', 'terreno', 'terrenos',
               'rambla', 'norte', 'sur', 'este', 'oeste', 'poniente', 'levante', 'mediodía', 'mediodia', 'saliente', 'dominio', 'vial', 'viales',
               'zonas', 'portal', 'escalera', 'rellano', 'hueco', 'hermanos', 'herederos', 'polígono', 'poligono', 'sector', 'unidad', 'urbanización',
               'urbanizacion', 'edificio', 'nave', 'casa', 'huerta', 'regadío', 'regadio', 'secano', 'paraje', 'sitio', 'partida', 'pago', 'lugar',
               'sareb', 'bbva', 'unicaja', 'ibercaja', 'kutxabank', 'bankinter', 'abanca', 'cajamar', 'adif', 'renfe', 'iberdrola', 'endesa',
               'naturgy', 'telefónica', 'telefonica', 'mercantil', 'empresa', 'compañía', 'compania', 'promociones', 'construcciones',
               'inversiones', 'inmobiliaria', 'gestión', 'gestion', 'servicios', 'patrimonio', 'consorcio', 'parque', 'polideportivo',
               'colegio', 'hospital', 'cementerio', 'san', 'santa', 'santo', 'nuestra', 'virgen', 'ilustre', 'documento',
               'numero', 'número', 'escritura', 'compraventa', 'herencia', 'hipoteca', 'nota', 'simple', 'protocolo', 'madrid', 'españa'}
_ES_ENTIDAD = r'^\s*,?\s*(?:S\.?\s?[AL]\.?(?:U\.?)?|S\.?\s?L\.?\s?P\.?|S\.?\s?C\.?|C\.?\s?B\.?|S\.?\s?A\.?\s?T\.?|sociedad)\b'
# la comparecencia: de «COMPARECE(N)» al «INTERVIENEN» / «EXPONEN»
_COMPARECENCIA = r'(?s)\b(?:COMPARECEN?|Comparecen?)\b.{0,6000}?(?=\b(?:INTERVIENEN?|Intervienen?|INTERVENCI[ÓO]N|EXPONEN?|Exponen?|OTORGAN|Y\s+DICEN|DICEN)\b|$)'
_MAYUS_SEQ = rf"{_WM}(?:[ ]+(?:(?:DE|DEL|DE LA|DE LOS|DE LAS)[ ]+)?{_WM}){{1,6}}"
_NOTARIO_DESPUES = r'^\s*,?\s*(?:(?i:notari[oa]|registrador[a]?|abogad[oa]|letrad[oa]))'
_NOTARIO_ANTES = (r'(?i)(?:ante\s+m[íi],?|notari[oa]\s+(?:(?:autorizante|que\s+fue\s+de\s+[^\n,]{2,40}|del?\s+[^\n,]{2,40}),?\s*)?,?\s*'
                  r'(?:don|doña|d\.ª?|dña\.?|d\.)?)\s*$')


def _diccionario():
    """El diccionario de nombres de pila y apellidos del navegador (static/lib/nombres_es.json), también aquí."""
    if _DIC.get('d') is None:
        import json
        from pathlib import Path
        _DIC['d'] = {}
        for f in (Path(__file__).resolve().parent.parent / 'static' / 'lib' / 'nombres_es.json',):
            try:
                d = json.loads(f.read_text(encoding='utf-8'))
                _DIC['d'] = {'n': set(d.get('n') or []), 'a': set(d.get('a') or []), 'c': set(d.get('comunes') or [])}
            except (OSError, ValueError):
                pass
    return _DIC['d']


_DIC = {}


def _sin_tilde(s):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn')


USAR_PRESIDIO = False          # lo fija app.leer_config() desde config.json («anonimizar_presidio»)
_PRESIDIO = {'motor': None, 'estado': ''}


def presidio_disponible():
    """'' si no está instalado; si lo está, descripción. Presidio + spaCy es_core_news_md se instalan con INSTALAR.bat (carpeta wheels_presidio)."""
    try:
        import presidio_analyzer  # noqa: F401
        import spacy
        if not spacy.util.is_package('es_core_news_md'):
            _PRESIDIO['error'] = 'Falta el modelo de español es_core_news_md (ejecute DESCARGAR PYTHON Y OCR.bat y después INSTALAR.bat).'
            return ''
        _PRESIDIO['error'] = ''
        return 'Microsoft Presidio + spaCy es_core_news_md'
    except Exception as e:
        _PRESIDIO['error'] = f'{e.__class__.__name__}: {e}'[:300]
        return ''


def _presidio_engine():
    if _PRESIDIO['motor'] is not None or _PRESIDIO['estado'] == 'error':
        return _PRESIDIO['motor']
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        prov = NlpEngineProvider(nlp_configuration={'nlp_engine_name': 'spacy', 'models': [{'lang_code': 'es', 'model_name': 'es_core_news_md'}]})
        _PRESIDIO['motor'] = AnalyzerEngine(nlp_engine=prov.create_engine(), supported_languages=['es'])
        _PRESIDIO['estado'] = 'ok'
    except Exception:
        _PRESIDIO['estado'] = 'error'
        _PRESIDIO['motor'] = None
    return _PRESIDIO['motor']


class Anonimizador:
    def __init__(self):
        self.mapa = {}          # texto original (normalizado) → etiqueta
        self.originales = {}    # etiqueta → texto original (primera aparición)
        self.contadores = {'NIF': 0, 'PERSONA': 0, 'ENTIDAD': 0, 'REFCAT': 0, 'IDUFIR': 0, 'FINCA': 0, 'MATRICULA': 0, 'NACIMIENTO': 0}
        self.sustituciones = 0

    def _etiqueta(self, clave, tipo):
        k = re.sub(r'\s+', ' ', clave.strip().lower())
        if k not in self.mapa:
            self.contadores[tipo] = self.contadores.get(tipo, 0) + 1
            self.mapa[k] = f'[{tipo}-{self.contadores[tipo]}]'
            self.originales[self.mapa[k]] = re.sub(r'\s+', ' ', clave.strip())
        return self.mapa[k]

    def _cnt_et(self, n, tipo='FINCA'):
        """El número de finca sin los puntos de los miles («4.521» y «4521», la misma etiqueta); se repone como se escribió la primera vez."""
        self.sustituciones += 1
        nuevo = n.replace('.', '').strip().lower() not in self.mapa
        e = self._etiqueta(n.replace('.', ''), tipo)
        if nuevo:
            self.originales[e] = n.strip()
        return e

    def _sub(self, patron, texto, tipo, flags=0, grupo=0):
        def repl(m):
            self.sustituciones += 1
            return m.group(0).replace(m.group(grupo), self._etiqueta(m.group(grupo), tipo)) if grupo else self._etiqueta(m.group(0), tipo)
        return re.sub(patron, repl, texto, flags=flags)

    def nombres(self, personas, tipo='PERSONA'):
        """Registra nombres conocidos (del lector: comparecientes, representados, titulares)."""
        for p in personas or []:
            if isinstance(p, dict):
                n = ' '.join(x for x in (p.get('nombre', ''), p.get('apellidos', '')) if x).strip()
                t = 'ENTIDAD' if (p.get('tipo') == 'juridica' or (n and not p.get('apellidos') and not p.get('sexo'))) else tipo
            else:
                n, t = str(p).strip(), tipo
            if len(n) >= 4:
                self._etiqueta(n, t)

    def texto(self, txt):
        txt = re.sub(_EMAIL, lambda m: self._cnt('[correo]'), txt)
        txt = re.sub(_EMAIL_OFUSCADO, lambda m: self._cnt('[correo]'), txt)
        # referencia catastral, IDUFIR/CRU, matrículas y fecha de nacimiento, antes que los DNI y los teléfonos
        txt = self._sub(_REFCAT, txt, 'REFCAT')
        txt = self._sub(_REFCAT_CTX, txt, 'REFCAT', grupo=1)
        txt = self._sub(_IDUFIR, txt, 'IDUFIR', grupo=1)
        txt = re.sub(_FINCA_UNA, lambda m: m.group(1) + self._cnt_et(m.group(2), 'FINCA'), txt)
        txt = re.sub(_FINCA_VARIAS, lambda m: m.group(1) + re.sub(r'\d{1,3}(?:\.\d{3})+|\d{1,7}', lambda n: self._cnt_et(n.group(0), 'FINCA'), m.group(2)), txt)
        txt = self._sub(_MATRICULA_CTX, txt, 'MATRICULA', grupo=1)
        txt = self._sub(_MATRICULA, txt, 'MATRICULA')
        txt = self._sub(_MATRICULA_ANT, txt, 'MATRICULA')
        txt = self._sub(_NACIMIENTO, txt, 'NACIMIENTO', grupo=1)
        txt = self._sub(_NAF_CTX, txt, 'NIF', grupo=1)
        txt = self._sub(_NAF, txt, 'NIF')
        txt = re.sub(_IBAN, lambda m: self._cnt('[cuenta bancaria]'), txt)
        txt = re.sub(_CCC, lambda m: self._cnt('[cuenta bancaria]'), txt)
        txt = re.sub(_TARJETA, lambda m: self._cnt('[tarjeta]'), txt)
        txt = re.sub(_TEL_INT, lambda m: self._cnt('[teléfono]'), txt)
        txt = re.sub(_TEL_PARES, lambda m: self._cnt('[teléfono]'), txt)
        txt = re.sub(_TEL, lambda m: self._cnt('[teléfono]'), txt)
        txt = re.sub(_DIRECCION_NUM, lambda m: self._cnt('[DOMICILIO]'), txt)
        txt = re.sub(_DOMICILIO, lambda m: self._cnt(m.group(1) + ' [DOMICILIO]'), txt)
        txt = re.sub(_DIRECCION, lambda m: self._cnt('[DOMICILIO]'), txt)
        txt = re.sub(_CP, lambda m: self._cnt('[DOMICILIO]'), txt)
        txt = re.sub(_CP_SUELTO, self._cp_suelto, txt)
        txt = self._sub(_NIE, txt, 'NIF')
        txt = self._sub(_CIF, txt, 'NIF')
        txt = self._sub(_DNI, txt, 'NIF')
        txt = self._sub(_PASAPORTE, txt, 'NIF', flags=re.I, grupo=1)
        # identificadores mal leídos por el OCR (cifras de menos o de más) tras «D.N.I. número», «N.I.E.», «pasaporte»…
        txt = self._sub(_ID_OCR, txt, 'NIF', flags=re.I, grupo=1)
        # el Notario autorizante en mayúsculas («Ante mí, FULANO DE TAL, Notario») se conserva: no es dato del interesado
        # nombres conocidos (los más largos primero, para no dejar restos)
        conocidos = [k for k, v in self.mapa.items() if v.startswith(('[PERSONA', '[ENTIDAD'))]
        for k in sorted(conocidos, key=len, reverse=True):
            palabras = [w for w in re.split(r'[\s\-]+', k) if w]
            if not palabras:
                continue
            pat = r'(?i)(?<![\w])' + r'[\s\-]*'.join(re.escape(w) for w in palabras) + r'(?![\w])'
            txt, n = re.subn(pat, self.mapa[k], txt)
            self.sustituciones += n
        # apellidos sueltos de las personas conocidas (p. ej. «los señores GOMEZA OLARRA»)
        for k in conocidos:
            if not self.mapa[k].startswith('[PERSONA'):
                continue
            palabras = [w for w in re.split(r'[\s\-]+', k) if w and w not in ('de', 'del', 'la', 'los', 'las', 'y')]
            if len(palabras) >= 3:
                ap = palabras[-2:]
                pat = r'(?i)(?<![\w])' + r'[\s\-]*'.join(re.escape(w) for w in ap) + r'(?![\w])'
                txt, n = re.subn(pat, self.mapa[k], txt)
                self.sustituciones += n
        # la razón social de las sociedades, antes que los nombres («Construcciones Ruiz, S.L.» no es una persona)
        txt = re.sub(_RAZON, self._razon, txt)
        # nombres tras tratamiento que el lector no conociera; el del Notario se conserva («ante el Notario de Madrid don …»)
        txt = self._sub_trat(_TRAT + r'\s+' + _NOMBRE, txt)
        # nombre de una sola palabra tras don/doña/Sr./Sra. («don Pedro y doña Ana», «el Sr. Gómez»)
        txt = self._sub_trat(_TRAT_1 + r'\s+(' + _W + r')(?![\w\-’\'])', txt)
        # solicitante de la nota simple y otras personas en mayúsculas sin tratamiento («solicitud formulada por FULANO»)
        txt = self._sub(r'(?i:solicitud\s+formulada\s+por|a\s+instancia\s+de|solicitante\s*:|presentante\s*:|presentad[oa]\s+por|nombre\s*[.\s]*:|titular(?:es)?\s*:|herederos\s+de|hros\.?\s+de|viuda\s+de|hijos\s+de)\s+' + _NOMBRE_MAYUS, txt, 'PERSONA', grupo=1)
        txt = self._sub(r'(?i:herederos\s+de|hros\.?\s+de|viuda\s+de|hijos\s+de|sucesores\s+de)\s+' + _NOMBRE, txt, 'PERSONA', grupo=1)
        # filiación, «a favor de», «propiedad de», «titular», linderos, la comparecencia en mayúsculas y el diccionario
        txt = self._personas(txt, _FILIACION, 1)
        txt = self._personas(txt, _A_FAVOR, 1)
        txt = re.sub(_LINDA, lambda m: self._linderos(m.group(0)), txt)
        txt = re.sub(_COMPARECENCIA, lambda m: self._comparecencia(m.group(0)), txt)
        txt = self._por_diccionario(txt)
        if USAR_PRESIDIO:
            txt = self._pasada_presidio(txt)
        return txt

    # segunda pasada opcional con Microsoft Presidio (reconocimiento de nombres por modelo de lenguaje, en local)
    _STOP = {'vende', 'compra', 'dona', 'hipoteca', 'notario', 'registrador', 'registro', 'finca', 'linda', 'norte', 'sur', 'este', 'oeste',
             'calle', 'plaza', 'avenida', 'banco', 'caja', 'ayuntamiento', 'juzgado', 'tribunal', 'sociedad', 'don', 'doña'}

    def _pasada_presidio(self, txt):
        eng = _presidio_engine()
        if eng is None:
            return txt
        try:
            t2 = re.sub(r'\b[A-ZÁÉÍÓÚÑÜ]{2,}\b', lambda m: m.group(0).capitalize(), txt)   # las mayúsculas confunden al modelo
            res = eng.analyze(text=t2, language='es', entities=['PERSON'], score_threshold=0.6)
        except Exception:
            return txt
        for r in sorted(res, key=lambda r: -r.start):
            s = txt[r.start:r.end]
            palabras = [w for w in re.split(r'[\s\-]+', s.strip()) if w]
            if len(palabras) < 2 or '[' in s or ']' in s:
                continue
            if all(w.lower().strip('.,;:') in self._STOP or w.lower() in ('de', 'del', 'la', 'y', 'e') for w in palabras):
                continue
            if any(w.lower().strip('.,;:') in ('notario', 'registrador', 'registro', 'finca', 'calle', 'juzgado', 'tribunal') for w in palabras):
                continue
            if re.search(r'\[(PERSONA|ENTIDAD|NIF)-\d+\]', txt[max(0, r.start - 12):r.end + 12]):
                continue
            txt = txt[:r.start] + self._etiqueta(s.strip('.,;: '), 'PERSONA') + txt[r.end:]
            self.sustituciones += 1
        return txt

    def _cnt(self, s):
        self.sustituciones += 1
        return s

    def _sub_trat(self, patron, txt):
        def repl(m):
            if re.search(_NOTARIO_ANTES, m.string[max(0, m.start() - 70):m.start(1)]):
                return m.group(0)
            self.sustituciones += 1
            return m.group(0)[:m.start(1) - m.start(0)] + self._etiqueta(m.group(1), 'PERSONA') + m.group(0)[m.end(1) - m.start(0):]
        return re.sub(patron, repl, txt)

    def _cp_suelto(self, m):
        antes, despues = m.string[max(0, m.start() - 40):m.start()], m.string[m.end():m.end() + 40]
        prev = re.search(r'([A-Za-zÁÉÍÓÚÑÜáéíóúñü]+)\.?[,\s(]*$', antes)
        if prev and _sin_tilde(prev.group(1)) in _NO_ANTES_CP:
            return m.group(0)
        sig = re.match(r'\s*[,)\-]?\s*([A-Za-zÁÉÍÓÚÑÜáéíóúñü]+)', despues)
        # el municipio va con mayúscula inicial y en minúsculas el resto («Madrid»; «RJ 10149» es una cita, no un código postal)
        tras_muni = (prev and len(prev.group(1)) >= 3 and prev.group(1)[0].isupper() and not prev.group(1).isupper()
                     and not (sig and sig.group(1)[0].islower()))
        ante_muni = sig and sig.group(1)[0].isupper() and _sin_tilde(sig.group(1)) not in _NO_ANTES_CP
        return self._cnt('[DOMICILIO]') if tras_muni or ante_muni else m.group(0)

    def _razon(self, m):
        pal = m.group(1).split()
        while pal and _sin_tilde(pal[0]) in _RAZON_FUERA:
            pal.pop(0)
        if not pal or any(_sin_tilde(w.strip('.,')) in _RAZON_PUBLICA for w in pal) or len(' '.join(pal)) < 3:
            return m.group(0)
        nombre = ' '.join(pal)
        ini = m.group(1).rfind(nombre)
        self.sustituciones += 1
        return m.group(0)[:ini] + self._etiqueta(nombre, 'ENTIDAD') + m.group(0)[ini + len(nombre):]

    # personas sin tratamiento («hijo de», «a favor de», linderos, comparecencia en mayúsculas, diccionario)
    def _persona(self, nombre, despues='', minimo=1):
        """La etiqueta para un nombre, o None si no parece una persona (una calle, un organismo, una palabra suelta)."""
        n = nombre.strip(' ,.;:')
        pal = [w for w in re.split(r'[\s\-]+', n) if w and w.lower() not in ('de', 'del', 'la', 'los', 'las')]
        if len(pal) < minimo or not pal or _sin_tilde(pal[0]) in _NO_PERSONA or pal[0].lower() in _NO_PERSONA:
            return None
        if len(pal) == 1 and len(pal[0]) < 3:
            return None
        self.sustituciones += 1
        return self._etiqueta(n, 'ENTIDAD' if re.match(_ES_ENTIDAD, despues) else 'PERSONA')

    def _personas(self, txt, patron, minimo):
        def repl(m):
            g = m.group(1)
            despues = m.string[m.end(1):m.end(1) + 20]
            trozos = re.split(r'(\s*(?:,|\by\b|\be\b)\s*(?:(?i:de)\s+)?' + _PERS_TRAT + ')', g)
            out = []
            for i, t in enumerate(trozos):
                if i % 2 or not t.strip():
                    out.append(t)
                    continue
                e = self._persona(t, despues if i == len(trozos) - 1 else '', minimo)
                out.append(e if e else t)
            return m.group(0)[:m.start(1) - m.start(0)] + ''.join(out) + m.group(0)[m.end(1) - m.start(0):]
        return re.sub(patron, repl, txt)

    def _linderos(self, seg):
        def repl(m):
            explicito = bool(m.group(1).strip() != 'con')
            e = self._persona(m.group(2), m.string[m.end(2):m.end(2) + 20], 1 if explicito else 2)
            return m.group(0)[:m.start(2) - m.start(0)] + e + m.group(0)[m.end(2) - m.start(0):] if e else m.group(0)
        return re.sub(_LINDA_CON, repl, seg)

    def _comparecencia(self, seg):
        dic = _diccionario()

        def repl(m):
            s = m.group(0)
            if re.match(_NOTARIO_DESPUES, m.string[m.end():m.end() + 30]) or re.search(_NOTARIO_ANTES, m.string[max(0, m.start() - 60):m.start()]):
                return s
            pal = [_sin_tilde(w) for w in re.split(r'[\s\-]+', s) if w and w not in ('DE', 'DEL', 'LA', 'LOS', 'LAS')]
            if any(w in _NO_PERSONA for w in pal):
                return s
            if dic and not any(w in dic['n'] or w in dic['a'] for w in pal):
                return s
            e = self._persona(s, m.string[m.end():m.end() + 20], 2)
            return e or s
        return re.sub(_MAYUS_SEQ, repl, seg)

    _SEQ_DIC = re.compile(r"(?<![\[\w\-])([A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü'’]+(?:\s+(?:(?:de\s+la|de\s+los|del|de|DE\s+LA|DE\s+LOS|DEL|DE)\s+)?"
                          r"[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü'’]+){1,6})(?![\w\-])")
    _ANTES_LUGAR = re.compile(r'(?i)(calle|c/|avenida|avda\.?|plaza|paseo|camino|carretera|parque|colegio|instituto|hospital|iglesia|parroquia|'
                              r'san|santa|santo|barrio|urbanización|edificio|registro\s+de|notaría\s+de|juzgado\s+de|municipio\s+de|término\s+de)\s*$')

    def _por_diccionario(self, txt):
        """Como anonimizarPorDiccionario() del navegador (08b_ocr_visor.js): nombres sin «don» que reconoce el diccionario."""
        dic = _diccionario()
        if not dic:
            return txt
        n, a, c = dic['n'], dic['a'], dic['c']

        def vale(nn):
            if len(nn) < 2 or not all(w in n or w in a for w in nn) or all(w in c for w in nn):
                return False
            ape, nom = sum(w in a for w in nn), sum(w in n for w in nn)
            return (nn[0] in n and any(w in a for w in nn[1:])) or (ape >= 2 and nom >= 1) or sum(w in a and w not in c for w in nn) >= 2

        def repl(m):
            seq, pos = m.group(1), m.start(1)
            pal = [(x.group(0), x.start()) for x in re.finditer(r"[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü'’]+", seq) if x.group(0) not in ('DE', 'DEL')]
            for i in range(len(pal) - 1):
                for j in range(len(pal) - 1, i, -1):
                    tramo = pal[i:j + 1]
                    if any(re.fullmatch(_NO_NOMBRE, w) for w, _ in tramo) or not vale([_sin_tilde(w) for w, _ in tramo]):
                        continue
                    ini, fin = tramo[0][1], tramo[-1][1] + len(tramo[-1][0])
                    antes = m.string[max(0, pos + ini - 60):pos + ini]
                    if self._ANTES_LUGAR.search(antes[-30:]) or re.search(_NOTARIO_ANTES, antes) or re.match(_NOTARIO_DESPUES, m.string[pos + fin:pos + fin + 30]):
                        return seq
                    # el segundo apellido poco corriente que no está en el diccionario («… Etxeberria Goikoetxea»)
                    if j + 1 < len(pal) and j + 1 - i <= 3:
                        w, p = pal[j + 1]
                        if (re.fullmatch(r'\s+', seq[fin:p]) and not re.fullmatch(_NO_NOMBRE, w) and _sin_tilde(w) not in _NO_PERSONA
                                and _sin_tilde(w) not in c and _sin_tilde(w) not in n):
                            fin = p + len(w)
                    self.sustituciones += 1
                    return seq[:ini] + self._etiqueta(re.sub(r'\s+', ' ', seq[ini:fin]), 'PERSONA') + seq[fin:]
            return seq
        return self._minusculas(self._SEQ_DIC.sub(repl, txt), dic)

    _PAL_MIN = re.compile(r"(?<![\w\[\-])[a-záéíóúñüàèòïç]{2,}(?![\w\-’'])")
    _ANTES_MIN = re.compile(r'(?i)(?:\b(?:don|doña|señor|señora|comparecen?|vende|venden|compra|compran|otorga|otorgan|y|e|a\s+favor\s+de|'
                            r'titular(?:es)?|hij[oa]s?\s+de|esposa?\s+de|cónyuge|conyuge)(?:\s+a)?|\bd\.|\bdña\.|,)\s*$')

    def _minusculas(self, txt, dic):
        """Nombres escritos todo en minúsculas (un OCR, un texto pegado): «comparece juan pérez garcía». Hace falta un nombre de pila
        que no sea palabra común seguido de apellidos del diccionario; con dos palabras, además, algo delante que anuncie a una persona."""
        n, a, c = dic['n'], dic['a'], dic['c']
        pal = [(x.group(0), x.start(), x.end()) for x in self._PAL_MIN.finditer(txt)]
        cortes = []
        i = 0
        while i < len(pal):
            w0 = _sin_tilde(pal[i][0])
            if w0 not in n or w0 in _NO_PERSONA:
                i += 1
                continue
            j, ult = i, i
            while j + 1 < len(pal) and j - i < 5:
                hueco = txt[pal[j][2]:pal[j + 1][1]]
                sig = _sin_tilde(pal[j + 1][0])
                if not re.fullmatch(r'\s+', hueco):
                    break
                if sig in ('de', 'del', 'la', 'los', 'i', 'y'):
                    j += 1
                    continue
                if sig in a or sig in n:
                    j += 1
                    ult = j
                    continue
                break
            nucleo = [_sin_tilde(w) for w, _, _ in pal[i:ult + 1] if _sin_tilde(w) not in ('de', 'del', 'la', 'los', 'i', 'y')]
            apell = [w for w in nucleo[1:] if w in a and w not in c]
            antes = txt[max(0, pal[i][1] - 25):pal[i][1]]
            # si el nombre de pila es también palabra común («rosa», «pilar»), hacen falta los dos apellidos
            if apell and (len(apell) >= 2 if w0 in c else (len(nucleo) >= 3 or (len(nucleo) == 2 and self._ANTES_MIN.search(antes)))):
                cortes.append((pal[i][1], pal[ult][2]))
                i = ult + 1
            else:
                i += 1
        for ini, fin in reversed(cortes):
            self.sustituciones += 1
            txt = txt[:ini] + self._etiqueta(txt[ini:fin], 'PERSONA') + txt[fin:]
        return txt

    def reponer(self, t):
        """Las etiquetas de vuelta a su texto (solo para lo que se devuelve al propio usuario, nunca hacia la IA)."""
        return re.sub(r'\[[A-Z]+-S?\d+(?:\.\d+)?\]', lambda m: self.originales.get(m.group(0), m.group(0)), str(t or ''))


def anonimizar_textos(textos, datos=None):
    """`textos` = {'documento': str, 'nota_simple': str, 'complementarios': [{'nombre','texto'}]}; `datos` = lo que
    extrajo el lector (para conocer los nombres). Devuelve (textos_anonimizados, resumen)."""
    a = Anonimizador()
    datos = datos or {}
    for c in datos.get('comparecientes') or []:
        a.nombres([c])
        if c.get('representado'):
            a.nombres([c['representado']])
    a.nombres(datos.get('otorgantes') or [])
    a.nombres(datos.get('representantes') or [])
    a.nombres(datos.get('titulares') or [])
    for f in datos.get('fincas') or []:
        if isinstance(f, dict):
            a.nombres(f.get('titulares') or [])
    out = {}
    for k, v in textos.items():
        if k == 'complementarios':
            out[k] = [{'nombre': c.get('nombre', ''), 'texto': a.texto(c.get('texto') or ''), 'clase': c.get('clase', '')} for c in v]
        elif isinstance(v, str):
            out[k] = a.texto(v)
    resumen = {'sustituciones': a.sustituciones, 'personas': a.contadores['PERSONA'], 'entidades': a.contadores['ENTIDAD'],
               'identificadores': a.contadores['NIF'] + a.contadores['REFCAT'] + a.contadores['IDUFIR'] + a.contadores['MATRICULA'],
               'equivalencias': dict(a.originales)}
    return out, resumen


# ----------------------------------------------------------------------------
# PDF de solo texto (sin dependencias): Helvetica, codificación WinAnsi (cp1252)
# ----------------------------------------------------------------------------
def _lineas(texto, ancho=95):
    out = []
    for parrafo in texto.replace('\r', '').split('\n'):
        p = parrafo.rstrip()
        if not p:
            out.append('')
            continue
        while len(p) > ancho:
            corte = p.rfind(' ', 0, ancho)
            if corte < ancho // 2:
                corte = ancho
            out.append(p[:corte].rstrip())
            p = p[corte:].lstrip()
        out.append(p)
    return out


def _pdf_texto(s):
    b = s.encode('cp1252', 'replace')
    return b.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')


def escribir_pdf(ruta, titulo, texto, lineas_pagina=62, pie='DOCUMENTO ANONIMIZADO'):
    lineas = _lineas(texto)
    paginas = [lineas[i:i + lineas_pagina] for i in range(0, max(1, len(lineas)), lineas_pagina)] or [[]]
    objetos = []   # cada elemento: bytes del cuerpo del objeto (sin «n 0 obj»)

    def add(cuerpo):
        objetos.append(cuerpo)
        return len(objetos)

    font = add(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>')
    pages_id = len(objetos) + 1 + 2 * len(paginas)   # se crea al final
    page_ids = []
    for n, pag in enumerate(paginas, start=1):
        contenido = [b'BT /F1 10 Tf 12 TL 50 800 Td']
        contenido.append(b'(' + _pdf_texto(f'{titulo} - pág. {n}/{len(paginas)}' + (f' - {pie}' if pie else '')) + b') Tj T*')
        contenido.append(b'T*')
        for ln in pag:
            contenido.append(b'(' + _pdf_texto(ln) + b') Tj T*')
        contenido.append(b'ET')
        flujo = zlib.compress(b'\n'.join(contenido))
        cid = add(b'<< /Length ' + str(len(flujo)).encode() + b' /Filter /FlateDecode >>\nstream\n' + flujo + b'\nendstream')
        pid = add(b'<< /Type /Page /Parent ' + str(pages_id).encode() + b' 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 '
                  + str(font).encode() + b' 0 R >> >> /Contents ' + str(cid).encode() + b' 0 R >>')
        page_ids.append(pid)
    kids = b' '.join(str(p).encode() + b' 0 R' for p in page_ids)
    real_pages = add(b'<< /Type /Pages /Kids [' + kids + b'] /Count ' + str(len(page_ids)).encode() + b' >>')
    assert real_pages == pages_id
    cat = add(b'<< /Type /Catalog /Pages ' + str(pages_id).encode() + b' 0 R >>')
    out = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = []
    for i, cuerpo in enumerate(objetos, start=1):
        offsets.append(len(out))
        out += f'{i} 0 obj\n'.encode() + cuerpo + b'\nendobj\n'
    xref = len(out)
    out += f'xref\n0 {len(objetos) + 1}\n'.encode() + b'0000000000 65535 f \n'
    for o in offsets:
        out += f'{o:010d} 00000 n \n'.encode()
    out += f'trailer\n<< /Size {len(objetos) + 1} /Root {cat} 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    with open(ruta, 'wb') as f:
        f.write(bytes(out))
    return str(ruta)
