"""Configuracao central do Hub do Sistema Financeiro Nacional."""
import os

# ---------------------------------------------------------------- APIs do BCB
OLINDA_IFDATA = "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/"
OLINDA_SPI    = "https://olinda.bcb.gov.br/olinda/servico/SPI/versao/v1/odata/"
CSV_STR       = "https://www.bcb.gov.br/content/estabilidadefinanceira/str1/ParticipantesSTR.csv"

# Visao prudencial do IF.data (casa com a segmentacao S1-S5)
TIPO_INSTITUICAO = 1

# ---------------------------------------------------------------- IF.data
RELATORIOS = {
    "1": "Resumo", "2": "Ativo", "3": "Passivo", "4": "Demonstracao de Resultado",
    "5": "Informacoes de Capital", "7": "Carteira - por indexador",
    "8": "Carteira - por nivel de risco", "9": "Carteira - por regiao geografica",
    "10": "Carteira - clientes e operacoes", "11": "Carteira PF - modalidade e prazo",
    "12": "Carteira PJ - por atividade (CNAE)", "13": "Carteira PJ - modalidade e prazo",
    "14": "Carteira PJ - por porte do tomador", "16": "Carteira - por instrumentos financeiros",
}

# ---------------------------------------------------------------- Hierarquia de tipos
# TCB (Tipo de Consolidado Bancario) -> grupo (hierarquia) + descricao
TIPOS = {
    "b1":  ("Bancos", "Banco comercial / multiplo c/ carteira comercial / Caixa"),
    "b2":  ("Bancos", "Banco multiplo s/ carteira comercial / investimento / cambio"),
    "b4":  ("Bancos", "Banco de desenvolvimento / agencia de fomento"),
    "b3s": ("Cooperativas", "Cooperativa de credito singular"),
    "b3c": ("Cooperativas", "Cooperativa central de credito"),
    "n1":  ("Credito nao-bancario", "SCFI / financeira / credito nao-bancario"),
    "n2":  ("Mercado de capitais", "Corretora / distribuidora (CTVM / DTVM)"),
    "n3":  ("Consorcios", "Administradora de consorcio"),
    "n4":  ("Pagamentos", "Instituicao de pagamento"),
}
def tipo_info(tcb):
    return TIPOS.get((tcb or "").lower(), ("Outras", "Nao classificada"))

TC_LBL = {"1": "Publico", "2": "Privado Nacional", "3": "Estrangeiro", "4": "Estrangeiro"}

# Metricas-chave (relatorio, nome_coluna, alias)
METRICAS_CHAVE = [
    ("1", "Ativo Total", "ativo"), ("1", "Carteira de Credito", "credito"),
    ("1", "Patrimonio Liquido", "pl"), ("1", "Lucro Liquido", "lucro"),
    ("1", "Captacoes", "captacoes"), ("1", "Numero de Agencias", "agencias"),
    ("5", "Indice de Basileia", "basileia"), ("5", "Indice de Capital Nivel I", "capital_n1"),
    ("5", "Razao de Alavancagem", "alavancagem"), ("5", "Indice de Imobilizacao", "imobilizacao"),
]

# ---------------------------------------------------------------- Coleta
MODO = os.environ.get("BCB_MODO", "rapido")
if MODO == "completo":
    ANOS_HISTORICO = 5
    RELATORIOS_COLETA = list(RELATORIOS.keys())
else:
    ANOS_HISTORICO = 2
    RELATORIOS_COLETA = ["1", "2", "3", "4", "5"]

# ---------------------------------------------------------------- Caminhos
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("BCB_DB_PATH") or os.path.join(RAIZ, "dados", "bcb.db")
AUTH_DB_PATH = os.environ.get("BCB_AUTH_DB_PATH") or os.path.join(RAIZ, "dados", "usuarios.db")
FRONTEND_DIR = os.path.join(RAIZ, "frontend")
PORTA = int(os.environ.get("BCB_PORTA", "8765"))

# ---------------------------------------------------------------- Servidor
HOST = os.environ.get("BCB_HOST", "127.0.0.1")
# Login obrigatorio (desligue so para uso local: BCB_AUTH=0)
AUTH = os.environ.get("BCB_AUTH", "1") != "0"
# Abre o navegador ao subir (uso local); no servidor: BCB_ABRIR_NAVEGADOR=0
ABRIR_NAVEGADOR = os.environ.get("BCB_ABRIR_NAVEGADOR", "1") != "0"
# Porta fixa (no servidor nao tenta as proximas se estiver ocupada)
PORTA_FIXA = os.environ.get("BCB_PORTA_FIXA", "0") == "1"
# Cookie de sessao so via HTTPS (ligar no servidor atras do Cloudflare)
COOKIE_SEGURO = os.environ.get("BCB_COOKIE_SEGURO", "0") == "1"
