"""Coletor da 'Lista de participantes ativos do Pix' (BCB).

Arquivo CSV oficial (ISO-8859-1, separado por ';') publicado em dias uteis em:
  https://www.bcb.gov.br/content/estabilidadefinanceira/participantes_pix/
  lista-participantes-instituicoes-em-adesao-pix-AAAAMMDD.csv

Traz, por instituicao, atributos que NAO existem em nenhuma outra fonte do painel:
  - Tipo de Participacao no SPI  -> Direta / Indireta  (o "direto/indireto")
  - Autorizada pelo BCB          -> Sim / Nao          (tem ou nao autorizacao)
  - Tipo de Instituicao          -> inclui "Instituicao de Pagamento nao sujeita
                                     a autorizacao pelo BCB" (sujeita x nao sujeita)
  - Modalidade de Participacao no Pix (Provedor de Conta Transacional / Iniciador…)
  - Iniciacao de Transacao de Pagamento (Pix Automatico/iniciador) e FSS.

Cada linha cruza com o cadastro do IF.data pelo CNPJ raiz (8 digitos): o ISPB
publicado JA e o CNPJ raiz; quando vem vazio, usamos os 8 primeiros do CNPJ.
~99% dos participantes casam com o cadastro.
"""
import urllib.request, csv, io, ssl
from datetime import date, timedelta

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE
BASE = ("https://www.bcb.gov.br/content/estabilidadefinanceira/participantes_pix/"
        "lista-participantes-instituicoes-em-adesao-pix-{}.csv")


def _baixa(url):
    req = urllib.request.Request(url, headers={"User-Agent": "painel-sfn/1.0"})
    with urllib.request.urlopen(req, timeout=120, context=_CTX) as r:
        if r.status != 200:
            return None
        return r.read().decode("latin-1", "replace")


def _so_digitos(s):
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _parse(texto):
    """Le as DUAS secoes do arquivo por posicao fixa de coluna.

    Secao 1 (11 colunas): participantes ativos, ultima col = FSS.
    Secao 2 (10 colunas): instituicoes em adesao, ultima col = etapa (ex.:
      'Etapa Homologatoria'); nao tem as colunas Iniciacao/FSS.
    Colunas comuns (por indice): 1=Nome, 2=ISPB, 3=CNPJ, 4=Tipo de Instituicao,
      5=Autorizada pelo BCB, 6=Tipo de Participacao no SPI, 7=...no Pix, 8=Modalidade.
    """
    linhas = list(csv.reader(io.StringIO(texto), delimiter=";"))
    out = {}
    for r in linhas:
        if len(r) < 10:
            continue
        nome = r[1].strip()
        if not nome or nome.lower() == "nome reduzido":  # pula cabecalhos das 2 secoes
            continue
        ispb = _so_digitos(r[2])
        cnpj = _so_digitos(r[3])
        cnpj8 = (ispb.zfill(8) if ispb else (cnpj[:8] if len(cnpj) >= 8 else ""))
        if len(cnpj8) != 8 or not cnpj8.isdigit():
            continue
        tipo = r[4].strip()
        ativo = len(r) >= 11
        out[cnpj8] = {
            "cnpj8": cnpj8,
            "nome": nome,
            "tipo_inst": tipo,
            "autorizada": 1 if r[5].strip().lower().startswith("sim") else 0,
            "nao_sujeita": 1 if "nao sujeita" in _ascii(tipo) else 0,
            "part_spi": r[6].strip() or None,     # Direta / Indireta / None
            "part_pix": r[7].strip() or None,     # Facultativa / Obrigatoria
            "modalidade": r[8].strip() or None,   # Provedor de Conta Transacional / Iniciador…
            "iniciador": 1 if (ativo and r[9].strip().lower().startswith("sim")) else 0,
            "fss": (r[10].strip() if ativo else None),
            "situacao": "Ativo" if ativo else (r[9].strip() or "Em adesao"),
        }
    return list(out.values())


def _ascii(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


def lista(dias_max=12):
    """Retorna (data_referencia AAAA-MM-DD, [ {cnpj8, ...}, ... ]) do arquivo mais recente."""
    d = date.today()
    for _ in range(dias_max):
        url = BASE.format(d.strftime("%Y%m%d"))
        try:
            txt = _baixa(url)
        except Exception:  # noqa
            txt = None
        if txt and "Nome Reduzido" in txt:
            itens = _parse(txt)
            if itens:
                return d.strftime("%Y-%m-%d"), itens
        d -= timedelta(days=1)
    return None, []
