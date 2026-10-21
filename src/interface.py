from pathlib import Path
import threading
import time
import math

import pandas as pd
import osmnx as ox
import dash
import dash_leaflet as dl

from dash import Input, Output, State, dcc, html

from src.busca_espaco import construir_indice, buscar_entregadores
from src.gera_entregadores import gerar_entregadores


CAMINHO_CSV = Path(__file__).resolve().parent.parent / "bares.csv"
CAMINHO_CACHE = Path(__file__).resolve().parent.parent / "bares_geocodificados.csv"

_LOCK = threading.RLock()
_INDICE_FROTA = None

_CARREGAMENTO_INICIADO = False
_MODO_CARREGAMENTO = None
_GERACAO_CARREGAMENTO = 0

_RESTAURANTES = []
_COORDENADAS = {}
_ERRO_CARREGAMENTO = None
_THREAD_GEOCODIFICACAO = None

_TOTAL_PENDENTES = 0
_PROCESSADOS = 0
_FALHAS = 0
_ULTIMA_ASSINATURA_RESTAURANTES = None

# Para consulta no OpenStreetMap
def normalizar_tipo_logradouro(valor):
    if pd.isna(valor):
        return ""

    tipos = {
        "AVE": "Avenida",
        "AV": "Avenida",
        "AVENIDA": "Avenida",
        "R": "Rua",
        "RUA": "Rua",
        "PC": "Praça",
        "PCA": "Praça",
        "PRACA": "Praça",
        "PRAÇA": "Praça",
        "AL": "Alameda",
        "ROD": "Rodovia",
        "TR": "Travessa",
    }

    texto = str(valor).strip().upper()
    return tipos.get(texto, str(valor).strip().title())


def valor_coluna(linha, *nomes):
    for nome in nomes:
        valor = linha.get(nome)

        if valor is not None and pd.notna(valor):
            texto = str(valor).strip()
            if texto and texto.lower() != "nan":
                return texto

    return ""


def construir_endereco(bar):
    tipo = normalizar_tipo_logradouro(valor_coluna(bar, "DESC_LOGRADOURO"))
    logradouro = valor_coluna(bar, "NOME_LOGRADOURO")
    numero = valor_coluna(bar, "NUMERO_IMOVEL")
    bairro = valor_coluna(bar, "NOME_BAIRRO")

    partes = [
        " ".join(p for p in (tipo, logradouro) if p),
        numero,
        bairro,
        "Belo Horizonte",
        "MG",
        "Brasil",
    ]

    return ", ".join(p for p in partes if p)


def criar_restaurante(bar, lat, lon):
    nome = valor_coluna(bar, "NOME_FANTASIA", "NOME")
    tipo = normalizar_tipo_logradouro(valor_coluna(bar, "DESC_LOGRADOURO"))
    logradouro = valor_coluna(bar, "NOME_LOGRADOURO")
    numero = valor_coluna(bar, "NUMERO_IMOVEL")
    bairro = valor_coluna(bar, "NOME_BAIRRO")

    endereco = " ".join(p for p in (tipo, logradouro) if p)

    if numero:
        endereco += f", {numero}"
    if bairro:
        endereco += f" - {bairro}"

    return {
        "id": str(bar["_id"]),
        "name": nome or "Estabelecimento sem nome",
        "address": endereco or "Endereço não informado",
        "lat": float(lat),
        "lon": float(lon),
    }

def salvar_cache(geracao=None):
    with _LOCK:
        if (geracao is not None and geracao != _GERACAO_CARREGAMENTO):
            return

        linhas = [
            {
                "_id": str(identificador),
                "lat": coordenadas[0],
                "lon": coordenadas[1],
            }
            for identificador, coordenadas in _COORDENADAS.items()
        ]

        cache = pd.DataFrame(linhas, columns=["_id", "lat", "lon"])

        temporario = CAMINHO_CACHE.with_suffix(".tmp")
        cache.to_csv(temporario, index=False)
        temporario.replace(CAMINHO_CACHE)


