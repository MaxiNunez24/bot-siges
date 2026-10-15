"""Leer la planilla de Google tal como la usa la preceptora.

En la planilla real hay dos cosas que un CSV pierde:

1. **Las filas pintadas de amarillo.** Es la marca que usa ella (ya cargados, o
   para revisar): el bot NO las toca. Un CSV no guarda colores, así que la
   planilla se baja como Excel: Archivo → Descargar → Microsoft Excel (.xlsx).
2. **El rango de fechas.** No se carga toda la planilla, sino las respuestas de
   ciertos días. Se filtra por la columna "Marca temporal" (o la que se elija).

Se corre así, para ver qué quedaría sin abrir ningún navegador:
    python planilla_google.py inscriptos.xlsx --desde 01/10/2026 --hasta 14/10/2026

Ojo con el amarillo de "formato condicional"
--------------------------------------------
Si el amarillo lo pone una REGLA (Formato → Formato condicional) y no la
persona con el balde de pintura, el .xlsx no trae el color en la celda sino la
regla, y acá no se ve. En ese caso el programa avisa "0 amarillas" y conviene
mirar la planilla antes de seguir.
"""

import argparse
import colorsys
import sys
from datetime import date, datetime

import normalizar

# Encabezado de la planilla → clave que usa normalizar.py. Se compara sin
# acentos, sin puntos ("D.N.I") y en minúsculas, y solo con lo que está ANTES
# del paréntesis: en la planilla real, "APELLIDO/S (Tal cual figura en el DNI)"
# dice "dni" en la aclaración y no es la columna del DNI. El orden importa: gana
# la primera que coincide, por eso "fecha de nacimiento" va antes que "fecha".
COLUMNAS = [
    ('marca temporal', 'marca_temporal'),
    ('marca_temporal', 'marca_temporal'),
    ('fecha de nacimiento', 'fecha_nacimiento'),
    ('fecha_nacimiento', 'fecha_nacimiento'),
    ('fecha inscripcion', 'fecha_inscripcion'),
    ('fecha de inscripcion', 'fecha_inscripcion'),
    ('dni', 'dni'),
    ('documento', 'dni'),
    ('apellido', 'apellidos'),
    ('nombre', 'nombres'),
    ('genero', 'genero'),
    ('sexo', 'genero'),
    ('edad', 'edad'),
    ('nacionalidad', 'nacionalidad'),
    ('provincia', 'provincia'),
    ('lugar de nacimiento', 'provincia'),
    ('domicilio', 'domicilio'),
    ('direccion', 'domicilio'),
    ('localidad', 'localidad'),
    ('celular', 'celular'),
    ('telefono', 'celular'),
    # Educación: una columna por nivel, con "completo" / "incompleto" / "cursando"
    # (de cualquier forma escrita: ver normalizar.interpretar_educacion).
    ('primari', 'edu_primario'),
    ('secundari', 'edu_secundario'),
    ('terciari', 'edu_terciario'),
    ('universitari', 'edu_universitario'),
]

# Lo mínimo para que normalizar.py pueda trabajar.
OBLIGATORIAS = ['dni', 'apellidos', 'nombres', 'genero', 'fecha_nacimiento',
                'nacionalidad', 'provincia', 'domicilio', 'localidad', 'celular']


def clave_de(encabezado, ya_usadas):
    e = normalizar.sin_acentos(normalizar.limpiar(str(encabezado or ''))).lower()
    e = e.split('(')[0].replace('.', '')
    if 'contacto' in e:
        # "NOMBRE / CELULAR DE LA PERSONA DE CONTACTO": no son de quien se inscribe.
        return None
    for texto, clave in COLUMNAS:
        if texto in e and clave not in ya_usadas:
            return clave
    return None


def es_amarillo(celda):
    """¿La celda está pintada de algún amarillo?

    No alcanza con comparar contra 'FFFF00': Google tiene ocho amarillos en la
    paleta (el clarito FFF2CC es el que más se usa) y la gente elige cualquiera.
    Se mira el tono: entre el naranja y el verde.
    """
    relleno = celda.fill
    if relleno is None or relleno.fill_type != 'solid':
        return False
    color = relleno.fgColor
    if color is None or color.type != 'rgb' or not isinstance(color.rgb, str):
        return False
    rgb = color.rgb[-6:]
    try:
        r, g, b = (int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return False
    tono, saturacion, brillo = colorsys.rgb_to_hsv(r, g, b)
    return 40 <= tono * 360 <= 70 and saturacion >= 0.15 and brillo >= 0.6


def como_texto(valor):
    """Lo que trae Excel (fechas, números) pasado al texto que espera normalizar.py."""
    if valor is None:
        return ''
    if isinstance(valor, datetime):
        return valor.strftime('%d/%m/%Y %H:%M:%S') if (valor.hour or valor.minute) \
            else valor.strftime('%d/%m/%Y')
    if isinstance(valor, date):
        return valor.strftime('%d/%m/%Y')
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))       # el DNI y el celular llegan como 40000004.0
    return str(valor)


