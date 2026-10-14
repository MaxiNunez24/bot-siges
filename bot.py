"""Paso 2 del bot: cargar en el SiGeS las personas que quedaron listas.

Cómo funciona, en una frase
---------------------------
Playwright abre un navegador de verdad y hace exactamente lo que haría una
persona: escribe el DNI, toca "Buscar estudiante", completa el formulario y
guarda. No hay ninguna magia ni ninguna "conexión secreta" con el Ministerio:
es el mismo Chrome, manejado por Python en vez de por una mano.

Por qué así y no de otra forma
------------------------------
Un sistema como el SiGeS normalmente ofrecería una API (una puerta pensada para
que otros programas le hablen). El SiGeS no la tiene, o al menos no está abierta
para un CFP. Cuando no hay puerta, queda la ventana: automatizar el navegador.
Es más frágil —si el Ministerio cambia el formulario, el bot deja de andar— pero
es lo único disponible, y es exactamente lo que se hace en la vida real cuando
hay que integrarse con un sistema que no coopera.

Las tres reglas que este bot no rompe
-------------------------------------
1. **Por defecto va contra el SIMULADOR**, no contra el sistema real. Para ir al
   real hay que pedirlo explícitamente con --real.
2. **Nunca inicia sesión solo.** No hay usuario ni contraseña en el código, ni
   los pide. La persona se loguea a mano y recién ahí el bot toma el control.
   Contra el sistema real, además, es la persona la que busca el DNI y abre el
   formulario: el bot completa uno que ya está en pantalla.
3. **Nunca aprieta "Generar matrícula inicial".** El bot deja a la persona como
   PRE INSCRIPTA, que es un estado reversible: si algo salió mal, se borra con
   el tachito. La matrícula la genera una persona, mirando.
4. **Contra el sistema real tampoco guarda.** Completa lo que sabe y deja el
   formulario en pantalla; "Guardar estudiante" lo aprieta una persona después
   de revisar. Ver `siges_real.py`, que además explica qué secciones NO toca.

Se corre así:
    python bot.py                      # contra el simulador, mostrando el navegador
    python bot.py --lento              # con pausas, para que se vea en una demo
    python bot.py --real <url>         # contra el SiGeS (pide confirmación)

    # La planilla de Google bajada como Excel: saltea las filas amarillas y
    # carga solo las respuestas de esas fechas (por la "Marca temporal").
    python bot.py inscriptos.xlsx --desde 01/10/2026 --hasta 14/10/2026 --real <url>
"""

import argparse
import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

import normalizar
import planilla_google
import siges_real

# Windows a veces abre la consola en cp1252, que no sabe escribir ✅ ni ⛔, y el
# programa se cae con UnicodeEncodeError a mitad de una carga. Que un emoji se
# vea como "?" es infinitamente mejor que perder la corrida por un adorno.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:                                       # noqa: BLE001
    pass

AQUI = pathlib.Path(__file__).parent
SIMULADOR = (AQUI / 'siges_falso.html').as_uri()


def cargar_una(page, datos, lento=0):
    """Carga UNA persona EN EL SIMULADOR. Devuelve (ok, detalle).

    El formulario real se completa en siges_real.py: son dos pantallas
    distintas y cada una tiene su función, para que arreglar una no rompa la
    otra.
    """

    def respirar():
        if lento:
            time.sleep(lento)

    # --- 1. Buscar por documento -------------------------------------------
    page.fill('#numero-documento', datos['dni'])
    respirar()
    page.click('#buscar-estudiante')
    page.wait_for_selector('#apellidos', state='visible')
    respirar()

    # --- 2. Completar el formulario ----------------------------------------
    # Se llena campo por campo, igual que a mano. Si alguno no existe (porque el
    # formulario cambió), se avisa en vez de seguir a ciegas.
    campos = {
        '#apellidos': datos['apellidos'],
        '#nombres': datos['nombres'],
        '#nacionalidad': datos['nacionalidad'],
        '#lugar-nacimiento': datos['lugar_nacimiento'],
        '#fecha-nacimiento': datos['fecha_nacimiento'],
        '#calle': datos['calle'],
        '#altura': datos['altura'],
        '#distrito': datos['distrito'],
        '#localidad': datos['localidad'],
        '#celular': datos['celular'],
    }
    for selector, valor in campos.items():
        if valor is None:
            continue
        if page.locator(selector).count() == 0:
            return False, f'no encontré el campo {selector} (¿cambió el formulario?)'
        page.fill(selector, str(valor))
        respirar()

    page.check(f'input[name="sexo"][value="{datos["sexo"]}"]')
    if page.locator('#identidad-genero').count():
        page.select_option('#identidad-genero', label=datos['identidad_genero'])
    respirar()

    # --- 3. Guardar ---------------------------------------------------------
    page.click('#guardar')
    page.wait_for_selector('#alerta', state='visible')
    mensaje = page.inner_text('#alerta-texto')
    page.click('#entendido')
    page.wait_for_selector('#alerta', state='hidden')

    ok = 'correctamente' in mensaje.lower()
    return ok, mensaje


