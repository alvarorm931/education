"""RUCT para grados: ficha y memoria de cada grado, con las mismas piezas de lectura que los másters.

Reutiliza sin modificarlos los parsers de motor/estudios/ruct.py (ficha, memoria, centros, materias y
asignaturas). Lo que cambia aquí:
  - el tipo de estudio en la URL de la ficha es «G» (grado) en lugar de «M»;
  - cada petición pasa por el robots.txt del servidor (motor.http.comprobar_robots), como el resto del motor; el
    lector de másters abre su propia sesión y no lo comprueba;
  - los originales van al archivo con la política del motor (solo huella en la rama pública; enteros en el
    almacén privado con MOTOR_ORIGINALES=s3), porque la rama sondas es pública;
  - la memoria de un grado (240 créditos) tiene muchas más páginas que la de un máster: límite de 900.

Uso:
  python -m motor.grados.ruct_grados --codigos 2500094,1500045 --nivel memoria --salida ruta/
  python -m motor.grados.ruct_grados --muestra 24 --catalogo …/catalogo.jsonl --nivel ficha --salida ruta/
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

from motor.archivo import Archivo, solo_huella_por_defecto
from motor.estudios import ruct
from motor.http import ROBOTS_ESTADO, RobotsProhibe, _origen, comprobar_robots, robots_de

TIPO_GRADO = "G"
MAX_PAGINAS = 900
PAUSA_CORTE = 120   # segundos de espera cuando el servidor deja de responder
PAUSAS_MAX = 5

# Registro público por norma: «tendrá carácter público y de registro administrativo» (RD 1509/2008, art. 1.1) y «la
# consulta al RUCT será pública» (art. 7). Su robots.txt no responde (30/10/2026: tiempo agotado desde GitHub, «Empty
# reply from server» desde el servidor de España), y la RFC 9309 manda tratar eso como prohibido. Excepción, igual
# que los boletines oficiales: solo en estas rutas y SOLO mientras robots.txt no se pueda leer; si un día responde,
# manda lo que diga. Una petición por segundo, identificada, desde los ejecutores de GitHub.
REGISTRO_PUBLICO = "https://www.educacion.gob.es/ruct/"
DECISION_RUCT = ("Claude, por mandato de Álvaro del 30/10/2026 a las 02:51 («de mí nada, sigue, hay que sacar toda la "
                 "info»), con el mismo criterio que los boletines oficiales", "2026-10-30")


class LectorConRobots(ruct.Lector):
    """El lector del RUCT con la comprobación de robots.txt antes de cada petición."""

    def __init__(self, archivo, pausa: float = ruct.PAUSA):
        super().__init__(archivo, pausa)
        self.prohibidas = 0
        self.robots_error: str | None = None
        self.excepcion_registro = 0

    def get(self, url: str, intentos: int = 3):
        try:
            comprobar_robots(url, self.s)
        except RobotsProhibe as e:
            if url.startswith(REGISTRO_PUBLICO) and robots_de(url, self.s).todo_prohibido:
                self.excepcion_registro += 1  # robots.txt ilegible, no una prohibición escrita
            else:
                self.prohibidas += 1
                self.robots_error = str(e)[:300]
                return 0, "", None
        return super().get(url, intentos)

    def estado_robots(self) -> str | None:
        return ROBOTS_ESTADO.get(_origen(REGISTRO_PUBLICO))


def muestra(catalogo: list[dict], n: int, semilla: int) -> list[str]:
    """Grados activos al azar por estratos: públicas y privadas a partes iguales, y en cada una un sexto con
    memoria del formato RD 822/2021 (códigos 15xxxxx, el 8,5 % de los activos), que es distinto del anterior.
    Más 2 dobles grados para comprobar si el RUCT tiene ficha de los códigos 70xxxxx."""
    rnd = random.Random(semilla)
    activos = [t for t in catalogo if t["situacion"] == "Activo"]
    salida = []
    for tipo in ("Pública", "Privada"):
        mitad = n // 2 if tipo == "Pública" else n - n // 2
        nuevos = max(1, mitad // 6)
        for regimen, cuantos in (("RD 822/2021", nuevos), ("RD 1393/2007", mitad - nuevos)):
            grupo = [t["codigo"] for t in activos if t["clase"] == "grado" and t["universidad_tipo"] == tipo
                     and t["regimen"] == regimen]
            salida += rnd.sample(grupo, min(cuantos, len(grupo)))
    dob = [t["codigo"] for t in activos if t["clase"] == "doble"]
    return salida + rnd.sample(dob, 2)


def resumen_memoria(m: dict) -> dict:
    materias = [x for b in m.get("plan", []) for x in b.get("materias", [])]
    asignaturas = [a for x in materias for a in x.get("asignaturas", [])]
    hojas = asignaturas or materias
    return {
        "paginas": m.get("paginas"),
        "modulos": len(m.get("plan", [])),
        "materias": len(materias),
        "asignaturas": len(asignaturas),
        "ects_hojas": round(sum(h.get("ects") or 0 for h in hojas), 1),
        "con_caracter": sum(1 for h in hojas if h.get("caracter")),
        "con_despliegue": sum(1 for h in hojas if h.get("despliegue")),
        "materias_con_evaluacion": sum(1 for x in materias if x.get("evaluacion")),
        "materias_con_actividades": sum(1 for x in materias if x.get("actividades")),
        "materias_con_contenidos": sum(1 for x in materias if x.get("contenidos")),
        "centros": len(m.get("centros", [])),
        "centros_con_plazas": sum(1 for c in m.get("centros", []) if c.get("plazas_total")),
        "acceso_caracteres": sum(len(t) for t in m.get("acceso", {}).get("textos", [])),
        "avisos": len(m.get("avisos", [])),
    }


def ejecutar(codigos: list[str], raiz: Path, nivel: str, max_minutos: float) -> dict:
    archivo = Archivo(raiz / "archivo", indice_por_fuente=True, solo_huella=solo_huella_por_defecto())
    lector = LectorConRobots(archivo)
    destino = raiz / "datos" / "estudios" / "grados" / "ruct"
    destino.mkdir(parents=True, exist_ok=True)
    fin = time.time() + max_minutos * 60
    hechos, errores, seguidos, alerta, pausas = 0, Counter(), 0, None, 0
    resumenes = {}
    pendientes = list(codigos)
    recientes_fallidos: list[str] = []
    while pendientes:
        codigo = pendientes.pop(0)
        if time.time() > fin:
            alerta = f"tiempo agotado: quedan {len(pendientes) + 1} códigos"
            break
        ficha = ruct.leer_ficha(lector, codigo, tipo=TIPO_GRADO)
        if lector.prohibidas:
            alerta = f"robots.txt: {lector.robots_error}"
            print(f"ALERTA RUCT (grados): {alerta}", file=sys.stderr)
            break
        seguidos = seguidos + 1 if "estado 0" in ficha.get("error", "") else 0
        if seguidos >= 3:
            # El RUCT tiene cortes de minutos desde GitHub: se espera y se sigue; solo se para si no vuelve
            pausas += 1
            if pausas > PAUSAS_MAX:
                alerta = f"el servidor no responde tras {PAUSAS_MAX} pausas de {PAUSA_CORTE} s; ejecución detenida"
                print(f"ALERTA RUCT (grados): {alerta}", file=sys.stderr)
                break
            recientes_fallidos.append(codigo)
            pendientes.extend(c for c in recientes_fallidos if c not in pendientes)
            recientes_fallidos.clear()
            seguidos = 0
            time.sleep(PAUSA_CORTE)
            continue
        if "estado 0" in ficha.get("error", ""):
            recientes_fallidos.append(codigo)
            continue
        pausas = 0
        if "error" in ficha:
            errores[ficha["error"]] += 1
        elif nivel == "memoria":
            ficha["memoria"] = ruct.leer_memoria(lector, ficha, max_paginas=MAX_PAGINAS)
            resumenes[codigo] = resumen_memoria(ficha["memoria"])
        (destino / f"{codigo}.json").write_text(json.dumps(ficha, ensure_ascii=False, indent=1), encoding="utf-8")
        hechos += 1
    if recientes_fallidos:
        errores["sin respuesta del servidor"] += len(recientes_fallidos)
    res = {"pedidos": len(codigos), "hechos": hechos, "errores": dict(errores), "peticiones": lector.peticiones,
           "alerta": alerta, "robots_txt": lector.estado_robots(),
           "peticiones_por_excepcion_de_registro_publico": lector.excepcion_registro,
           "decision_excepcion": DECISION_RUCT if lector.excepcion_registro else None, "memorias": resumenes}
    (destino / f"resumen-{int(time.time())}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                               encoding="utf-8")
    return res


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--codigos", help="códigos separados por comas")
    p.add_argument("--codigos-fichero", help="fichero con un código por línea")
    p.add_argument("--desde", type=int, default=0)
    p.add_argument("--hasta", type=int)
    p.add_argument("--catalogo", help="catalogo.jsonl de grados (con --muestra)")
    p.add_argument("--muestra", type=int, default=0)
    p.add_argument("--semilla", type=int, default=20261030)
    p.add_argument("--nivel", choices=["ficha", "memoria"], default="ficha")
    p.add_argument("--max-minutos", type=float, default=50)
    p.add_argument("--salida", required=True)
    a = p.parse_args()
    if a.codigos_fichero:
        codigos = Path(a.codigos_fichero).read_text(encoding="utf-8").split()[a.desde:a.hasta]
    elif a.codigos:
        codigos = [c.strip() for c in a.codigos.split(",") if c.strip()]
    elif a.catalogo and a.muestra:
        cat = [json.loads(x) for x in Path(a.catalogo).read_text(encoding="utf-8").splitlines() if x.strip()]
        codigos = muestra(cat, a.muestra, a.semilla)
    else:
        sys.exit("Falta --codigos o --catalogo con --muestra")
    print(json.dumps(ejecutar(codigos, Path(a.salida), a.nivel, a.max_minutos), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
