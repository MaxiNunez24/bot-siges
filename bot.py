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
import motor

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

    if args.real:
        # Freno a mano. Cargar en el sistema del Ministerio no puede pasar por
        # accidente ni por tener una terminal abierta de ayer.
        print('\n' + '=' * 62)
        print('  ⚠️  ESTO VA CONTRA EL SISTEMA REAL DEL MINISTERIO')
        print('=' * 62)
        print(f'  Destino : {args.real}')
        print(f'  Personas: {len(listos)}')
        print('\n  Cómo es contra el sistema real:')
        print('   · Iniciá sesión vos en el navegador que se va a abrir.')
        print('   · El bot busca cada DNI, abre "Agregar estudiante", completa y para.')
        print('   · Lo marcado en amarillo lo completás vos. "Guardar estudiante" y la')
        print('     encuesta, también vos. Salud, discapacidad y restricción judicial')
        print('     el bot NO los toca nunca. La matrícula la genera una persona.')
        if input('\n  Escribí CARGAR para continuar: ').strip() != 'CARGAR':
            print('  Cancelado. No se tocó nada.')
            return
        # El mismo motor que usa la aplicación de ventanas (app.py), con las
        # opciones que se guardaron ahí (configuracion.json).
        ajustes = motor.cargar_ajustes()
        ajustes.update(url=args.real, simulador=False, demo=False, lento=args.lento)
        motor.correr(listos, ajustes, Consola())
        return

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=args.sin_ventana)
        page = navegador.new_page()
        page.goto(SIMULADOR)
        print(f'\n{"=" * 62}\nCargando {len(listos)} persona(s) en el simulador\n{"=" * 62}')

        bien, mal = 0, []
        for i, datos in listos:
            quien = f'{datos["apellidos"]}, {datos["nombres"]}'
            print(f'  fila {i:>3}  {quien:<38}', end=' ', flush=True)
            try:
                ok, detalle = cargar_una(page, datos, lento=0.35 if args.lento else 0)
            except Exception as e:                      # noqa: BLE001
                ok, detalle = False, f'{type(e).__name__}: {e}'
            if ok:
                bien += 1
                print('✅')
            else:
                mal.append((quien, detalle))
                print(f'⛔ {detalle}')

        print(f'\n{"=" * 62}')
        print(f'  Cargados: {bien}    Con problema: {len(mal)}')
        for quien, detalle in mal:
            print(f'   · {quien}: {detalle}')
        print('=' * 62)

        if not args.sin_ventana:
            input('\nEnter para cerrar el navegador... ')
        navegador.close()


class Consola:
    """El `ui` del motor, en la terminal: lo que la ventana muestra con botones,
    acá es un print y un Enter."""

    def contar(self, texto, tipo='info'):
        print(texto)

    def progreso(self, hechos, total, quien):
        pass

    def esperar(self, mensaje, boton):
        input(f'\n  {mensaje}\n  [{boton}: Enter] ')

    def preguntar(self, pregunta):
        return input(f'  {pregunta} (s/n) ').strip().lower().startswith('s')


if __name__ == '__main__':
    sys.exit(main())