def main():
    ap = argparse.ArgumentParser(description='Carga alumnos en el SiGeS.')
    ap.add_argument('csv', nargs='?', default='datos_ejemplo.csv',
                    help='La planilla: .csv, o .xlsx bajado de Google (respeta el amarillo)')
    ap.add_argument('--desde', type=planilla_google.fecha_argumento,
                    help='Solo .xlsx: respuestas desde esta fecha (dd/mm/aaaa)')
    ap.add_argument('--hasta', type=planilla_google.fecha_argumento,
                    help='Solo .xlsx: respuestas hasta esta fecha (dd/mm/aaaa)')
    ap.add_argument('--hoja', help='Solo .xlsx: nombre de la hoja (por defecto, la primera)')
    ap.add_argument('--real', metavar='URL',
                    help='Ir contra el SiGeS de verdad (por defecto va al simulador)')
    ap.add_argument('--lento', action='store_true',
                    help='Pausas entre campo y campo, para que se vea en una demo')
    ap.add_argument('--sin-ventana', action='store_true',
                    help='Sin mostrar el navegador (más rápido, no sirve para demostrar)')
    args = ap.parse_args()

    # --- Primero limpiar. Solo se carga lo que pasó el control. -------------
    ruta = args.csv if pathlib.Path(args.csv).is_absolute() or pathlib.Path(args.csv).exists() \
        else str(AQUI / args.csv)
    if ruta.lower().endswith('.xlsx'):
        filas = planilla_google.leer(ruta, args.desde, args.hasta, args.hoja)
    elif args.desde or args.hasta:
        sys.exit('--desde/--hasta necesitan la planilla en .xlsx '
                 '(Archivo → Descargar → Microsoft Excel).')
    else:
        filas = None
    listos = normalizar.main(ruta, filas)
    if not listos:
        print('No hay nadie para cargar. Fin.')
        return

    destino = args.real or SIMULADOR

    if args.real:
        # Freno a mano. Cargar en el sistema del Ministerio no puede pasar por
        # accidente ni por tener una terminal abierta de ayer.
        print('\n' + '=' * 62)
        print('  ⚠️  ESTO VA CONTRA EL SISTEMA REAL DEL MINISTERIO')
        print('=' * 62)
        print(f'  Destino : {destino}')
        print(f'  Personas: {len(listos)}')
        print('\n  Cómo es contra el sistema real:')
        print('   · Iniciá sesión vos en el navegador que se va a abrir.')
        print('   · De cada persona, vos buscás el DNI y abrís "Agregar estudiante".')
        print('   · El bot completa lo que sabe y para. NO guarda.')
        print('   · Dirección, Vivienda y Contacto los completás vos: no están relevados.')
        print('   · Salud, discapacidad y restricción judicial el bot NO los toca nunca.')
        print('   · Guardás vos, y la matrícula la genera una persona: quedan pre inscriptos.')
        if input('\n  Escribí CARGAR para continuar: ').strip() != 'CARGAR':
            print('  Cancelado. No se tocó nada.')
            return

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=args.sin_ventana)
        page = navegador.new_page()
        page.goto(destino)

        if args.real:
            input('\n  Iniciá sesión y navegá hasta el trayecto. '
                  'Cuando esté listo, apretá Enter acá... ')

        print(f'\n{"=" * 62}\nCargando {len(listos)} persona(s) en '
              f'{"el SiGeS REAL" if args.real else "el simulador"}\n{"=" * 62}')

        bien, mal = 0, []
        for i, datos in listos:
            quien = f'{datos["apellidos"]}, {datos["nombres"]}'
            if args.real:
                # Contra el sistema real, cada persona empieza con una mano
                # humana: buscar el DNI y abrir "Agregar estudiante". El bot
                # completa un formulario que ya está en pantalla.
                print(f'\n  fila {i:>3}  {quien}  (DNI {datos["dni"]})')
                input('    Buscá ese DNI, abrí "Agregar estudiante" y apretá Enter... ')
                print(f'    completando…', end=' ', flush=True)
            else:
                print(f'  fila {i:>3}  {quien:<38}', end=' ', flush=True)
            try:
                if args.real:
                    pausa = (lambda: time.sleep(0.35)) if args.lento else (lambda: None)
                    ok, detalle = siges_real.completar(page, datos, pausa)
                else:
                    ok, detalle = cargar_una(page, datos, lento=0.35 if args.lento else 0)
            except Exception as e:                      # noqa: BLE001
                ok, detalle = False, f'{type(e).__name__}: {e}'
            if ok and args.real:
                bien += 1
                print(f'✅ {detalle}')
                input('    Revisá, completá eso y apretá "Guardar estudiante" vos. Enter para seguir... ')
            elif ok:
                bien += 1
                print('✅')
            else:
                mal.append((quien, detalle))
                print(f'⛔ {detalle}')

        print(f'\n{"=" * 62}')
        etiqueta = 'Completados' if args.real else 'Cargados'
        print(f'  {etiqueta}: {bien}    Con problema: {len(mal)}')
        for quien, detalle in mal:
            print(f'   · {quien}: {detalle}')
        print('=' * 62)

        if not args.sin_ventana:
            input('\nEnter para cerrar el navegador... ')
        navegador.close()


if __name__ == '__main__':
    sys.exit(main())
