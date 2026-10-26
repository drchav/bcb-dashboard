"""Coletor de credito agregado do SFN via SGS (Sistema Gerenciador de Series Temporais).

Usa a API publica do SGS (https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados).
Os codigos e nomes foram confirmados no Portal de Dados Abertos do BCB (CKAN).
"""
import urllib.request, json, ssl, time

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados?formato=json&dataInicial={ini}"

# codigo -> (nome, unidade, tipo)  [tipo: 'moeda_mi' | 'pct']
SERIES = [
    ("20539", "Saldo da carteira de crédito — Total",            "R$ milhões", "moeda_mi"),
    ("20541", "Saldo da carteira de crédito — Pessoas Físicas",  "R$ milhões", "moeda_mi"),
    ("20540", "Saldo da carteira de crédito — Pessoas Jurídicas","R$ milhões", "moeda_mi"),
    ("20634", "Concessões de crédito (recursos livres) — Total", "R$ milhões", "moeda_mi"),
    ("20714", "Taxa média de juros das operações de crédito — Total", "% a.a.", "pct"),
    ("21082", "Inadimplência da carteira de crédito — Total",    "%",          "pct"),
]


def _get(cod, ini):
    # apenas a data precisa de escape (o host/esquema ficam intactos)
    url = BASE.format(cod=cod, ini=ini.replace("/", "%2F"))
    req = urllib.request.Request(url, headers={"User-Agent": "painel-sfn/1.0"})
    with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
        return json.loads(r.read().decode("utf-8"))


def series(anos=6):
    """Retorna lista de dicts: {codigo, nome, unidade, tipo, pontos:[{data,valor}]}.

    Coleta do SGS a partir de `anos` atras (intervalo de datas; mais robusto que ultimos/N).
    """
    from datetime import date
    ini = f"01/01/{date.today().year - anos}"
    out = []
    for i, (cod, nome, unidade, tipo) in enumerate(SERIES):
        if i:
            time.sleep(0.4)  # respiro entre chamadas (evita bloqueio por rajada)
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
        out.append({"codigo": cod, "nome": nome, "unidade": unidade,
                    "tipo": tipo, "pontos": pontos})
    return out
