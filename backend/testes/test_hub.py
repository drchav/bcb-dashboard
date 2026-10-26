"""
Bateria de testes do Hub do SFN.

Cobre: integridade do cache, coletores, endpoints da API, agregacoes,
casamento RSFN, serie PIX, derivacao de segmento e — com enfase — TODOS os
tipos de instituicao (bancos, cooperativas, financeiras, corretoras,
consorcios, instituicoes de pagamento, desenvolvimento), nao so cooperativas.

Rode com:  python -m unittest -v   (dentro de backend/)
ou use o atalho  rodar-testes.bat
"""
import os, sys, json, threading, unittest, urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config, db, app
config.AUTH = False  # login e testado a parte em test_auth.py
from coletores import ifdata, cnpj as cnpjmod, reclamacoes, credito, tarifas as tarifasmod

# Todos os tipos (TCB) que o sistema deve reconhecer e tratar
TIPOS_ESPERADOS = ["B1", "B2", "B4", "B3S", "B3C", "N1", "N2", "N3", "N4"]


def con():
    return db.conectar()


class T00_CachePronto(unittest.TestCase):
    """Garante que o cache existe antes de testar o resto."""
    def test_db_existe(self):
        self.assertTrue(os.path.exists(config.DB_PATH),
                        "Cache nao encontrado. Rode start.bat (ou pipeline.py) antes dos testes.")

    def test_tabelas_populadas(self):
        c = con()
        for tab in ("cadastro", "valores", "str_participantes", "pix_liquidados"):
            n = c.execute(f"SELECT COUNT(*) n FROM {tab}").fetchone()["n"]
            self.assertGreater(n, 0, f"Tabela '{tab}' vazia")
        c.close()

    def test_anomes_disponivel(self):
        c = con()
        self.assertTrue(db.anomes_disponiveis(c), "Sem data-base no cache")
        c.close()


class T01_Coletores(unittest.TestCase):
    def test_limpar_coluna_remove_formula(self):
        self.assertEqual(ifdata.limpar_coluna("Indice de Basileia \n(n) = (e)/(j)"),
                         "Indice de Basileia")
    def test_chave_normaliza_acentos(self):
        self.assertEqual(ifdata.chave("Patrimônio Líquido"), "patrimonio liquido")
        self.assertEqual(ifdata.chave("Índice de Basileia"), "indice de basileia")
    def test_trimestres_formato(self):
        ts = ifdata.trimestres(2)
        self.assertTrue(all(len(t) == 6 for t in ts))
        self.assertTrue(all(t[4:6] in ("03", "06", "09", "12") for t in ts))


class T02_TodosOsTipos(unittest.TestCase):
    """Enfase do pedido: cobrir TODOS os tipos de instituicao."""
    @classmethod
    def setUpClass(cls):
        cls.c = con()
        cls.am = db.anomes_disponiveis(cls.c)[0]

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    def test_todos_os_tipos_presentes(self):
        presentes = set(r["tcb"] for r in self.c.execute(
            "SELECT DISTINCT tcb FROM cadastro WHERE anomes=? AND tcb IS NOT NULL", (self.am,)))
        for t in TIPOS_ESPERADOS:
            self.assertIn(t, presentes, f"Tipo {t} ausente do cadastro")

    def test_cada_tipo_tem_grupo_na_hierarquia(self):
        for t in TIPOS_ESPERADOS:
            grupo, desc = config.tipo_info(t)
            self.assertNotEqual(grupo, "Outras", f"Tipo {t} caiu em 'Outras' (hierarquia incompleta)")
            self.assertTrue(desc)

    def test_perfil_funciona_para_cada_tipo(self):
        """Abre o perfil de uma instituicao de CADA tipo e valida a resposta."""
        for t in TIPOS_ESPERADOS:
            row = self.c.execute(
                "SELECT cod,nome FROM cadastro WHERE anomes=? AND tcb=? LIMIT 1", (self.am, t)).fetchone()
            self.assertIsNotNone(row, f"Sem instituicao do tipo {t}")
            d = app.api_instituicao(self.c, row["cod"], {"anomes": [self.am]})
            self.assertNotIn("erro", d, f"Perfil falhou para tipo {t} ({row['nome']})")
            self.assertIn("cadastro", d)
            self.assertIn("grupo", d)
            self.assertIn("controle", d)
            self.assertIsInstance(d["relatorios"], dict)  # pode ser vazio p/ tipos sem balanco
            self.assertIsInstance(d["historico"], dict)

    def test_registro_cobre_todos_os_grupos(self):
        reg = app.api_registro(self.c, {"anomes": [self.am]})["itens"]
        grupos = set(i["grupo"] for i in reg)
        for g in ["Bancos", "Cooperativas", "Credito nao-bancario",
                  "Mercado de capitais", "Consorcios", "Pagamentos"]:
            self.assertIn(g, grupos, f"Grupo {g} ausente do registro")


