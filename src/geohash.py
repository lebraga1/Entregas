
BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def divisao_binaria(eixo: float, intervalo: list) -> int:
    ponto_medio = (intervalo[0] + intervalo[1]) / 2

    if eixo < ponto_medio:
        intervalo[1] = ponto_medio
        return 0
    else:
        intervalo[0] = ponto_medio
        return 1


def geohash(coordenadas, precision=8):
    lat, lon = coordenadas

    if not (-90 <= lat <= 90):
        raise ValueError("Latitude deve estar entre -90 e 90.")

    if not (-180 <= lon <= 180):
        raise ValueError("Longitude deve estar entre -180 e 180.")

    if not isinstance(precision, int) or isinstance(precision, bool) or precision <= 0:
        raise ValueError("A precisão deve ser um inteiro positivo.")

    geohash_str = ""
    tamanho_str = precision * 5
    intervalo_longitude = [-180, 180]
    intervalo_latitude = [-90, 90]

    bits = []
    for i in range(tamanho_str):
        if i % 2 == 0:
            bit = divisao_binaria(lon, intervalo_longitude)
        else:
            bit = divisao_binaria(lat, intervalo_latitude)

        bits.append(bit)

    for i in range(0, tamanho_str, 5):
        decimal = 0
        for bit in bits[i:i + 5]:
            decimal = (decimal << 1) | bit

        geohash_str += BASE32[decimal]

    return geohash_str