def ler_coordenadas_cache():
    if not CAMINHO_CACHE.exists():
        return {}

    cache = pd.read_csv(CAMINHO_CACHE, dtype={"_id": str})

    if not {"_id", "lat", "lon"}.issubset(cache.columns):
        return {}

    cache = cache.dropna(subset=["_id", "lat", "lon"])
    cache = cache.drop_duplicates("_id", keep="last")

    coordenadas = {}

    for _, linha in cache.iterrows():
        try:
            identificador = str(linha["_id"])
            lat = float(linha["lat"])
            lon = float(linha["lon"])

            if (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                coordenadas[identificador] = (lat, lon)

        except (TypeError, ValueError):
            continue

    return coordenadas

def geocodificar_pendentes(barras, geracao):
    global _PROCESSADOS, _FALHAS, _THREAD_GEOCODIFICACAO

    try:
        for indice, bar in enumerate(barras):
            identificador = str(bar["_id"])

            with _LOCK:
                if geracao != _GERACAO_CARREGAMENTO:
                    return

            try:
                localizacao = ox.geocode(construir_endereco(bar))

                with _LOCK:
                    if geracao != _GERACAO_CARREGAMENTO:
                        return

                    if localizacao:
                        lat, lon = map(float, localizacao)

                        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                            raise ValueError("Coordenadas inválidas retornadas pelo geocodificador.")

                        _COORDENADAS[identificador] = (lat, lon)
                        _RESTAURANTES.append(criar_restaurante(bar, lat, lon))
                    else:
                        _FALHAS += 1

                    _PROCESSADOS += 1

            except Exception as erro:
                with _LOCK:
                    if geracao != _GERACAO_CARREGAMENTO:
                        return
                    _FALHAS += 1

                print(f"Falha ao geocodificar {identificador}: {erro}")

            if (indice + 1) % 10 == 0:
                salvar_cache(geracao)

            if indice < len(barras) - 1:
                time.sleep(1)

        salvar_cache(geracao)

    finally:
        with _LOCK:
            if geracao == _GERACAO_CARREGAMENTO:
                _THREAD_GEOCODIFICACAO = None


def iniciar_carregamento(modo="cache"):
    global _CARREGAMENTO_INICIADO, _MODO_CARREGAMENTO
    global _GERACAO_CARREGAMENTO, _RESTAURANTES, _COORDENADAS
    global _TOTAL_PENDENTES, _PROCESSADOS, _FALHAS
    global _ERRO_CARREGAMENTO, _THREAD_GEOCODIFICACAO
    global _ULTIMA_ASSINATURA_RESTAURANTES

    if modo not in ("cache", "all"):
        raise ValueError("O modo deve ser 'cache' ou 'all'.")

    with _LOCK:
        if _CARREGAMENTO_INICIADO and _MODO_CARREGAMENTO == modo:
            return

        _GERACAO_CARREGAMENTO += 1
        geracao = _GERACAO_CARREGAMENTO

        _MODO_CARREGAMENTO = modo
        _CARREGAMENTO_INICIADO = True
        _RESTAURANTES = []
        _COORDENADAS = {}
        _TOTAL_PENDENTES = 0
        _PROCESSADOS = 0
        _FALHAS = 0
        _ERRO_CARREGAMENTO = None
        _THREAD_GEOCODIFICACAO = None
        _ULTIMA_ASSINATURA_RESTAURANTES = None

    try:
        bares = pd.read_csv(CAMINHO_CSV, dtype={"_id": str})

        if "_id" not in bares.columns:
            raise ValueError("bares.csv precisa conter a coluna '_id'.")

        coordenadas_cache = ler_coordenadas_cache()
        restaurantes = []
        pendentes = []

        for _, bar in bares.iterrows():
            identificador = str(bar["_id"])
            coordenadas = coordenadas_cache.get(identificador)

            if coordenadas is None:
                if modo == "all":
                    pendentes.append(bar.to_dict())
                continue

            lat, lon = coordenadas
            restaurantes.append(criar_restaurante(bar, lat, lon))

        with _LOCK:
            if geracao != _GERACAO_CARREGAMENTO:
                return

            _RESTAURANTES = restaurantes
            _COORDENADAS = coordenadas_cache
            _TOTAL_PENDENTES = len(pendentes)

        print(
            f"Modo: {modo}. "
            f"{len(restaurantes)} bares do cache; "
            f"{len(pendentes)} pendentes."
        )

        if modo == "all" and pendentes:
            thread = threading.Thread(
                target=geocodificar_pendentes,
                args=(pendentes, geracao),
                daemon=True,
                name="geocodificacao-restaurantes",
            )

            with _LOCK:
                if geracao != _GERACAO_CARREGAMENTO:
                    return
                _THREAD_GEOCODIFICACAO = thread

            thread.start()

    except Exception as erro:
        with _LOCK:
            if geracao == _GERACAO_CARREGAMENTO:
                _ERRO_CARREGAMENTO = str(erro)
                _CARREGAMENTO_INICIADO = False


def estado_carregamento():
    with _LOCK:
        restaurantes = [r.copy() for r in _RESTAURANTES]
        erro = _ERRO_CARREGAMENTO
        total = _TOTAL_PENDENTES
        processados = _PROCESSADOS
        falhas = _FALHAS
        modo = _MODO_CARREGAMENTO

    if erro:
        mensagem = f"Erro ao carregar restaurantes: {erro}"
    elif modo == "cache":
        mensagem = (
            f"{len(restaurantes)} bares disponíveis no cache. "
            "Nenhuma geocodificação foi iniciada."
        )
    elif processados < total:
        mensagem = (
            f"{len(restaurantes)} bares disponíveis. "
            f"Geocodificação: {processados}/{total}; "
            f"{falhas} falhas."
        )
    elif total > 0 and falhas:
        mensagem = (
            f"{len(restaurantes)} bares carregados. "
            f"Geocodificação concluída com {falhas} falhas."
        )
    else:
        mensagem = (
            f"{len(restaurantes)} bares carregados. "
            "Geocodificação concluída."
        )

    return restaurantes, mensagem, erro

def camada_base():
    """Mapa inicial sem marcadores de restaurantes ou entregadores."""
    
    return [
        dl.TileLayer(
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution="© OpenStreetMap contributors",
        ),
        dl.LayerGroup(id="restaurant-layer", children=[]),
        dl.LayerGroup(id="courier-layer", children=[]),
        dl.LayerGroup(id="search-layer", children=[]),
    ]


def marcador_restaurante_selecionado(restaurantes, restaurante_id):
    if restaurante_id is None:
        return []

    restaurante = next(
        (
            r for r in (restaurantes or [])
            if str(r["id"]) == str(restaurante_id)
        ),
        None,
    )

    if restaurante is None:
        return []

    return [
        dl.Marker(
            position=[restaurante["lat"], restaurante["lon"]],
            children=[
                dl.Tooltip(restaurante["name"]),
                dl.Popup(
                    html.Div([
                        html.Strong(restaurante["name"]),
                        html.Br(),
                        restaurante["address"],
                    ])
                ),
            ],
        )
    ]


def marcador_entregador(entregador, cor):
    return dl.CircleMarker(
        center=[float(entregador["lat"]), float(entregador["lon"])],
        radius=5,
        color=cor,
        fill=True,
        fillColor=cor,
        fillOpacity=0.9,
        children=dl.Tooltip(str(entregador["id"])),
    )


def tabela_resultados(resultados):
    if not resultados:
        return html.P(
            "Nenhum entregador encontrado neste raio.",
            className="py-6 text-center text-sm text-gray-500",
        )

    linhas = [
        html.Tr(
            [
                html.Td(
                    resultado["id"],
                    className="px-6 py-4 font-medium text-gray-900",
                ),
                html.Td(
                    f'{resultado["distance"]:.2f} km',
                    className="px-6 py-4 text-gray-600",
                ),
                html.Td(
                    f'{resultado["eta_minutes"]:.0f} min',
                    className="px-6 py-4 text-gray-600",
                ),
            ],
            className="border-b border-gray-200 bg-white",
        )
        for resultado in resultados
    ]

    return html.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Entregador", className="px-6 py-3 text-left"),
                        html.Th("Distância", className="px-6 py-3 text-left"),
                        html.Th("Tempo estimado", className="px-6 py-3 text-left"),
                    ]
                ),
                className="bg-gray-50",
            ),
            html.Tbody(linhas),
        ],
        className="w-full text-left text-sm text-gray-500",
    )
    
