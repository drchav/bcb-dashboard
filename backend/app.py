"""Servidor local (stdlib) - Hub do SFN: API JSON + frontend estatico."""
import json, os, threading, webbrowser, urllib.parse, gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import defaultdict, Counter

import config, db, auth
from coletores import ifdata, cnpj as cnpjmod, tarifas as tarifasmod

# ================================================================ helpers dominio
_seg_cache = {}
def segmento_map(con, anomes):
    if anomes in _seg_cache:
        return _seg_cache[anomes]
    grp = defaultdict(Counter)
    for r in con.execute(
        "SELECT cod_prud, sr FROM cadastro WHERE anomes=? AND sr IS NOT NULL AND cod_prud IS NOT NULL",
        (anomes,)):
        grp[r["cod_prud"]][r["sr"]] += 1
    seg_grupo = {g: c.most_common(1)[0][0] for g, c in grp.items()}
    m = {}
    for r in con.execute("SELECT cod, sr, cod_prud FROM cadastro WHERE anomes=?", (anomes,)):
        m[r["cod"]] = r["sr"] or seg_grupo.get(r["cod_prud"]) or "NA"
    _seg_cache[anomes] = m
    return m

_rsfn_cache = {}
def rsfn_map(con):
    if _rsfn_cache:
        return _rsfn_cache
    for r in con.execute("SELECT ispb,codigo,acesso,nome_reduzido,participa_compe FROM str_participantes"):
        _rsfn_cache[r["ispb"].zfill(8)] = {"codigo": r["codigo"], "acesso": r["acesso"],
                                   "nome": r["nome_reduzido"],
                                   "direto": r["acesso"] == "RSFN",
                                   "compe": r["participa_compe"] == "Sim"}
    return _rsfn_cache

_pix_cache = None
def pix_set(con):
    """Conjunto de ISPBs (8 digitos) participantes do arranjo PIX."""
    global _pix_cache
    if _pix_cache is None:
        _pix_cache = set(r["ispb"].zfill(8) for r in con.execute("SELECT ispb FROM pix_participantes"))
    return _pix_cache

_pixlista_cache = None
def pixlista_map(con):
    """cnpj8 (raiz) -> atributos da Lista de participantes do Pix (SPI direto/indireto,
    autorizacao pelo BCB, sujeicao a autorizacao, modalidade)."""
    global _pixlista_cache
    if _pixlista_cache is None:
        _pixlista_cache = {}
        for r in con.execute("SELECT cnpj8,tipo_inst,autorizada,nao_sujeita,part_spi,"
                             "part_pix,modalidade,iniciador,fss,situacao FROM pix_lista"):
            _pixlista_cache[r["cnpj8"]] = dict(r)
    return _pixlista_cache

_codfin_cache = None
def _codfin_set(con):
    global _codfin_cache
    if _codfin_cache is None:
        _codfin_cache = set(r["cod"] for r in con.execute("SELECT DISTINCT cod FROM valores"))
    return _codfin_cache

# caches de payload por anomes (invalidados a cada reinicio do servidor / recoleta)
_registro_cache = {}
_prudencial_cache = {}

_PIVOT = [(alias, rel, ifdata.chave(label)) for rel, label, alias in config.METRICAS_CHAVE]
def _pivot_sql():
    return ",\n".join(
        f"MAX(CASE WHEN v.relatorio='{rel}' AND v.coluna_norm='{norm}' THEN v.saldo END) AS {alias}"
        for alias, rel, norm in _PIVOT)

def anomes_vigente(con, q):
    am = q.get("anomes", [None])[0]
    disp = db.anomes_disponiveis(con)
    return am if (am and am in disp) else (disp[0] if disp else None)

def ispb_de(cnpj_lider):
    return (cnpj_lider or "").zfill(8) if cnpj_lider else None

# ================================================================ endpoints
def api_meta(con, q):
    disp = db.anomes_disponiveis(con)
    return {
        "ultima_atualizacao": db.get_meta(con, "ultima_atualizacao"),
        "modo": db.get_meta(con, "modo"),
        "anomes_disponiveis": disp,
        "relatorios": config.RELATORIOS,
        "total_cadastro": con.execute("SELECT COUNT(*) n FROM cadastro WHERE anomes=(SELECT MAX(anomes) FROM cadastro)").fetchone()["n"],
        "total_com_financas": con.execute("SELECT COUNT(DISTINCT cod) n FROM valores").fetchone()["n"],
        "total_rsfn": con.execute("SELECT COUNT(*) n FROM str_participantes").fetchone()["n"],
    }

def api_panorama(con, q):
    am = anomes_vigente(con, q)
    if not am:
        return {"anomes": None}
    seg = segmento_map(con, am)
    rsfn = rsfn_map(con)
    codfin = _codfin_set(con)
    por_grupo = Counter(); por_tipo = Counter(); por_situacao = Counter()
    por_uf = Counter(); por_controle = Counter(); por_seg = Counter()
    total = 0
    for r in con.execute("SELECT cod,tcb,td,tc,uf,situacao,cnpj_lider FROM cadastro WHERE anomes=? AND td='I'", (am,)):
        total += 1
        g, _ = config.tipo_info(r["tcb"])
        por_grupo[g] += 1
        por_tipo[r["tcb"] or "?"] += 1
        por_situacao["Ativa" if r["situacao"] == "A" else (r["situacao"] or "?")] += 1
        if r["uf"]: por_uf[r["uf"]] += 1
        por_controle[config.TC_LBL.get(str(r["tc"]), "?")] += 1
        if r["cod"] in codfin:
            por_seg[seg.get(r["cod"], "NA")] += 1
    # totais financeiros (prudencial)
    tot = con.execute(f"""
        SELECT MAX(CASE WHEN v.relatorio='1' AND v.coluna_norm='ativo total' THEN v.saldo END) a
        FROM valores v WHERE v.anomes=?""", (am,)).fetchone()
    ativo_total = con.execute("""SELECT SUM(saldo) s FROM valores
        WHERE anomes=? AND relatorio='1' AND coluna_norm='ativo total'""", (am,)).fetchone()["s"]
    credito_total = con.execute("""SELECT SUM(saldo) s FROM valores
        WHERE anomes=? AND relatorio='1' AND coluna_norm='carteira de credito'""", (am,)).fetchone()["s"]
    pix = con.execute("SELECT data,quantidade,total,media FROM pix_liquidados ORDER BY data DESC LIMIT 1").fetchone()
    pix_pico = con.execute("SELECT data,quantidade FROM pix_liquidados ORDER BY quantidade DESC LIMIT 1").fetchone()
    return {
        "anomes": am, "total_instituicoes": total,
        "ativo_total": ativo_total, "credito_total": credito_total,
        "rsfn_total": con.execute("SELECT COUNT(*) n FROM str_participantes").fetchone()["n"],
        "por_grupo": [{"k": k, "n": n} for k, n in por_grupo.most_common()],
        "por_tipo": [{"k": k, "nome": config.tipo_info(k)[1], "n": n} for k, n in por_tipo.most_common()],
        "por_situacao": [{"k": k, "n": n} for k, n in por_situacao.most_common()],
        "por_uf": [{"k": k, "n": n} for k, n in por_uf.most_common()],
        "por_controle": [{"k": k, "n": n} for k, n in por_controle.most_common()],
        "por_segmento": [{"k": k, "n": por_seg.get(k, 0)} for k in ["S1","S2","S3","S4","S5","NA"]],
        "pix_dia": dict(pix) if pix else None,
        "pix_pico": dict(pix_pico) if pix_pico else None,
    }