def a_fecha(valor):
    """La fecha de una celda, venga como fecha de Excel o como texto."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = normalizar.limpiar(str(valor or '')).split(' ')[0]
    for formato in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            pass
    return None


def fecha_argumento(texto):
    f = a_fecha(texto)
    if f is None:
        raise argparse.ArgumentTypeError(f'no entiendo la fecha "{texto}" (usá dd/mm/aaaa)')
    return f


def leer(ruta, desde=None, hasta=None, hoja=None, columna_fecha=None,
         informar=True):
    """Devuelve las filas que hay que cargar, como diccionarios para normalizar.py.

    Cada fila trae además '_fila' (el número de fila en la planilla), para que
    los mensajes coincidan con lo que ella ve en pantalla.
    """
    try:
        import openpyxl
    except ImportError:
        sys.exit('Falta openpyxl. Instalalo con:  pip install openpyxl')

    libro = openpyxl.load_workbook(ruta, data_only=True)
    ws = libro[hoja] if hoja else libro.worksheets[0]

    filas_hoja = ws.iter_rows()
    encabezados = next(filas_hoja)
    columnas = {}                   # índice de columna → clave
    for celda in encabezados:
        clave = clave_de(celda.value, set(columnas.values()))
        if clave:
            columnas[celda.column - 1] = clave

    if informar:
        print(f'\nHoja "{ws.title}". Columnas reconocidas:')
        for celda in encabezados:
            clave = columnas.get(celda.column - 1)
            if celda.value:
                print(f'   {"→ " + clave if clave else "  (se ignora)":<22} {celda.value}')
    faltan = [c for c in OBLIGATORIAS if c not in columnas.values()]
    if faltan:
        sys.exit(f'\n⛔ No encontré estas columnas: {", ".join(faltan)}.\n'
                 f'   Revisá los encabezados o agregalos a COLUMNAS en planilla_google.py.')
    if columna_fecha is None:
        # La "FECHA INSCRIPCIÓN" la escribe la preceptora; la marca temporal la
        # pone Google. Si está la de ella, se filtra por esa.
        columna_fecha = 'fecha_inscripcion' if 'fecha_inscripcion' in columnas.values() \
            else 'marca_temporal'
    if (desde or hasta) and columna_fecha not in columnas.values():
        sys.exit(f'\n⛔ Se pidió filtrar por fecha pero no hay columna "{columna_fecha}".')

    def indice(clave):
        return next((i for i, c in columnas.items() if c == clave), None)

    elegidas, amarillas, fuera_de_rango, sin_fecha, fechas_raras = [], [], 0, [], []
    for celdas in filas_hoja:
        if all(c.value in (None, '') for c in celdas):
            continue
        numero = celdas[0].row
        fila = {clave: como_texto(celdas[i].value) if i < len(celdas) else ''
                for i, clave in columnas.items()}
        fila['_fila'] = numero

        # Si la fecha que escribió ella está lejos del día en que respondieron,
        # casi seguro es un error de tipeo (2025 por 2026, 06 por 07), y el
        # filtro la va a dejar afuera o adentro sin que nadie lo note.
        i_ins, i_marca = indice('fecha_inscripcion'), indice('marca_temporal')
        if i_ins is not None and i_marca is not None:
            f_ins, f_marca = a_fecha(celdas[i_ins].value), a_fecha(celdas[i_marca].value)
            if f_ins and f_marca and abs((f_ins - f_marca).days) > 7:
                fechas_raras.append((numero, f_ins, f_marca))

        if desde or hasta:
            f = a_fecha(celdas[indice(columna_fecha)].value)
            if f is None:
                sin_fecha.append(numero)
                continue
            if (desde and f < desde) or (hasta and f > hasta):
                fuera_de_rango += 1
                continue

        if any(es_amarillo(c) for c in celdas):
            amarillas.append(fila)
            continue

        elegidas.append(fila)

    if informar:
        rango = (f'del {desde:%d/%m/%Y}' if desde else 'desde el principio') + \
                (f' al {hasta:%d/%m/%Y}' if hasta else ' hasta hoy')
        print(f'\nFiltro de fechas ({columna_fecha}): {rango}' if (desde or hasta)
              else '\nSin filtro de fechas.')
        if desde or hasta:
            print(f'   {fuera_de_rango} fila(s) quedan afuera por la fecha.')
        if sin_fecha:
            print(f'   ⚠️  Sin fecha legible, se saltean: filas {sin_fecha}')
        for numero, f_ins, f_marca in fechas_raras:
            print(f'   ⚠️  fila {numero}: la inscripción dice {f_ins:%d/%m/%Y} pero respondió '
                  f'el {f_marca:%d/%m/%Y}. ¿Error de tipeo?')
        print(f'🟨 Pintadas de amarillo, NO se tocan: {len(amarillas)}')
        for f in amarillas:
            print(f'   fila {f["_fila"]:>3}  {f.get("apellidos", "")}, {f.get("nombres", "")}')
        print(f'➡️  Pasan al control de datos: {len(elegidas)}')

    return elegidas


def todas(ruta, hoja=None):
    """Para la aplicación: TODAS las filas, sin descartar ninguna.

    La que decide es la preceptora, con las casillas del listado: acá solo se
    marca cada fila con lo que sirve para decidir. Sirve para .xlsx y .csv.

    Devuelve (columnas, filas, faltan):
      columnas: [(encabezado, clave o None)], para mostrar qué se reconoció;
      filas: diccionarios para normalizar.py, más '_fila' (el número en la
             planilla), '_amarilla' y '_fecha' (la de inscripción o la marca
             temporal, para filtrar por fecha);
      faltan: las columnas obligatorias que no aparecieron.
    """
    if ruta.lower().endswith('.csv'):
        import csv
        with open(ruta, encoding='utf-8-sig', newline='') as f:
            lector = csv.reader(f)
            encabezados = next(lector, [])
            crudas = [(n, [(v, False) for v in celdas]) for n, celdas in enumerate(lector, start=2)]
    else:
        try:
            import openpyxl
        except ImportError:
            raise RuntimeError('Falta openpyxl para leer .xlsx')
        libro = openpyxl.load_workbook(ruta, data_only=True)
        ws = libro[hoja] if hoja else libro.worksheets[0]
        filas_hoja = ws.iter_rows()
        encabezados = [c.value for c in next(filas_hoja, [])]
        crudas = [(celdas[0].row, [(c.value, es_amarillo(c)) for c in celdas]) for celdas in filas_hoja]

    columnas = {}
    for i, enc in enumerate(encabezados):
        clave = clave_de(enc, set(columnas.values()))
        if clave:
            columnas[i] = clave
    faltan = [c for c in OBLIGATORIAS if c not in columnas.values()]
    fecha_de = 'fecha_inscripcion' if 'fecha_inscripcion' in columnas.values() else 'marca_temporal'
    i_fecha = next((i for i, c in columnas.items() if c == fecha_de), None)

    filas = []
    for numero, celdas in crudas:
        if all(v in (None, '') for v, _ in celdas):
            continue
        fila = {clave: como_texto(celdas[i][0]) if i < len(celdas) else ''
                for i, clave in columnas.items()}
        fila['_fila'] = numero
        fila['_amarilla'] = any(amarilla for _, amarilla in celdas)
        fila['_fecha'] = a_fecha(celdas[i_fecha][0]) if i_fecha is not None and i_fecha < len(celdas) else None
        filas.append(fila)
    return [(str(e), columnas.get(i)) for i, e in enumerate(encabezados) if e], filas, faltan


def main():
    ap = argparse.ArgumentParser(description='Lee la planilla de Google bajada como .xlsx.')
    ap.add_argument('xlsx')
    ap.add_argument('--desde', type=fecha_argumento, help='dd/mm/aaaa, inclusive')
    ap.add_argument('--hasta', type=fecha_argumento, help='dd/mm/aaaa, inclusive')
    ap.add_argument('--hoja', help='Nombre de la hoja (por defecto, la primera)')
    ap.add_argument('--columna-fecha', choices=['fecha_inscripcion', 'marca_temporal'],
                    help='Por qué columna filtrar (por defecto, FECHA INSCRIPCIÓN si existe)')
    args = ap.parse_args()
    filas = leer(args.xlsx, args.desde, args.hasta, args.hoja, args.columna_fecha)
    normalizar.main(args.xlsx, filas)


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:                                   # noqa: BLE001
        pass
    main()
