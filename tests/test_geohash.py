import pytest

from src.geohash import geohash


def test_geohash_known_location():
    assert geohash((-25.382708, -49.265506), precision=8) == "6gkzwgjz"


def test_geohash_precision():
    assert len(geohash((-19.9191, -43.9386), precision=8)) == 8


def test_geohash_rejects_invalid_coordinates():
    with pytest.raises(ValueError):
        geohash((100, 0))