def api_registro(con, q):
    """Registro central de instituicoes (todos os tipos) no periodo vigente."""
    am = anomes_vigente(con, q)
    if not am:
        return {"anomes": None, "itens": []}
    if am in _registro_cache:
        return _registro_cache[am]
    seg = segmento_map(con, am)
    rsfn = rsfn_map(con)
    pix = pix_set(con)
    plista = pixlista_map(con)
    codfin = _codfin_set(con)
    # metricas-chave (so existem p/ quem tem financas)
    fin = {}
    for r in con.execute(f"SELECT c.cod, {_pivot_sql()} FROM cadastro c "
                         f"JOIN valores v ON v.cod=c.cod AND v.anomes=c.anomes "
                         f"WHERE c.anomes=? GROUP BY c.cod", (am,)):
        fin[r["cod"]] = dict(r)
    itens = []
    for r in con.execute("""SELECT cod,nome,tcb,td,tc,uf,municipio,situacao,cnpj_lider,dt_inicio
                            FROM cadastro WHERE anomes=?""", (am,)):
        grupo, tipo_desc = config.tipo_info(r["tcb"])
        ispb = ispb_de(r["cnpj_lider"])
        rs = rsfn.get(ispb) if ispb else None
        item = {
            "cod": r["cod"], "nome": r["nome"], "tcb": r["tcb"],
            "grupo": grupo, "tipo_desc": tipo_desc,
            "td": "Individual" if r["td"] == "I" else "Conglomerado",
            "controle": config.TC_LBL.get(str(r["tc"]), "?"),
            "uf": r["uf"], "municipio": r["municipio"],
            "situacao": "Ativa" if r["situacao"] == "A" else (r["situacao"] or "?"),
            "cnpj": r["cnpj_lider"], "seg": seg.get(r["cod"], "NA"),
            "rsfn": bool(rs), "compe_cod": rs["codigo"] if rs else None,
            "acesso": rs["acesso"] if rs else None,
            "rsfn_direto": bool(rs and rs["direto"]),
            "compe": bool(rs and rs["compe"]),
            "pix": bool(ispb and ispb in pix),
            "tem_financas": r["cod"] in codfin,
        }
        # atributos da Lista de participantes do Pix (por CNPJ raiz = cod)
        pl = plista.get(r["cod"])
        if pl:
            # autorizacao: 3 estados mutuamente exclusivos
            autoriz = ("nao_sujeita" if pl["nao_sujeita"]
                       else "autorizada" if pl["autorizada"] else "nao_autorizada")
            item.update({
                "part_spi": pl["part_spi"],          # Direta / Indireta / None
                "autorizada": bool(pl["autorizada"]),
                "nao_sujeita": bool(pl["nao_sujeita"]),
                "autoriz": autoriz,                  # autorizada | nao_autorizada | nao_sujeita
                "modalidade_pix": pl["modalidade"],
                "iniciador": bool(pl["iniciador"]),
                "tipo_inst_pix": pl["tipo_inst"],
                "situacao_pix": pl["situacao"],
                "no_pix_lista": True,
            })
        f = fin.get(r["cod"])
        if f:
            for alias, _, _ in _PIVOT:
                item[alias] = f.get(alias)
            item["roe"] = (f.get("lucro")/f.get("pl")) if f.get("pl") else None
        itens.append(item)
    out = {"anomes": am, "itens": itens}
    _registro_cache[am] = out
    return out

def api_prudencial_overview(con, q):
    am = anomes_vigente(con, q)
    if not am:
        return {"anomes": None}
    if am in _prudencial_cache:
        return _prudencial_cache[am]
    seg = segmento_map(con, am)
    rows = con.execute("""SELECT c.cod,c.uf,
        MAX(CASE WHEN v.relatorio='1' AND v.coluna_norm='ativo total' THEN v.saldo END) ativo,
        MAX(CASE WHEN v.relatorio='1' AND v.coluna_norm='patrimonio liquido' THEN v.saldo END) pl,
        MAX(CASE WHEN v.relatorio='1' AND v.coluna_norm='lucro liquido' THEN v.saldo END) lucro,
        MAX(CASE WHEN v.relatorio='1' AND v.coluna_norm='carteira de credito' THEN v.saldo END) credito
        FROM cadastro c JOIN valores v ON v.cod=c.cod AND v.anomes=c.anomes
        WHERE c.anomes=? GROUP BY c.cod""", (am,)).fetchall()
    por_seg = defaultdict(lambda: {"n":0,"ativo":0.0,"pl":0.0,"lucro":0.0,"credito":0.0})
    por_uf = defaultdict(lambda: {"n":0,"ativo":0.0})
    tot = {"n":0,"ativo":0.0,"pl":0.0,"lucro":0.0,"credito":0.0}
    for r in rows:
        s = seg.get(r["cod"], "NA")
        for k in ("ativo","pl","lucro","credito"):
            por_seg[s][k]+=r[k] or 0; tot[k]+=r[k] or 0
        por_seg[s]["n"]+=1; tot["n"]+=1
        if r["uf"]: por_uf[r["uf"]]["n"]+=1; por_uf[r["uf"]]["ativo"]+=r["ativo"] or 0
    ordem=["S1","S2","S3","S4","S5","NA"]
    out = {"anomes":am,"totais":tot,
           "por_segmento":[dict(seg=s,**por_seg[s]) for s in ordem if s in por_seg],
           "por_uf":sorted([dict(uf=u,**por_uf[u]) for u in por_uf],key=lambda x:-x["ativo"])}
    _prudencial_cache[am] = out
    return out

def api_pagamentos(con, q):
    pix = [dict(r) for r in con.execute(
        "SELECT data,quantidade,total,media FROM pix_liquidados ORDER BY data")]
    rsfn_rows = [dict(r) for r in con.execute(
        "SELECT ispb,nome_reduzido,codigo,participa_compe,acesso,nome_extenso,inicio "
        "FROM str_participantes ORDER BY nome_reduzido")]
    por_acesso = Counter(r["acesso"] for r in rsfn_rows if r["acesso"])
    return {"pix_serie": pix, "rsfn": rsfn_rows,
            "rsfn_total": len(rsfn_rows),
            "rsfn_por_acesso": [{"k":k,"n":n} for k,n in por_acesso.most_common()]}