# INTERFACE

app = dash.Dash(
    __name__,
    external_stylesheets=[
        "https://cdnjs.cloudflare.com/ajax/libs/flowbite/2.5.2/flowbite.min.css",
    ],
    external_scripts=[
        "https://cdn.tailwindcss.com",
        "https://cdnjs.cloudflare.com/ajax/libs/flowbite/2.5.2/flowbite.min.js",
    ],
)

app.layout = html.Div(
    className="min-h-screen bg-gray-50 p-4 md:p-8",
    children=[
        html.Div(
            className="mx-auto max-w-screen-2xl space-y-6",
            children=[
                html.Header(
                    className="rounded-lg bg-white p-6 shadow-sm",
                    children=[
                        html.H1(
                            "Sistema de Entregadores",
                            className="mb-2 text-3xl font-bold tracking-tight text-gray-900",
                        ),
                        html.P(
                            "Geração de frota e busca espacial por proximidade.",
                            className="text-gray-500",
                        ),
                    ],
                ),

                dcc.Store(id="restaurant-store", data=[]),
                dcc.Store(id="courier-store", data=[]),

                dcc.Interval(
                    id="intervalo-carregamento",
                    interval=2000,
                    n_intervals=0,
                    disabled=False,
                ),

                html.Section(
                    className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm",
                    children=[
                        html.H2(
                            "Configuração da busca",
                            className="mb-5 text-xl font-semibold text-gray-900",
                        ),

                        html.Div(
                            className="mb-5 rounded-lg bg-gray-50 p-4",
                            children=[
                                html.Label(
                                    "Carregamento dos bares",
                                    className="mb-3 block text-sm font-medium text-gray-900",
                                ),
                                dcc.RadioItems(
                                    id="loading-mode",
                                    options=[
                                        {
                                            "label": " Usar apenas os bares disponíveis no cache",
                                            "value": "cache",
                                        },
                                        {
                                            "label": " Carregar todos os bares",
                                            "value": "all",
                                        },
                                    ],
                                    value="cache",
                                    className="flex flex-col gap-3",
                                    inputClassName="mr-2",
                                    labelClassName="text-sm text-gray-700",
                                ),
                                html.P(
                                    "O modo cache é mais rápido e não realiza requisições externas. "
                                    "O modo completo geocodifica os bares sem coordenadas.",
                                    className="mt-3 text-xs text-gray-500",
                                ),
                            ],
                        ),

                        html.Div(
                            className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3",
                            children=[
                                html.Div([
                                    html.Label(
                                        "Restaurante",
                                        className="mb-2 block text-sm font-medium text-gray-900",
                                    ),
                                    dcc.Dropdown(
                                        id="restaurant-select",
                                        options=[],
                                        placeholder="Carregando restaurantes...",
                                        clearable=True,
                                        className="text-sm",
                                    ),
                                ]),
                                html.Div([
                                    html.Label(
                                        "Raio de busca (km)",
                                        htmlFor="radius-input",
                                        className="mb-2 block text-sm font-medium text-gray-900",
                                    ),
                                    dcc.Input(
                                        id="radius-input",
                                        type="number",
                                        min=0,
                                        max=50,
                                        step=0.5,
                                        value=2,
                                        className="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900",
                                    ),
                                ]),
                                html.Div([
                                    html.Label(
                                        "Quantidade de entregadores",
                                        htmlFor="courier-quantity",
                                        className="mb-2 block text-sm font-medium text-gray-900",
                                    ),
                                    dcc.Input(
                                        id="courier-quantity",
                                        type="number",
                                        min=1,
                                        step=1,
                                        value=100,
                                        className="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900",
                                    ),
                                ]),
                            ],
                        ),

                        html.Div(
                            className="mt-6 flex flex-col gap-3 sm:flex-row",
                            children=[
                                html.Button(
                                    "Gerar entregadores",
                                    id="generate-button",
                                    n_clicks=0,
                                    className="rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-800",
                                ),
                                html.Button(
                                    "Buscar entregadores",
                                    id="search-button",
                                    n_clicks=0,
                                    className="rounded-lg bg-green-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-green-800",
                                ),
                            ],
                        ),
                    ],
                ),

                html.Div(
                    id="status-message",
                    className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-700 shadow-sm",
                    children="Preparando o carregamento dos restaurantes...",
                ),

                html.Section(
                    className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm md:p-6",
                    children=[
                        html.Div(
                            className="mb-4 flex items-center justify-between",
                            children=[
                                html.H2(
                                    "Mapa da frota",
                                    className="text-xl font-semibold text-gray-900",
                                ),
                                html.Span(
                                    "OpenStreetMap",
                                    className="rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-800",
                                ),
                            ],
                        ),
                        dl.Map(
                            id="fleet-map",
                            center=[-19.9191, -43.9386],
                            zoom=12,
                            children=camada_base(),
                            style={
                                "width": "100%",
                                "height": "600px",
                                "borderRadius": "0.5rem",
                                "zIndex": "0",
                            },
                        ),
                        html.Div(
                            className="mt-4 flex flex-wrap gap-4 text-sm text-gray-600",
                            children=[
                                html.Div([
                                    html.Span(className="me-2 inline-block h-3 w-3 rounded-full bg-red-600"),
                                    "Encontrados",
                                ]),
                                html.Div([
                                    html.Span(className="me-2 inline-block h-3 w-3 rounded-full bg-gray-500"),
                                    "Demais entregadores",
                                ]),
                                html.Div([
                                    html.Span(className="me-2 inline-block h-3 w-3 rounded-full bg-blue-600"),
                                    "Raio de busca",
                                ]),
                            ],
                        ),
                    ],
                ),

                html.Section(
                    className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm md:p-6",
                    children=[
                        html.H2(
                            "Entregadores encontrados",
                            className="text-xl font-semibold text-gray-900",
                        ),
                        html.P(
                            "Entregadores dentro do raio selecionado, ordenados por distância.",
                            className="mt-1 text-sm text-gray-500",
                        ),
                        html.Div(
                            id="results-table",
                            children=html.P(
                                "Realize uma busca para ver os resultados.",
                                className="py-6 text-center text-sm text-gray-500",
                            ),
                            className="mt-4 overflow-x-auto",
                        ),
                    ],
                ),
            ],
        ),
    ],
)

