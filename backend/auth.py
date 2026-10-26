"""Autenticacao (stdlib): usuarios, senhas (PBKDF2) e sessoes em SQLite proprio.

Fica num banco separado (dados/usuarios.db) para que a coleta/atualizacao dos
dados do BCB nunca toque nos usuarios.

CLI (dentro de backend/):
  python3 auth.py criar-admin <email> [nome]   cria/reseta um admin (pede a senha)
  python3 auth.py listar
"""
import hashlib, hmac, os, secrets, sqlite3, sys, time, threading, getpass
import config

ITERACOES = 600_000
SESSAO_DIAS = 7
COOKIE = "bcb_sessao"
SENHA_MIN = 8

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL COLLATE NOCASE,
  nome TEXT,
  senha_hash TEXT NOT NULL,
  admin INTEGER NOT NULL DEFAULT 0,
  ativo INTEGER NOT NULL DEFAULT 1,
  criado_em INTEGER NOT NULL,
  ultimo_login INTEGER
);
CREATE TABLE IF NOT EXISTS sessoes (
  token_hash TEXT PRIMARY KEY,
  usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
  criado_em INTEGER NOT NULL,
  expira_em INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessoes_usuario ON sessoes (usuario_id);
"""


def conectar():
    os.makedirs(os.path.dirname(config.AUTH_DB_PATH), exist_ok=True)
    con = sqlite3.connect(config.AUTH_DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    return con


# ---------------------------------------------------------------- senhas
def hash_senha(senha):
    sal = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, ITERACOES)
    return f"pbkdf2_sha256${ITERACOES}${sal.hex()}${dk.hex()}"


def confere_senha(senha, armazenado):
    try:
        alg, it, sal, dk = armazenado.split("$")
        if alg != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), int(it))
        return hmac.compare_digest(calc.hex(), dk)
    except Exception:
        return False


# hash "falso" para gastar o mesmo tempo quando o e-mail nao existe
_HASH_FALSO = hash_senha(secrets.token_hex(8))


def valida_senha(senha):
    if not senha or len(senha) < SENHA_MIN:
        return f"A senha precisa ter pelo menos {SENHA_MIN} caracteres."
    return None


# ---------------------------------------------------------------- limite de tentativas
_tentativas = {}
_lock = threading.Lock()
JANELA, MAX_TENT = 15 * 60, 10


def bloqueado(chave):
    agora = time.time()
    with _lock:
        lst = [t for t in _tentativas.get(chave, []) if agora - t < JANELA]
        _tentativas[chave] = lst
        return len(lst) >= MAX_TENT


def registra_falha(chave):
    with _lock:
        _tentativas.setdefault(chave, []).append(time.time())


def limpa_falhas(chave):
    with _lock:
        _tentativas.pop(chave, None)


# ---------------------------------------------------------------- usuarios
def _publico(r):
    return {"id": r["id"], "email": r["email"], "nome": r["nome"], "admin": bool(r["admin"]),
            "ativo": bool(r["ativo"]), "criado_em": r["criado_em"], "ultimo_login": r["ultimo_login"]}


def autenticar(con, email, senha):
    r = con.execute("SELECT * FROM usuarios WHERE email=?", ((email or "").strip(),)).fetchone()
    if not r:
        confere_senha(senha or "", _HASH_FALSO)
        return None
    if not confere_senha(senha or "", r["senha_hash"]) or not r["ativo"]:
        return None
    con.execute("UPDATE usuarios SET ultimo_login=? WHERE id=?", (int(time.time()), r["id"]))
    con.commit()
    return _publico(r)


def listar(con):
    return [_publico(r) for r in con.execute("SELECT * FROM usuarios ORDER BY email")]


def obter(con, uid):
    r = con.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
    return _publico(r) if r else None


def criar(con, email, nome, senha, admin=False):
    email = (email or "").strip()
    if "@" not in email:
        raise ValueError("E-mail invalido.")
    erro = valida_senha(senha)
    if erro:
        raise ValueError(erro)
    try:
        cur = con.execute(
            "INSERT INTO usuarios (email,nome,senha_hash,admin,criado_em) VALUES (?,?,?,?,?)",
            (email, (nome or "").strip() or None, hash_senha(senha), int(bool(admin)), int(time.time())))
    except sqlite3.IntegrityError:
        raise ValueError("Ja existe um usuario com esse e-mail.")
    con.commit()
    return obter(con, cur.lastrowid)


def _admins_ativos(con, exceto=None):
    return con.execute("SELECT COUNT(*) n FROM usuarios WHERE admin=1 AND ativo=1 AND id<>?",
                       (exceto or 0,)).fetchone()["n"]


def atualizar(con, uid, nome=None, admin=None, ativo=None, senha=None):
    atual = obter(con, uid)
    if not atual:
        raise ValueError("Usuario nao encontrado.")
    perde_admin = (admin is False or ativo is False) and atual["admin"] and atual["ativo"]
    if perde_admin and not _admins_ativos(con, exceto=uid):
        raise ValueError("Precisa sobrar pelo menos um administrador ativo.")
    if nome is not None:
        con.execute("UPDATE usuarios SET nome=? WHERE id=?", (nome.strip() or None, uid))
    if admin is not None:
        con.execute("UPDATE usuarios SET admin=? WHERE id=?", (int(bool(admin)), uid))
    if ativo is not None:
        con.execute("UPDATE usuarios SET ativo=? WHERE id=?", (int(bool(ativo)), uid))
        if not ativo:
            con.execute("DELETE FROM sessoes WHERE usuario_id=?", (uid,))
    if senha is not None:
        erro = valida_senha(senha)
        if erro:
            raise ValueError(erro)
        con.execute("UPDATE usuarios SET senha_hash=? WHERE id=?", (hash_senha(senha), uid))
    con.commit()
    return obter(con, uid)


def remover(con, uid):
    atual = obter(con, uid)
    if not atual:
        raise ValueError("Usuario nao encontrado.")
    if atual["admin"] and atual["ativo"] and not _admins_ativos(con, exceto=uid):
        raise ValueError("Precisa sobrar pelo menos um administrador ativo.")
    con.execute("DELETE FROM usuarios WHERE id=?", (uid,))
    con.commit()


# ---------------------------------------------------------------- sessoes
def _h(token):
    return hashlib.sha256(token.encode()).hexdigest()


def criar_sessao(con, uid):
    token = secrets.token_urlsafe(32)
    agora = int(time.time())
    con.execute("DELETE FROM sessoes WHERE expira_em<?", (agora,))
    con.execute("INSERT INTO sessoes VALUES (?,?,?,?)",
                (_h(token), uid, agora, agora + SESSAO_DIAS * 86400))
    con.commit()
    return token


def usuario_da_sessao(con, token):
    if not token:
        return None
    r = con.execute(
        "SELECT u.* FROM sessoes s JOIN usuarios u ON u.id=s.usuario_id "
        "WHERE s.token_hash=? AND s.expira_em>? AND u.ativo=1",
        (_h(token), int(time.time()))).fetchone()
    return _publico(r) if r else None


def encerrar_sessao(con, token):
    if token:
        con.execute("DELETE FROM sessoes WHERE token_hash=?", (_h(token),))
        con.commit()


def encerrar_outras_sessoes(con, uid, token_atual):
    con.execute("DELETE FROM sessoes WHERE usuario_id=? AND token_hash<>?", (uid, _h(token_atual or "")))
    con.commit()


# ---------------------------------------------------------------- CLI
def _cli(argv):
    if len(argv) >= 2 and argv[0] == "criar-admin":
        email, nome = argv[1], (argv[2] if len(argv) > 2 else None)
        senha = os.environ.get("BCB_SENHA_ADMIN") or getpass.getpass("Senha: ")
        con = conectar()
        r = con.execute("SELECT id FROM usuarios WHERE email=?", (email,)).fetchone()
        if r:
            atualizar(con, r["id"], admin=True, ativo=True, senha=senha)
            print(f"Admin {email} atualizado (senha redefinida).")
        else:
            criar(con, email, nome, senha, admin=True)
            print(f"Admin {email} criado.")
    elif argv[:1] == ["listar"]:
        for u in listar(conectar()):
            print(f"{u['id']:>3}  {u['email']:<35} {'admin' if u['admin'] else 'usuario':<8} "
                  f"{'ativo' if u['ativo'] else 'INATIVO'}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