def api_participacao(con, q):
    """Matriz de participacao nos arranjos: PIX, STR/TED, RSFN direto e COMPE,
    com as intersecoes (cruzamento por ISPB)."""
    pix = pix_set(con)
    strrows = list(con.execute("SELECT ispb,acesso,participa_compe FROM str_participantes"))
    str_set = set(r["ispb"].zfill(8) for r in strrows)
    direto = set(r["ispb"].zfill(8) for r in strrows if r["acesso"] == "RSFN")
    compe = set(r["ispb"].zfill(8) for r in strrows if r["participa_compe"] == "Sim")
    n = len
    return {
        "pix_data": db.get_meta(con, "pix_participantes_data"),
        "totais": {
            "pix": n(pix), "str": n(str_set), "rsfn_direto": n(direto), "compe": n(compe),
        },
        "cruzamentos": {
            "pix_e_str": n(pix & str_set),
            "pix_e_rsfn_direto": n(pix & direto),
            "pix_sem_str": n(pix - str_set),
            "str_sem_pix": n(str_set - pix),
            "compe_e_pix": n(compe & pix),
            "str_indireto": n(str_set - direto),
        },
        # por segmento do PIX (contexto)
        "pix_por_segmento": [{"k": k, "n": v} for k, v in Counter(
            r["segmento"] for r in con.execute("SELECT segmento FROM pix_participantes")).most_common()],
    }

def api_supervisao(con, q):
    """Atos e eventos do BCB sobre instituicoes: regimes especiais + penalidades."""
    regimes = [dict(r) for r in con.execute(
        "SELECT cnpj8,cnpj,nome,inicio,tipo,responsavel,municipio,uf,endereco,cep,emails,telefones "
        "FROM regimes_especiais "
        "ORDER BY substr(inicio,7,4)||substr(inicio,4,2)||substr(inicio,1,2) DESC")]
    # o 'cod' do cadastro e a raiz do CNPJ (8 digitos) p/ instituicoes individuais;
    # casa cnpj8 do regime -> cod para tornar a linha clicavel (abrir a instituicao)
    am = anomes_vigente(con, q)
    cods = {c["cod"] for c in con.execute("SELECT cod FROM cadastro WHERE anomes=?", (am,))}
    for r in regimes:
        r["cod"] = r["cnpj8"] if r["cnpj8"] in cods else None
    pen = list(con.execute(
        "SELECT nome,cnpj8,data_decisao,tipo_penalidade,valor_multa,situacao,pas FROM penalidades"))
    por_tipo = Counter((r["tipo_penalidade"] or "—") for r in pen)
    por_situacao = Counter((r["situacao"] or "—") for r in pen)
    # top instituicoes por nº de penalidades
    por_inst = Counter((r["nome"] or "—") for r in pen)
    recentes = sorted(pen, key=lambda r: (r["data_decisao"] or ""), reverse=True)[:300]
    return {
        "regimes": regimes,
        "regimes_total": len(regimes),
        "penalidades_total": len(pen),
        "penalidades_por_tipo": [{"k": k, "n": v} for k, v in por_tipo.most_common()],
        "penalidades_por_situacao": [{"k": k, "n": v} for k, v in por_situacao.most_common(8)],
        "penalidades_top_instituicoes": [{"k": k, "n": v} for k, v in por_inst.most_common(20)],
        "penalidades_recentes": [dict(r) for r in recentes],
    }

def api_eventos(con, q):
    """Comunicados do BCB sobre instituicoes (eventos regulatorios), com link oficial."""
    rows = [dict(r) for r in con.execute(
        "SELECT numero,data,data_texto,titulo,assunto,categoria FROM eventos ORDER BY numero DESC")]
    for r in rows:
        r["url"] = ("https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo"
                    f"?tipo=Comunicado&numero={r['numero']}")
    por_cat = Counter((r["categoria"] or "—") for r in rows)
    return {"itens": rows, "total": len(rows),
            "por_categoria": [{"k": k, "n": v} for k, v in por_cat.most_common()],
            "numero_max": db.get_meta(con, "eventos_max")}

def api_instituicao(con, cod, q):
    am = anomes_vigente(con, q)
    cad = con.execute("SELECT * FROM cadastro WHERE cod=? AND anomes=?", (cod, am)).fetchone()
    if not cad:
        cad = con.execute("SELECT * FROM cadastro WHERE cod=? ORDER BY anomes DESC LIMIT 1", (cod,)).fetchone()
    if not cad:
        return {"erro": "nao encontrada"}
    am = cad["anomes"]
    seg = segmento_map(con, am)
    rsfn = rsfn_map(con)
    ispb = ispb_de(cad["cnpj_lider"])
    grupo, tipo_desc = config.tipo_info(cad["tcb"])
    d = {"cadastro": dict(cad), "seg": seg.get(cod, "NA"), "anomes": am,
         "grupo": grupo, "tipo_desc": tipo_desc,
         "controle": config.TC_LBL.get(str(cad["tc"]), "?"),
         "rsfn": rsfn.get(ispb) if ispb else None,
         "cnpj8": ispb,
         "cnpj_completo": cnpjmod.cnpj_completo(ispb) if ispb else None,
         "relatorios_nomes": config.RELATORIOS}
    # taxas praticadas (por cnpj8): imobiliario (mensal) + credito por modalidade (semanal)
    if ispb:
        d["taxas"] = [dict(r) for r in con.execute(
            "SELECT modalidade,taxa_mes,taxa_ano,posicao,anomes FROM taxas WHERE cnpj8=? ORDER BY taxa_ano", (ispb,))]
        d["taxas_credito"] = [dict(r) for r in con.execute(
            "SELECT segmento,modalidade,taxa_mes,taxa_ano,posicao,periodo_ini,periodo_fim "
            "FROM taxas_credito WHERE cnpj8=? ORDER BY segmento, taxa_ano", (ispb,))]
    else:
        d["taxas"] = []
        d["taxas_credito"] = []
    # supervisao: regime especial + penalidades + participacao no PIX (por cnpj8)
    if ispb:
        reg = con.execute(
            "SELECT tipo,inicio,responsavel,municipio,uf FROM regimes_especiais WHERE cnpj8=? LIMIT 1",
            (ispb,)).fetchone()
        d["regime"] = dict(reg) if reg else None
        d["penalidades"] = [dict(r) for r in con.execute(
            "SELECT data_decisao,tipo_penalidade,valor_multa,situacao,pas FROM penalidades "
            "WHERE cnpj8=? ORDER BY data_decisao DESC", (ispb,))]
        d["pix_participa"] = ispb in pix_set(con)
    else:
        d["regime"] = None; d["penalidades"] = []; d["pix_participa"] = False
    # Lista de participantes do Pix (por CNPJ raiz = cod): SPI direto/indireto,
    # autorizacao pelo BCB, sujeicao a autorizacao, modalidade, situacao
    pl = pixlista_map(con).get(cod)
    if pl:
        pl = dict(pl)
        pl["autoriz"] = ("nao_sujeita" if pl["nao_sujeita"]
                         else "autorizada" if pl["autorizada"] else "nao_autorizada")
        pl["pix_lista_data"] = db.get_meta(con, "pix_lista_data")
    d["pix_lista"] = pl
    d["reclamacoes"] = reclamacoes_de(con, cad["nome"])
    rel = defaultdict(list)
    for r in con.execute("SELECT relatorio,grupo,coluna,saldo FROM valores WHERE cod=? AND anomes=? ORDER BY relatorio", (cod, am)):
        rel[r["relatorio"]].append({"grupo": r["grupo"], "coluna": r["coluna"], "saldo": r["saldo"]})
    d["relatorios"] = dict(rel)
    hist = defaultdict(list)
    for alias, reln, norm in _PIVOT:
        for r in con.execute("SELECT anomes,saldo FROM valores WHERE cod=? AND relatorio=? AND coluna_norm=? ORDER BY anomes", (cod, reln, norm)):
            hist[alias].append({"anomes": r["anomes"], "valor": r["saldo"]})
    d["historico"] = hist
    return d

