# ─────────────────────────────────────────────────────────────────────
#  alumno.py  —  ESTE ES EL ARCHIVO DE USTEDES
# ─────────────────────────────────────────────────────────────────────
#
#  Es la misma clase Alumno del miércoles, con más datos. Y aprende una
#  cosa nueva: decir si está listo para cargarse en el SiGeS o no.
#
#  Van completando problemas() de a un control por vez, igual que en la
#  página de la clase. Cada control que agregan es un alumno con datos
#  rotos que el bot deja de cargar.
# ─────────────────────────────────────────────────────────────────────

from datetime import date

from ayudas import leer_fecha


class Alumno:
    def __init__(self, dni, apellidos, nombres, fecha_nacimiento, celular, nacionalidad, domicilio):
        self.dni = dni
        self.apellidos = apellidos
        self.nombres = nombres
        self.fecha_nacimiento = fecha_nacimiento
        self.celular = celular
        self.nacionalidad = nacionalidad
        self.domicilio = domicilio

    def nombre_completo(self):
        return f"{self.apellidos}, {self.nombres}"

    def problemas(self):
        """Devuelve la lista de motivos por los que NO se puede cargar.

        Si la lista vuelve vacía, el alumno está listo.
        """
        lista = []

        # 1. El DNI: solo números, y que tenga 7 u 8


        # 2. La fecha de nacimiento: que se entienda, y que no esté en el futuro
        #    (leer_fecha devuelve la fecha, o None si no la entiende)


        # 3. El celular: 10 números. Ojo, hay quien lo escribe con espacios


        # 4. La nacionalidad: que no esté vacía ni diga "Completar"


        # 5. El domicilio: que no sea el DNI pegado en la columna equivocada


        return lista

    def esta_listo(self):
        # Está listo si no tiene ningún problema.
        pass
