from pathlib import Path

import numpy as np
import osmnx as ox

from src.geohash import geohash

CAMINHO_GRAFO = (
    Path(__file__).resolve().parent.parent / "cache" / "bh_malha_viaria.graphml"
)

_GRAFO = None
_IDS_NOS = None
_XS = None
_YS = None


def carregar_grafo():
    """Carrega a rede viária de Belo Horizonte e calcula tempos de viagem."""
    global _GRAFO, _IDS_NOS, _XS, _YS

    if _GRAFO is None:
        if CAMINHO_GRAFO.exists():
            grafo = ox.load_graphml(CAMINHO_GRAFO)
        else:
            ox.settings.use_cache = True

            grafo = ox.graph_from_place(
                "Belo Horizonte, Minas Gerais, Brazil",
                network_type="drive",
            )

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

            grafo = ox.routing.add_edge_speeds(
                grafo,
                hwy_speeds=velocidades,
                fallback=20,
            )
            grafo = ox.routing.add_edge_travel_times(grafo)

            CAMINHO_GRAFO.parent.mkdir(exist_ok=True)
            ox.save_graphml(grafo, CAMINHO_GRAFO)

        nos = list(grafo.nodes(data=True))
        if not nos:
            raise RuntimeError("O grafo viário não possui nós.")

        _IDS_NOS = [no for no, _ in nos]
        _XS = np.array([float(data["x"]) for _, data in nos])
        _YS = np.array([float(data["y"]) for _, data in nos])
        _GRAFO = grafo

    return _GRAFO


def no_mais_proximo(lat, lon):
    """Encontra o nó viário mais próximo sem depender de scikit-learn."""
    carregar_grafo()

    fator_lon = max(abs(np.cos(np.radians(lat))), 0.01)

    distancias = (_YS - lat) ** 2 + ((_XS - lon) * fator_lon) ** 2

    return _IDS_NOS[int(np.argmin(distancias))]


def estimar_rota(lat_origem, lon_origem, lat_destino, lon_destino):
    """Retorna a distância e o ETA estimado pela rede viária."""
    grafo = carregar_grafo()

    origem = no_mais_proximo(
        float(lat_origem),
        float(lon_origem),
    )
    destino = no_mais_proximo(
        float(lat_destino),
        float(lon_destino),
    )

    rota = ox.routing.shortest_path(
        grafo,
        origem,
        destino,
        weight="travel_time",
    )

    if rota is None:
        return None

    arestas = ox.routing.route_to_gdf(grafo, rota)

    return {
        "distance": float(arestas["length"].sum()) / 1000,
        "eta_minutes": float(arestas["travel_time"].sum()) / 60,
    }


def gerar_entregadores(restaurantes, quantidade, sigma_km=1.0):
    """
    Gera entregadores próximos aos restaurantes e os posiciona
    em nós da rede viária.
    """
    if not isinstance(quantidade, int) or isinstance(quantidade, bool):
        raise ValueError("A quantidade deve ser um inteiro.")

    if quantidade < 0:
        raise ValueError("A quantidade deve ser não negativa.")

    if not np.isfinite(sigma_km) or sigma_km <= 0:
        raise ValueError("sigma_km deve ser positivo.")

    if quantidade == 0:
        return []

    if not restaurantes:
        raise ValueError("É necessário ter restaurantes carregados.")

    grafo = carregar_grafo()
    rng = np.random.default_rng()

    lat_min, lat_max = float(_YS.min()), float(_YS.max())
    lon_min, lon_max = float(_XS.min()), float(_XS.max())

    # Distribui a quantidade solicitada entre os restaurantes.
    distribuicao = [
        quantidade // len(restaurantes)
        + (1 if i < quantidade % len(restaurantes) else 0)
        for i in range(len(restaurantes))
    ]

    entregadores = []
    contador = 1

    for restaurante, n in zip(restaurantes, distribuicao):
        if n == 0:
            continue

        lat0 = float(restaurante["lat"])
        lon0 = float(restaurante["lon"])

        fator_lon = max(abs(np.cos(np.radians(lat0))), 0.01)

        # Se o restaurante estiver fora da área do grafo,
        # usa o nó viário mais próximo como centro.
        no_centro = no_mais_proximo(lat0, lon0)
        lat_centro = float(grafo.nodes[no_centro]["y"])
        lon_centro = float(grafo.nodes[no_centro]["x"])

        gerados = 0
        tentativas = 0
        max_tentativas = max(100, n * 50)

        while gerados < n and tentativas < max_tentativas:
            tentativas += 1

            lat = lat_centro + rng.normal(
                0,
                sigma_km / 111.32,
            )
            lon = lon_centro + rng.normal(
                0,
                sigma_km / (111.32 * fator_lon),
            )

            # Evita procurar fora da área do grafo.
            if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
                continue

            no = no_mais_proximo(lat, lon)

            lat_rua = float(grafo.nodes[no]["y"])
            lon_rua = float(grafo.nodes[no]["x"])

            entregadores.append(
                {
                    "id": f"entregador_{contador}",
                    "lat": lat_rua,
                    "lon": lon_rua,
                    "geohash": geohash(
                        (lat_rua, lon_rua),
                        precision=8,
                    ),
                }
            )

            contador += 1
            gerados += 1

        if gerados < n:
            distancias = (_YS - lat_centro) ** 2 + ((_XS - lon_centro) * fator_lon) ** 2

            quantidade_nos = min(
                max(n * 10, n),
                len(_IDS_NOS),
            )

            indices = np.argpartition(
                distancias,
                quantidade_nos - 1,
            )[:quantidade_nos]

            for _ in range(n - gerados):
                indice = int(rng.choice(indices))
                no = _IDS_NOS[indice]

                lat_rua = float(grafo.nodes[no]["y"])
                lon_rua = float(grafo.nodes[no]["x"])

                entregadores.append(
                    {
                        "id": f"entregador_{contador}",
                        "lat": lat_rua,
                        "lon": lon_rua,
                        "geohash": geohash(
                            (lat_rua, lon_rua),
                            precision=8,
                        ),
                    }
                )

                contador += 1

    return entregadores