# ---------------------------------------------------------------- CNPJ / fontes
def api_cnpj(con, raiz8, q):
    raiz8 = (raiz8 or "").zfill(8)
    row = con.execute("SELECT dados FROM cnpj_cache WHERE cnpj8=?", (raiz8,)).fetchone()
    if row:
        return json.loads(row["dados"])
    try:
        d = cnpjmod.consultar(raiz8)
    except Exception as e:  # noqa
        return {"erro": f"consulta CNPJ indisponivel: {e}", "cnpj": cnpjmod.cnpj_completo(raiz8)}
    import datetime as _dt
    con.execute("INSERT OR REPLACE INTO cnpj_cache(cnpj8,dados,obtido) VALUES(?,?,?)",
                (raiz8, json.dumps(d, ensure_ascii=False), _dt.datetime.now().isoformat(timespec="seconds")))
    con.commit()
    return d

FONTES = [
    {"dominio":"Instituições","nome":"IF.data — Dados de instituições financeiras","status":"integrado",
     "desc":"Cadastro, balanço, capital e segmentação por instituição, com histórico.",
     "url":"https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/",
     "site":"https://www3.bcb.gov.br/ifdata/"},
    {"dominio":"Instituições","nome":"Segmentação (Resolução CMN 4.553/2017)","status":"integrado",
     "desc":"Define os segmentos S1–S5 por porte e atividade internacional.",
     "url":"https://www.bcb.gov.br/content/estabilidadefinanceira/segmentacaosfn/Resolucao_CMN_4553.pdf",
     "site":"https://www.bcb.gov.br/estabilidadefinanceira/segmentacaosfn"},
    {"dominio":"Pagamentos","nome":"Participantes da RSFN / STR","status":"integrado",
     "desc":"Diretório das instituições com conexão direta à RSFN (ISPB, código COMPE, acesso).",
     "url":"https://www.bcb.gov.br/content/estabilidadefinanceira/str1/ParticipantesSTR.csv",
     "site":"https://www.bcb.gov.br/estabilidadefinanceira/participantesstr"},
    {"dominio":"Pagamentos","nome":"SPI — PIX liquidados","status":"integrado",
     "desc":"Estatísticas diárias do PIX liquidado no Sistema de Pagamentos Instantâneos.",
     "url":"https://olinda.bcb.gov.br/olinda/servico/SPI/versao/v1/odata/",
     "site":"https://www.bcb.gov.br/estabilidadefinanceira/estatisticaspix"},
    {"dominio":"Pagamentos","nome":"Participantes do PIX (diretório)","status":"integrado",
     "desc":"Instituições participantes do arranjo PIX (por ISPB e segmento), para cruzar com RSFN/STR e COMPE — quem está e quem não está no PIX.",
     "url":"https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/",
     "site":"https://www.bcb.gov.br/estabilidadefinanceira/participantespix"},
    {"dominio":"Pagamentos","nome":"Lista de participantes ativos do Pix","status":"integrado",
     "desc":"Por instituição: participação no SPI (direta/indireta), se é autorizada pelo BCB, se é sujeita ou não à autorização, modalidade (Provedor de Conta Transacional / Iniciador) e situação (ativo / em adesão). Cruza por CNPJ raiz com o cadastro.",
     "url":"https://www.bcb.gov.br/content/estabilidadefinanceira/participantes_pix/lista-participantes-instituicoes-em-adesao-pix-20261023.csv",
     "site":"https://www.bcb.gov.br/estabilidadefinanceira/participantespix"},
    {"dominio":"Pagamentos","nome":"COMPE / boleto (sinal via ParticipantesSTR)","status":"parcial",
     "desc":"Flag de participação na COMPE (compensação) do arquivo da RSFN. ATENÇÃO: não é a lista de participantes de boleto da Nucléa — o BCB/Nucléa não publicam essa lista como dado aberto estruturado (apenas PDFs, e o SLC da Nucléa é de cartões).",
     "url":"https://www.bcb.gov.br/content/estabilidadefinanceira/str1/ParticipantesSTR.csv",
     "site":"https://www.nuclea.com.br/"},
    {"dominio":"Crédito","nome":"Taxas de juros por instituição e modalidade","status":"integrado",
     "desc":"Taxas praticadas por instituição em todas as modalidades de crédito (crédito pessoal, consignado, veículos, cartão, cheque especial, capital de giro etc.) para PF e PJ, além de financiamento imobiliário.",
     "url":"https://olinda.bcb.gov.br/olinda/servico/taxaJuros/versao/v2/odata/",
     "site":"https://www.bcb.gov.br/estabilidadefinanceira/txjuros"},
    {"dominio":"Cadastral","nome":"CNPJ — Receita Federal (via BrasilAPI)","status":"integrado",
     "desc":"Razão social, situação cadastral, CNAE, endereço, capital social, porte e quadro de sócios (QSA).",
     "url":"https://brasilapi.com.br/api/cnpj/v1/","site":"https://brasilapi.com.br/"},
    {"dominio":"Crédito","nome":"Crédito agregado do SFN (SGS)","status":"integrado",
     "desc":"Saldo da carteira (total, PF, PJ), concessões, taxa média de juros e inadimplência — séries mensais do SGS.",
     "url":"https://api.bcb.gov.br/dados/serie/bcdata.sgs.20539/dados?formato=json",
     "site":"https://www3.bcb.gov.br/sgspub/"},
    {"dominio":"Crédito","nome":"SCR — carteira por modalidade, UF e cliente","status":"integrado",
     "desc":"Carteira de crédito do SFN detalhada por modalidade, UF/sub-região e tipo de cliente (PF/PJ), com operações e valor vencido (inadimplência) — SCR por sub-região.",
     "url":"https://olinda.bcb.gov.br/olinda/servico/scr_sub_regiao/versao/v1/odata/",
     "site":"https://www.bcb.gov.br/estabilidadefinanceira/scr"},
    {"dominio":"Conduta","nome":"Ranking de reclamações","status":"integrado",
     "desc":"Ranking trimestral de reclamações por instituição e índice de reclamações.",
     "url":"https://www3.bcb.gov.br/rdrweb/rest/ext/ranking","site":"https://www.bcb.gov.br/estabilidadefinanceira/rankingreclamacoes"},
    {"dominio":"Tarifas","nome":"Tarifas de serviços por instituição","status":"integrado",
     "desc":"Tarifas de serviços bancários por instituição e por grupo consolidado (consulta por CNPJ).",
     "url":"https://olinda.bcb.gov.br/olinda/servico/Informes_ListaTarifasPorInstituicaoFinanceira/versao/v1/odata/",
     "site":"https://www.bcb.gov.br/estabilidadefinanceira/tarifas"},
    {"dominio":"Supervisão","nome":"Instituições em regime especial","status":"integrado",
     "desc":"Instituições sob liquidação extrajudicial, intervenção ou RAET — com CNPJ, data de início, tipo e liquidante/responsável.",
     "url":"https://olinda.bcb.gov.br/olinda/servico/regimes_especiais/versao/v1/odata/Regimes?$format=json",
     "site":"https://www.bcb.gov.br/estabilidadefinanceira/regimesespeciais"},
    {"dominio":"Supervisão","nome":"Processo administrativo sancionador (penalidades)","status":"integrado",
     "desc":"Penalidades aplicadas pelo BCB a instituições e pessoas (multas, inabilitações etc.), por CNPJ/CPF, com decisões de 1ª e 2ª instância.",
     "url":"https://olinda.bcb.gov.br/olinda/servico/Gepad_QuadroPenalidades/versao/v1/odata/",
     "site":"https://www.bcb.gov.br/acessoinformacao/legado?url=https:%2F%2Fwww.bcb.gov.br%2Ffis%2Fpas%2F"},
    {"dominio":"Supervisão","nome":"Comunicados do BCB sobre instituições","status":"integrado",
     "desc":"Comunicados oficiais do BCB com eventos de instituições: intenção de cancelar autorização, decretação de liquidação extrajudicial, intervenção/RAET, mudança de controle societário e posse/eleição de dirigentes — com link direto para cada comunicado. Filtramos os comunicados de política monetária/mercado (leilões, swap, TBF).",
     "url":"https://www.bcb.gov.br/api/conteudo/app/normativos/exibeoutrasnormas?p1=Comunicado&p2=46150",
     "site":"https://www.bcb.gov.br/estabilidadefinanceira/buscanormas"},
    {"dominio":"Supervisão","nome":"Busca de normas do BCB","status":"parcial",
     "desc":"Atos normativos (resoluções, circulares) do BCB. A API de busca existe (api/search/app/normativos/buscanormativos, ~47 mil normas), mas retorna títulos não padronizados (nomes internos de arquivo), sem data/ementa estruturadas — por isso só linkamos a busca oficial em vez de listar dados de baixa qualidade.",
     "url":"https://www.bcb.gov.br/api/search/app/normativos/buscanormativos?querytext=%27*%27&startrow=0&rowlimit=10",
     "site":"https://www.bcb.gov.br/estabilidadefinanceira/buscanormas"},
    {"dominio":"Macro","nome":"Expectativas de Mercado (Focus)","status":"integrado",
     "desc":"Projeções de mercado para Selic, inflação, câmbio e PIB.",
     "url":"https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/",
     "site":"https://www.bcb.gov.br/controleinflacao/expectativas"},
    {"dominio":"Macro","nome":"SGS — Séries Temporais (indicadores macro)","status":"integrado",
     "desc":"Meta Selic, IPCA (mensal e 12 meses), IGP-M, câmbio (dólar e euro) e PIB mensal — séries do SGS. Crédito agregado também integrado no domínio Crédito.",
     "url":"https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados?formato=json",
     "site":"https://www3.bcb.gov.br/sgspub/"},
]
def api_fontes(con, q):
    return {"fontes": FONTES}