# FUNCOES INTERFACE

@app.callback(
    Output("restaurant-select", "options"),
    Output("restaurant-select", "placeholder"),
    Output("restaurant-store", "data"),
    Output("status-message", "children"),
    Output("intervalo-carregamento", "disabled"),
    Input("intervalo-carregamento", "n_intervals"),
    Input("loading-mode", "value"),
)
def atualizar_restaurantes(_, modo):
    global _ULTIMA_ASSINATURA_RESTAURANTES

    if not _CARREGAMENTO_INICIADO or _MODO_CARREGAMENTO != modo:
        iniciar_carregamento(modo)

    restaurantes, mensagem, erro = estado_carregamento()

    with _LOCK:
        processados = _PROCESSADOS
        total = _TOTAL_PENDENTES

    if erro:
        placeholder = "Erro ao carregar restaurantes"
    elif modo == "cache" and not restaurantes:
        placeholder = "Nenhum bar disponível no cache"
        mensagem = (
            "Nenhum bar com coordenadas válidas foi encontrado no cache. "
            "Selecione 'Carregar todos os bares' para geocodificar os restantes."
        )
    elif not restaurantes:
        placeholder = "Carregando restaurantes..."
    else:
        placeholder = "Selecione um restaurante"

    intervalo_desativado = (
        modo != "all"
        or erro is not None
        or processados >= total
    )

    assinatura = (
        modo,
        erro,
        tuple(
            (
                r["id"],
                r["name"],
                r["address"],
                r["lat"],
                r["lon"],
            )
            for r in restaurantes
        ),
    )

    with _LOCK:
        dados_mudaram = assinatura != _ULTIMA_ASSINATURA_RESTAURANTES

        if dados_mudaram:
            _ULTIMA_ASSINATURA_RESTAURANTES = assinatura

    if dados_mudaram:
        opcoes = [
            {
                "label": f'{r["name"]} — {r["address"]}',
                "value": r["id"],
            }
            for r in restaurantes
        ]
        return (
            opcoes,
            placeholder,
            restaurantes,
            mensagem,
            intervalo_desativado,
        )

    return (
        dash.no_update,
        placeholder,
        dash.no_update,
        mensagem,
        intervalo_desativado,
    )


