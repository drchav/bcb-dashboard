"""Testes do login, sessoes e administracao de usuarios.

Usa um banco de usuarios temporario (nao mexe em dados/usuarios.db).
Rode com:  python -m unittest -v testes.test_auth   (dentro de backend/)
"""
import os, sys, json, tempfile, threading, unittest, urllib.request, urllib.error
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config, auth, app


class _SemRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class T00_Senhas(unittest.TestCase):
    def test_hash_confere(self):
        h = auth.hash_senha("segredo123")
        self.assertTrue(auth.confere_senha("segredo123", h))
        self.assertFalse(auth.confere_senha("errada123", h))
        self.assertNotIn("segredo123", h)

    def test_hash_com_sal(self):
        self.assertNotEqual(auth.hash_senha("x" * 8), auth.hash_senha("x" * 8))

    def test_senha_curta(self):
        self.assertIsNotNone(auth.valida_senha("1234567"))
        self.assertIsNone(auth.valida_senha("12345678"))


class T01_Http(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls._antes = (config.AUTH, config.AUTH_DB_PATH)
        config.AUTH, config.AUTH_DB_PATH = True, os.path.join(cls.tmp.name, "u.db")
        con = auth.conectar()
        cls.admin = auth.criar(con, "admin@teste.com", "Admin", "senhaadmin1", admin=True)
        auth.criar(con, "user@teste.com", "User", "senhauser1")
        con.close()
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.porta = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close()
        config.AUTH, config.AUTH_DB_PATH = cls._antes
        auth._tentativas.clear()
        cls.tmp.cleanup()

    def setUp(self):
        auth._tentativas.clear()

    def req(self, metodo, path, body=None, cookie=None, ctype="application/json"):
        dados = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(f"http://127.0.0.1:{self.porta}{path}", data=dados, method=metodo)
        if dados is not None:
            r.add_header("Content-Type", ctype)
        if cookie:
            r.add_header("Cookie", cookie)
        op = urllib.request.build_opener(_SemRedirect)
        try:
            with op.open(r, timeout=20) as resp:
                return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def login(self, email, senha):
        st, h, _ = self.req("POST", "/api/auth/login", {"email": email, "senha": senha})
        self.assertEqual(st, 200)
        return h["Set-Cookie"].split(";")[0]

    def test_sem_login_api_401(self):
        self.assertEqual(self.req("GET", "/api/meta")[0], 401)

    def test_sem_login_pagina_redireciona(self):
        st, h, _ = self.req("GET", "/")
        self.assertEqual(st, 302)
        self.assertEqual(h["Location"], "/login")

    def test_pagina_login_publica(self):
        self.assertEqual(self.req("GET", "/login")[0], 200)
        self.assertEqual(self.req("GET", "/styles.css")[0], 200)

    def test_login_errado(self):
        st, _, b = self.req("POST", "/api/auth/login", {"email": "admin@teste.com", "senha": "nada-a-ver"})
        self.assertEqual(st, 401)
        st, _, _ = self.req("POST", "/api/auth/login", {"email": "ninguem@teste.com", "senha": "nada-a-ver"})
        self.assertEqual(st, 401)

    def test_cookie_httponly(self):
        _, h, _ = self.req("POST", "/api/auth/login", {"email": "user@teste.com", "senha": "senhauser1"})
        self.assertIn("HttpOnly", h["Set-Cookie"])
        self.assertIn("SameSite=Lax", h["Set-Cookie"])

    def test_login_libera_painel(self):
        ck = self.login("user@teste.com", "senhauser1")
        self.assertEqual(self.req("GET", "/", cookie=ck)[0], 200)
        st, _, b = self.req("GET", "/api/auth/eu", cookie=ck)
        self.assertEqual(json.loads(b)["usuario"]["email"], "user@teste.com")

    def test_logout_invalida_sessao(self):
        ck = self.login("user@teste.com", "senhauser1")
        self.req("POST", "/api/auth/logout", {}, cookie=ck)
        self.assertEqual(self.req("GET", "/api/auth/eu", cookie=ck)[0], 401)

    def test_limite_tentativas(self):
        for _ in range(auth.MAX_TENT):
            self.req("POST", "/api/auth/login", {"email": "user@teste.com", "senha": "errada!!"})
        st, _, _ = self.req("POST", "/api/auth/login", {"email": "user@teste.com", "senha": "senhauser1"})
        self.assertEqual(st, 429)

    def test_usuario_comum_nao_administra(self):
        ck = self.login("user@teste.com", "senhauser1")
        self.assertEqual(self.req("GET", "/api/usuarios", cookie=ck)[0], 403)
        self.assertEqual(self.req("GET", "/usuarios", cookie=ck)[0], 403)
        st, _, _ = self.req("POST", "/api/usuarios", {"email": "x@y.com", "senha": "12345678"}, cookie=ck)
        self.assertEqual(st, 403)

    def test_admin_cadastra_e_desativa(self):
        ck = self.login("admin@teste.com", "senhaadmin1")
        st, _, b = self.req("POST", "/api/usuarios",
                            {"email": "novo@teste.com", "nome": "Novo", "senha": "senhanova1"}, cookie=ck)
        self.assertEqual(st, 201)
        uid = json.loads(b)["usuario"]["id"]
        ck2 = self.login("novo@teste.com", "senhanova1")
        self.req("PATCH", f"/api/usuarios/{uid}", {"ativo": False}, cookie=ck)
        self.assertEqual(self.req("GET", "/api/auth/eu", cookie=ck2)[0], 401)
        self.assertEqual(self.req("DELETE", f"/api/usuarios/{uid}", {}, cookie=ck)[0], 200)

    def test_admin_nao_se_rebaixa(self):
        ck = self.login("admin@teste.com", "senhaadmin1")
        st, _, _ = self.req("PATCH", f"/api/usuarios/{self.admin['id']}", {"admin": False}, cookie=ck)
        self.assertEqual(st, 400)

    def test_trocar_senha(self):
        con = auth.conectar(); auth.criar(con, "troca@teste.com", None, "antiga123"); con.close()
        ck = self.login("troca@teste.com", "antiga123")
        st, _, _ = self.req("POST", "/api/auth/senha", {"atual": "errada99", "nova": "novasenha1"}, cookie=ck)
        self.assertEqual(st, 400)
        st, _, _ = self.req("POST", "/api/auth/senha", {"atual": "antiga123", "nova": "novasenha1"}, cookie=ck)
        self.assertEqual(st, 200)
        self.login("troca@teste.com", "novasenha1")

    def test_post_exige_json(self):
        ck = self.login("admin@teste.com", "senhaadmin1")
        st, _, _ = self.req("POST", "/api/usuarios", {"email": "a@b.com", "senha": "12345678"},
                            cookie=ck, ctype="text/plain")
        self.assertEqual(st, 403)


if __name__ == "__main__":
    unittest.main()