def api_credito(con, q):
    """Credito agregado do SFN (series SGS)."""
    series = []
    for cod in con.execute("SELECT DISTINCT codigo FROM sgs_credito ORDER BY codigo"):
        c = cod["codigo"]
        meta_r = con.execute("SELECT nome,unidade,tipo FROM sgs_credito WHERE codigo=? LIMIT 1", (c,)).fetchone()
        pts = [dict(r) for r in con.execute(
            "SELECT data,valor FROM sgs_credito WHERE codigo=? ORDER BY substr(data,7,4)||substr(data,4,2)", (c,))]
        if not pts:
            continue
        series.append({"codigo": c, "nome": meta_r["nome"], "unidade": meta_r["unidade"],
                       "tipo": meta_r["tipo"], "pontos": pts,
                       "ultimo": pts[-1], "primeiro": pts[0]})
    return {"series": series, "atualizado": db.get_meta(con, "ultima_atualizacao")}

def api_scr(con, q):
    """Carteira de credito do SFN por modalidade, UF e cliente (SCR, R$)."""
    MIL = 1000.0  # CARTEIRA/vencido vem em R$ mil
    rows = con.execute(
        "SELECT cliente,estado,modalidade,operacoes,carteira,vencido FROM scr_credito").fetchall()
    if not rows:
        return {"data_base": None, "por_modalidade": [], "por_uf": [], "total": {}}
    por_mod = defaultdict(lambda: {"carteira":0.0,"vencido":0.0,"operacoes":0,"pf":0.0,"pj":0.0})
    por_uf = defaultdict(lambda: {"carteira":0.0,"vencido":0.0,"operacoes":0})
    tot = {"carteira":0.0,"vencido":0.0,"operacoes":0,"pf":0.0,"pj":0.0}
    for r in rows:
        cart = (r["carteira"] or 0)*MIL; venc = (r["vencido"] or 0)*MIL; op = r["operacoes"] or 0
        m = por_mod[r["modalidade"] or "—"]
        m["carteira"]+=cart; m["vencido"]+=venc; m["operacoes"]+=op
        u = por_uf[r["estado"] or "—"]
        u["carteira"]+=cart; u["vencido"]+=venc; u["operacoes"]+=op
        tot["carteira"]+=cart; tot["vencido"]+=venc; tot["operacoes"]+=op
        if r["cliente"] == "PF": m["pf"]+=cart; tot["pf"]+=cart
        elif r["cliente"] == "PJ": m["pj"]+=cart; tot["pj"]+=cart
    def fin(d):
        d = dict(d); d["inadimplencia"] = (d["vencido"]/d["carteira"]) if d["carteira"] else None; return d
    por_mod_l = sorted([{"modalidade":k, **fin(v)} for k,v in por_mod.items()], key=lambda x:-x["carteira"])
    por_uf_l = sorted([{"uf":k, **fin(v)} for k,v in por_uf.items()], key=lambda x:-x["carteira"])
    db_base = db.get_meta(con, "scr_data_base")
    return {"data_base": db_base, "total": fin(tot),
            "por_modalidade": por_mod_l, "por_uf": por_uf_l}