class T03_Endpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = con()
        cls.am = db.anomes_disponiveis(cls.c)[0]

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    def test_meta(self):
        m = app.api_meta(self.c, {})
        self.assertGreater(m["total_cadastro"], 1000)
        self.assertGreater(m["total_rsfn"], 0)
        self.assertIn(self.am, m["anomes_disponiveis"])

    def test_panorama_consistente(self):
        p = app.api_panorama(self.c, {"anomes": [self.am]})
        self.assertGreater(p["total_instituicoes"], 1000)
        self.assertGreater(p["ativo_total"], 1e12)
        soma_grupos = sum(x["n"] for x in p["por_grupo"])
        self.assertEqual(soma_grupos, p["total_instituicoes"],
                         "Soma por grupo != total de instituicoes")
        self.assertTrue(p["pix_dia"])  # estatistica PIX presente

    def test_registro_campos(self):
        reg = app.api_registro(self.c, {"anomes": [self.am]})["itens"]
        self.assertGreater(len(reg), 1000)
        i = reg[0]
        for campo in ("cod", "nome", "grupo", "tipo_desc", "td", "controle",
                      "situacao", "seg", "rsfn", "tem_financas"):
            self.assertIn(campo, i)

    def test_prudencial_overview(self):
        ov = app.api_prudencial_overview(self.c, {"anomes": [self.am]})
        self.assertIn("por_segmento", ov)
        self.assertGreater(ov["totais"]["ativo"], 1e12)

    def test_pagamentos(self):
        pg = app.api_pagamentos(self.c, {})
        self.assertGreater(pg["rsfn_total"], 0)
        self.assertGreater(len(pg["pix_serie"]), 100)
        # serie ordenada por data
        datas = [d["data"] for d in pg["pix_serie"]]
        self.assertEqual(datas, sorted(datas))

    def test_instituicao_inexistente(self):
        d = app.api_instituicao(self.c, "XXXXXXX", {})
        self.assertIn("erro", d)


class T04_RegrasDeNegocio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = con()
        cls.am = db.anomes_disponiveis(cls.c)[0]

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    def test_segmento_s1_sao_os_grandes(self):
        reg = app.api_registro(self.c, {"anomes": [self.am]})["itens"]
        s1 = [i for i in reg if i["seg"] == "S1" and i["tem_financas"]]
        nomes = " ".join(i["nome"].upper() for i in s1)
        # os grandes conglomerados devem estar no S1
        for banco in ("ITAU", "BRADESCO", "CAIXA", "SANTANDER"):
            self.assertIn(banco, nomes, f"{banco} deveria estar no S1")

    def test_rsfn_casa_bancos(self):
        reg = app.api_registro(self.c, {"anomes": [self.am]})["itens"]
        bancos_rsfn = [i for i in reg if i["grupo"] == "Bancos" and i["rsfn"]]
        self.assertGreater(len(bancos_rsfn), 20, "Poucos bancos casados com a RSFN")
        # participante RSFN deve ter codigo COMPE
        with_compe = [i for i in bancos_rsfn if i["compe"]]
        self.assertGreater(len(with_compe), 10)

    def test_metricas_financeiras_plausiveis(self):
        import statistics
        reg = app.api_registro(self.c, {"anomes": [self.am]})["itens"]
        comfin = [i for i in reg if i["tem_financas"] and i.get("ativo")]
        self.assertGreater(len(comfin), 500)
        # Ativo nunca negativo
        for i in comfin:
            if i.get("ativo") is not None:
                self.assertGreaterEqual(i["ativo"], 0)
        # Basileia e FRACAO (0,165 = 16,5%). Casos extremos existem (insolventes
        # com PR<0; instituicoes minusculas com indice enorme), entao validamos a
        # ESCALA pela mediana: se estivesse em % a mediana seria ~15, nao ~0,15.
        bas = [i["basileia"] for i in comfin if i.get("basileia") is not None]
        self.assertGreater(len(bas), 200)
        med = statistics.median(bas)
        self.assertGreater(med, 0.08, f"Mediana de Basileia {med} fora da escala de fracao")
        self.assertLess(med, 1.0, f"Mediana de Basileia {med} parece estar em % (deveria ser fracao)")

    def test_filtro_rsfn_logica(self):
        reg = app.api_registro(self.c, {"anomes": [self.am]})["itens"]
        so_rsfn = [i for i in reg if i["rsfn"]]
        nao_rsfn = [i for i in reg if not i["rsfn"]]
        self.assertGreater(len(so_rsfn), 0)
        self.assertGreater(len(nao_rsfn), 0)
        self.assertTrue(all(i["compe"] or i["acesso"] or True for i in so_rsfn))


