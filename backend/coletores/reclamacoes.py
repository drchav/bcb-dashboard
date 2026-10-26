"""Coletor do ranking de reclamacoes (RDR / BCB)."""
import urllib.request, ssl, json, csv, io, unicodedata

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
BASE = "https://www3.bcb.gov.br/rdrweb/rest/ext/ranking"


def _get(url):
    req = urllib.request.Request(url.replace(" ", "+"), headers={"User-Agent": "painel-sfn/1.0"})
    with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
        return r.read()


def _num(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def chave_nome(n):
    n = (n or "").split("(")[0].strip()
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode()
    return n.upper().strip()


def ultimo_trimestre():
    cat = json.loads(_get(BASE + "?ano=2025&periodicidade=TRIMESTRAL&periodo=1&tipo=Bancos+e+financeiras"))
    melhor = None
    for a in cat["anos"]:
        for p in a["periodicidades"]:
            if p["periodicidade"] != "TRIMESTRAL":
                continue
            for per in p["periodos"]:
                if any(t["tipo"] == "Bancos e financeiras" for t in per["tipos"]):
                    melhor = (a["ano"], per["periodo"])
    return melhor


def trimestres_recentes(n=8):
    """Ultimos n trimestres (ano, periodo) disponiveis para 'Bancos e financeiras'."""
    cat = json.loads(_get(BASE + "?ano=2025&periodicidade=TRIMESTRAL&periodo=1&tipo=Bancos+e+financeiras"))
    pares = []
    for a in cat["anos"]:
        for p in a["periodicidades"]:
            if p["periodicidade"] != "TRIMESTRAL":
                continue
            for per in p["periodos"]:
                if any(t["tipo"] == "Bancos e financeiras" for t in per["tipos"]):
                    pares.append((int(a["ano"]), int(per["periodo"])))
    pares = sorted(set(pares), reverse=True)
    return pares[:n]


def ranking_trimestre(ano, tri):
    url = (BASE + f"/arquivo?ano={ano}&periodicidade=TRIMESTRAL&periodo={tri}"
           "&tipo=Bancos+e+financeiras")
    raw = _get(url).decode("latin-1")
    rows = list(csv.reader(io.StringIO(raw), delimiter=";"))
    if not rows:
        return []
    out = []
    for r in rows[1:]:
        if len(r) < 12 or not r[5].strip():
            continue
        out.append({
            "ano": r[0].strip(), "trimestre": r[1].strip(), "categoria": r[2].strip(),
            "nome": r[5].strip(), "nome_norm": chave_nome(r[5]),
            "indice": _num(r[6]),
            "reclamacoes": _num(r[7]), "procedentes": _num(r[8]),
            "analisadas": _num(r[10]) if len(r) > 10 else None,
            "clientes": _num(r[11]) if len(r) > 11 else None,
        })
    return out
