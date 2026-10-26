"""Coletor da lista de participantes do arranjo PIX.

Usa o servico Pix_DadosAbertos (Olinda/BCB), funcao ChavesPix(Data='AAAA-MM-DD'),
que lista o estoque de chaves por participante. Agregamos para obter o diretorio
de participantes do PIX (ISPB + nome + segmento + PF/PJ + total de chaves).
Cada ISPB cruza com o cadastro (CNPJ raiz) e com os participantes da RSFN/STR.
"""
import urllib.request, json, ssl
from datetime import date

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
BASE = "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/"


def _get(url):
    req = urllib.request.Request(url.replace(" ", "%20"), headers={"User-Agent": "painel-sfn/1.0"})
    with urllib.request.urlopen(req, timeout=120, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8", "replace")).get("value", [])


def _trimestres_recentes(n=6):
    """Fins de trimestre (31/03, 30/06, 30/09, 31/12) do mais recente para tras."""
    hoje = date.today()
    fins = [(3, 31), (6, 30), (9, 30), (12, 31)]
    out = []
    ano = hoje.year
    while len(out) < n:
        for mes, dia in reversed(fins):
            d = date(ano, mes, dia)
            if d <= hoje:
                out.append(d.strftime("%Y-%m-%d"))
        ano -= 1
    return out[:n]


def _agrega(url_data):
    # groupby em 3 dimensoes retorna o diretorio completo (a variante com
    # aggregate e truncada em ~1000 linhas pelo servidor Olinda).
    url = (BASE + f"ChavesPix(Data=@d)?@d='{url_data}'"
           "&$apply=groupby((ISPB,Nome,Segmento))&$format=json")
    linhas = _get(url)
    part = {}
    for r in linhas:
        ispb = (r.get("ISPB") or "").zfill(8)
        if not ispb:
            continue
        part[ispb] = {"ispb": ispb, "nome": r.get("Nome"), "segmento": r.get("Segmento")}
    return list(part.values())


def participantes():
    """Retorna (data_referencia, [ {ispb,nome,segmento}, ... ])."""
    for d in _trimestres_recentes():
        try:
            lst = _agrega(d)
            if lst:
                return d, lst
        except Exception:  # noqa
            continue
    return None, []