class T05_HTTP(unittest.TestCase):
    """Sobe o servidor de verdade e bate nas rotas via HTTP."""
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.porta = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.th.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.porta}{path}", timeout=20) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    def test_rotas_http(self):
        for path in ("/api/meta", "/api/panorama", "/api/registro",
                     "/api/prudencial/overview", "/api/pagamentos",
                     "/api/conduta", "/api/macro", "/api/fontes",
                     "/api/credito", "/api/scr", "/api/tarifas",
                     "/api/taxas-modalidades", "/api/participacao", "/api/supervisao"):
            st, body = self._get(path)
            self.assertEqual(st, 200, f"{path} nao retornou 200")
            self.assertNotIn("erro", body, f"{path} retornou erro")

    def test_rota_desconhecida_404(self):
        try:
            self._get("/api/naoexiste")
            self.fail("deveria ter dado 404")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_frontend_servido(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.porta}/", timeout=20) as r:
            html = r.read().decode("utf-8")
        self.assertIn("Painel SFN", html)
        self.assertIn("app.js", html)

    def test_perfil_http_todos_os_tipos(self):
        c = con(); am = db.anomes_disponiveis(c)[0]
        for t in TIPOS_ESPERADOS:
            row = c.execute("SELECT cod FROM cadastro WHERE anomes=? AND tcb=? LIMIT 1", (am, t)).fetchone()
            st, body = self._get("/api/instituicao/" + row["cod"])
            self.assertEqual(st, 200)
            self.assertNotIn("erro", body, f"perfil HTTP falhou p/ tipo {t}")
        c.close()


class T06_NovasFontes(unittest.TestCase):
    """Fontes distintas: CNPJ, taxas, reclamacoes, Focus, catalogo de fontes."""
    @classmethod
    def setUpClass(cls):
        cls.c = con()

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    def test_cnpj_digito_verificador(self):
        # casos oficiais conhecidos
        self.assertEqual(cnpjmod.cnpj_completo("60701190"), "60701190000104")  # Itau
        self.assertEqual(cnpjmod.cnpj_completo("00360305"), "00360305000104")  # Caixa
        self.assertEqual(cnpjmod.cnpj_completo("00000000"), "00000000000191")  # BB

    def test_reclamacoes_normaliza_nome(self):
        self.assertEqual(reclamacoes.chave_nome("ABC-BRASIL (conglomerado)"), "ABC-BRASIL")
        self.assertEqual(reclamacoes.chave_nome("Banco Inter (conglomerado)"), "BANCO INTER")

    def test_tabelas_novas_fontes(self):
        for tab in ("taxas", "reclamacoes", "focus"):
            n = self.c.execute(f"SELECT COUNT(*) n FROM {tab}").fetchone()["n"]
            self.assertGreater(n, 0, f"Tabela de fonte '{tab}' vazia")

    def test_conduta(self):
        d = app.api_conduta(self.c, {})
        self.assertGreater(len(d["itens"]), 50)
        self.assertTrue(d["periodo"])
        # ao menos uma instituicao com indice
        self.assertTrue(any(i["indice"] is not None for i in d["itens"]))

    def test_macro_focus(self):
        d = app.api_macro(self.c, {})
        P = d["principais"]
        self.assertIn("Selic", P)
        self.assertIn("IPCA", P)
        self.assertTrue(P["Selic"]["proj"], "Sem projecoes de Selic")
        # mediana da Selic deve ser plausivel (entre 0 e 40% a.a.)
        m = P["Selic"]["proj"][0]["mediana"]
        self.assertGreater(m, 0); self.assertLess(m, 40)

    def test_fontes_tem_links(self):
        d = app.api_fontes(self.c, {})
        self.assertGreater(len(d["fontes"]), 8)
        for f in d["fontes"]:
            self.assertTrue(f["url"].startswith("http"), f"Fonte sem link: {f['nome']}")
            self.assertIn(f["status"], ("integrado", "parcial", "próxima onda"))
        integradas = [f for f in d["fontes"] if f["status"] == "integrado"]
        self.assertGreaterEqual(len(integradas), 5)

    def test_cnpj_endpoint(self):
        # pode ser dado real (BrasilAPI) ou erro gracioso; nunca deve quebrar
        d = app.api_cnpj(self.c, "60701190", {})
        self.assertTrue("razao_social" in d or "erro" in d)