@app.callback(
    Output("restaurant-layer", "children"),
    Input("restaurant-select", "value"),
    State("restaurant-store", "data"),
)
def atualizar_restaurante_selecionado(restaurante_id, restaurantes):
    return marcador_restaurante_selecionado(restaurantes or [], restaurante_id)


@app.callback(
    Output("courier-store", "data"),
    Output("courier-layer", "children"),
    Output("search-layer", "children"),
    Output("results-table", "children"),
    Output("status-message", "children", allow_duplicate=True),
    Input("generate-button", "n_clicks"),
    State("courier-quantity", "value"),
    State("restaurant-store", "data"),
    prevent_initial_call=True,
)
def gerar_frota(n_clicks, quantidade, restaurantes):
    global _INDICE_FROTA

    _INDICE_FROTA = None

    if not restaurantes:
        return (
            [],
            [],
            [],
            "Frota não gerada.",
            "Nenhum restaurante carregado. Aguarde o carregamento ou selecione o modo completo.",
        )

    try:
        if quantidade is None or isinstance(quantidade, bool):
            raise ValueError("Informe a quantidade de entregadores.")

        valor = float(quantidade)

        if not math.isfinite(valor) or not valor.is_integer() or valor <= 0:
            raise ValueError("A quantidade deve ser um inteiro maior que zero.")

        quantidade = int(valor)

        print("\nGERANDO ENTRAGADORES!")
        print("Restaurantes disponíveis:", len(restaurantes))
        print("Quantidade solicitada:", quantidade)

        frota = gerar_entregadores(restaurantes, quantidade)

        if frota is None:
            raise RuntimeError("gerar_entregadores() retornou None.")

        frota = list(frota)

        if not frota:
            raise RuntimeError(
                "A função retornou zero entregadores. "
                "Verifique src/gera_entregadores.py."
            )

        for i, entregador in enumerate(frota):
            if not isinstance(entregador, dict):
                raise TypeError(
                    f"O entregador na posição {i} não é um dicionário."
                )

            for campo in ("id", "lat", "lon"):
                if campo not in entregador:
                    raise ValueError(
                        f"O entregador na posição {i} não possui '{campo}'."
                    )

            lat = float(entregador["lat"])
            lon = float(entregador["lon"])

            if not (
                math.isfinite(lat)
                and math.isfinite(lon)
                and -90 <= lat <= 90
                and -180 <= lon <= 180
            ):
                raise ValueError(
                    f"Coordenadas inválidas no entregador {entregador['id']}."
                )

        _INDICE_FROTA = construir_indice(frota)

        marcadores = [
            marcador_entregador(entregador, "gray")
            for entregador in frota
        ]

        print("Entregadores gerados:", len(frota))
        print("========================")

        return (
            frota,
            marcadores,
            [],
            html.P(
                "Realize uma busca para ver os resultados.",
                className="py-6 text-center text-sm text-gray-500",
            ),
            f"{len(frota)} entregadores gerados com sucesso.",
        )

    except Exception as erro:
        _INDICE_FROTA = None
        print(f"Erro ao gerar a frota: {erro}")

        return (
            [],
            [],
            [],
            html.P("Frota não gerada."),
            f"Erro ao gerar entregadores: {erro}",
        )


