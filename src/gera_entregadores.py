import numpy as np
import osmnx as ox

from src.geohash import geohash

_GRAFO = None
_IDS_NOS = None
_XS = None
_YS = None

def carregar_grafo():
    """Carrega a rede viária de Belo Horizonte do OpenStreetMap e calcula tempos de viagem."""
    global _GRAFO, _IDS_NOS, _XS, _YS

    if _GRAFO is None:
        ox.settings.use_cache = True

        grafo = ox.graph_from_place("Belo Horizonte, Minas Gerais, Brazil", network_type="drive",)

        # Velocidades estimadas para calcular tempo de chegada.
        velocidades = {
            "motorway": 80,
            "trunk": 60,
            "primary": 40,
            "secondary": 30,
            "tertiary": 30,
            "residential": 30,
            "unclassified": 30,
            "service": 30,
            "living_street": 30,
        }

        grafo = ox.routing.add_edge_speeds(grafo,hwy_speeds=velocidades,fallback=20)
        grafo = ox.routing.add_edge_travel_times(grafo)

        nos = list(grafo.nodes(data=True))

        _IDS_NOS = [no for no, _ in nos]
        _XS = np.array([float(data["x"]) for _, data in nos])
        _YS = np.array([float(data["y"]) for _, data in nos])
        _GRAFO = grafo

    return _GRAFO


def no_mais_proximo(lat, lon):
    """Encontra o nó viário mais próximo no grafo viário usando distância euclidiana"""
    carregar_grafo()

    fator_lon = max(abs(np.cos(np.radians(lat))), 0.01)

    distancias = ((_YS - lat) ** 2 + ((_XS - lon) * fator_lon) ** 2)

    return _IDS_NOS[int(np.argmin(distancias))]


def estimar_rota(lat_origem, lon_origem, lat_destino, lon_destino):
    """Retorna a distância e o tempo de chegada estimado pela rede viária."""
    grafo = carregar_grafo()

    origem = no_mais_proximo(float(lat_origem), float(lon_origem))
    destino = no_mais_proximo(float(lat_destino), float(lon_destino))

    rota = ox.routing.shortest_path(grafo, origem, destino, weight="travel_time")

    if rota is None:
        return None

    arestas = ox.routing.route_to_gdf(grafo, rota)

    return {
        "distance": float(arestas["length"].sum()) / 1000,
        "eta_minutes": float(arestas["travel_time"].sum()) / 60,
    }


def gerar_entregadores(restaurantes, quantidade, sigma_km=1.0):
    """Gera entregadores com distribuição normal ao redor dos restaurantes
    e ajusta suas posições para os nós mais próximos do grafo viário.
    """

    if quantidade < 0:
        raise ValueError("A quantidade deve ser não negativa.")

    if not restaurantes:
        raise ValueError("É necessário ter restaurantes carregados.")


    grafo = carregar_grafo()
    random = np.random.default_rng()

    # quantos entregadores serão gerados ao redor de cada restaurante
    quantidade_por_restaurante = quantidade // len(restaurantes)
    resto = quantidade % len(restaurantes)

    distribuicao = []

    for i in range(len(restaurantes)):
        n = quantidade_por_restaurante

        if i < resto:
            n += 1

        distribuicao.append(n)

    entregadores = []

    for i in range(len(restaurantes)):
        restaurante = restaurantes[i]
        n = distribuicao[i]

        lat0 = float(restaurante["lat"])
        lon0 = float(restaurante["lon"])

        # gera pontos seguindo uma distribuição normal
        sigma_lat = sigma_km / 111.32
        sigma_lon = sigma_km / (111.32 * max(abs(np.cos(np.radians(lat0))), 0.01))

        latitudes = random.normal(lat0, sigma_lat, n)
        longitudes = random.normal(lon0, sigma_lon, n)

        # adapta cada ponto à rede viária
        for j in range(n):
            lat = float(latitudes[j])
            lon = float(longitudes[j])

            no = no_mais_proximo(lat, lon)

            lat_rua = float(grafo.nodes[no]["y"])
            lon_rua = float(grafo.nodes[no]["x"])
            
            # criacao do entregador
            entregadores.append({
                "id": f"entregador_{len(entregadores) + 1}",
                "lat": lat_rua,
                "lon": lon_rua,
                "geohash": geohash(
                    (lat_rua, lon_rua),
                    precision=8,
                ),
            })

    return entregadores
