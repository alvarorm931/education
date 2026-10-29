from motor.estudios import cobertura


def test_medir_por_capas():
    listas = {"l": {"dominios": ["a.es", "b.com", "c.es", "a.es"]}}
    censo = {"a.es": {"id": "prov-a"}, "b.com": {"id": "prov-b"}}
    m = cobertura.medir(listas, cc={"a.es"}, censo=censo, verificados={"prov-a"})["l"]
    assert m == {"total": 3, "en_commoncrawl": 1, "en_censo": 2, "verificados": 1,
                 "faltan_en_censo": ["c.es"], "sin_verificar": ["b.com"]}


def test_referencia_bien_formada():
    import json
    d = json.loads(cobertura.REFERENCIA.read_text(encoding="utf-8"))
    assert all(v["origen"] and v["dominios"] for v in d["listas"].values())
