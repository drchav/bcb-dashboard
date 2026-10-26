"""Coletor de indicadores macroeconomicos via SGS (Series Temporais do BCB).

Mesma API publica do SGS usada em credito.py. Series selecionadas e conferidas
ao vivo (Selic, inflacao, cambio PTAX, atividade) para o dominio Indicadores Macro.
"""
import urllib.request, json, ssl, time
from datetime import date

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados?formato=json&dataInicial={ini}"

# codigo -> (nome, grupo, unidade, tipo, frequencia)
#   tipo:  'pct' (percentual) | 'moeda' (R$, poucas casas) | 'moeda_mi' (R$ milhoes)
#   freq:  'D' diaria | 'M' mensal  -> define a janela de coleta
SERIES = [
    ("432",   "Meta Selic (Copom)",                    "Juros & inflação", "% a.a.",     "pct",      "D"),
    ("433",   "IPCA — variação mensal",                "Juros & inflação", "% no mês",   "pct",      "M"),
    ("13522", "IPCA — acumulado em 12 meses",          "Juros & inflação", "% a.a.",     "pct",      "M"),
    ("189",   "IGP-M — variação mensal",               "Juros & inflação", "% no mês",   "pct",      "M"),
    ("1",     "Dólar americano (venda)",               "Câmbio",           "R$",         "moeda",    "D"),
    ("21619", "Euro (venda)",                          "Câmbio",           "R$",         "moeda",    "D"),
    ("4380",  "PIB mensal — valores correntes",        "Atividade",        "R$ milhões", "moeda_mi", "M"),
]


def _get(cod, ini):
    url = BASE.format(cod=cod, ini=ini.replace("/", "%2F"))
    req = urllib.request.Request(url, headers={"User-Agent": "painel-sfn/1.0"})
    with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8"))


def series(anos_diaria=4, anos_mensal=8):
    """Retorna lista de dicts: {codigo,nome,grupo,unidade,tipo,pontos:[{data,valor}]}.

    Series diarias usam janela mais curta (muitos pontos); mensais, janela maior.
    """
    ano = date.today().year
    out = []
    for i, (cod, nome, grupo, unidade, tipo, freq) in enumerate(SERIES):
        if i:
            time.sleep(0.4)
        ini = f"01/01/{ano - (anos_diaria if freq == 'D' else anos_mensal)}"
        dados = []
        for _ in range(3):
            try:
                dados = _get(cod, ini)
                break
            except Exception:  # noqa
                time.sleep(0.8)
        pontos = []
        for d in dados:
            try:
                pontos.append({"data": d["data"], "valor": float(str(d["valor"]).replace(",", "."))})
            except Exception:  # noqa
                continue
        out.append({"codigo": cod, "nome": nome, "grupo": grupo,
                    "unidade": unidade, "tipo": tipo, "pontos": pontos})
    return out