@app.callback(
    Output("courier-layer", "children", allow_duplicate=True),
    Output("search-layer", "children", allow_duplicate=True),
    Output("results-table", "children", allow_duplicate=True),
    Output("status-message", "children", allow_duplicate=True),
    Input("search-button", "n_clicks"),
    State("restaurant-select", "value"),
    State("radius-input", "value"),
    State("restaurant-store", "data"),
    State("courier-store", "data"),
    prevent_initial_call=True,
)
def consultar_frota(n_clicks, restaurante_id, raio_km, restaurantes, frota):
    if not restaurante_id:
        return (
            dash.no_update,
            [],
            html.P("Selecione um restaurante."),
            "Selecione um restaurante para realizar a busca.",
        )

    try:
        raio_km = float(raio_km)

        if not math.isfinite(raio_km) or not 0 <= raio_km <= 50:
            raise ValueError("O raio deve estar entre 0 e 50 km.")

    except (TypeError, ValueError) as erro:
        return (
            dash.no_update,
            [],
            html.P("Raio inválido."),
            f"Informe um raio numérico entre 0 e 50 km. {erro}",
        )

    if not frota:
        return (
            [],
            [],
            html.P("Gere uma frota primeiro."),
            "Não há entregadores para consultar. Gere a frota antes de buscar.",
        )

    restaurante = next(
        (
            r for r in (restaurantes or [])
            if str(r["id"]) == str(restaurante_id)
        ),
        None,
    )

    if restaurante is None:
        return (
            dash.no_update,
            [],
            html.P("Restaurante não encontrado."),
            "O restaurante selecionado não está disponível.",
        )

    try:
        inicio = time.perf_counter()

        resultados = buscar_entregadores(
            frota,
            restaurante,
            raio_km,
            indice=_INDICE_FROTA,
        )

        duracao = time.perf_counter() - inicio

        ids_encontrados = {
            str(resultado["id"])
            for resultado in resultados
        }

        marcadores = [
            marcador_entregador(
                entregador,
                "red" if str(entregador["id"]) in ids_encontrados else "gray",
            )
            for entregador in frota
        ]

        circulo = [
            dl.Circle(
                center=[restaurante["lat"], restaurante["lon"]],
                radius=raio_km * 1000,
                color="blue",
                fill=True,
                fillOpacity=0.12,
            )
        ]

        status = (
            f"{len(resultados)} entregadores encontrados em "
            f"{duracao:.4f} segundos."
        )

        return (
            marcadores,
            circulo,
            tabela_resultados(resultados),
            status,
        )

    except Exception as erro:
        print(f"Erro na busca espacial: {erro}")
        return (
            dash.no_update,
            [],
            html.P("Não foi possível realizar a busca."),
            f"Erro na busca: {erro}",
        )

