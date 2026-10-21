
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


def geohash_celula(linha, coluna, precision=8):
    """
    Codifica índices de uma célula Geohash sem recalcular seus intervalos para aumentar eficiência.

    Essa função é usada para gerar muitas células vizinhas.
    """

    total_bits = precision * 5
    bits_lon = (total_bits + 1) // 2
    bits_lat = total_bits // 2

    valor = 0
    bits_no_caractere = 0
    resultado = []
    for i in range(total_bits):
        if i % 2 == 0:
            deslocamento = bits_lon - 1 - i // 2
            bit = (coluna >> deslocamento) & 1
        else:
            deslocamento = bits_lat - 1 - i // 2
            bit = (linha >> deslocamento) & 1

        valor = (valor << 1) | bit
        bits_no_caractere += 1
        if bits_no_caractere == 5:
            resultado.append(BASE32[valor])
            valor = 0
            bits_no_caractere = 0

    return "".join(resultado)