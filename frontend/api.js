// Camada de acesso a API local do Hub
// sessao expirada -> volta para o login
const fetch = (url, opts) => window.fetch(url, opts).then(r => {
  if(r.status === 401) location.replace("/login");
  return r;
});
let _anomes = null;
export function setAnomes(a){ _anomes = a; }
function qs(extra={}){
  const p = new URLSearchParams();
  if(_anomes) p.set("anomes", _anomes);
  for(const[k,v] of Object.entries(extra)) if(v!=null) p.set(k,v);
  const s = p.toString(); return s?("?"+s):"";
}
async function get(path, extra){
  const r = await fetch(path+qs(extra));
  if(!r.ok) throw new Error("HTTP "+r.status);
  return r.json();
}
export const api = {
  meta:        ()    => fetch("/api/meta").then(r=>r.json()),
  panorama:    ()    => get("/api/panorama"),
  registro:    ()    => get("/api/registro"),
  prudencial:  ()    => get("/api/prudencial/overview"),
  pagamentos:  ()    => fetch("/api/pagamentos").then(r=>r.json()),
  instituicao: (cod) => get("/api/instituicao/"+encodeURIComponent(cod)),
  cnpj:        (c8)  => fetch("/api/cnpj/"+encodeURIComponent(c8)).then(r=>r.json()),
  fontes:      ()    => fetch("/api/fontes").then(r=>r.json()),
  conduta:     ()    => fetch("/api/conduta").then(r=>r.json()),
  macro:       ()    => fetch("/api/macro").then(r=>r.json()),
  credito:     ()    => fetch("/api/credito").then(r=>r.json()),
  scr:         ()    => fetch("/api/scr").then(r=>r.json()),
  tarifas:     ()    => fetch("/api/tarifas").then(r=>r.json()),
  taxasModalidades: () => fetch("/api/taxas-modalidades").then(r=>r.json()),
  participacao:()    => fetch("/api/participacao").then(r=>r.json()),
  supervisao:  ()    => fetch("/api/supervisao").then(r=>r.json()),
  eventos:     ()    => fetch("/api/eventos").then(r=>r.json()),
  tarifasGrupo:(cod) => fetch("/api/tarifas/grupo/"+encodeURIComponent(cod)).then(r=>r.json()),
  tarifasIf:   (c8)  => fetch("/api/tarifas/if/"+encodeURIComponent(c8)).then(r=>r.json()),
};
