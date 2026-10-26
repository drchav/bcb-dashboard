"""Coletor das Expectativas de Mercado (Focus) - Olinda."""
import urllib.request, json, ssl

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
BASE = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"


def _get(url):
    req = urllib.request.Request(url.replace(" ", "%20"), headers={"User-Agent": "painel-sfn/1.0"})
    with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8")).get("value", [])


def expectativas_anuais():
    """Projecoes anuais mais recentes (Selic, IPCA, Cambio, PIB) por ano de referencia."""
    # pega as projecoes recentes (ultimos ~400 registros) e deixa o backend filtrar o mais novo
    url = (BASE + "ExpectativasMercadoAnuais?$format=json&$orderby=Data desc&$top=800"
           "&$select=Indicador,Data,DataReferencia,Media,Mediana,Minimo,Maximo,numeroRespondentes,baseCalculo")
    return _get(url)
