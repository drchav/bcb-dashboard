"""Coletor de tarifas de servicos por instituicao (Olinda - Informes).

Servico: Informes_ListaTarifasPorInstituicaoFinanceira
- GruposConsolidados: lista os grupos consolidados (Codigo, Nome)
- ListaInstituicoesDeGrupoConsolidado(CodigoGrupoConsolidado='NN'): CNPJ(8)+Nome
- ListaTarifasPorInstituicaoFinanceira(PessoaFisicaOuJuridica='J',CNPJ='NNNNNNNN'): tarifas

Observacao importante: o CNPJ aceito e a RAIZ de 8 digitos (nao os 14).
"""
import urllib.request, json, ssl

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
BASE = ("https://olinda.bcb.gov.br/olinda/servico/"
        "Informes_ListaTarifasPorInstituicaoFinanceira/versao/v1/odata/")


def _get(url):
    req = urllib.request.Request(url.replace(" ", "%20"),
                                 headers={"User-Agent": "painel-sfn/1.0"})
    with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8")).get("value", [])


def grupos():
    """Lista de grupos consolidados: [{codigo, nome}]."""
    d = _get(BASE + "GruposConsolidados?$format=json")
    return [{"codigo": g.get("Codigo"), "nome": g.get("Nome")} for g in d]


def instituicoes_do_grupo(codigo):
    """Instituicoes de um grupo consolidado: [{cnpj8, nome}]."""
    url = (BASE + "ListaInstituicoesDeGrupoConsolidado("
           f"CodigoGrupoConsolidado='{codigo}')?$format=json")
    d = _get(url)
    return [{"cnpj8": (x.get("Cnpj") or "").zfill(8), "nome": x.get("Nome")} for x in d]


def tarifas_de(cnpj8, pf_pj="J"):
    """Tarifas de servicos de uma instituicao pela raiz de 8 digitos do CNPJ."""
    cnpj8 = (cnpj8 or "").zfill(8)
    url = (BASE + "ListaTarifasPorInstituicaoFinanceira("
           f"PessoaFisicaOuJuridica='{pf_pj}',CNPJ='{cnpj8}')?$format=json")
    d = _get(url)
    out = []
    for t in d:
        out.append({
            "codigo": t.get("CodigoServico"),
            "servico": t.get("Servico"),
            "unidade": t.get("Unidade"),
            "vigencia": t.get("DataVigencia"),
            "valor_maximo": t.get("ValorMaximo"),
            "tipo_valor": t.get("TipoValor"),
            "periodicidade": t.get("Periodicidade"),
        })
    return out
