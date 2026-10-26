"""Coletor de atos e eventos do BCB sobre instituicoes (supervisao).

Duas fontes do Portal de Dados Abertos / Olinda:
  * regimes_especiais  -> instituicoes em liquidacao extrajudicial, intervencao, RAET
  * Gepad_QuadroPenalidades -> processo administrativo sancionador (multas/penalidades)
Ambas trazem CNPJ, permitindo cruzar com o cadastro do IF.data.
"""
import urllib.request, json, ssl

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
REGIMES = "https://olinda.bcb.gov.br/olinda/servico/regimes_especiais/versao/v1/odata/Regimes?$format=json"
PENAS = ("https://olinda.bcb.gov.br/olinda/servico/Gepad_QuadroPenalidades/versao/v1/odata/"
         "QuadroGeralProcessoAdministrativoSancionador?$format=json")


def _get(url):
    req = urllib.request.Request(url.replace(" ", "%20"), headers={"User-Agent": "painel-sfn/1.0"})
    with urllib.request.urlopen(req, timeout=120, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8", "replace")).get("value", [])


def regimes():
    """Instituicoes sob regime especial (posicao atual)."""
    out = []
    for r in _get(REGIMES):
        cnpj = (r.get("CnpjInstituicao") or "").strip()
        raiz = (r.get("CnpjRaiz") or (cnpj[:8] if cnpj else "")).zfill(8)
        out.append({
            "cnpj": cnpj, "cnpj8": raiz, "nome": r.get("NomeInstituicao"),
            "inicio": r.get("Inicio"), "tipo": r.get("Tipo"),
            "responsavel": r.get("Responsavel"),
            "municipio": r.get("Municipio"), "uf": r.get("UF"),
            "endereco": r.get("Endereco"), "cep": r.get("CEP"),
            "emails": r.get("Emails"), "telefones": r.get("Telefones"),
        })
    return out


def penalidades():
    """Penalidades aplicadas em processo administrativo sancionador."""
    out = []
    for r in _get(PENAS):
        doc = (r.get("CPF_CNPJ") or "").strip()
        raiz = doc[:8].zfill(8) if len(doc) >= 8 else ""
        # usa a penalidade/decisao de instancia mais avancada disponivel
        tipo = r.get("Tipo_penalidade_2_instancia") or r.get("Tipo_penalidade_1_instancia")
        valor = r.get("Valor_da_multa_2_instancia")
        if valor is None:
            valor = r.get("Valor_da_multa_1_instancia")
        data = r.get("Data_da_decisao_2_instancia") or r.get("Data_da_decisao_1_instancia")
        out.append({
            "pas": r.get("PAS"), "nome": r.get("Nome"), "cnpj_cpf": doc, "cnpj8": raiz,
            "data_citacao": r.get("Data_da_citacao"), "data_decisao": data,
            "tipo_penalidade": tipo, "valor_multa": valor,
            "situacao": r.get("Situacao"),
        })
    return out
