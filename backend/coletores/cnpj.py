"""Consulta de dados publicos de CNPJ via BrasilAPI (com cache)."""
import urllib.request, json, ssl
import config

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
BRASILAPI = "https://brasilapi.com.br/api/cnpj/v1/"


def cnpj_completo(raiz8):
    """Monta o CNPJ de 14 digitos (matriz 0001) a partir da raiz de 8 digitos."""
    base = (raiz8 or "").zfill(8) + "0001"
    def dv(nums):
        pesos = list(range(2, 10)) * 2
        s = sum(int(d) * p for d, p in zip(reversed(nums), pesos))
        r = s % 11
        return "0" if r < 2 else str(11 - r)
    d1 = dv(base)
    d2 = dv(base + d1)
    return base + d1 + d2


def consultar(raiz8):
    """Consulta a BrasilAPI. Retorna o JSON publico do CNPJ (matriz)."""
    cnpj = cnpj_completo(raiz8)
    req = urllib.request.Request(BRASILAPI + cnpj, headers={"User-Agent": "painel-sfn/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=_CTX) as r:
        d = json.loads(r.read().decode("utf-8"))
    d["_cnpj_formatado"] = cnpj
    d["_fonte"] = BRASILAPI + cnpj
    return d
