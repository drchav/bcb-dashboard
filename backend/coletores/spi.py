"""Coletor de estatisticas do SPI (PIX liquidados por dia)."""
import urllib.request, json, ssl
import config

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "painel-sfn/1.0"})
    with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8")).get("value", [])


def pix_liquidados():
    """Serie diaria de PIX liquidados no SPI (quantidade, valor, media)."""
    url = (config.OLINDA_SPI +
           "PixLiquidadosAtual?$format=json&$orderby=Data")
    return _get(url)
