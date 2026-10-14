"""Ayudas del bot. Este archivo NO hace falta tocarlo hoy.

Acá está todo lo que el bot necesita y que no es la parte importante: leer una
fecha escrita a mano, pasar "Arg" a "ARGENTINA", partir "Calle 47 nro 629" en
calle y altura. Está a la vista para quien tenga curiosidad, pero el corazón
del proyecto está en alumno.py: ahí se decide quién se carga y quién no.
"""

import csv
import pathlib
import re
from datetime import datetime

AQUI = pathlib.Path(__file__).parent
SIMULADOR = (AQUI / 'siges_falso.html').as_uri()


def leer_fecha(texto):
    """Convierte "3/12/2004" en una fecha de verdad.

    Si no se entiende (vacía, "Completar", "32/13/2000"), devuelve None.
    """
    texto = (texto or '').strip()
    for formato in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            pass
    return None


def leer_filas(ruta):
    """La planilla como diccionarios, indexada por DNI. La usa el bot para los
    datos que el SiGeS pide y que la clase Alumno no guarda (el domicilio
    partido, el género, la provincia)."""
    with open(AQUI / ruta, encoding='utf-8-sig', newline='') as f:
        return {fila['dni']: fila for fila in csv.DictReader(f)}


def _limpiar(texto):
    return re.sub(r'\s+', ' ', (texto or '').strip())


def _titulo(texto):
    """'HERRERA' y 'herrera' -> 'Herrera'."""
    return _limpiar(texto).title()


def _nacionalidad(texto):
    """Las cuatro formas de escribir argentina pasan a ser una sola."""
    t = _limpiar(texto)
    if t.lower().startswith('arg'):
        return 'ARGENTINA'
    return t.upper()


def _provincia(texto):
    t = _limpiar(texto).lower()
    if t in {'buenos aires', 'bs as', 'bsas', 'bs. as.'}:
        return 'BUENOS AIRES'
    # "Ensenada" o "Punta Lara" en la columna de la provincia: confundieron la
    # pregunta, pero todas esas localidades son de Buenos Aires.
    if t in {'ensenada', 'punta lara', 'la plata', 'berisso'}:
        return 'BUENOS AIRES'
    return _limpiar(texto).upper()


def _partir_direccion(domicilio):
    """El SiGeS pide calle y altura por separado.

    'Calle 47 nro 629'       -> ('Calle 47 nro', '629')
    '31 entre 40 y 42 bis s/n' -> ('31 entre 40 y 42 bis', 's/n')

    Ante la duda, todo va a la calle y la altura queda "s/n": es lo que hace la
    preceptora a mano, y es mejor que inventar un número.
    """
    d = _limpiar(domicilio)
    if re.search(r'\bs/?n\b', d, re.IGNORECASE):
        return re.sub(r'\s*\bs/?n\b\s*$', '', d, flags=re.IGNORECASE), 's/n'
    m = re.match(r'^(.*?)[\s,]+(\d{1,5})$', d)
    if m:
        return _limpiar(m.group(1)), m.group(2)
    return d, 's/n'


SEXO = {'mujer': 'Femenino', 'varón': 'Masculino', 'varon': 'Masculino'}


def datos_para_siges(fila):
    """Todo lo que el formulario del SiGeS pide, a partir de una fila."""
    calle, altura = _partir_direccion(fila.get('domicilio', ''))
    fecha = leer_fecha(fila.get('fecha_nacimiento', ''))
    genero = _limpiar(fila.get('genero', ''))
    return {
        'dni': _limpiar(fila.get('dni', '')),
        'apellidos': _titulo(fila.get('apellidos', '')),
        'nombres': _titulo(fila.get('nombres', '')),
        'sexo': SEXO.get(genero.lower(), 'X'),
        'identidad_genero': genero.title(),
        'fecha_nacimiento': fecha.strftime('%d/%m/%Y') if fecha else '',
        'nacionalidad': _nacionalidad(fila.get('nacionalidad', '')),
        'lugar_nacimiento': _provincia(fila.get('provincia', '')),
        'calle': calle,
        'altura': altura,
        'distrito': _titulo(fila.get('localidad', '')),
        'localidad': _titulo(fila.get('localidad', '')),
        'celular': (fila.get('celular') or '').replace(' ', ''),
    }