def api_tarifas(con, q):
    """Grupos consolidados (cache) para navegacao do dominio Tarifas."""
    grp = [dict(r) for r in con.execute("SELECT codigo,nome FROM tarifa_grupos ORDER BY codigo")]
    return {"grupos": grp}

def api_tarifas_grupo(con, codigo, q):
    """Instituicoes de um grupo consolidado (consulta ao vivo no BCB)."""
    try:
        insts = tarifasmod.instituicoes_do_grupo(codigo)
    except Exception as e:  # noqa
        return {"erro": f"consulta indisponivel: {e}", "codigo": codigo, "itens": []}
    nome = con.execute("SELECT nome FROM tarifa_grupos WHERE codigo=?", (codigo,)).fetchone()
    return {"codigo": codigo, "grupo": nome["nome"] if nome else codigo,
            "itens": sorted(insts, key=lambda x: (x["nome"] or ""))}

def api_tarifas_if(con, cnpj8, q):
    """Tarifas de servicos de uma instituicao (ao vivo + cache por cnpj8)."""
    cnpj8 = (cnpj8 or "").zfill(8)
    row = con.execute("SELECT dados FROM tarifa_cache WHERE cnpj8=?", (cnpj8,)).fetchone()
    if row:
        return json.loads(row["dados"])
    try:
        itens = tarifasmod.tarifas_de(cnpj8)
    except Exception as e:  # noqa
        return {"erro": f"consulta de tarifas indisponivel: {e}", "cnpj8": cnpj8, "itens": []}
    out = {"cnpj8": cnpj8, "itens": itens,
           "fonte": tarifasmod.BASE + "ListaTarifasPorInstituicaoFinanceira"}
    import datetime as _dt
    con.execute("INSERT OR REPLACE INTO tarifa_cache(cnpj8,dados,obtido) VALUES(?,?,?)",
                (cnpj8, json.dumps(out, ensure_ascii=False), _dt.datetime.now().isoformat(timespec="seconds")))
    con.commit()
    return out

def api_conduta(con, q):
    periodo = db.get_meta(con, "reclamacoes_periodo")
    rows = [dict(r) for r in con.execute(
        "SELECT nome_norm,nome,categoria,indice,reclamacoes,procedentes,analisadas,clientes "
        "FROM reclamacoes WHERE periodo=?", (periodo,))]
    # mapa nome_norm -> cod (melhor esforco) para tornar as linhas clicaveis
    am = anomes_vigente(con, q)
    nome2cod = {}
    for c in con.execute("SELECT cod,nome FROM cadastro WHERE anomes=?", (am,)):
        nome2cod.setdefault(_norm_nome(c["nome"]), c["cod"])
    # historia de indice por instituicao (para sparkline no drill-down)
    hist = defaultdict(list)
    for r in con.execute("SELECT nome_norm,periodo,indice,reclamacoes FROM reclamacoes ORDER BY periodo"):
        hist[r["nome_norm"]].append({"periodo": r["periodo"], "indice": r["indice"], "reclamacoes": r["reclamacoes"]})
    for r in rows:
        nn = r["nome_norm"]
        cod = nome2cod.get(nn)
        if not cod:  # tenta prefixo
            for k, v in nome2cod.items():
                if k.startswith(nn) or nn.startswith(k):
                    cod = v; break
        r["cod"] = cod
        r["pct_procedente"] = (r["procedentes"] / r["reclamacoes"]) if r.get("reclamacoes") else None
        r["historia"] = hist.get(nn, [])
    return {"periodo": periodo, "itens": rows,
            "periodos": sorted({h["periodo"] for v in hist.values() for h in v}, reverse=True)}

def api_macro(con, q):
    import unicodedata as _u
    def norm(s): return _u.normalize("NFKD", s or "").encode("ascii","ignore").decode()
    principais = ["Selic", "IPCA", "Câmbio", "PIB Total"]
    out = {}
    # data mais recente por indicador
    for ind in principais:
        ultima = con.execute("SELECT MAX(data) d FROM focus WHERE indicador=?", (ind,)).fetchone()
        if not ultima or not ultima["d"]:
            continue
        linhas = con.execute(
            "SELECT referencia,mediana,minimo,maximo,respondentes FROM focus WHERE indicador=? AND data=? ORDER BY referencia",
            (ind, ultima["d"])).fetchall()
        out[norm(ind)] = {"indicador": ind, "data": ultima["d"],
                          "proj": [dict(r) for r in linhas if r["referencia"] and r["referencia"].isdigit()]}
    # series macro do SGS (Selic, inflacao, cambio, atividade)
    series = []
    for cod in con.execute("SELECT DISTINCT codigo FROM sgs_macro ORDER BY codigo"):
        c = cod["codigo"]
        meta_r = con.execute("SELECT nome,grupo,unidade,tipo FROM sgs_macro WHERE codigo=? LIMIT 1", (c,)).fetchone()
        pts = [dict(r) for r in con.execute(
            "SELECT data,valor FROM sgs_macro WHERE codigo=? ORDER BY substr(data,7,4)||substr(data,4,2)||substr(data,1,2)", (c,))]
        if not pts:
            continue
        series.append({"codigo": c, "nome": meta_r["nome"], "grupo": meta_r["grupo"],
                       "unidade": meta_r["unidade"], "tipo": meta_r["tipo"],
                       "pontos": pts, "ultimo": pts[-1]})
    return {"principais": out, "data_focus": db.get_meta(con, "ultima_atualizacao"),
            "series_sgs": series}

