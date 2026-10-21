from math import floor, cos, radians

from src.geohash import geohash
from src.trie import CompactTrie
from math import radians, sin, cos, asin, sqrt
from src.gera_entregadores import estimar_rota

PRECISAO_INDICE = 5


def construir_indice(entregadores):
    """Constrói uma Trie e o mapa de IDs para a frota atual."""
    trie = CompactTrie()
    por_id = {}
    for entregador in entregadores:
        trie.insert(entregador["geohash"], entregador["id"])
        por_id[entregador["id"]] = entregador
    return {"trie": trie, "por_id": por_id}


def buscar_prefixos_vizinhos(centro, raio_km, precision=PRECISAO_INDICE):
    """Retorna as células Geohash que cobrem a caixa do raio de busca."""
    if raio_km < 0:
        raise ValueError("O raio deve ser não negativo.")
    lat, lon = centro
    margem_lat = raio_km / 110.574
    margem_lon = raio_km / (111.320 * max(abs(cos(radians(lat))), 0.01))
    lat_min = max(-90.0, lat - margem_lat)
    lat_max = min(90.0, lat + margem_lat)
    lon_min = max(-180.0, lon - margem_lon)
    lon_max = min(180.0, lon + margem_lon)

    total_bits = precision * 5
    bits_lon = (total_bits + 1) // 2
    bits_lat = total_bits // 2
    altura = 180.0 / (2**bits_lat)
    largura = 360.0 / (2**bits_lon)

    linha_min = max(0, floor((lat_min + 90.0) / altura) - 1)
    linha_max = min(2**bits_lat - 1, floor((lat_max + 90.0) / altura) + 1)
    coluna_min = max(0, floor((lon_min + 180.0) / largura) - 1)
    coluna_max = min(2**bits_lon - 1, floor((lon_max + 180.0) / largura) + 1)

    prefixos = set()
    for linha in range(linha_min, linha_max + 1):
        for coluna in range(coluna_min, coluna_max + 1):
            lat_centro = -90.0 + (linha + 0.5) * altura
            lon_centro = -180.0 + (coluna + 0.5) * largura
            prefixos.add(geohash((lat_centro, lon_centro), precision))
    return prefixos


def distancia_km(lat1, lon1, lat2, lon2):
    delta_lat = (lat2 - lat1) * 111.32
    delta_lon = (lon2 - lon1) * 111.32 * 0.94

    return sqrt(delta_lat**2 + delta_lon**2)


def buscar_entregadores(
    frota,
    restaurante,
    raio_km,
    indice=None,
):
    """Busca candidatos pelo Geohash e calcula distância e ETA pela rede viária."""
    raio_km = float(raio_km)

    if raio_km < 0:
        raise ValueError("O raio deve ser não negativo.")

    lat_rest = float(restaurante["lat"])
    lon_rest = float(restaurante["lon"])

    # Usa a Trie para obter candidatos nas células Geohash vizinhas.
    if indice is not None:
        prefixos = buscar_prefixos_vizinhos(
            (lat_rest, lon_rest),
            raio_km,
        )

        ids_candidatos = set()

        for prefixo in prefixos:
            ids_candidatos.update(indice["trie"].search_prefix(prefixo))

        candidatos = [
            indice["por_id"][identificador]
            for identificador in ids_candidatos
            if identificador in indice["por_id"]
        ]
    else:
        # Alternativa sem índice, útil para testes.
        candidatos = frota

    encontrados = []

    for entregador in candidatos:
        lat = float(entregador["lat"])
        lon = float(entregador["lon"])

        # Confirma o raio com distância geográfica exata.
        distancia_direta = distancia_km(
            lat_rest,
            lon_rest,
            lat,
            lon,
        )

        if distancia_direta > raio_km:
            continue

        # Calcula a rota viária apenas para os resultados relevantes.
        # rota do entregador até o restaurante
        rota = estimar_rota(
            lat,
            lon,
            lat_rest,
            lon_rest,
        )

        if rota is None:
            continue

        resultado = dict(entregador)
        resultado["distance"] = rota["distance"]
        resultado["eta_minutes"] = rota["eta_minutes"]
        encontrados.append(resultado)

    encontrados.sort(key=lambda item: item["eta_minutes"])

    return encontrados
