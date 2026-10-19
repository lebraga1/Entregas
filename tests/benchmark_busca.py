
"""Benchmark de consulta espacial: Trie compacta vs. busca exaustiva.

Execute com:
    python -m tests.benchmark_busca_espacial \
        --quantidades 1000 5000 10000 20000 50000 \
        --repeticoes 10 --raio 2
"""

import argparse
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


CENTRO = (-19.9191, -43.9386)


def gerar_frota(quantidade, seed=3):
    """Gera uma frota sintética sem carregar o grafo viário."""
    rng = np.random.default_rng(seed)
    lat0, lon0 = CENTRO
    frota = []

    for i in range(quantidade):
        lat = float(lat0 + rng.normal(0, 0.04))
        lon = float(lon0 + rng.normal(0, 0.04))

        frota.append({
            "id": f"e{i}",
            "lat": lat,
            "lon": lon,
            "geohash": geohash((lat, lon), precision=8),
        })

    return frota


def consulta_exaustiva(frota, centro, raio_km):
    """Examina toda a frota e filtra pela distância em linha reta."""
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


def consulta_trie(indice, centro, raio_km):
    """Usa a Trie para selecionar candidatos e filtra por distância."""
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
    """Retorna os tempos individuais e o resultado da última execução."""
    tempos = []
    resultado = None

    # Aquecimento fora das medições
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
        frota = gerar_frota(quantidade)

        # A construção do índice fica fora da medição.
        indice = construir_indice(frota)

        tempos_trie, resultado_trie = medir(
            lambda: consulta_trie(indice, centro, raio_km),
            repeticoes,
        )

        tempos_exaustivos, resultado_exaustivo = medir(
            lambda: consulta_exaustiva(frota, centro, raio_km),
            repeticoes,
        )

        mediana_trie = statistics.median(tempos_trie)
        mediana_exaustiva = statistics.median(tempos_exaustivos)

        speedup = (
            mediana_exaustiva / mediana_trie
            if mediana_trie > 0
            else float("inf")
        )

        ids_trie = set(resultado_trie)
        ids_exaustivos = set(resultado_exaustivo)
        corretos = ids_trie == ids_exaustivos

        print(f"\n--- Frota: {quantidade:,} entregadores ---")
        print(f"Candidatos retornados pela Trie: {len(ids_trie)}")
        print(f"Resultados da busca exaustiva: {len(ids_exaustivos)}")
        print(f"Resultados idênticos: {'SIM' if corretos else 'NÃO'}")
        print(f"Consulta com Trie: {mediana_trie * 1000:.3f} ms")
        print(
            f"Consulta exaustiva: "
            f"{mediana_exaustiva * 1000:.3f} ms"
        )
        print(f"Speedup da Trie: {speedup:.2f}x")

        if not corretos:
            ausentes = ids_exaustivos - ids_trie
            extras = ids_trie - ids_exaustivos
            print(f"Resultados ausentes na Trie: {len(ausentes)}")
            print(f"Resultados extras na Trie: {len(extras)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Benchmark isolado de consulta espacial."
    )
    parser.add_argument(
        "--quantidades",
        nargs="+",
        type=int,
        default=[1000, 5000, 10000, 20000, 50000],
    )
    parser.add_argument("--repeticoes", type=int, default=10)
    parser.add_argument("--raio", type=float, default=2.0)

    args = parser.parse_args()

    if any(q <= 0 for q in args.quantidades):
        parser.error("Todas as quantidades devem ser positivas.")
    if args.repeticoes <= 0:
        parser.error("O número de repetições deve ser positivo.")
    if args.raio < 0:
        parser.error("O raio não pode ser negativo.")

    executar(args.quantidades, args.repeticoes, args.raio)