def api_taxas_modalidades(con, q):
    """Ranking de taxas de juros por modalidade de credito (ConsultaUnificada)."""
    periodo = db.get_meta(con, "taxas_credito_periodo")
    rows = con.execute(
        "SELECT segmento,modalidade,cnpj8,instituicao,taxa_mes,taxa_ano "
        "FROM taxas_credito ORDER BY segmento, modalidade, taxa_ano").fetchall()
    grupos = {}
    for r in rows:
        chave = (r["segmento"], r["modalidade"])
        g = grupos.setdefault(chave, {"segmento": r["segmento"], "modalidade": r["modalidade"],
                                       "instituicoes": []})
        g["instituicoes"].append({"cnpj8": r["cnpj8"], "instituicao": r["instituicao"],
                                   "taxa_mes": r["taxa_mes"], "taxa_ano": r["taxa_ano"]})
    modalidades = []
    for g in grupos.values():
        taxas_ano = [i["taxa_ano"] for i in g["instituicoes"] if i["taxa_ano"] is not None]
        g["n"] = len(g["instituicoes"])
        g["min"] = min(taxas_ano) if taxas_ano else None
        g["max"] = max(taxas_ano) if taxas_ano else None
        g["mediana"] = sorted(taxas_ano)[len(taxas_ano)//2] if taxas_ano else None
        modalidades.append(g)
    modalidades.sort(key=lambda x: (x["segmento"] or "", x["modalidade"] or ""))
    return {"periodo": periodo, "modalidades": modalidades}

def _norm_nome(nome):
    import unicodedata as _u
    base = (nome or "").upper().split("(")[0].replace(" - PRUDENCIAL", "").strip()
    return _u.normalize("NFKD", base).encode("ascii", "ignore").decode()

def reclamacoes_de(con, nome):
    """Snapshot do ultimo trimestre + historia por trimestre da instituicao."""
    base = _norm_nome(nome)
    k = con.execute("SELECT nome_norm FROM reclamacoes WHERE nome_norm=? LIMIT 1", (base,)).fetchone()
    if not k:
        k = con.execute("SELECT nome_norm FROM reclamacoes WHERE nome_norm LIKE ? LIMIT 1", (base + "%",)).fetchone()
    if not k:
        return None
    nn = k["nome_norm"]
    hist = [dict(r) for r in con.execute(
        "SELECT periodo,indice,reclamacoes,procedentes,clientes,analisadas FROM reclamacoes "
        "WHERE nome_norm=? ORDER BY periodo", (nn,))]
    ult = con.execute(
        "SELECT nome,categoria,indice,reclamacoes,procedentes,clientes,analisadas,periodo "
        "FROM reclamacoes WHERE nome_norm=? ORDER BY periodo DESC LIMIT 1", (nn,)).fetchone()
    d = dict(ult)
    d["historia"] = hist
    return d

ROTAS = {
    "/api/meta": api_meta,
    "/api/panorama": api_panorama,
    "/api/registro": api_registro,
    "/api/prudencial/overview": api_prudencial_overview,
    "/api/pagamentos": api_pagamentos,
    "/api/fontes": api_fontes,
    "/api/conduta": api_conduta,
    "/api/macro": api_macro,
    "/api/credito": api_credito,
    "/api/scr": api_scr,
    "/api/tarifas": api_tarifas,
    "/api/taxas-modalidades": api_taxas_modalidades,
    "/api/participacao": api_participacao,
    "/api/supervisao": api_supervisao,
    "/api/eventos": api_eventos,
}

# ================================================================ HTTP
# Caminhos acessiveis sem login
PUBLICOS = {"/login", "/login.html", "/styles.css", "/api/auth/login"}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    usuario = None
    _cookies_extra = ()
    def _aceita_gzip(self):
        return "gzip" in (self.headers.get("Accept-Encoding") or "").lower()
    def _enviar(self, body, code, content_type):
        """Envia corpo com gzip quando vale a pena (payload >1KB e cliente aceita)."""
        headers = [("Content-Type", content_type), ("Cache-Control", "no-store"),
                   ("Vary", "Accept-Encoding")]
        if len(body) > 1024 and self._aceita_gzip():
            body = gzip.compress(body, 6)
            headers.append(("Content-Encoding", "gzip"))
        self.send_response(code)
        for k, v in headers + self._seguranca():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, default=float).encode("utf-8")
        self._enviar(body, code, "application/json; charset=utf-8")
    # ------------------------------------------------------------ auth
    def _seguranca(self):
        h = [("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"),
             ("Referrer-Policy", "same-origin")]
        return h + [("Set-Cookie", c) for c in self._cookies_extra]
    def _token(self):
        for parte in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = parte.strip().partition("=")
            if k == auth.COOKIE:
                return v
        return None
    def _cookie(self, valor, max_age):
        seguro = "; Secure" if config.COOKIE_SEGURO else ""
        self._cookies_extra = (f"{auth.COOKIE}={valor}; Path=/; HttpOnly; SameSite=Lax; "
                               f"Max-Age={max_age}{seguro}",)
    def _ip(self):
        return self.headers.get("X-Real-IP") or self.client_address[0]
    def _autenticado(self, path):
        """Carrega self.usuario; responde 401/redirect e devolve False se faltar login."""
        if not config.AUTH:
            self.usuario = {"id": 0, "email": "local", "nome": "Uso local", "admin": True}
            return True
        acon = auth.conectar()
        try:
            self.usuario = auth.usuario_da_sessao(acon, self._token())
        finally:
            acon.close()
        if self.usuario or path in PUBLICOS:
            return True
        if path.startswith("/api/"):
            self._json({"erro": "login necessario"}, 401)
        else:
            self.send_response(302)
            self.send_header("Location", "/login")
            self.send_header("Content-Length", "0")
            self.end_headers()
        return False
    def _corpo_json(self):
        """Le o corpo JSON de um POST/PATCH/DELETE (com checagem anti-CSRF)."""
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            raise PermissionError("Content-Type deve ser application/json")
        origem = self.headers.get("Origin")
        if origem and urllib.parse.urlparse(origem).netloc != self.headers.get("Host"):
            raise PermissionError("origem nao permitida")
        n = int(self.headers.get("Content-Length") or 0)
        if n > 64 * 1024:
            raise ValueError("corpo muito grande")
        return json.loads(self.rfile.read(n) or b"{}") if n else {}
    def _escrita(self, metodo):
        path = urllib.parse.urlparse(self.path).path
        if not self._autenticado(path):
            return
        try:
            dados = self._corpo_json()
            self._json(*self._rota_escrita(metodo, path, dados))
        except PermissionError as e:
            self._json({"erro": str(e)}, 403)
        except ValueError as e:
            self._json({"erro": str(e)}, 400)
        except Exception as e:  # noqa
            import traceback; traceback.print_exc()
            self._json({"erro": str(e)}, 500)
    def do_POST(self): self._escrita("POST")
    def do_PATCH(self): self._escrita("PATCH")
    def do_DELETE(self): self._escrita("DELETE")
    def _rota_escrita(self, metodo, path, d):
        acon = auth.conectar()
        try:
            if metodo == "POST" and path == "/api/auth/login":
                if not config.AUTH:
                    return {"ok": True}, 200
                email = (d.get("email") or "").strip().lower()
                chaves = ("ip:" + self._ip(), "email:" + email)
                if any(auth.bloqueado(k) for k in chaves):
                    return {"erro": "Muitas tentativas. Aguarde alguns minutos."}, 429
                u = auth.autenticar(acon, email, d.get("senha"))
                if not u:
                    for k in chaves: auth.registra_falha(k)
                    return {"erro": "E-mail ou senha invalidos."}, 401
                for k in chaves: auth.limpa_falhas(k)
                self._cookie(auth.criar_sessao(acon, u["id"]), auth.SESSAO_DIAS * 86400)
                return {"usuario": u}, 200
            if metodo == "POST" and path == "/api/auth/logout":
                auth.encerrar_sessao(acon, self._token())
                self._cookie("", 0)
                return {"ok": True}, 200
            if metodo == "POST" and path == "/api/auth/senha":
                if not config.AUTH:
                    raise ValueError("Login desligado (BCB_AUTH=0).")
                row = acon.execute("SELECT senha_hash FROM usuarios WHERE id=?",
                                   (self.usuario["id"],)).fetchone()
                if not auth.confere_senha(d.get("atual") or "", row["senha_hash"]):
                    raise ValueError("Senha atual incorreta.")
                auth.atualizar(acon, self.usuario["id"], senha=d.get("nova"))
                auth.encerrar_outras_sessoes(acon, self.usuario["id"], self._token())
                return {"ok": True}, 200
            # ---- administracao de usuarios
            if path == "/api/usuarios" or path.startswith("/api/usuarios/"):
                if not self.usuario.get("admin"):
                    raise PermissionError("apenas administradores")
                if not config.AUTH:
                    raise ValueError("Login desligado (BCB_AUTH=0).")
                if metodo == "POST" and path == "/api/usuarios":
                    return {"usuario": auth.criar(acon, d.get("email"), d.get("nome"),
                                                  d.get("senha"), bool(d.get("admin")))}, 201
                uid = path.rsplit("/", 1)[1]
                if not uid.isdigit():
                    return {"erro": "rota desconhecida"}, 404
                uid = int(uid)
                if metodo == "PATCH":
                    if uid == self.usuario["id"] and (d.get("admin") is False or d.get("ativo") is False):
                        raise ValueError("Voce nao pode remover o proprio acesso de admin.")
                    return {"usuario": auth.atualizar(acon, uid, nome=d.get("nome"), admin=d.get("admin"),
                                                      ativo=d.get("ativo"), senha=d.get("senha") or None)}, 200
                if metodo == "DELETE":
                    if uid == self.usuario["id"]:
                        raise ValueError("Voce nao pode remover a si mesmo.")
                    auth.remover(acon, uid)
                    return {"ok": True}, 200
            return {"erro": "rota desconhecida"}, 404
        finally:
            acon.close()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path, q = parsed.path, urllib.parse.parse_qs(parsed.query)
        if not self._autenticado(path):
            return
        if path == "/api/auth/eu":
            self._json({"usuario": self.usuario, "auth": config.AUTH}); return
        if path == "/api/usuarios":
            if not self.usuario.get("admin"):
                self._json({"erro": "apenas administradores"}, 403); return
            acon = auth.conectar()
            try: self._json({"usuarios": auth.listar(acon)})
            finally: acon.close()
            return
        if path in ("/usuarios", "/usuarios.html") and not self.usuario.get("admin"):
            self.send_error(403); return
        if path.startswith("/api/"):
            con = db.conectar()
            try:
                if path in ROTAS:
                    self._json(ROTAS[path](con, q))
                elif path.startswith("/api/instituicao/"):
                    self._json(api_instituicao(con, urllib.parse.unquote(path.rsplit("/",1)[1]), q))
                elif path.startswith("/api/cnpj/"):
                    self._json(api_cnpj(con, urllib.parse.unquote(path.rsplit("/",1)[1]), q))
                elif path.startswith("/api/tarifas/grupo/"):
                    self._json(api_tarifas_grupo(con, urllib.parse.unquote(path.rsplit("/",1)[1]), q))
                elif path.startswith("/api/tarifas/if/"):
                    self._json(api_tarifas_if(con, urllib.parse.unquote(path.rsplit("/",1)[1]), q))
                else:
                    self._json({"erro": "rota desconhecida"}, 404)
            except Exception as e:  # noqa
                import traceback; traceback.print_exc()
                self._json({"erro": str(e)}, 500)
            finally:
                con.close()
            return
        self._static(path)
    def _static(self, path):
        if path in ("/", ""): path = "/index.html"
        if path in ("/login", "/usuarios"): path += ".html"
        alvo = os.path.normpath(os.path.join(config.FRONTEND_DIR, path.lstrip("/")))
        if not alvo.startswith(config.FRONTEND_DIR) or not os.path.isfile(alvo):
            self.send_error(404); return
        tipos = {".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",
                 ".css":"text/css; charset=utf-8",".json":"application/json",
                 ".svg":"image/svg+xml",".ico":"image/x-icon"}
        with open(alvo, "rb") as f: body = f.read()
        ct = tipos.get(os.path.splitext(alvo)[1].lower(), "application/octet-stream")
        self._enviar(body, 200, ct)

