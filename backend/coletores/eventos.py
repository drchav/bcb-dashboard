"""Coletor de Comunicados do BCB sobre instituicoes (eventos regulatorios).

Os Comunicados do BCB saem numerados em sequencia e expoem conteudo limpo via
`api/conteudo/app/normativos/exibeoutrasnormas?p1=Comunicado&p2=<numero>`
(Titulo, Tipo, Data, DataTexto, Numero, Assunto em HTML).

A maioria e de politica monetaria/mercado (leiloes de swap, compromissadas, TBF/TR)
e NAO interessa aqui. Filtramos para os eventos *sobre instituicoes*: cancelamento de
autorizacao, liquidacao extrajudicial, intervencao/RAET, controle societario, posse/
eleicao de dirigentes. Varremos uma janela dos numeros mais recentes.
"""
import urllib.request, json, ssl, re, html, unicodedata
from concurrent.futures import ThreadPoolExecutor

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
URL = ("https://www.bcb.gov.br/api/conteudo/app/normativos/exibeoutrasnormas"
       "?p1=Comunicado&p2={n}")
DEFAULT_MAX = 46200   # palpite de bootstrap (numero recente); a varredura corrige
JANELA = 600          # quantos numeros varrer abaixo do maximo
WORKERS = 32


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return s.lower()


def _texto(hjson):
    return re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", html.unescape(hjson or ""))).strip()


# padroes de exclusao (politica monetaria / mercado) e de inclusao (eventos de instituicao)
_EXCLUI = re.compile(r"leila|swap|compromissad|taxa basica financeira|\btbf\b|"
                     r"taxa referencial|redutor|oferta publica|reservas internacionais|"
                     r"ptax|taxa selic|resultado de leiloes")
_CATS = [
    ("Cancelamento de autorização", r"cancel\w*\s+.*autoriza|cancelamento de autoriza"),
    ("Liquidação extrajudicial",    r"liquidacao extrajudicial"),
    ("Intervenção / RAET",          r"intervencao|\braet\b|administracao especial"),
    ("Controle societário",         r"controlador|condicao de controle|transferencia de controle|aquisicao de controle"),
    ("Autorização / funcionamento", r"autoriza\w*\s+.*funcionamento|funcionamento d|constituicao e funcionamento"),
    ("Dirigentes / órgãos",         r"eleit|nomead|orgaos estatutarios|objec|posse de"),
]


def _classificar(assunto):
    t = _norm(assunto)
    if not t or _EXCLUI.search(t):
        return None
    for cat, pat in _CATS:
        if re.search(pat, t):
            return cat
    return None


def _busca(n):
    try:
        req = urllib.request.Request(URL.format(n=n), headers={"User-Agent": "painel-sfn/1.0"})
        with urllib.request.urlopen(req, timeout=12, context=_CTX) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        c = (d.get("conteudo") or [None])[0]
        if not c:
            return None
        return {"numero": int(c.get("Numero") or n),
                "titulo": (c.get("Titulo") or "").strip(),
                "data": (c.get("Data") or "")[:10],
                "data_texto": c.get("DataTexto") or "",
                "assunto": _texto(c.get("Assunto"))}
    except Exception:  # noqa
        return None


def _sweep(nums, workers=WORKERS):
    out = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for n, res in zip(nums, ex.map(_busca, nums)):
            if res:
                out[n] = res
    return out


def eventos(seed_max=None, janela=JANELA):
    """Retorna (max_numero, lista de eventos de instituicao), mais recentes primeiro.

    Varredura unica da faixa [guess-janela .. guess+300]: acha o maximo real e ja
    coleta a janela. O +300 cobre numeros novos acima do palpite (stored max).
    """
    guess = seed_max or DEFAULT_MAX
    got = _sweep(range(guess - janela, guess + 300))
    mx = max(got) if got else guess
    evs = []
    for n in sorted(got, reverse=True):
        if n < mx - janela:
            continue
        c = got[n]
        cat = _classificar(c["assunto"])
        if cat:
            c = dict(c); c["categoria"] = cat
            evs.append(c)
    return mx, evs
