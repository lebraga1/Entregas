from math import floor, cos, radians, sqrt

from src.geohash import geohash_celula
from src.gera_entregadores import estimar_rota
from src.trie import CompactTrie

PRECISAO_INDICE = 6
PRECISAO_MAXIMA = 8


def construir_indice(entregadores, precision=PRECISAO_INDICE):
    """Cria uma Trie para localizar entregadores por Geohash."""

    if not isinstance(precision, int) or isinstance(precision, bool):
        raise ValueError("A precisão deve ser um inteiro.")
    if not 1 <= precision <= PRECISAO_MAXIMA:
        raise ValueError(f"A precisão deve estar entre 1 e {PRECISAO_MAXIMA}.")

    trie = CompactTrie()
    por_id = {}

    for entregador in entregadores:
        trie.insert(entregador["geohash"], entregador["id"])
        por_id[entregador["id"]] = entregador

    # A Trie localiza os IDs e o dicionário recupera os dados completos
    return {"trie": trie, "por_id": por_id, "precision": precision}


def buscar_prefixos_vizinhos(centro, raio_km, precision=PRECISAO_INDICE):
    """Encontra células Geohash que podem conter pontos dentro do raio."""

    if raio_km < 0:
        raise ValueError("O raio deve ser não negativo.")
    if not isinstance(precision, int) or isinstance(precision, bool):
        raise ValueError("A precisão deve ser um inteiro.")
    if not 1 <= precision <= PRECISAO_MAXIMA:
        raise ValueError(f"A precisão deve estar entre 1 e {PRECISAO_MAXIMA}.")

    lat, lon = centro

    # Converte o raio de quilômetros em margens aproximadas de latitude e longitude.
    margem_lat = 1.01 * raio_km / 110.574
    margem_lon = 1.01 * raio_km / (111.320 * max(abs(cos(radians(lat))), 0.01))

    lat_min = max(-90, lat - margem_lat)
    lat_max = min(90, lat + margem_lat)
    lon_min = max(-180, lon - margem_lon)
    lon_max = min(180, lon + margem_lon)

    # Cada caractere Geohash representa 5 bits de informação espacial.
    total_bits = precision * 5
    bits_lon = (total_bits + 1) // 2
    bits_lat = total_bits // 2

    # Divide o globo em linhas e colunas de células Geohash.
    altura = 180 / (2**bits_lat)
    largura = 360 / (2**bits_lon)

    # A folga de 1% na caixa já cobre as bordas; não precisa de uma célula extra.
    linha_min = max(0, floor((lat_min + 90) / altura))
    linha_max = min(2**bits_lat - 1, floor((lat_max + 90) / altura))
    coluna_min = max(0, floor((lon_min + 180) / largura))
    coluna_max = min(2**bits_lon - 1, floor((lon_max + 180) / largura))

    prefixos = set()

    for linha in range(linha_min, linha_max + 1):
        for coluna in range(coluna_min, coluna_max + 1):
            prefixos.add(geohash_celula(linha, coluna, precision))

    return prefixos


def buscar_ids_candidatos(indice, prefixos):
    """Busca os IDs associados a qualquer um dos prefixos."""

    return indice["trie"].search_prefixes(prefixos)


def distancia_km(lat1, lon1, lat2, lon2):
    """Estima a distância em linha reta, em quilômetros."""
    delta_lat = (lat2 - lat1) * 111.32
    lat_media = radians((lat1 + lat2) / 2)
    delta_lon = (lon2 - lon1) * 111.32 * cos(lat_media)

    return sqrt(delta_lat**2 + delta_lon**2)


def buscar_entregadores(frota, restaurante, raio_km, indice=None):
    """Filtra entregadores por distância e ordena pelo tempo de rota."""

    raio_km = float(raio_km)

    if raio_km < 0:
        raise ValueError("O raio deve ser não negativo.")

    lat_rest = float(restaurante["lat"])
    lon_rest = float(restaurante["lon"])

    if indice is None:
        # Sem índice, verifica todos os entregadores para busca exaustiva
        candidatos = frota
    else:
        # A Trie reduz a busca aos entregadores das células próximas
        precision = indice["precision"]
        prefixos = buscar_prefixos_vizinhos((lat_rest, lon_rest), raio_km, precision)
        ids = buscar_ids_candidatos(indice, prefixos)

        candidatos = []
        for identificador in ids:
            if identificador in indice["por_id"]:
                candidatos.append(indice["por_id"][identificador])

    encontrados = []

    if not candidatos:
        return encontrados

    # calcula rota e distância
    for entregador in candidatos:
        lat = float(entregador["lat"])
        lon = float(entregador["lon"])

        # Elimina pontos fora do raio antes de calcular uma rota mais cara
        if distancia_km(lat_rest, lon_rest, lat, lon) > raio_km:
            continue

        # Do entregador até o restaurante: o grafo é dirigido (ruas de mão única).
        rota = estimar_rota(lat, lon, lat_rest, lon_rest)

        # Ignora pontos para os quais não foi possível estimar uma rota
        if rota is None:
            continue

        resultado = dict(entregador)
        resultado["distance"] = rota["distance"]
        resultado["eta_minutes"] = rota["eta_minutes"]
        encontrados.append(resultado)

    # Menor eta significa menor tempo estimado de entrega
    encontrados.sort(key=lambda item: item["eta_minutes"])

    return encontrados

