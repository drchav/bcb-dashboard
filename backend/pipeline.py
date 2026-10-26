"""Orquestra a coleta das fontes do BCB para o cache SQLite."""
import sys, time
from datetime import datetime

import config, db
from coletores import (ifdata, participantes, spi, taxas, reclamacoes, focus,
                       credito, tarifas, sgs_macro, pix_participantes, pix_lista,
                       supervisao, scr, eventos)


def _exige(dados):
    """Fonte que voltou vazia nao apaga o que ja temos (falha temporaria do BCB)."""
    if not dados:
        raise ValueError("resposta vazia; mantidos os dados anteriores")
    return dados


def coletar(progresso=print):
    con = db.conectar()
    db.init(con)

    meses = ifdata.trimestres(config.ANOS_HISTORICO)
    progresso(f"Modo: {config.MODO} | {len(meses)} trimestres | "
              f"{len(config.RELATORIOS_COLETA)} relatorios")

    meses_ok = []
    for anomes in meses:
        try:
            cad = ifdata.cadastro(anomes)
        except Exception as e:  # noqa
            progresso(f"  {anomes}: erro cadastro ({e}); pulando")
            continue
        if not cad:
            continue  # trimestre ainda nao publicado
        meses_ok.append(anomes)
        _grava_cadastro(con, anomes, cad)
        progresso(f"[{anomes}] cadastro: {len(cad)} instituicoes")

        for rel in config.RELATORIOS_COLETA:
            try:
                vals = ifdata.valores(anomes, rel)
            except Exception as e:  # noqa
                progresso(f"    rel {rel}: erro ({e})")
                continue
            _grava_valores(con, anomes, rel, vals)
            progresso(f"    rel {rel} ({config.RELATORIOS.get(rel,rel)}): {len(vals)} linhas")
        con.commit()

    # ---- RSFN / STR (conexoes diretas) ----
    try:
        parts = _exige(participantes.participantes_str())
        con.execute("DELETE FROM str_participantes")
        con.executemany(
            """INSERT OR REPLACE INTO str_participantes
               (ispb,nome_reduzido,codigo,participa_compe,acesso,nome_extenso,inicio)
               VALUES (?,?,?,?,?,?,?)""",
            [(p["ispb"], p["nome_reduzido"], p["codigo"], p["participa_compe"],
              p["acesso"], p["nome_extenso"], p["inicio"]) for p in parts])
        con.commit()
        progresso(f"RSFN/STR: {len(parts)} participantes")
    except Exception as e:  # noqa
        progresso(f"RSFN/STR: erro ({e})")

    # ---- Participantes do PIX (diretorio por ISPB) ----
    try:
        data_pix, parts_pix = pix_participantes.participantes()
        if parts_pix:
            con.execute("DELETE FROM pix_participantes")
            con.executemany(
                "INSERT OR REPLACE INTO pix_participantes (ispb,nome,segmento) VALUES (?,?,?)",
                [(p["ispb"], p["nome"], p["segmento"]) for p in parts_pix])
            con.commit()
            db.set_meta(con, "pix_participantes_data", data_pix)
            progresso(f"Participantes PIX ({data_pix}): {len(parts_pix)} instituicoes")
    except Exception as e:  # noqa
        progresso(f"Participantes PIX: erro ({e})")

    # ---- Lista de participantes ativos do Pix (participacao SPI direta/indireta,
    #      autorizacao pelo BCB, sujeicao a autorizacao, modalidade) ----
    try:
        data_lp, lp = pix_lista.lista()
        if lp:
            con.execute("DELETE FROM pix_lista")
            con.executemany(
                "INSERT OR REPLACE INTO pix_lista "
                "(cnpj8,nome,tipo_inst,autorizada,nao_sujeita,part_spi,part_pix,modalidade,iniciador,fss,situacao) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(p["cnpj8"], p["nome"], p["tipo_inst"], p["autorizada"], p["nao_sujeita"],
                  p["part_spi"], p["part_pix"], p["modalidade"], p["iniciador"], p["fss"], p["situacao"])
                 for p in lp])
            con.commit()
            db.set_meta(con, "pix_lista_data", data_lp)
            progresso(f"Lista de participantes Pix ({data_lp}): {len(lp)} instituicoes")
    except Exception as e:  # noqa
        progresso(f"Lista de participantes Pix: erro ({e})")

    # ---- Supervisao: regimes especiais + penalidades (sancionador) ----
    try:
        reg = _exige(supervisao.regimes())
        con.execute("DELETE FROM regimes_especiais")
        con.executemany(
            """INSERT INTO regimes_especiais (cnpj8,cnpj,nome,inicio,tipo,responsavel,municipio,uf,endereco,cep,emails,telefones)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(r["cnpj8"], r["cnpj"], r["nome"], r["inicio"], r["tipo"],
              r["responsavel"], r["municipio"], r["uf"],
              r.get("endereco"), r.get("cep"), r.get("emails"), r.get("telefones")) for r in reg])
        con.commit()
        progresso(f"Regimes especiais: {len(reg)} instituicoes")
    except Exception as e:  # noqa
        progresso(f"Regimes especiais: erro ({e})")
    try:
        pen = _exige(supervisao.penalidades())
        con.execute("DELETE FROM penalidades")
        con.executemany(
            """INSERT INTO penalidades (pas,nome,cnpj_cpf,cnpj8,data_citacao,data_decisao,tipo_penalidade,valor_multa,situacao)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            [(p["pas"], p["nome"], p["cnpj_cpf"], p["cnpj8"], p["data_citacao"],
              p["data_decisao"], p["tipo_penalidade"], p["valor_multa"], p["situacao"]) for p in pen])
        con.commit()
        progresso(f"Penalidades (sancionador): {len(pen)} registros")
    except Exception as e:  # noqa
        progresso(f"Penalidades: erro ({e})")

    # ---- SPI / PIX liquidados (serie diaria) ----
    try:
        pix = _exige(spi.pix_liquidados())
        con.execute("DELETE FROM pix_liquidados")
        con.executemany(
            """INSERT OR REPLACE INTO pix_liquidados
               (data,quantidade,canal_primario,canal_secundario,total,media)
               VALUES (?,?,?,?,?,?)""",
            [(r.get("Data"), r.get("Quantidade"), r.get("CanalPrimario"),
              r.get("CanalSecundario"), r.get("Total"), r.get("Media")) for r in pix])
        con.commit()
        progresso(f"PIX/SPI: {len(pix)} dias de estatistica")
    except Exception as e:  # noqa
        progresso(f"PIX/SPI: erro ({e})")

    # ---- Taxas de juros por instituicao (ultimo mes) ----
    try:
        mes = taxas.ultimo_mes()
        if mes:
            linhas = taxas.taxas_do_mes(mes)
            con.execute("DELETE FROM taxas")
            con.executemany(
                """INSERT INTO taxas (cnpj8,anomes,modalidade,posicao,instituicao,taxa_mes,taxa_ano)
                   VALUES (?,?,?,?,?,?,?)""",
                [((r.get("cnpj8") or "").zfill(8), r.get("anoMes"), r.get("Modalidade"),
                  r.get("Posicao"), r.get("InstituicaoFinanceira"),
                  r.get("TaxaJurosAoMes"), r.get("TaxaJurosAoAno")) for r in linhas])
            con.commit()
            db.set_meta(con, "taxas_mes", mes)
            progresso(f"Taxas de juros imobiliario ({mes}): {len(linhas)} linhas")
    except Exception as e:  # noqa
        progresso(f"Taxas imobiliario: erro ({e})")

    # ---- Taxas de juros de credito por modalidade (ConsultaUnificada, ultimo periodo) ----
    try:
        per = taxas.ultimo_periodo_unificado()
        if per:
            linhas = taxas.taxas_unificadas(per)
            con.execute("DELETE FROM taxas_credito")
            con.executemany(
                """INSERT INTO taxas_credito
                   (periodo_ini,periodo_fim,segmento,cod_modalidade,modalidade,posicao,cnpj8,instituicao,taxa_mes,taxa_ano)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                [(r.get("InicioPeriodo"), r.get("FimPeriodo"), r.get("Segmento"),
                  str(r.get("codigoModalidade") or ""), r.get("Modalidade"), r.get("Posicao"),
                  (r.get("cnpj8") or "").zfill(8), r.get("InstituicaoFinanceira"),
                  r.get("TaxaJurosAoMes"), r.get("TaxaJurosAoAno")) for r in linhas])
            con.commit()
            db.set_meta(con, "taxas_credito_periodo", per)
            progresso(f"Taxas de credito por modalidade ({per}): {len(linhas)} linhas")
    except Exception as e:  # noqa
        progresso(f"Taxas de credito: erro ({e})")

    # ---- Reclamacoes (historico: ultimos trimestres) ----
    try:
        tris = reclamacoes.trimestres_recentes(8)
        if tris:
            con.execute("DELETE FROM reclamacoes")
            total = 0
            for ano, t in tris:
                linhas = reclamacoes.ranking_trimestre(ano, t)
                con.executemany(
                    """INSERT INTO reclamacoes (nome_norm,nome,categoria,periodo,indice,reclamacoes,procedentes,analisadas,clientes)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    [(r["nome_norm"], r["nome"], r["categoria"], f"{ano}T{t}", r["indice"],
                      r["reclamacoes"], r["procedentes"], r["analisadas"], r["clientes"]) for r in linhas])
                total += len(linhas)
            con.commit()
            ano0, t0 = tris[0]
            db.set_meta(con, "reclamacoes_periodo", f"{ano0}T{t0}")
            progresso(f"Reclamacoes: {total} linhas em {len(tris)} trimestres (atual {ano0}T{t0})")
    except Exception as e:  # noqa
        progresso(f"Reclamacoes: erro ({e})")

    # ---- Eventos / Comunicados do BCB sobre instituicoes ----
    try:
        seed = db.get_meta(con, "eventos_max")
        seed = int(seed) if seed else None
        mx, evs = eventos.eventos(seed_max=seed)
        if evs:
            con.execute("DELETE FROM eventos")
            con.executemany(
                """INSERT OR REPLACE INTO eventos (numero,data,data_texto,titulo,assunto,categoria)
                   VALUES (?,?,?,?,?,?)""",
                [(e["numero"], e["data"], e["data_texto"], e["titulo"], e["assunto"], e["categoria"]) for e in evs])
            con.commit()
            db.set_meta(con, "eventos_max", str(mx))
            progresso(f"Eventos (comunicados): {len(evs)} eventos de instituicao (max #{mx})")
    except Exception as e:  # noqa
        progresso(f"Eventos: erro ({e})")

    # ---- Expectativas Focus ----
    try:
        exp = _exige(focus.expectativas_anuais())
        con.execute("DELETE FROM focus")
        con.executemany(
            """INSERT INTO focus (indicador,data,referencia,mediana,media,minimo,maximo,respondentes)
               VALUES (?,?,?,?,?,?,?,?)""",
            [(r.get("Indicador"), r.get("Data"), str(r.get("DataReferencia")),
              r.get("Mediana"), r.get("Media"), r.get("Minimo"), r.get("Maximo"),
              r.get("numeroRespondentes")) for r in exp if r.get("baseCalculo") in (0, None)])
        con.commit()
        progresso(f"Focus: {con.execute('SELECT COUNT(*) n FROM focus').fetchone()['n']} projecoes")
    except Exception as e:  # noqa
        progresso(f"Focus: erro ({e})")

    # ---- Credito agregado do SFN (SGS) ----
    try:
        sgs = [s for s in credito.series(6) if s["pontos"]]
        _exige(sgs)
        linhas = []
        for s in sgs:
            con.execute("DELETE FROM sgs_credito WHERE codigo=?", (s["codigo"],))
            for p in s["pontos"]:
                linhas.append((s["codigo"], s["nome"], s["unidade"], s["tipo"],
                               p["data"], p["valor"]))
        con.executemany(
            """INSERT OR REPLACE INTO sgs_credito (codigo,nome,unidade,tipo,data,valor)
               VALUES (?,?,?,?,?,?)""", linhas)
        con.commit()
        progresso(f"Credito/SGS: {len(sgs)} series, {len(linhas)} pontos")
    except Exception as e:  # noqa
        progresso(f"Credito/SGS: erro ({e})")

    # ---- SCR: carteira de credito por modalidade/UF/cliente ----
    try:
        base_scr, linhas_scr = scr.carteira()
        if linhas_scr:
            con.execute("DELETE FROM scr_credito")
            con.executemany(
                """INSERT INTO scr_credito (data_base,cliente,estado,sub_regiao,modalidade,operacoes,carteira,vencido)
                   VALUES (?,?,?,?,?,?,?,?)""",
                [(base_scr, r["cliente"], r["estado"], r["sub_regiao"], r["modalidade"],
                  r["operacoes"], r["carteira"], r["vencido"]) for r in linhas_scr])
            con.commit()
            db.set_meta(con, "scr_data_base", str(base_scr))
            progresso(f"SCR ({base_scr}): {len(linhas_scr)} linhas")
    except Exception as e:  # noqa
        progresso(f"SCR: erro ({e})")

    # ---- Indicadores macro (SGS: Selic, inflacao, cambio, atividade) ----
    try:
        macro = [s for s in sgs_macro.series() if s["pontos"]]
        _exige(macro)
        linhas = []
        for s in macro:
            con.execute("DELETE FROM sgs_macro WHERE codigo=?", (s["codigo"],))
            for p in s["pontos"]:
                linhas.append((s["codigo"], s["nome"], s["grupo"], s["unidade"],
                               s["tipo"], p["data"], p["valor"]))
        con.executemany(
            """INSERT OR REPLACE INTO sgs_macro (codigo,nome,grupo,unidade,tipo,data,valor)
               VALUES (?,?,?,?,?,?,?)""", linhas)
        con.commit()
        progresso(f"Macro/SGS: {len(macro)} series, {len(linhas)} pontos")
    except Exception as e:  # noqa
        progresso(f"Macro/SGS: erro ({e})")

    # ---- Tarifas: grupos consolidados (as tarifas em si sao consultadas ao vivo) ----
    try:
        grp = tarifas.grupos()
        con.execute("DELETE FROM tarifa_grupos")
        con.executemany("INSERT OR REPLACE INTO tarifa_grupos (codigo,nome) VALUES (?,?)",
                        [(g["codigo"], g["nome"]) for g in grp])
        con.commit()
        progresso(f"Tarifas: {len(grp)} grupos consolidados")
    except Exception as e:  # noqa
        progresso(f"Tarifas: erro ({e})")

    db.set_meta(con, "ultima_atualizacao", datetime.now().isoformat(timespec="seconds"))
    db.set_meta(con, "anomes_recente", meses_ok[0] if meses_ok else "")
    db.set_meta(con, "modo", config.MODO)
    con.commit()
    # estatisticas para o otimizador do SQLite (acelera o pivot de metricas-chave)
    try:
        con.execute("ANALYZE"); con.commit()
    except Exception:  # noqa
        pass
    progresso(f"Concluido. Trimestres carregados: {', '.join(meses_ok)}")
    con.close()