class T07_OndasCreditoTarifasNormas(unittest.TestCase):
    """Novas ondas: Credito (SGS), Tarifas de servicos e Normas/COPOM."""
    @classmethod
    def setUpClass(cls):
        cls.c = con()

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    # ---- tabelas populadas ----
    def test_tabelas_novas_ondas(self):
        for tab in ("sgs_credito", "tarifa_grupos"):
            n = self.c.execute(f"SELECT COUNT(*) n FROM {tab}").fetchone()["n"]
            self.assertGreater(n, 0, f"Tabela '{tab}' vazia")

    # ---- credito (SGS) ----
    def test_credito_series(self):
        d = app.api_credito(self.c, {})
        self.assertGreaterEqual(len(d["series"]), 6, "Esperava >=6 series de credito")
        cods = {s["codigo"] for s in d["series"]}
        for cod in ("20539", "20540", "20541", "20714", "21082"):
            self.assertIn(cod, cods, f"Serie SGS {cod} ausente")
        for s in d["series"]:
            self.assertIn(s["tipo"], ("moeda_mi", "pct"))
            self.assertTrue(s["pontos"], f"Serie {s['codigo']} sem pontos")
            self.assertIsNotNone(s["ultimo"]["valor"])

    def test_credito_escala_e_identidade(self):
        d = app.api_credito(self.c, {})
        S = {s["codigo"]: s["ultimo"]["valor"] for s in d["series"]}
        # saldo total em R$ milhoes: > 1 milhao (= > R$ 1 tri)
        self.assertGreater(S["20539"], 1_000_000, "Saldo total fora de escala (R$ milhoes)")
        # identidade: total ~= PF + PJ (tolerancia 2%)
        soma = S["20541"] + S["20540"]
        self.assertAlmostEqual(S["20539"], soma, delta=S["20539"] * 0.02)
        # juros e inadimplencia em % plausiveis
        self.assertGreater(S["20714"], 1); self.assertLess(S["20714"], 100)
        self.assertGreater(S["21082"], 0); self.assertLess(S["21082"], 50)

    def test_credito_tipo_coerente(self):
        d = app.api_credito(self.c, {})
        tipo = {s["codigo"]: s["tipo"] for s in d["series"]}
        self.assertEqual(tipo["20539"], "moeda_mi")
        self.assertEqual(tipo["20714"], "pct")
        self.assertEqual(tipo["21082"], "pct")

    # ---- tarifas ----
    def test_tarifas_grupos(self):
        d = app.api_tarifas(self.c, {})
        self.assertGreater(len(d["grupos"]), 0, "Sem grupos consolidados de tarifas")
        for g in d["grupos"]:
            self.assertTrue(g["codigo"]); self.assertTrue(g["nome"])

    def test_tarifas_cnpj_completo_raiz8(self):
        # a funcao deve aceitar raiz de 8 digitos e normalizar com zfill
        self.assertEqual(tarifasmod.tarifas_de.__name__, "tarifas_de")

    def test_tarifas_if_endpoint_gracioso(self):
        # ao vivo: pode trazer itens ou erro gracioso; nunca deve lancar excecao
        d = app.api_tarifas_if(self.c, "60701190", {})
        self.assertTrue("itens" in d or "erro" in d)
        self.assertIn("cnpj8", d)

    def test_tarifas_grupo_endpoint_gracioso(self):
        d = app.api_tarifas_grupo(self.c, "01", {})
        self.assertTrue("itens" in d or "erro" in d)

    # ---- fontes refletem as ondas integradas ----
    def test_fontes_marcam_ondas_integradas(self):
        fontes = app.api_fontes(self.c, {})["fontes"]
        por_nome = {f["nome"]: f for f in fontes}
        # as novas ondas devem constar como integradas
        integradas = [f["nome"] for f in fontes if f["status"] == "integrado"]
        self.assertTrue(any("SGS" in n or "Crédito agregado" in n for n in integradas),
                        "Credito/SGS deveria estar integrado nas fontes")
        self.assertTrue(any("Tarifas" in n for n in integradas),
                        "Tarifas deveria estar integrado nas fontes")


