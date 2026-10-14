# ─────────────────────────────────────────────────────────────────────
#  planilla.py  —  ESTE TAMBIÉN ES DE USTEDES
# ─────────────────────────────────────────────────────────────────────
#
#  Lee la planilla que deja el formulario de inscripción y convierte cada
#  fila en un Alumno. Acá se juntan las dos cosas: el CSV trae los datos,
#  la clase les da comportamiento.
# ─────────────────────────────────────────────────────────────────────

import csv

from alumno import Alumno


def leer_inscriptos(ruta):
    """Lee la planilla y devuelve una lista de Alumno, uno por fila."""
    inscriptos = []

    # 1. Abrir el archivo, con encoding="utf-8"
    # 2. csv.DictReader: cada fila llega como un diccionario
    #    (las claves son los títulos de la primera línea de la planilla)
    # 3. Por cada fila, crear un Alumno y agregarlo a la lista

    return inscriptos
