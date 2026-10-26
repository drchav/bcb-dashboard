"""Coletor de taxas de juros por instituicao (API taxaJuros v2 do BCB)."""
import urllib.request, json, ssl
import config

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
BASE = "https://olinda.bcb.gov.br/olinda/servico/taxaJuros/versao/v2/odata/"


def _get(url):
    url = url.replace(" ", "%20")
    req = urllib.request.Request(url, headers={"User-Agent": "painel-sfn/1.0"})
    with urllib.request.urlopen(req, timeout=90, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8")).get("value", [])


def ultimo_mes():
    d = _get(BASE + "TaxasJurosMensalPorMes?$top=1&$orderby=anoMes%20desc&$format=json&$select=anoMes")
    return d[0]["anoMes"] if d else None


def taxas_do_mes(anomes):
    """Todas as taxas (todas modalidades/instituicoes) de um mes 'YYYY-MM'.
    Observacao: este EntitySet cobre apenas financiamento imobiliario."""
    url = (BASE + "TaxasJurosMensalPorMes?$format=json"
           f"&$filter=anoMes eq '{anomes}'")
    return _get(url)


# ----------------------------------------------------------------- consulta unificada
# EntitySet ConsultaUnificada: TODAS as modalidades de credito (PF e PJ) por
# instituicao e periodo semanal (credito pessoal, veiculos, cartao, cheque
# especial, consignado, capital de giro, ACC etc.).

def ultimo_periodo_unificado():
    d = _get(BASE + "ConsultaUnificada?$top=1&$orderby=InicioPeriodo desc"
                    "&$select=InicioPeriodo&$format=json")
    return d[0]["InicioPeriodo"] if d else None


def taxas_unificadas(inicio_periodo):
    """Todas as taxas de credito do periodo (InicioPeriodo 'YYYY-MM-DD')."""
    url = (BASE + "ConsultaUnificada?$format=json"
           f"&$filter=InicioPeriodo eq '{inicio_periodo}'")
    return _get(url)
