"""¿Los selectores del bot encuentran lo que tienen que encontrar en el SiGeS real?

Se prueba contra las pantallas guardadas del proceso entero (15/10/2026), que
están en capturas/siges-2026-10-15/ —fuera de Git, porque tienen datos de
personas—. Si no están, el script avisa y sale.

    python probar_selectores.py

Cada selector tiene que encontrar EXACTAMENTE UN elemento: cero quiere decir que
cambió el formulario, y dos que el bot podría tocar el equivocado. Las pantallas
se abren con JavaScript apagado: es la foto de cómo estaba, no la aplicación.

Lo que esto NO puede probar (la aplicación tiene que estar viva): el formato de
fecha que acepta, las opciones de los menús y de los buscadores de Distrito y
Localidad. Para eso el bot frena y le pide a la persona que elija.
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

import siges_real as s

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
CAPTURAS = pathlib.Path(__file__).resolve().parent / 'capturas' / 'siges-2026-10-15'

# (página, qué es, cómo se arma el selector con las funciones de siges_real)
CHEQUEOS = [
    (14, 'botón "+" del listado', lambda p: p.locator('button:has(mat-icon:text-is("add"))')),
    (1, 'buscador: Tipo de documento', lambda p: p.get_by_label('Tipo de documento', exact=True)),
    (1, 'buscador: Número de documento', lambda p: p.locator('input[name="numero_de_documento"]')),
    (1, 'buscador: botón Buscar estudiante', lambda p: s._boton(p, 'Buscar estudiante', exacto=False)),
    *[(2, f'campo {rotulo}', (lambda n: lambda p: s._campo(p, n))(nombre)) for nombre, _, rotulo in s.CAMPOS_DE_TEXTO],
    *[(2, f'opción {rotulo}', (lambda g, v: lambda p: p.locator(f'mat-radio-button:has(input[type="radio"][name="{g}"][value="{v}"])'))(grupo, valor))
      for grupo, valor, rotulo in s.RADIOS_FIJOS],
    *[(2, f'sexo = {v}', (lambda v: lambda p: p.locator(f'mat-radio-button:has(input[type="radio"][name="sexo"][value="{v}"])'))(v))
      for v in ('femenino', 'masculino', 'x')],
    (2, 'menú Identidad de género', lambda p: p.locator('mat-select[formcontrolname="identidad"]')),
    (2, 'botón Agregar direccion', lambda p: s._boton(p, 'Agregar direccion')),
    (2, 'botón Agregar contacto', lambda p: s._boton(p, 'Agregar contacto')),
    (2, 'botón Agregar vivienda (se resalta)', lambda p: s._boton(p, 'Agregar vivienda')),
    (2, 'botón Agregar educacion (se resalta)', lambda p: s._boton(p, 'Agregar educacion')),
    (2, 'botón Guardar estudiante (lo aprieta la persona)', lambda p: s._boton(p, 'Guardar estudiante')),
    (5, 'dirección: Calle', lambda p: s._campo(p, 'calle')),
    (5, 'dirección: Altura', lambda p: s._campo(p, 'altura')),
    (5, 'dirección: buscador Distrito', lambda p: p.get_by_label('Distrito', exact=True)),
    (5, 'dirección: buscador Localidad', lambda p: p.get_by_label('Localidad', exact=True)),
    (5, 'dirección: botón Agregar', lambda p: s._boton(p, 'Agregar')),
    (8, 'contacto: menú Tipo de contacto', lambda p: p.locator('mat-select[formcontrolname="tipo_de_contacto"]')),
    (8, 'contacto: número', lambda p: s._campo(p, 'valor')),
    (8, 'contacto: botón Agregar', lambda p: s._boton(p, 'Agregar')),
    (2, 'casilla de transporte (valor fijo)', lambda p: p.get_by_label(s.CONFIG_INICIAL['transporte'], exact=True)),
    *[(7, f'vivienda: número {n}', (lambda n: lambda p: s._campo(p, n))(n))
      for n in ('cuantas_personas', 'cuantos_adultos', 'cuantos_ninios')],
    *[(7, f'vivienda: {g} = {v}', (lambda g, v: lambda p: p.locator(f'mat-radio-button:has(input[type="radio"][name="{g}"][value="{v}"])'))(g, v))
      for g, v in [('vivienda', z) for z in s.ZONAS] + [(g, b) for g in ('hijos', 'extranjera', 'indigena', 'originarios')
                                                         for b in ('true', 'false')]],
    (8, 'contacto: con WhatsApp sí', lambda p: p.locator('mat-radio-button:has(input[name="con_whatsapp"][value="true"])')),
    (8, 'contacto: con WhatsApp no', lambda p: p.locator('mat-radio-button:has(input[name="con_whatsapp"][value="false"])')),
    (9, 'educación: menú Nivel máximo', lambda p: p.locator('mat-select[formcontrolname="max_nivel_alcanzado"]')),
    *[(9, f'educación: {g} = {b}', (lambda g, v: lambda p: p.locator(f'mat-radio-button:has(input[type="radio"][name="{g}"][value="{v}"])'))(g, b))
      for g in ('completo', 'cursando') for b in ('true', 'false')],
]

# Y lo que tiene que estar, pero NO tocar: si alguno de estos desaparece o se
# duplica, cambió el formulario y hay que revisar las reglas del bot.
# (En la pantalla 14, la del listado: con un diálogo abierto, el fondo queda
# aria-hidden y get_by_role no lo ve.)
NO_TOCAR = [
    (14, 'botón Generar matrícula inicial (NUNCA lo toca)', lambda p: s._boton(p, 'Generar matrícula inicial')),
]

# La razón por la que las opciones se buscan por grupo y value, y no por texto.
AMBIGUO = [(2, 'una opción por su texto "Si"', lambda p: p.get_by_label('Si', exact=True))]


def main():
    if not CAPTURAS.is_dir():
        print(f'No están las pantallas guardadas en {CAPTURAS}.\n'
              'Son las del 15/10/2026: van ahí, fuera de Git.')
        return 1
    fallas = 0
    with sync_playwright() as pw:
        nav = pw.chromium.launch()
        ctx = nav.new_context(java_script_enabled=False)
        paginas = {}

        def pagina(num):
            if num not in paginas:
                pg = ctx.new_page()
                pg.goto((CAPTURAS / f'SisGE-{num}.html').as_uri(), wait_until='domcontentloaded')
                paginas[num] = pg
            return paginas[num]

        print('Lo que usa el bot (tiene que haber exactamente 1):')
        for num, que, armar in CHEQUEOS + NO_TOCAR:
            n = armar(pagina(num)).count()
            marca = '✅' if n == 1 else '❌'
            fallas += n != 1
            print(f'  {marca} {que:<52} pantalla {num:>2}: {n}')

        print('\nPor qué las opciones van por grupo y value:')
        for num, que, armar in AMBIGUO:
            n = armar(pagina(num)).count()
            print(f'  ℹ️  {que:<52} pantalla {num:>2}: {n} coincidencias')
        nav.close()

    print(f'\n{"Todo en orden." if not fallas else f"{fallas} selector(es) con problema."}')
    return 1 if fallas else 0


if __name__ == '__main__':
    sys.exit(main())