def _grava_cadastro(con, anomes, cad):
    con.execute("DELETE FROM cadastro WHERE anomes=?", (anomes,))
    con.executemany(
        """INSERT OR REPLACE INTO cadastro
           (cod,anomes,nome,tcb,td,tc,sr,segmento_tb,atividade,uf,municipio,
            cnpj_lider,situacao,cod_prud,dt_inicio)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [(r.get("CodInst"), anomes, r.get("NomeInstituicao"), r.get("Tcb"),
          r.get("Td"), r.get("Tc"), r.get("Sr"), r.get("SegmentoTb"),
          r.get("Atividade"), r.get("Uf"), r.get("Municipio"),
          r.get("CnpjInstituicaoLider"), r.get("Situacao"),
          r.get("CodConglomeradoPrudencial"), r.get("DataInicioAtividade"))
         for r in cad])


def _grava_valores(con, anomes, rel, vals):
    con.execute("DELETE FROM valores WHERE anomes=? AND relatorio=?", (anomes, rel))
    linhas = []
    for r in vals:
        col = ifdata.limpar_coluna(r.get("NomeColuna"))
        if not col:
            continue
        linhas.append((r.get("CodInst"), anomes, rel, r.get("Grupo") or "",
                       col, ifdata.chave(col), r.get("Saldo")))
    con.executemany(
        """INSERT OR REPLACE INTO valores
           (cod,anomes,relatorio,grupo,coluna,coluna_norm,saldo)
           VALUES (?,?,?,?,?,?,?)""", linhas)


if __name__ == "__main__":
    t0 = time.time()
    coletar()
    print(f"Tempo total: {time.time()-t0:.0f}s")