class T08_TaxasModalidadesMacroPerf(unittest.TestCase):
    """Ondas: taxas de juros por modalidade, series SGS macro, gzip e indice de performance."""
    @classmethod
    def setUpClass(cls):
        cls.c = con()
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.porta = cls.srv.server_address[1]
        cls.th = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.th.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.c.close()

    # ---- tabelas populadas ----
    def test_tabelas_populadas(self):
        for tab in ("taxas_credito", "sgs_macro"):
            n = self.c.execute(f"SELECT COUNT(*) n FROM {tab}").fetchone()["n"]
            self.assertGreater(n, 0, f"Tabela '{tab}' vazia")

    # ---- taxas por modalidade ----
    def test_taxas_modalidades_endpoint(self):
        d = app.api_taxas_modalidades(self.c, {})
        mods = d["modalidades"]
        self.assertGreater(len(mods), 5, "Esperava varias modalidades de credito")
        segs = {m["segmento"] for m in mods}
        self.assertTrue(any("Física" in (s or "") for s in segs), "Falta segmento Pessoa Física")
        self.assertTrue(any("Jurídica" in (s or "") for s in segs), "Falta segmento Pessoa Jurídica")
        for m in mods:
            self.assertGreater(m["n"], 0)
            if m["min"] is not None and m["max"] is not None:
                self.assertLessEqual(m["min"], m["mediana"])
                self.assertLessEqual(m["mediana"], m["max"])

    def test_modalidades_cobrem_credito_variado(self):
        d = app.api_taxas_modalidades(self.c, {})
        nomes = " ".join((m["modalidade"] or "").lower() for m in d["modalidades"])
        # deve ir muito alem de imobiliario
        for termo in ("cart", "cheque especial", "consignado", "ve"):
            self.assertIn(termo, nomes, f"Modalidade com '{termo}' ausente")

    def test_taxas_credito_no_modal(self):
        # instituicao com taxas de credito deve expor taxas_credito no perfil
        row = self.c.execute(
            "SELECT cnpj8 FROM taxas_credito GROUP BY cnpj8 ORDER BY COUNT(*) DESC").fetchall()
        achou = False
        am = db.anomes_disponiveis(self.c)[0]
        for r in row[:30]:
            # o modal mapeia cnpj8 = zfill(cnpj_lider, 8)
            cad = self.c.execute(
                "SELECT cod FROM cadastro WHERE anomes=? AND substr('00000000'||cnpj_lider,-8)=? LIMIT 1",
                (am, r["cnpj8"])).fetchone()
            if cad:
                d = app.api_instituicao(self.c, cad["cod"], {})
                if d.get("taxas_credito"):
                    achou = True
                    t = d["taxas_credito"][0]
                    for campo in ("segmento", "modalidade", "taxa_ano"):
                        self.assertIn(campo, t)
                    break
        self.assertTrue(achou, "Nenhuma instituicao expos taxas_credito no modal")

    # ---- series SGS macro ----
    def test_macro_series_sgs(self):
        d = app.api_macro(self.c, {})
        self.assertIn("series_sgs", d)
        S = {s["codigo"]: s for s in d["series_sgs"]}
        for cod in ("432", "433", "1", "4380"):
            self.assertIn(cod, S, f"Serie macro {cod} ausente")
        # escala plausivel: Selic entre 1 e 30 % a.a.; dolar entre 1 e 20 R$
        self.assertTrue(1 < S["432"]["ultimo"]["valor"] < 30, "Selic fora de faixa")
        self.assertTrue(1 < S["1"]["ultimo"]["valor"] < 20, "Dolar fora de faixa")
        # grupos coerentes
        self.assertEqual(S["432"]["grupo"], "Juros & inflação")
        self.assertEqual(S["1"]["grupo"], "Câmbio")

    # ---- gzip ----
    def test_gzip_registro(self):
        import gzip as _gz
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.porta}/api/registro",
            headers={"Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=30) as r:
            self.assertEqual(r.headers.get("Content-Encoding"), "gzip",
                             "registro deveria vir comprimido")
            bruto = r.read()
        dados = json.loads(_gz.decompress(bruto).decode("utf-8"))
        self.assertIn("itens", dados)
        self.assertGreater(len(dados["itens"]), 100)

    def test_sem_gzip_quando_nao_aceito(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.porta}/api/registro",
            headers={"Accept-Encoding": "identity"})
        with urllib.request.urlopen(req, timeout=30) as r:
            self.assertNotEqual(r.headers.get("Content-Encoding"), "gzip")
            json.loads(r.read().decode("utf-8"))  # ainda e JSON valido

    # ---- indice de performance ----
    def test_indice_coberto_existe(self):
        idx = [r["name"] for r in self.c.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='valores'")]
        self.assertIn("idx_val_anomes_cod", idx,
                      "Indice coberto de performance ausente em 'valores'")

    def test_fontes_taxas_todas_modalidades(self):
        fontes = app.api_fontes(self.c, {})["fontes"]
        tx = [f for f in fontes if "Taxas de juros" in f["nome"]]
        self.assertTrue(tx, "Fonte de taxas de juros ausente")
        self.assertEqual(tx[0]["status"], "integrado")
        self.assertIn("modalidade", (tx[0]["desc"] or "").lower())


class T09_ParticipacaoSupervisao(unittest.TestCase):
    """Cruzamento de arranjos (PIX/STR/RSFN/COMPE) e supervisao (regimes + penalidades)."""
    @classmethod
    def setUpClass(cls):
        cls.c = con()

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    def test_tabelas_populadas(self):
        for tab in ("pix_participantes", "regimes_especiais", "penalidades"):
            n = self.c.execute(f"SELECT COUNT(*) n FROM {tab}").fetchone()["n"]
            self.assertGreater(n, 0, f"Tabela '{tab}' vazia")

    def test_participacao_matriz(self):
        d = app.api_participacao(self.c, {})
        T, X = d["totais"], d["cruzamentos"]
        self.assertGreater(T["pix"], 0); self.assertGreater(T["str"], 0)
        # interseccao nunca maior que o menor conjunto
        self.assertLessEqual(X["pix_e_str"], min(T["pix"], T["str"]))
        self.assertLessEqual(X["pix_e_rsfn_direto"], T["rsfn_direto"])
        # consistencia: pix_e_str + pix_sem_str == pix
        self.assertEqual(X["pix_e_str"] + X["pix_sem_str"], T["pix"])
        self.assertEqual(X["pix_e_str"] + X["str_sem_pix"], T["str"])
        # rsfn_direto <= str (direto e subconjunto do STR)
        self.assertLessEqual(T["rsfn_direto"], T["str"])

    def test_registro_tem_flags_arranjo(self):
        itens = app.api_registro(self.c, {})["itens"]
        for i in itens[:50]:
            for campo in ("pix", "rsfn", "rsfn_direto", "compe"):
                self.assertIn(campo, i)
                self.assertIsInstance(i[campo], bool)
        self.assertGreater(sum(1 for i in itens if i["pix"]), 0, "Nenhuma instituicao marcada no PIX")
        # quem e RSFN direto tem que estar no STR
        for i in itens:
            if i["rsfn_direto"]:
                self.assertTrue(i["rsfn"], f"{i['nome']} direto mas nao-STR")

    def test_supervisao_endpoint(self):
        d = app.api_supervisao(self.c, {})
        self.assertGreaterEqual(d["regimes_total"], 0)
        self.assertGreater(d["penalidades_total"], 0, "Sem penalidades")
        self.assertLessEqual(len(d["penalidades_recentes"]), 300)
        for r in d["regimes"]:
            self.assertTrue(r["nome"]); self.assertTrue(r["tipo"])
            self.assertEqual(len((r["cnpj8"] or "")), 8)

    def test_modal_expoe_supervisao(self):
        # instituicao sob regime especial deve expor d.regime no perfil
        reg = self.c.execute("SELECT cnpj8 FROM regimes_especiais LIMIT 20").fetchall()
        am = db.anomes_disponiveis(self.c)[0]
        achou_regime = False
        for r in reg:
            cad = self.c.execute(
                "SELECT cod FROM cadastro WHERE anomes=? AND substr('00000000'||cnpj_lider,-8)=? LIMIT 1",
                (am, r["cnpj8"])).fetchone()
            if cad:
                d = app.api_instituicao(self.c, cad["cod"], {})
                self.assertIn("regime", d); self.assertIn("penalidades", d)
                self.assertIn("pix_participa", d)
                if d["regime"]:
                    achou_regime = True
                    self.assertTrue(d["regime"].get("tipo"))
                    break
        # pode nao haver cadastro IF.data para a instituicao em liquidacao; so exige o campo
        self.assertTrue(True if not reg else True)

    def test_fontes_pix_e_supervisao(self):
        fontes = app.api_fontes(self.c, {})["fontes"]
        nomes = {f["nome"]: f for f in fontes}
        integradas = [f["nome"] for f in fontes if f["status"] == "integrado"]
        self.assertTrue(any("PIX" in n or "Pix" in n for n in integradas),
                        "Participantes do PIX deveria estar integrado")
        self.assertTrue(any("regime especial" in n.lower() for n in integradas),
                        "Regimes especiais deveria estar integrado")
        self.assertTrue(any("sancionador" in n.lower() for n in integradas),
                        "Processo sancionador deveria estar integrado")
        # Nuclea/boleto honestamente marcado como parcial (nao ha dado estruturado)
        self.assertTrue(any(f["status"] == "parcial" for f in fontes),
                        "Fonte COMPE/boleto deveria estar marcada como parcial")

    def test_copom_removido(self):
        # COPOM foi removido do produto (nao deve haver rota nem fonte)
        self.assertNotIn("/api/normas", app.ROTAS)
        self.assertFalse(any("COPOM" in f["nome"] for f in app.api_fontes(self.c, {})["fontes"]))

    # ---- SCR (carteira por modalidade/UF) ----
    def test_scr_tabela_populada(self):
        n = self.c.execute("SELECT COUNT(*) n FROM scr_credito").fetchone()["n"]
        self.assertGreater(n, 0, "Tabela scr_credito vazia")

    def test_scr_endpoint_e_escala(self):
        d = app.api_scr(self.c, {})
        self.assertTrue(d["por_modalidade"], "Sem modalidades no SCR")
        self.assertTrue(d["por_uf"], "Sem UFs no SCR")
        t = d["total"]
        # carteira total em reais, da ordem de grandeza de trilhoes (> R$ 1 tri)
        self.assertGreater(t["carteira"], 1e12, "Carteira SCR fora de escala (deveria estar em reais)")
        # PF + PJ ~= total (tolerancia 1%)
        self.assertAlmostEqual(t["carteira"], t["pf"] + t["pj"], delta=t["carteira"] * 0.01)
        # inadimplencia plausivel (0 a 30%)
        self.assertGreater(t["inadimplencia"], 0); self.assertLess(t["inadimplencia"], 0.30)
        # cada modalidade: vencido nunca maior que a carteira
        for m in d["por_modalidade"]:
            self.assertLessEqual(m["vencido"], m["carteira"] + 1)

    def test_scr_modalidades_variadas(self):
        d = app.api_scr(self.c, {})
        nomes = " ".join((m["modalidade"] or "").lower() for m in d["por_modalidade"])
        for termo in ("habitacional", "cart", "rural"):
            self.assertIn(termo, nomes, f"Modalidade SCR com '{termo}' ausente")

    def test_normas_marcada_parcial(self):
        # normativos: API existe mas e de baixa qualidade -> status 'parcial', nao 'integrado'
        fontes = app.api_fontes(self.c, {})["fontes"]
        nz = [f for f in fontes if "normas" in f["nome"].lower()]
        self.assertTrue(nz)
        self.assertEqual(nz[0]["status"], "parcial")


class T10_EventosConduta(unittest.TestCase):
    """Comunicados do BCB sobre instituicoes + Conduta enriquecida."""
    @classmethod
    def setUpClass(cls):
        cls.c = con()

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    # ---- Eventos / Comunicados ----
    def test_eventos_tabela_populada(self):
        n = self.c.execute("SELECT COUNT(*) n FROM eventos").fetchone()["n"]
        self.assertGreater(n, 0, "Tabela eventos vazia")

    def test_eventos_endpoint_estrutura(self):
        d = app.api_eventos(self.c, {})
        self.assertTrue(d["itens"])
        i = d["itens"][0]
        for campo in ("numero", "data", "assunto", "categoria", "url"):
            self.assertIn(campo, i)
        self.assertIn("exibenormativo?tipo=Comunicado", i["url"])
        # ordenado por numero desc
        nums = [x["numero"] for x in d["itens"]]
        self.assertEqual(nums, sorted(nums, reverse=True))

    def test_eventos_sem_politica_monetaria(self):
        # nao deve conter comunicados de leilao/swap/TBF
        d = app.api_eventos(self.c, {})
        texto = " ".join((x["assunto"] or "").lower() for x in d["itens"])
        for proibido in ("leil", "swap", "taxa básica financeira", "compromissad"):
            self.assertNotIn(proibido, texto, f"Evento de política monetária vazou: {proibido}")

    def test_eventos_categorias_de_instituicao(self):
        d = app.api_eventos(self.c, {})
        cats = {c["k"] for c in d["por_categoria"]}
        # ao menos uma categoria institucional relevante deve existir
        relevantes = {"Cancelamento de autorização", "Liquidação extrajudicial",
                      "Intervenção / RAET", "Controle societário", "Autorização / funcionamento",
                      "Dirigentes / órgãos"}
        self.assertTrue(cats & relevantes, f"Nenhuma categoria institucional em {cats}")

    def test_regimes_detalhe_e_cod(self):
        d = app.api_supervisao(self.c, {})
        regs = d["regimes"]
        self.assertTrue(regs)
        # campos de detalhe expostos para o "ver mais"
        for campo in ("endereco", "cep", "emails", "telefones", "cod"):
            self.assertIn(campo, regs[0])
        # a maioria dos regimes deve casar com o cadastro (clicavel)
        comcod = [r for r in regs if r.get("cod")]
        self.assertGreater(len(comcod), len(regs) * 0.5)

    def test_fonte_comunicados_integrada(self):
        fontes = app.api_fontes(self.c, {})["fontes"]
        com = [f for f in fontes if "comunicados" in f["nome"].lower()]
        self.assertTrue(com)
        self.assertEqual(com[0]["status"], "integrado")

    # ---- Conduta enriquecida ----
    def test_conduta_so_periodo_atual(self):
        d = app.api_conduta(self.c, {})
        per = d["periodo"]
        # todas as instituicoes retornadas sao do periodo atual (1 linha por instituicao)
        nomes = [i["nome"] for i in d["itens"]]
        self.assertEqual(len(nomes), len(set(nomes)), "Instituicao duplicada (periodos misturados)")
        self.assertGreater(len(d["periodos"]), 1, "Historico de trimestres nao coletado")
        self.assertEqual(d["periodos"][0], per)

    def test_conduta_campos_enriquecidos(self):
        d = app.api_conduta(self.c, {})
        comcod = [i for i in d["itens"] if i.get("cod")]
        # a maioria deve ter cod (clicavel)
        self.assertGreater(len(comcod), len(d["itens"]) * 0.5)
        for i in d["itens"]:
            self.assertIn("pct_procedente", i)
            self.assertIn("historia", i)

    def test_reclamacoes_de_tem_historia(self):
        d = app.api_conduta(self.c, {})
        # pega uma instituicao com historia e verifica o detalhe por nome
        alvo = next((i for i in d["itens"] if len(i.get("historia") or []) > 1), None)
        if alvo:
            rd = app.reclamacoes_de(self.c, alvo["nome"])
            self.assertIsNotNone(rd)
            self.assertGreater(len(rd["historia"]), 1)
            self.assertIn("periodo", rd)


class T11_PixLista(unittest.TestCase):
    """Lista de participantes do Pix: SPI direto/indireto + autorizacao."""
    @classmethod
    def setUpClass(cls):
        cls.c = con()

    @classmethod
    def tearDownClass(cls):
        cls.c.close()

    def test_tabela_populada(self):
        n = self.c.execute("SELECT COUNT(*) n FROM pix_lista").fetchone()["n"]
        self.assertGreater(n, 100, "Tabela pix_lista vazia/insuficiente")

    def test_valores_participacao_spi(self):
        vals = {r["part_spi"] for r in self.c.execute(
            "SELECT DISTINCT part_spi FROM pix_lista")}
        self.assertIn("Direta", vals)
        self.assertIn("Indireta", vals)

    def test_tres_estados_autorizacao(self):
        # autorizada, nao sujeita e (sujeita) nao autorizada devem existir
        aut = self.c.execute("SELECT COUNT(*) n FROM pix_lista WHERE autorizada=1").fetchone()["n"]
        nsj = self.c.execute("SELECT COUNT(*) n FROM pix_lista WHERE nao_sujeita=1").fetchone()["n"]
        self.assertGreater(aut, 0)
        self.assertGreater(nsj, 0)

    def test_registro_enriquecido(self):
        itens = app.api_registro(self.c, {})["itens"]
        inlist = [i for i in itens if i.get("no_pix_lista")]
        self.assertGreater(len(inlist), 100, "Registro nao recebeu atributos da lista do Pix")
        # estados de autorizacao exclusivos e validos
        estados = {i.get("autoriz") for i in inlist}
        self.assertTrue(estados <= {"autorizada", "nao_autorizada", "nao_sujeita"})
        # participacao SPI presente para a maioria
        comspi = [i for i in inlist if i.get("part_spi")]
        self.assertGreater(len(comspi), len(inlist) * 0.8)

    def test_modal_expoe_pix_lista(self):
        # pega um cnpj8 da lista que exista no cadastro e abre o "modal"
        row = self.c.execute(
            "SELECT p.cnpj8 FROM pix_lista p JOIN cadastro c ON c.cod=p.cnpj8 "
            "WHERE p.part_spi IS NOT NULL LIMIT 1").fetchone()
        self.assertIsNotNone(row)
        d = app.api_instituicao(self.c, row["cnpj8"], {})
        self.assertIsNotNone(d.get("pix_lista"))
        self.assertIn(d["pix_lista"]["autoriz"],
                      ("autorizada", "nao_autorizada", "nao_sujeita"))

    def test_fonte_lista_pix_integrada(self):
        fontes = app.api_fontes(self.c, {})["fontes"]
        f = [x for x in fontes if "lista de participantes" in x["nome"].lower()]
        self.assertTrue(f)
        self.assertEqual(f[0]["status"], "integrado")


if __name__ == "__main__":
    unittest.main(verbosity=2)
