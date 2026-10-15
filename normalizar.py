"""Paso 1 del bot: leer la planilla y dejar los datos listos para cargar.

Esto NO toca el SiGeS. Solo lee el CSV que sale del formulario de Google y
devuelve, por cada persona, o bien los datos limpios o bien el motivo por el que
no se pueden cargar.

Por qué existe este paso separado
---------------------------------
Podríamos ir del CSV al SiGeS de una. Sería un error. Los datos que llegan del
formulario están escritos por 30 personas distintas y tienen de todo:

    Nacionalidad: "Argentino", "Argentina", "Arg", "argentina"
    Provincia:    "Buenos Aires", "Bs as", "buenos aires", "Ensenada" (¡es una
                  localidad, no una provincia!)
    Celular:      "2215550001" y "221 555 0010"
    Domicilio:    "40000010"  ← alguien puso el DNI en el campo del domicilio
    Fecha:        "13/10/2072" ← todavía no nació
    Edad:         "Completar"

Si el bot cargara eso tal cual, ensuciaría el sistema del Ministerio a 40
registros por minuto en vez de a uno por minuto. **Un bot no arregla un proceso
malo: lo acelera.** Por eso primero se limpia, y lo que no se puede limpiar con
certeza NO se carga: se informa para que una persona lo mire.

Se corre así:
    python normalizar.py datos_ejemplo.csv
"""

import csv
import re
import sys
import unicodedata
from datetime import date, datetime

# --- Cuánto tiempo hacia atrás es razonable que alguien haya nacido -----------
EDAD_MINIMA = 14
EDAD_MAXIMA = 100