def precisa_coletar():
    if not os.path.exists(config.DB_PATH):
        return True
    con = db.conectar()
    try:
        if not con.execute("SELECT COUNT(*) n FROM sqlite_master WHERE type='table' AND name='valores'").fetchone()["n"]:
            return True
        return con.execute("SELECT COUNT(*) n FROM valores").fetchone()["n"] == 0
    except Exception:
        return True
    finally:
        con.close()

def main():
    try:
        import sys; sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    if precisa_coletar():
        print(">> Primeira execucao: baixando dados do Banco Central (pode levar alguns minutos)...")
        import pipeline; pipeline.coletar()
    else:
        con = db.conectar(); print(">> Cache encontrado. Ultima atualizacao:", db.get_meta(con,"ultima_atualizacao")); con.close()
    class Servidor(ThreadingHTTPServer):
        # no Windows SO_REUSEADDR deixaria dois paineis na mesma porta; no servidor (Linux)
        # ele so evita o "porta ocupada" por conexoes em TIME_WAIT logo apos um restart
        allow_reuse_address = config.PORTA_FIXA and os.name != "nt"
    srv = None
    if config.AUTH:
        acon = auth.conectar()
        if not acon.execute("SELECT COUNT(*) n FROM usuarios").fetchone()["n"]:
            print(">> Nenhum usuario cadastrado. Crie o primeiro admin com:\n"
                  "     python3 auth.py criar-admin seu@email")
        acon.close()
    for porta in ([config.PORTA] if config.PORTA_FIXA else range(config.PORTA, config.PORTA + 25)):
        try:
            srv = Servidor((config.HOST, porta), Handler); break
        except OSError:
            continue
    if srv is None:
        print(">> Nenhuma porta livre. Feche outros programas e tente de novo.")
        if config.ABRIR_NAVEGADOR: input("Enter para sair...")
        raise SystemExit(1)
    url = f"http://localhost:{srv.server_address[1]}"
    print(f">> Painel no ar em {url}  (feche esta janela para encerrar)")
    if config.ABRIR_NAVEGADOR:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
