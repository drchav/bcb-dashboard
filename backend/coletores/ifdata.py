"""Coletor do IF.data (Olinda) - cadastro e valores dos relatorios."""
import urllib.request, urllib.parse, json, ssl, unicodedata
from datetime import date

import config

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE  # alguns ambientes Windows nao tem a cadeia do BCB


def _get(url, tentativas=3):
    ult = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "painel-sfn/1.0"})
            with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
                return json.loads(r.read().decode("utf-8")).get("value", [])
        except Exception as e:  # noqa
            ult = e
    raise RuntimeError(f"Falha ao buscar {url[:90]}...: {ult}")


def limpar_coluna(nome):
    """Remove a formula anexa (apos quebra de linha) e espacos."""
    if not nome:
        return ""
    return nome.split("\n")[0].split("\r")[0].strip()


def chave(s):
    """Normaliza para comparacao: sem acento, minusculo."""
    s = limpar_coluna(s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower().strip()


def trimestres(anos):
    """Lista de AnoMes (YYYYMM) trimestrais nos ultimos N anos, mais recente primeiro."""
    hoje = date.today()
    out = []
    for ano in range(hoje.year, hoje.year - anos - 1, -1):
        for mes in (12, 9, 6, 3):
            if ano == hoje.year and mes > hoje.month:
                continue
            out.append(f"{ano}{mes:02d}")
    return out


def cadastro(anomes):
    url = (config.OLINDA_IFDATA +
           f"IfDataCadastro(AnoMes=@A)?@A={anomes}&$format=json")
    return _get(url)


def valores(anomes, relatorio, tipo=config.TIPO_INSTITUICAO):
    url = (config.OLINDA_IFDATA +
           "IfDataValores(AnoMes=@A,TipoInstituicao=@T,Relatorio=@R)"
           f"?@A={anomes}&@T={tipo}&@R='{relatorio}'&$format=json")
    return _get(url)
