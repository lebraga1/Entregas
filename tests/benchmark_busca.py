import statistics
import time

import numpy as np

from src.busca_espaco import (
    construir_indice,
    buscar_prefixos_vizinhos,
    PRECISAO_INDICE,
    distancia_km
)
from src.geohash import geohash

# Coordenada do centro de BH
CENTRO = (-19.9191, -43.9386)


def gerar_entregadores(quantidade, seed=3):
    random = np.random.default_rng(seed)
    lat0, lon0 = CENTRO
    entregadores = []

    for i in range(quantidade):
        lat = float(lat0 + random.normal(0, 0.04))
        lon = float(lon0 + random.normal(0, 0.04))

        entregadores.append({
            "id": f"e{i}",
            "lat": lat,
            "lon": lon,
            "geohash": geohash((lat, lon), precision=8),
        })

    return entregadores


def busca_exaustiva(frota, centro, raio_km):
    lat_c, lon_c = centro
    encontrados = []

    for entregador in frota:
        distancia = distancia_km(
            lat_c,
            lon_c,
            entregador["lat"],
            entregador["lon"],
        )

        if distancia <= raio_km:
            encontrados.append(entregador["id"])

    return encontrados


def busca_trie(indice, centro, raio_km):
    lat_c, lon_c = centro

    prefixos = buscar_prefixos_vizinhos(
        centro,
        raio_km,
        precision=PRECISAO_INDICE,
    )

    ids_candidatos = set()

    for prefixo in prefixos:
        ids_candidatos.update(
            indice["trie"].search_prefix(prefixo)
        )

    encontrados = []

    for identificador in ids_candidatos:
        entregador = indice["por_id"].get(identificador)

        if entregador is None:
            continue

        distancia = distancia_km(
            lat_c,
            lon_c,
            entregador["lat"],
            entregador["lon"],
        )

        if distancia <= raio_km:
            encontrados.append(identificador)

    return encontrados


def medir(funcao, repeticoes):
    tempos = []
    resultado = None

    # Cold start
    funcao()

    for _ in range(repeticoes):
        inicio = time.perf_counter()
        resultado = funcao()
        tempos.append(time.perf_counter() - inicio)

    return tempos, resultado


def executar(quantidades, repeticoes, raio_km, centro=CENTRO):
    print("\n=== Benchmark de consulta espacial ===")
    print(f"Centro: {centro}")
    print(f"Raio: {raio_km:.2f} km")
    print(f"Repetições: {repeticoes}")
    print("Rotas viárias e ETA: não calculados")

    for quantidade in quantidades:
        entregadores = gerar_entregadores(quantidade)

        indice = construir_indice(entregadores)

        tempos_trie, resultado_trie = medir(lambda: busca_trie(indice, centro, raio_km), repeticoes)

        tempos_exaustivos, resultado_exaustivo = medir(lambda: busca_exaustiva(entregadores, centro, raio_km), repeticoes)

        mediana_trie = statistics.median(tempos_trie)
        mediana_exaustiva = statistics.median(tempos_exaustivos)

        speedup = mediana_exaustiva / mediana_trie

        ids_trie = set(resultado_trie)
        ids_exaustivos = set(resultado_exaustivo)
        corretos = ids_trie == ids_exaustivos

        print(f"\n {quantidade:,} entregadores")
        print(f"Candidatos retornados pela Trie: {len(ids_trie)}")
        print(f"Resultados da busca exaustiva: {len(ids_exaustivos)}")
        print(f"Equivalentes: {'SIM' if corretos else 'NÃO'}")
        print(f"Consulta com Trie: {mediana_trie * 1000:.3f} ms")
        print(f"Consulta exaustiva: "f"{mediana_exaustiva * 1000:.3f} ms")
        print(f"Speedup da Trie: {speedup:.2f}x")


if __name__ == "__main__":
    executar([1000, 5000, 10000, 20000, 50000], 10, 2.0)