def sin_acentos(texto):
    """'Muñoz' -> 'Munoz'. Sirve para comparar, no para mostrar."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )


def limpiar(texto):
    """Saca espacios de más y deja una sola forma de escribir lo mismo."""
    return re.sub(r'\s+', ' ', (texto or '').strip())


def titulo(texto):
    """'SOFIA BEATRIZ' y 'sofia beatriz' -> 'Sofia Beatriz'."""
    return limpiar(texto).title()


def normalizar_nacionalidad(valor):
    """Las cuatro formas de escribir 'argentina' pasan a ser una sola."""
    v = sin_acentos(limpiar(valor)).lower()
    if v.startswith('arg'):
        return 'ARGENTINA', None
    if not v or v == 'completar':
        return None, 'falta la nacionalidad'
    # Cualquier otra nacionalidad se respeta tal cual, en mayúsculas.
    return limpiar(valor).upper(), None


# Localidades del partido que la gente escribe en la columna "provincia".
LOCALIDADES_CONOCIDAS = {'ensenada', 'punta lara', 'la plata', 'berisso'}


def normalizar_provincia(valor):
    v = sin_acentos(limpiar(valor)).lower()
    if v in {'buenos aires', 'bs as', 'bsas', 'bs. as.', 'pcia de buenos aires'}:
        return 'BUENOS AIRES', None
    if v in LOCALIDADES_CONOCIDAS:
        # No es un error de tipeo: es que confundieron la pregunta. Se asume
        # Buenos Aires (todas estas localidades lo son) pero se avisa.
        return 'BUENOS AIRES', f'escribieron la localidad "{limpiar(valor)}" en la provincia'
    if not v or v == 'completar':
        return None, 'falta la provincia'
    return limpiar(valor).upper(), None


def normalizar_dni(valor):
    """Solo los dígitos. El formulario ya pide 'sin puntos ni guiones', pero
    siempre hay alguien que los pone igual."""
    solo_digitos = re.sub(r'\D', '', valor or '')
    if not solo_digitos:
        return None, 'falta el DNI'
    if not 7 <= len(solo_digitos) <= 8:
        return None, f'el DNI tiene {len(solo_digitos)} dígitos, deberían ser 7 u 8'
    return solo_digitos, None


def normalizar_celular(valor):
    """El SiGeS lo quiere sin 0 adelante y sin el 15: '221' + número."""
    d = re.sub(r'\D', '', valor or '')
    if not d:
        return None, 'falta el celular'
    if d.startswith('0'):
        d = d[1:]
    # 221 15 5855775 -> 2215855775 (se saca el 15 que va después de la característica)
    if len(d) == 12 and d[3:5] == '15':
        d = d[:3] + d[5:]
    if len(d) != 10:
        return d, f'el celular quedó con {len(d)} dígitos, revisar'
    return d, None


def normalizar_fecha(valor):
    """Devuelve la fecha como date, o el motivo por el que no se pudo."""
    v = limpiar(valor)
    if not v or v.lower() == 'completar':
        return None, 'falta la fecha de nacimiento'
    for formato in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
        try:
            f = datetime.strptime(v, formato).date()
            break
        except ValueError:
            f = None
    if f is None:
        return None, f'no se entiende la fecha "{v}"'

    hoy = date.today()
    edad = hoy.year - f.year - ((hoy.month, hoy.day) < (f.month, f.day))
    if f > hoy:
        return None, f'la fecha "{v}" está en el futuro'
    if edad > EDAD_MAXIMA:
        return None, f'la fecha "{v}" da {edad} años'
    if edad < EDAD_MINIMA:
        return None, f'la fecha "{v}" da {edad} años'
    return f, None


def domicilio_sospechoso(domicilio, dni):
    """El caso real: alguien pegó el DNI en la columna del domicilio."""
    d = limpiar(domicilio)
    if not d or sin_acentos(d).lower() in {'completar', 'comoletar'}:
        return 'falta el domicilio'
    if re.fullmatch(r'\d{7,8}', d):
        return f'el domicilio dice "{d}", que parece un DNI'
    return None


def partir_direccion(domicilio):
    """El SiGeS pide Calle y Altura por separado.

    'Belgrano 629'          -> calle='Hernández',          altura='629'
    '31 entre 40 y 42 bis s/n' -> calle='5 entre 8 y 10 bis', altura='s/n'

    Ante la duda va todo a Calle y la altura queda 's/n': es lo que hizo la
    preceptora a mano, y es preferible a inventar un número.
    """
    d = limpiar(domicilio)
    if re.search(r'\bs/?n\b', d, re.IGNORECASE):
        return re.sub(r'\s*\bs/?n\b\s*$', '', d, flags=re.IGNORECASE), 's/n'
    m = re.match(r'^(.*?)[\s,]+(\d{1,5})$', d)
    if m:
        return limpiar(m.group(1)), m.group(2)
    return d, 's/n'


SEXO_POR_GENERO = {'mujer': 'Femenino', 'varon': 'Masculino'}

# Los niveles, de menor a mayor, con la clave de su columna en la planilla y su
# nombre en el menú del SiGeS.
NIVELES = [('edu_primario', 'Primario'), ('edu_secundario', 'Secundario'),
           ('edu_terciario', 'Terciario'), ('edu_universitario', 'Universitario')]


def interpretar_educacion(fila):
    """El nivel más alto que la persona marcó, y en qué estado.

    La planilla tiene una columna por nivel, y en cada una "completo",
    "incompleto" o "cursando" (escrito de cualquier forma: Completado, COMPLETO,
    En curso…). Devuelve {'nivel', 'completo', 'cursando'}, o None si no hay
    nada: entonces Educación queda para la preceptora (o los valores fijos).
    """
    mejor = None
    for clave, nombre in NIVELES:
        v = sin_acentos(limpiar(str(fila.get(clave, '') or ''))).lower()
        if not v:
            continue
        if 'curs' in v:
            estado = {'completo': False, 'cursando': True}
        elif 'incomplet' in v or v in ('no', 'no termino'):
            estado = {'completo': False, 'cursando': False}
        elif 'complet' in v or 'termin' in v or v in ('si',):
            estado = {'completo': True, 'cursando': False}
        else:
            continue
        mejor = {'nivel': nombre, **estado}   # los niveles van de menor a mayor: gana el último
    return mejor


def normalizar_fila(fila):
    """Devuelve (datos_limpios, lista_de_problemas)."""
    problemas = []

    def revisar(par):
        valor, problema = par
        if problema:
            problemas.append(problema)
        return valor

    genero = sin_acentos(limpiar(fila.get('genero', ''))).lower()
    fecha = revisar(normalizar_fecha(fila.get('fecha_nacimiento', '')))
    dni = revisar(normalizar_dni(fila.get('dni', '')))

    problema_dom = domicilio_sospechoso(fila.get('domicilio', ''), dni)
    if problema_dom:
        problemas.append(problema_dom)
    calle, altura = partir_direccion(fila.get('domicilio', ''))

    datos = {
        'dni': dni,
        'apellidos': titulo(fila.get('apellidos', '')),
        'nombres': titulo(fila.get('nombres', '')),
        'sexo': SEXO_POR_GENERO.get(genero),
        'identidad_genero': titulo(fila.get('genero', '')),
        'fecha_nacimiento': fecha.strftime('%d/%m/%Y') if fecha else None,
        'nacionalidad': revisar(normalizar_nacionalidad(fila.get('nacionalidad', ''))),
        'lugar_nacimiento': revisar(normalizar_provincia(fila.get('provincia', ''))),
        'calle': calle,
        'altura': altura,
        'localidad': titulo(fila.get('localidad', '')),
        'distrito': titulo(fila.get('localidad', '')),
        'celular': revisar(normalizar_celular(fila.get('celular', ''))),
        'educacion': interpretar_educacion(fila),
    }

    if not datos['apellidos']:
        problemas.append('falta el apellido')
    if not datos['sexo']:
        problemas.append(f'no se entiende el género "{fila.get("genero", "")}"')

    return datos, problemas


def leer(ruta):
    with open(ruta, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main(ruta, filas=None):
    """`filas` viene armado cuando la planilla es un .xlsx (ver planilla_google.py)."""
    if filas is None:
        filas = leer(ruta)
    listos, frenados = [], []

    for i, fila in enumerate(filas, start=2):  # 2 = la primera fila de datos
        i = fila.get('_fila', i)
        datos, problemas = normalizar_fila(fila)
        if problemas:
            frenados.append((i, datos, problemas))
        else:
            listos.append((i, datos))

    print(f'\nSe leyeron {len(filas)} personas de {ruta}\n')
    print(f'✅ LISTOS PARA CARGAR: {len(listos)}')
    for i, d in listos:
        print(f'   fila {i:>3}  {d["dni"]}  {d["apellidos"]}, {d["nombres"]}'
              f'  ({d["fecha_nacimiento"]})')

    print(f'\n⛔ FRENADOS, los tiene que mirar una persona: {len(frenados)}')
    for i, d, problemas in frenados:
        quien = f'{d["apellidos"]}, {d["nombres"]}'.strip(', ') or '(sin nombre)'
        print(f'   fila {i:>3}  {quien}')
        for p in problemas:
            print(f'            · {p}')

    print(f'\nEl bot cargaría {len(listos)} de {len(filas)}. '
          f'Los otros {len(frenados)} NO se tocan.\n')
    return listos


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'datos_ejemplo.csv')
