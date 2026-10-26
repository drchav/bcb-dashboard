"""Coletor de participantes da RSFN/STR (conexoes diretas) via CSV oficial."""
import urllib.request, ssl, csv, io
import config

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def participantes_str():
    req = urllib.request.Request(config.CSV_STR, headers={"User-Agent": "painel-sfn/1.0"})
    with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
        txt = r.read().decode("utf-8-sig")
    out = []
    for row in csv.DictReader(io.StringIO(txt)):
        ispb = (row.get("ISPB") or "").strip()
        if not ispb:
            continue
        out.append({
            "ispb": ispb.zfill(8),
            "nome_reduzido": (row.get("Nome_Reduzido") or "").strip(),
            "codigo": (row.get("Número_Código") or row.get("Numero_Codigo") or "").strip(),
            "participa_compe": (row.get("Participa_da_Compe") or "").strip(),
            "acesso": (row.get("Acesso_Principal") or "").strip(),
            "nome_extenso": (row.get("Nome_Extenso") or "").strip(),
            "inicio": (row.get("Início_da_Operação") or row.get("Inicio_da_Operacao") or "").strip(),
        })
    return out
