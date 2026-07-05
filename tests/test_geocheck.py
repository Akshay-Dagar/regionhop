import pytest

from regionhop.geocheck import GeoError, parse_ipapi_response


def test_parse_plain_json():
    raw = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"\r\n"
        b'{"country":"Brazil","countryCode":"BR","query":"1.2.3.4"}'
    )
    data = parse_ipapi_response(raw)
    assert data["countryCode"] == "BR"
    assert data["country"] == "Brazil"


def test_parse_with_trailing_noise():
    raw = b"HTTP/1.1 200 OK\r\n\r\n{\"countryCode\":\"JP\"}\n\n"
    assert parse_ipapi_response(raw)["countryCode"] == "JP"


def test_parse_non_json_raises():
    with pytest.raises(GeoError):
        parse_ipapi_response(b"HTTP/1.1 500 Internal Server Error\r\n\r\nnope")
