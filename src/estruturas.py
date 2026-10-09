BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

coordenada = (-19.92083, -43.93778)  # lat, long


def divisao_binaria(eixo: float, intervalo: list) -> int:
    ponto_medio = (intervalo[0] + intervalo[1]) / 2

    if eixo < ponto_medio:
        intervalo[1] = ponto_medio
        return 0
    else:
        intervalo[0] = ponto_medio
        return 1


def geohash(coordenada: tuple, precision: int = 8) -> str:
    geohash_str = ""
    tamanho_str = precision * 5
    intervalo_longitude = [-180, 180]
    intervalo_latitude = [-90, 90]

    bits = []
    for i in range(tamanho_str):
        if i % 2 == 0:
            bit = divisao_binaria(coordenada[1], intervalo_longitude)
            bits.append(bit)
        else:
            bit = divisao_binaria(coordenada[0], intervalo_latitude)
            bits.append(bit)

    # Conversão para Base 32
    for i in range(0, tamanho_str, 5):
        decimal = 0
        for bit in bits[i : i + 5]:
            decimal = (decimal << 1) | bit

        geohash_str += BASE32[decimal]

    return geohash_str


hash = geohash(coordenada)
print(hash)
