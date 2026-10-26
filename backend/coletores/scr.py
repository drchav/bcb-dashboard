"""Coletor do SCR por sub-regiao (carteira de credito detalhada).

Servico Olinda scr_sub_regiao: funcao scr_sub_regiao(DataBase=AAAAMM) com a carteira
de credito do SFN por tipo de cliente (PF/PJ), UF/sub-regiao e modalidade, incluindo
operacoes e valor vencido. CARTEIRA e os buckets vem em R$ mil.
"""
import urllib.request, json, ssl
from datetime import date

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
BASE = ("https://olinda.bcb.gov.br/olinda/servico/scr_sub_regiao/versao/v1/odata/"
        "scr_sub_regiao(DataBase=@m)?@m={m}&$format=json")


def _get(m):
    req = urllib.request.Request(BASE.format(m=m), headers={"User-Agent": "painel-sfn/1.0"})
    with urllib.request.urlopen(req, timeout=120, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8", "replace")).get("value", [])


def _bases_recentes(n=6):
    y, mo = date.today().year, date.today().month
    out = []
    for i in range(n):
        mm, yy = mo - i, y
        while mm <= 0:
            mm += 12; yy -= 1
        out.append(yy * 100 + mm)
    return out


def carteira():
    """Retorna (data_base, [ {cliente,estado,sub_regiao,modalidade,operacoes,carteira,vencido}, ... ]).

    carteira/vencido em R$ mil (converter *1000 para reais na exibicao).
    """
    for m in _bases_recentes():
        try:
            d = _get(m)
        except Exception:  # noqa
            continue
        if not d:
            continue
        linhas = []
        for r in d:
            linhas.append({
                "cliente": r.get("CLIENTE"), "estado": r.get("ESTADO"),
                "sub_regiao": r.get("SUB_REGIAO"), "modalidade": r.get("MODALIDADE"),
                "operacoes": int(r.get("OPERACOES") or 0),
                "carteira": float(r.get("CARTEIRA") or 0),
                "vencido": float(r.get("VENCIDO_ACIMA_DE_15_DIAS") or 0),
            })
        return m, linhas
    return None, []
