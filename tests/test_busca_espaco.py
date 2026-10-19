import numpy as np
import pytest

from src.busca_espaco import construir_indice, buscar_entregadores, distancia_km
from src.geohash import geohash


def test_indexed_search_matches_brute_force():
    rng = np.random.default_rng(42)
    centro = {"lat": -19.9191, "lon": -43.9386}
    entregadores = []
    for i in range(1500):
        lat = centro["lat"] + rng.normal(0, 0.04)
        lon = centro["lon"] + rng.normal(0, 0.04)
        entregadores.append({
            "id": f"e{i}",
            "lat": lat,
            "lon": lon,
            "geohash": geohash((lat, lon), precision=8),
        })

    indice = construir_indice(entregadores)
    for raio in (0.5, 2, 5):
        encontrados = buscar_entregadores(entregadores, centro, raio, indice)
        esperado = {
            e["id"] for e in entregadores
            if distancia_km(
                centro["lat"], centro["lon"],
                e["lat"], e["lon"],
            ) <= raio
        }
        assert {e["id"] for e in encontrados} == esperado
        assert all(e["distance"] <= raio for e in encontrados)


def test_empty_fleet():
    assert buscar_entregadores([], {"lat": -19.9, "lon": -43.9}, 2) == []


def test_negative_radius_is_rejected():
    with pytest.raises(ValueError):
        buscar_entregadores([], {"lat": -19.9, "lon": -43.9}, -1)
