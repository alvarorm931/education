"""Las pruebas no dependen del entorno del flujo que las lanza.

Los flujos diarios (motor, textos, boletines) fijan MOTOR_ORIGINALES=s3 para todo el trabajo, y la prueba previa
(«Instalar y probar») corre con esa variable: el archivo de originales pasaba a modo S3 y las pruebas que esperan
el modo por defecto fallaban (motor del 30/10/2026 a las 08:07). Cada prueba empieza sin ella; la que la necesite,
la pone con monkeypatch.setenv.
"""
import pytest


@pytest.fixture(autouse=True)
def _sin_almacen_del_flujo(monkeypatch):
    monkeypatch.delenv("MOTOR_ORIGINALES", raising=False)
