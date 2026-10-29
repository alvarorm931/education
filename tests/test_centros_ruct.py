from pathlib import Path

from motor.estudios import centros_ruct as c

F = Path(__file__).parent / "fixtures" / "ruct"


def L(n):
    return (F / n).read_bytes().decode("latin-1")


def test_lista_universidades_y_grupos():
    u = c.lista_universidades(L("consulta_universidades.html"))
    codigos = {x["codigo"]: x for x in u}
    assert len(u) == 109
    assert codigos["025"]["grupo"] == "universidad"
    assert codigos["091"]["grupo"] == "extranjero_autorizado"
    assert codigos["099"]["grupo"] == "ensenanzas_artisticas_superiores"
    assert codigos["086"]["grupo"] == "defensa"


def test_ficha_universidad():
    u = c.parsear_universidad(L("universidad_025.html"))
    assert (u["acronimo"], u["tipo"], u["web"], u["animo_de_lucro"]) == ("UPM", "Pública", "https://www.upm.es", "No")


def test_ficha_centro():
    x = c.parsear_centro(L("centro_28026870.html"))
    assert x["vinculacion"] == "Propio" and x["municipio"] == "Madrid" and x["web"] == "https://www.aq.upm.es/"


def test_centros_y_paginacion_de_lista():
    html = ('<a href="/ruct/centro.action;jsessionid=AB12?codigoUniversidad=091&amp;codigoCentro=28059999&amp;actual=centros">'
            'EU Business School</a><a href="/ruct/universidadcentros.action?codigoUniversidad=091&amp;d-123-p=2">2</a>')
    assert c.centros_de_lista(html) == [{"codigo": "28059999", "nombre": "EU Business School"}]
    assert c.paginas_siguientes(html) == ["/ruct/universidadcentros.action?codigoUniversidad=091&d-123-p=2"]
