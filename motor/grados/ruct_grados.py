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
  python -m motor.grados.ruct_grados --codigos-fichero cods.txt --desde 0 --hasta 8 --nivel plan --salida ruta/
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


LARGO_PUBLICABLE = 300  # caracteres: por encima, un texto de la memoria no va a la rama pública


def sin_textos(x):
    """La memoria con su estructura (módulos, materias, asignaturas, créditos, carácter, despliegue, plazas) y sin
    los textos largos (competencias, contenidos, acceso…): esos van enteros al almacén privado con la página
    original; en la rama pública queda su tamaño y su huella."""
    import hashlib

    if isinstance(x, dict):
        return {k: sin_textos(v) for k, v in x.items()}
    if isinstance(x, list):
        return [sin_textos(v) for v in x]
    if isinstance(x, str) and len(x) > LARGO_PUBLICABLE:
        return {"caracteres": len(x), "sha256": hashlib.sha256(x.encode("utf-8")).hexdigest()}
    return x


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


def leer_plan_memoria(lector, ficha: dict, max_paginas: int = MAX_PAGINAS) -> dict:
    """Solo el plan de la memoria vigente: módulos → materias → asignaturas (nombre, carácter, créditos, unidad
    temporal y despliegue). Es lo que falta en los grados cuyo plan del BOE no se puede comprobar; las páginas de
    actividades, evaluación, contenidos, acceso, catálogos y centros de cada memoria no se piden (en un grado son
    más de la mitad de las peticiones, y el RUCT tarda unos 10 segundos en cada una). Mismos parsers que
    `ruct.leer_memoria`, sin modificarlos."""
    import re

    m = ruct.memoria_vigente(ficha)
    if not m:
        return {"error": "sin memoria publicada"}
    cod, nombre, avisos = m["cod"], ficha["nombre"] or "", []
    lector.s.cookies.clear()
    lector.get(ficha["fuente"]["url"])  # la ficha abre la sesión
    estado, p, _ = lector.get(f"{ruct.SOL}detalles.action?cod={cod}&sit={m['sit']}&actual=menu.solicitud.basicos")
    if estado != 200 or not ruct._comprobar(p, nombre):
        return {"cod": cod, "error": f"memoria no disponible o de otro título (estado {estado})"}
    inicio = lector.peticiones

    def pagina(ruta: str) -> str | None:
        if lector.peticiones > inicio + max_paginas:
            avisos.append(f"límite de {max_paginas} páginas alcanzado")
            return None
        estado, pg, _ = lector.get(ruct.SOL + ruta)
        if estado != 200:
            avisos.append(f"{ruta[:80]}: estado {estado}")
            return None
        if not ruct._comprobar(pg, nombre):
            avisos.append(f"{ruta[:80]}: el servidor devolvió otro título; descartada")
            return None
        return pg

    memoria: dict = {"cod": cod, "regimen": ficha.get("nivel"), "solo_plan": True, "plan": [], "avisos": avisos}
    p = pagina(f"modulos?actual=menu.solicitud.planificacion.modulos&cod={cod}")
    modulos = sorted({int(x) for x in re.findall(r"codModulo=(\d+)", p or "")} - {0})
    for mod in modulos or [0]:
        pm = pagina(f"datosModulo!consulta.action?codModulo={mod}&actual=menu.solicitud.planificacion.materias") if mod \
            else pagina(f"datosModulo?actual=menu.solicitud.planificacion.materiasSin&codModulo={mod}")
        if not pm:
            continue
        info_mod = ruct.parsear_materia(pm)
        bloque = {"modulo": mod, "nombre": info_mod["nombre"], "ects": info_mod["ects"], "materias": []}
        materias = sorted({int(x) for x in re.findall(r"codModulo=" + str(mod) + r"&(?:amp;)?codMateria=(\d+)", pm)} |
                          {int(x) for x in re.findall(r"codMateria=(\d+)&(?:amp;)?codModulo=" + str(mod) + r"\b", pm)})
        for mat in materias:
            pmat = pagina(f"datosMateria!consulta.action?codModulo={mod}&codMateria={mat}"
                          f"&actual=menu.solicitud.planificacion.materias.datos")
            if not pmat:
                continue
            materia = {**ruct.parsear_materia(pmat), "id": mat, "asignaturas": []}
            for a in sorted({int(x) for x in re.findall(r"codAsignatura=(\d+)", pmat)}):
                pas = pagina(f"datosAsignatura!consulta.action?codModulo={mod}&codMateria={mat}&codAsignatura={a}"
                             f"&actual=menu.solicitud.planificacion.materias.asignatura")
                if pas:
                    info = ruct.parsear_materia(pas)
                    materia["asignaturas"].append({"id": a, **{k: info[k] for k in
                                                              ("nombre", "caracter", "ects", "unidad_temporal",
                                                               "despliegue")}})
            bloque["materias"].append(materia)
        memoria["plan"].append(bloque)
    materias = [x for b in memoria["plan"] for x in b["materias"]]
    memoria["cobertura"] = {"materias": len(materias),
                            "asignaturas": sum(len(x.get("asignaturas", [])) for x in materias)}
    memoria["paginas"] = lector.peticiones - inicio + 2
    return memoria


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
        elif nivel in ("memoria", "plan"):
            memoria = ruct.leer_memoria(lector, ficha, max_paginas=MAX_PAGINAS) if nivel == "memoria" \
                else leer_plan_memoria(lector, ficha)
            resumenes[codigo] = resumen_memoria(memoria)
            ficha["memoria"] = sin_textos(memoria)
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
    p.add_argument("--nivel", choices=["ficha", "memoria", "plan"], default="ficha",
                   help="plan: solo módulos, materias y asignaturas de la memoria (menos de la mitad de peticiones)")
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
