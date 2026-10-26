// Bloco do usuario logado (sidebar) + troca de senha + sair
async function post(url, body){
  const r = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json"},
                              body: JSON.stringify(body || {})});
  const d = await r.json().catch(() => ({}));
  if(!r.ok) throw new Error(d.erro || ("Erro " + r.status));
  return d;
}

export async function sair(){
  try { await post("/api/auth/logout"); } finally { location.replace("/login"); }
}

export function trocarSenha(){
  const dlg = document.createElement("dialog");
  dlg.className = "modal";
  dlg.innerHTML = `
    <form method="dialog">
      <h3 style="margin:0 0 16px">Trocar senha</h3>
      <div class="field"><label>Senha atual</label><input name="atual" type="password" autocomplete="current-password" required></div>
      <div class="field"><label>Nova senha (mín. 8)</label><input name="nova" type="password" autocomplete="new-password" minlength="8" required></div>
      <div class="field"><label>Repita a nova senha</label><input name="nova2" type="password" autocomplete="new-password" minlength="8" required></div>
      <div class="auth-msg erro" data-msg></div>
      <div class="acts"><button class="btn" value="cancel" formnovalidate>Cancelar</button>
        <button class="btn primary" value="ok">Salvar</button></div>
    </form>`;
  document.body.appendChild(dlg);
  const f = dlg.querySelector("form"), msg = dlg.querySelector("[data-msg]");
  f.addEventListener("submit", async ev => {
    if(ev.submitter && ev.submitter.value === "cancel"){ return; }
    ev.preventDefault(); msg.className = "auth-msg erro"; msg.textContent = "";
    if(f.nova.value !== f.nova2.value){ msg.textContent = "As senhas não conferem."; return; }
    try {
      await post("/api/auth/senha", {atual: f.atual.value, nova: f.nova.value});
      msg.className = "auth-msg ok"; msg.textContent = "Senha alterada.";
      setTimeout(() => dlg.close(), 900);
    } catch(e){ msg.textContent = e.message; }
  });
  dlg.addEventListener("close", () => dlg.remove());
  dlg.showModal();
}

export async function montarUsuario(alvo){
  const r = await fetch("/api/auth/eu");
  if(r.status === 401){ location.replace("/login"); return null; }
  const {usuario, auth} = await r.json();
  if(!auth || !alvo) return usuario;
  const box = document.createElement("div");
  box.className = "side-user";
  const nome = document.createElement("span");
  nome.textContent = usuario.nome || usuario.email;
  nome.title = usuario.email;
  const acts = document.createElement("div");
  acts.className = "acts";
  const links = [["Senha", trocarSenha], ["Sair", sair]];
  if(usuario.admin) links.unshift(["Usuários", () => location.assign("/usuarios")]);
  for(const [txt, fn] of links){
    const a = document.createElement("a"); a.textContent = txt; a.tabIndex = 0;
    a.addEventListener("click", fn);
    a.addEventListener("keydown", e => { if(e.key === "Enter") fn(); });
    acts.appendChild(a);
  }
  box.append(nome, acts);
  alvo.prepend(box);
  return usuario;
}
