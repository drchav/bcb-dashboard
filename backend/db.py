"""Camada SQLite: cache e historico."""
import sqlite3, os
import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS cadastro (
  cod TEXT, anomes TEXT, nome TEXT, tcb TEXT, td TEXT, tc INTEGER,
  sr TEXT, segmento_tb TEXT, atividade TEXT, uf TEXT, municipio TEXT,
  cnpj_lider TEXT, situacao TEXT, cod_prud TEXT, dt_inicio INTEGER,
  PRIMARY KEY (cod, anomes)
);
CREATE TABLE IF NOT EXISTS valores (
  cod TEXT, anomes TEXT, relatorio TEXT, grupo TEXT, coluna TEXT,
  coluna_norm TEXT, saldo REAL,
  PRIMARY KEY (cod, anomes, relatorio, grupo, coluna)
);
CREATE INDEX IF NOT EXISTS idx_val_lookup ON valores (anomes, relatorio, coluna_norm);
CREATE INDEX IF NOT EXISTS idx_val_cod ON valores (cod, anomes);
-- indice coberto: acelera o pivot de metricas-chave (JOIN cadastro x valores por anomes)
CREATE INDEX IF NOT EXISTS idx_val_anomes_cod ON valores (anomes, cod, coluna_norm, relatorio, saldo);
CREATE INDEX IF NOT EXISTS idx_cad_anomes ON cadastro (anomes);
CREATE TABLE IF NOT EXISTS str_participantes (
  ispb TEXT PRIMARY KEY, nome_reduzido TEXT, codigo TEXT, participa_compe TEXT,
  acesso TEXT, nome_extenso TEXT, inicio TEXT
);
CREATE TABLE IF NOT EXISTS pix_participantes (
  ispb TEXT PRIMARY KEY, nome TEXT, segmento TEXT
);
CREATE TABLE IF NOT EXISTS pix_lista (
  cnpj8 TEXT PRIMARY KEY, nome TEXT, tipo_inst TEXT,
  autorizada INTEGER, nao_sujeita INTEGER,
  part_spi TEXT, part_pix TEXT, modalidade TEXT,
  iniciador INTEGER, fss TEXT, situacao TEXT
);
CREATE TABLE IF NOT EXISTS regimes_especiais (
  cnpj8 TEXT, cnpj TEXT, nome TEXT, inicio TEXT, tipo TEXT,
  responsavel TEXT, municipio TEXT, uf TEXT,
  endereco TEXT, cep TEXT, emails TEXT, telefones TEXT
);
CREATE INDEX IF NOT EXISTS idx_regimes_cnpj ON regimes_especiais (cnpj8);
CREATE TABLE IF NOT EXISTS penalidades (
  pas TEXT, nome TEXT, cnpj_cpf TEXT, cnpj8 TEXT, data_citacao TEXT,
  data_decisao TEXT, tipo_penalidade TEXT, valor_multa REAL, situacao TEXT
);
CREATE INDEX IF NOT EXISTS idx_penas_cnpj ON penalidades (cnpj8);
CREATE TABLE IF NOT EXISTS pix_liquidados (
  data TEXT PRIMARY KEY, quantidade REAL, canal_primario REAL,
  canal_secundario REAL, total REAL, media REAL
);
CREATE TABLE IF NOT EXISTS taxas (
  cnpj8 TEXT, anomes TEXT, modalidade TEXT, posicao INTEGER,
  instituicao TEXT, taxa_mes REAL, taxa_ano REAL
);
CREATE INDEX IF NOT EXISTS idx_taxas_cnpj ON taxas (cnpj8, anomes);
CREATE INDEX IF NOT EXISTS idx_taxas_mod ON taxas (anomes, modalidade);
CREATE TABLE IF NOT EXISTS taxas_credito (
  periodo_ini TEXT, periodo_fim TEXT, segmento TEXT, cod_modalidade TEXT,
  modalidade TEXT, posicao INTEGER, cnpj8 TEXT, instituicao TEXT,
  taxa_mes REAL, taxa_ano REAL
);
CREATE INDEX IF NOT EXISTS idx_txcred_cnpj ON taxas_credito (cnpj8);
CREATE INDEX IF NOT EXISTS idx_txcred_mod ON taxas_credito (modalidade, taxa_ano);
CREATE TABLE IF NOT EXISTS cnpj_cache (cnpj8 TEXT PRIMARY KEY, dados TEXT, obtido TEXT);
CREATE TABLE IF NOT EXISTS reclamacoes (
  nome_norm TEXT, nome TEXT, categoria TEXT, periodo TEXT, indice REAL,
  reclamacoes REAL, procedentes REAL, analisadas REAL, clientes REAL
);
CREATE INDEX IF NOT EXISTS idx_recl_nome ON reclamacoes (nome_norm);
CREATE TABLE IF NOT EXISTS focus (
  indicador TEXT, data TEXT, referencia TEXT, mediana REAL, media REAL,
  minimo REAL, maximo REAL, respondentes INTEGER
);
CREATE TABLE IF NOT EXISTS sgs_credito (
  codigo TEXT, nome TEXT, unidade TEXT, tipo TEXT, data TEXT, valor REAL,
  PRIMARY KEY (codigo, data)
);
CREATE INDEX IF NOT EXISTS idx_sgs_cod ON sgs_credito (codigo, data);
CREATE TABLE IF NOT EXISTS eventos (
  numero INTEGER PRIMARY KEY, data TEXT, data_texto TEXT, titulo TEXT,
  assunto TEXT, categoria TEXT
);
CREATE INDEX IF NOT EXISTS idx_eventos_cat ON eventos (categoria);
CREATE TABLE IF NOT EXISTS scr_credito (
  data_base INTEGER, cliente TEXT, estado TEXT, sub_regiao TEXT, modalidade TEXT,
  operacoes INTEGER, carteira REAL, vencido REAL
);
CREATE INDEX IF NOT EXISTS idx_scr_mod ON scr_credito (modalidade);
CREATE INDEX IF NOT EXISTS idx_scr_uf ON scr_credito (estado);
CREATE TABLE IF NOT EXISTS sgs_macro (
  codigo TEXT, nome TEXT, grupo TEXT, unidade TEXT, tipo TEXT, data TEXT, valor REAL,
  PRIMARY KEY (codigo, data)
);
CREATE INDEX IF NOT EXISTS idx_sgsmacro_cod ON sgs_macro (codigo, data);
CREATE TABLE IF NOT EXISTS tarifa_grupos (codigo TEXT PRIMARY KEY, nome TEXT);
CREATE TABLE IF NOT EXISTS tarifa_cache (cnpj8 TEXT PRIMARY KEY, dados TEXT, obtido TEXT);
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT);
"""


def conectar():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init(con):
    con.executescript(SCHEMA)
    _migrar(con)
    con.commit()


# colunas adicionadas depois da criacao original de uma tabela (cache ja existente)
_MIGRACOES = {
    "regimes_especiais": [("endereco", "TEXT"), ("cep", "TEXT"),
                          ("emails", "TEXT"), ("telefones", "TEXT")],
}


def _migrar(con):
    for tabela, colunas in _MIGRACOES.items():
        existentes = {r[1] for r in con.execute(f"PRAGMA table_info({tabela})")}
        for nome, tipo in colunas:
            if nome not in existentes:
                con.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}")


def set_meta(con, chave, valor):
    con.execute("INSERT OR REPLACE INTO meta(chave,valor) VALUES(?,?)", (chave, str(valor)))


def get_meta(con, chave, padrao=None):
    r = con.execute("SELECT valor FROM meta WHERE chave=?", (chave,)).fetchone()
    return r["valor"] if r else padrao


def anomes_disponiveis(con):
    rows = con.execute(
        "SELECT DISTINCT anomes FROM cadastro ORDER BY anomes DESC").fetchall()
    return [r["anomes"] for r in rows]
