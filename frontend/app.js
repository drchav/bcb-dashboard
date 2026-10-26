import { api, setAnomes } from "./api.js";
import { montarUsuario } from "./conta.js";
import * as C from "./charts.js";
import {
  SEGS, SEG_COR, SEG_DESC, TC_LBL, GRUPO_COR, grupoCor,
  fmtR$, fmtPct, fmtInt, fmtNum, nomeLimpo, anomesLabel, el
} from "./util.js";

const content = document.getElementById("content");
const crumbs  = document.getElementById("crumbs");
const estado = { meta:null, anomes:null, registro:null, panorama:null, prudencial:null, pagamentos:null, fontes:null };

init();
async function init(){
  montarUsuario(document.querySelector(".side-foot"));
  estado.meta = await api.meta();
  const sel = document.getElementById("anomesSel");
  sel.innerHTML = estado.meta.anomes_disponiveis.map(a=>`<option value="${a}">${anomesLabel(a)}</option>`).join("");
  estado.anomes = estado.meta.anomes_disponiveis[0];
  setAnomes(estado.anomes); sel.value = estado.anomes;
  sel.onchange = ()=>{ estado.anomes=sel.value; setAnomes(estado.anomes);
    estado.registro=estado.panorama=estado.prudencial=null; route(); };
  document.getElementById("sideMeta").innerHTML =
    `Data-base <b>${anomesLabel(estado.anomes)}</b><br>`+
    `<b>${fmtInt(estado.meta.total_cadastro)}</b> instituições · <b>${estado.meta.total_rsfn}</b> na RSFN<br>`+
    `Atualizado: ${(estado.meta.ultima_atualizacao||"").replace("T"," ").slice(0,16)}`;
  setupBusca();
  setupMenuMobile();
  posicionarTip();
  window.addEventListener("hashchange", route);
  document.addEventListener("keydown", e=>{ if(e.key==="Escape") fecharModal(); });
  if(!location.hash) location.hash="#/panorama";
  route();
}

async function getRegistro(){
  if(estado.registro) return estado.registro;
  estado.registro = (await api.registro()).itens;
  return estado.registro;
}

function route(){
  const h=(location.hash||"#/panorama").slice(2);
  const [view,arg]=h.split("/");
  if(view==="instituicao" && arg){ abrirModal(arg); return; }   // deep-link
  const ovAberto=document.querySelector(".modal-overlay");
  if(ovAberto){ ovAberto.classList.remove("open"); setTimeout(()=>ovAberto.remove(),180); }
  document.querySelectorAll("#nav a").forEach(a=>a.classList.toggle("active",a.dataset.view===view));
  content.innerHTML='<div class="loading">Carregando…</div>';
  const views={ panorama:viewPanorama, instituicoes:()=>viewInstituicoes(),
    pagamentos:viewPagamentos, prudencial:viewPrudencial, fontes:viewFontes,
    cooperativismo:()=>viewInstituicoes("Cooperativas"),
    conduta:viewConduta, macro:viewMacro,
    credito:viewCredito, supervisao:viewSupervisao, tarifas:viewTarifas,
  };
  (views[view]||viewPanorama)();
}

// ================================================================ PANORAMA
async function viewPanorama(){
  crumbs.textContent="Panorama do Sistema Financeiro Nacional";
  const p = estado.panorama || (estado.panorama = await api.panorama());
  const pg = estado.pagamentos || (estado.pagamentos = await api.pagamentos());
  content.innerHTML="";
  const pixDia = p.pix_dia;
  content.append(
    kpiRow([
      ["Instituições (individuais)", fmtInt(p.total_instituicoes), "autorizadas e em atividade",
        "Contagem de instituições individuais (não conglomerados) com cadastro ativo no IF.data do BCB na data-base selecionada. Conglomerados são excluídos para não contar a mesma instituição duas vezes."],
      ["Ativo Total do SFN", fmtR$(p.ativo_total), anomesLabel(p.anomes),
        "Soma do Ativo Total de todas as instituições que reportam balanço na consolidação prudencial do IF.data, na data-base selecionada."],
      ["Carteira de Crédito", fmtR$(p.credito_total), "",
        "Soma do saldo da carteira de crédito reportada no balanço (IF.data) de todas as instituições na data-base. Difere do crédito agregado do SGS (metodologias distintas)."],
      ["Participantes da RSFN", fmtInt(p.rsfn_total), "conexão direta (STR)",
        "Número de participantes do STR (Sistema de Transferência de Reservas), onde roda a TED — lista oficial ParticipantesSTR.csv do BCB. É a porta de entrada direta na Rede do SFN (RSFN)."],
      ["PIX — último dia", pixDia?fmtInt(pixDia.quantidade):"–", pixDia?("R$ "+fmtNum(pixDia.total,0)+" mi · "+pixDia.data):"",
        "Quantidade de transações PIX liquidadas no SPI no último dia disponível na API de estatísticas do PIX (Olinda/BCB), com o valor financeiro total em R$ milhões."],
    ]),
    secTitle("Composição do sistema por tipo de instituição",
      "Como as instituições se distribuem por tipo. O 'grupo' agrega os tipos regulatórios (bancos, cooperativas, crédito não-bancário, mercado de capitais, consórcios, pagamentos). Fonte: cadastro do IF.data."),
    grid("g-2",
      card(h3i("Instituições por grupo","Agrupamento macro dos tipos de instituição, derivado do tipo de consolidado bancário (TCB) e da natureza da instituição no cadastro do BCB."), el("div",{class:"csub"},"Hierarquia de tipos"), el("div",{class:"chart",id:"cGrupo"})),
      card(h3i("Instituições por tipo detalhado","Tipo de Consolidado Bancário (TCB) do BCB: B1 (banco comercial/múltiplo com carteira comercial), B2, B3S/B3C (cooperativas), B4 (desenvolvimento), N1–N4 (não-bancárias, capitais, consórcio, pagamento)."), el("div",{class:"csub"},"Consolidado bancário (TCB)"), el("div",{class:"chart",id:"cTipo"})),
    ),
    secTitle("Distribuição geográfica e por controle",
      "UF = unidade da federação da sede da instituição (cadastro). Controle acionário classifica a origem do capital: Público, Privado Nacional ou Estrangeiro."),
    grid("g-2",
      card(h3i("Por estado (UF)","Quantidade de instituições por UF da sede. Reflete onde está o CNPJ matriz, não a área de atuação."), el("div",{class:"chart",id:"cUf"})),
      card(h3i("Por controle acionário","Origem do capital de controle, conforme o tipo de controle (TC) do cadastro do BCB: Público, Privado Nacional ou Estrangeiro."), el("div",{class:"chart sm",id:"cCtrl"})),
    ),
    secTitle("Pagamentos instantâneos (PIX)",
      "Série diária da quantidade de transações PIX liquidadas no SPI (Sistema de Pagamentos Instantâneos), da API de estatísticas do PIX do BCB."),
    card(h3i("PIX liquidados no SPI — evolução diária","Cada ponto é o total de transações PIX liquidadas no SPI naquele dia. O recorde (pico) é destacado no subtítulo."),
         el("div",{class:"csub"}, p.pix_pico?("recorde: "+fmtInt(p.pix_pico.quantidade)+" transações em "+p.pix_pico.data):""),
         el("div",{class:"chart lg",id:"cPix"})),
  );
  C.barH(byId("cGrupo"), p.por_grupo.map(x=>({label:x.k,v:x.n,cor:grupoCor(x.k)})),{money:false});
  C.barH(byId("cTipo"), p.por_tipo.slice(0,10).map(x=>({label:x.k,v:x.n,cor:"#4f93f0"})),{money:false});
  C.barH(byId("cUf"), p.por_uf.slice(0,12).map(x=>({label:x.k,v:x.n,cor:"#4f93f0"})),{money:false});
  C.barH(byId("cCtrl"), p.por_controle.map(x=>({label:x.k,v:x.n,cor:"#1fb286"})),{money:false});
  C.linhas(byId("cPix"), [{nome:"PIX/dia",pontos:pg.pix_serie.map(d=>({x:d.data,y:d.quantidade}))}]);
}

// ================================================================ INSTITUIÇÕES
const COLS_REG = [
  {k:"nome",label:"Instituição",t:"name",l:true,tip:"Nome da instituição no cadastro do BCB. Abaixo, o tipo detalhado e a cidade da sede. Clique na linha para abrir o perfil completo."},
  {k:"grupo",label:"Grupo",t:"grupo",l:true,tip:"Grupo macro do tipo de instituição (bancos, cooperativas, crédito não-bancário, mercado de capitais, consórcios, pagamentos), derivado do consolidado bancário."},
  {k:"uf",label:"UF",t:"txt",l:true,tip:"Unidade da federação da sede (CNPJ matriz), conforme o cadastro."},
  {k:"controle",label:"Controle",t:"txt",l:true,tip:"Controle acionário: Público, Privado Nacional ou Estrangeiro (tipo de controle do BCB)."},
  {k:"situacao",label:"Situação",t:"txt",l:true,tip:"Situação cadastral no BCB. 'Ativa' = autorizada e em funcionamento."},
  {k:"rsfn",label:"Arranjos",t:"rsfn",l:true,tip:"Em quais arranjos a instituição participa: PIX (arranjo de pagamentos instantâneos), STR (TED, com o código COMPE quando houver), RSFN↗ (conexão física direta à rede do SFN) e COMPE (compensação). Passe o mouse em cada etiqueta."},
  {k:"part_spi",label:"SPI / Autoriz.",t:"partspi",l:true,tip:"Da Lista de participantes do Pix (BCB): participação no SPI — Direta (liquida direto no Sistema de Pagamentos Instantâneos) ou Indireta (via um liquidante) — e a situação de autorização: Autorizada pelo BCB, Não sujeita a autorização (IP de propósito limitado), ou Sujeita mas ainda não autorizada (em adesão). Em branco = fora da lista do Pix."},
  {k:"ativo",label:"Ativo Total",t:"r$",tip:"Ativo Total do balanço na consolidação prudencial (IF.data), na data-base selecionada. Vazio quando a instituição não reporta balanço."},
  {k:"pl",label:"Patrim. Líq.",t:"r$",tip:"Patrimônio Líquido do balanço (IF.data) na data-base selecionada."},
  {k:"lucro",label:"Lucro Líq.",t:"r$",sign:true,tip:"Lucro (positivo, verde) ou prejuízo (negativo, vermelho) líquido do período, do IF.data."},
  {k:"roe",label:"ROE",t:"pct",tip:"Retorno sobre o Patrimônio Líquido = Lucro Líquido ÷ Patrimônio Líquido. Mede a rentabilidade do capital próprio."},
  {k:"basileia",label:"Basileia",t:"pct",tip:"Índice de Basileia = capital regulatório ÷ ativos ponderados pelo risco. Mínimo exigido de 8%. Quanto maior, mais capitalizada é a instituição."},
  {k:"seg",label:"Seg",t:"seg",l:true,tip:"Segmentação prudencial S1–S5 (Resolução CMN 4.553/2017), por porte e complexidade. S1 = maiores bancos; S5 = perfil simplificado. É só um atributo, não a organização do sistema."},
];
const fReg = { q:"", grupos:new Set(), uf:"", controle:"", situacao:"", td:"Individual", rsfn:"", fin:"", seg:"", pix:"", direto:"", partspi:"", autoriz:"" };
let ordReg = { k:"ativo", dir:-1 };

async function viewInstituicoes(presetGrupo){
  crumbs.textContent = presetGrupo? ("Instituições · "+presetGrupo) : "Instituições — registro central";
  const itens = await getRegistro();
  if(presetGrupo){ fReg.grupos=new Set([presetGrupo]); }
  const grupos=[...new Set(itens.map(i=>i.grupo))];
  const ufs=[...new Set(itens.map(i=>i.uf).filter(Boolean))].sort();

  content.innerHTML="";
  const bar=el("div",{class:"filterbar"});
  const busca=el("input",{type:"search",placeholder:"Buscar nome / cidade / CNPJ…",value:fReg.q,
    oninput:e=>{fReg.q=e.target.value.toLowerCase();desenha();}});
  const chips=el("div",{class:"chips"}, grupos.map(g=>{
    const c=el("div",{class:"chip"+(fReg.grupos.has(g)?" on":"")},el("span",{class:"dot"}),g);
    c.style.setProperty("--c",grupoCor(g));
    c.onclick=()=>{fReg.grupos.has(g)?fReg.grupos.delete(g):fReg.grupos.add(g);c.classList.toggle("on");desenha();};
    return c;
  }));
  const mkSel=(opts,cur,on,first)=>el("select",{onchange:e=>{on(e.target.value);desenha();}},
    first?el("option",{value:""},first):null,
    opts.map(o=>{const v=typeof o==="object"?o.v:o,lab=typeof o==="object"?o.l:o;
      return el("option",{value:v,selected:String(cur)===String(v)?"":null},lab);}));
  const tdSel=mkSel([{v:"Individual",l:"Só individuais"},{v:"Conglomerado",l:"Só conglomerados"},{v:"",l:"Todos (ind.+cong.)"}],fReg.td,v=>fReg.td=v,null);
  const segSel=mkSel(SEGS,fReg.seg,v=>fReg.seg=v,"Todos segmentos");
  const ufSel=mkSel(ufs,fReg.uf,v=>fReg.uf=v,"Todas UF");
  const ctrlSel=mkSel(["Público","Privado Nacional","Estrangeiro"],fReg.controle,v=>fReg.controle=v,"Todos controles");
  const sitSel=mkSel(["Ativa"],fReg.situacao,v=>fReg.situacao=v,"Todas situações");
  const pixSel=mkSel([{v:"sim",l:"Só participantes PIX"},{v:"nao",l:"Fora do PIX"}],fReg.pix,v=>fReg.pix=v,"PIX: todas");
  const rsfnSel=mkSel([{v:"sim",l:"Só no STR/TED (RSFN)"},{v:"nao",l:"Fora do STR/TED"}],fReg.rsfn,v=>fReg.rsfn=v,"STR/TED: todas");
  const diretoSel=mkSel([{v:"sim",l:"Só conexão RSFN direta"},{v:"nao",l:"Sem conexão direta"}],fReg.direto,v=>fReg.direto=v,"RSFN direto: todas");
  const partspiSel=mkSel([{v:"Direta",l:"SPI: só diretas"},{v:"Indireta",l:"SPI: só indiretas"}],fReg.partspi,v=>fReg.partspi=v,"SPI: todas");
  const autorizSel=mkSel([{v:"autorizada",l:"Autorizadas pelo BCB"},{v:"nao_sujeita",l:"Não sujeitas a autorização"},{v:"nao_autorizada",l:"Sujeitas, não autorizadas"},{v:"lista",l:"Na lista do Pix"}],fReg.autoriz,v=>fReg.autoriz=v,"Autorização: todas");
  const finSel=mkSel([{v:"sim",l:"Com balanço (IF.data)"}],fReg.fin,v=>fReg.fin=v,"Dados financ.: todos");
  const limpar=el("button",{class:"btn",onclick:()=>{Object.assign(fReg,{q:"",grupos:new Set(),uf:"",controle:"",situacao:"",td:"Individual",rsfn:"",fin:"",seg:"",pix:"",direto:"",partspi:"",autoriz:""});viewInstituicoes();}},"Limpar");
  const fcount=el("span",{class:"fcount",id:"fcountR"});
  bar.append(
    withInfo(busca,"Busca livre por nome da instituição, cidade da sede, CNPJ ou UF. Filtra a tabela em tempo real."),
    withInfo(chips,"Clique nos grupos para incluir/excluir tipos de instituição (bancos, cooperativas, etc.). Sem nenhum selecionado = todos os grupos."),
    el("div",{class:"fsep"}),
    withInfo(tdSel,"Individual = cada instituição isolada. Conglomerado = o grupo econômico consolidado. Por padrão mostramos só individuais para não contar em duplicidade."),
    withInfo(segSel,"Filtra pela segmentação prudencial S1–S5 (Res. CMN 4.553/2017). Só instituições que reportam balanço têm segmento."),
    withInfo(ufSel,"Filtra pela UF da sede (CNPJ matriz)."),
    withInfo(ctrlSel,"Filtra pela origem do capital de controle: Público, Privado Nacional ou Estrangeiro."),
    withInfo(sitSel,"Filtra pela situação cadastral no BCB."),
    withInfo(pixSel,"Participa ou não do arranjo PIX (cruzamento por ISPB com o diretório de participantes do PIX)."),
    withInfo(rsfnSel,"Participa ou não do STR/TED — o Sistema de Transferência de Reservas, onde a TED é liquidada (lista ParticipantesSTR.csv)."),
    withInfo(diretoSel,"Conexão física direta à Rede do SFN (acesso tipo 'RSFN'), diferente de quem acessa de forma indireta por um liquidante."),
    withInfo(partspiSel,"Participação no SPI (Sistema de Pagamentos Instantâneos): Direta = liquida diretamente; Indireta = liquida por meio de um participante direto. Da Lista de participantes do Pix (BCB)."),
    withInfo(autorizSel,"Situação de autorização (Lista de participantes do Pix): Autorizadas pelo BCB; Não sujeitas a autorização (IPs de propósito limitado); Sujeitas mas ainda não autorizadas (em adesão); ou todas as que estão na lista do Pix."),
    withInfo(finSel,"Só instituições com balanço publicado no IF.data (muitas de pagamento, consórcio e corretoras não reportam)."),
    limpar,fcount);
  recolhivel(bar);

  const wrap=el("div",{class:"tablewrap"});
  const table=el("table"); table.append(el("thead"),el("tbody"));
  wrap.append(table); content.append(bar,wrap);

  function filtra(){
    return itens.filter(i=>{
      if(fReg.td && i.td!==fReg.td) return false;
      if(fReg.grupos.size && !fReg.grupos.has(i.grupo)) return false;
      if(fReg.seg && i.seg!==fReg.seg) return false;
      if(fReg.uf && i.uf!==fReg.uf) return false;
      if(fReg.controle && i.controle!==fReg.controle) return false;
      if(fReg.situacao && i.situacao!==fReg.situacao) return false;
      if(fReg.rsfn==="sim" && !i.rsfn) return false;
      if(fReg.rsfn==="nao" && i.rsfn) return false;
      if(fReg.pix==="sim" && !i.pix) return false;
      if(fReg.pix==="nao" && i.pix) return false;
      if(fReg.direto==="sim" && !i.rsfn_direto) return false;
      if(fReg.direto==="nao" && i.rsfn_direto) return false;
      if(fReg.partspi){ if(!i.part_spi) return false;
        const dir=/^Dir/i.test(i.part_spi); if((fReg.partspi==="Direta")!==dir) return false; }
      if(fReg.autoriz){ if(fReg.autoriz==="lista"){ if(!i.no_pix_lista) return false; }
        else if(i.autoriz!==fReg.autoriz) return false; }
      if(fReg.fin==="sim" && !i.tem_financas) return false;
      if(fReg.q){ const hay=((i.nome||"")+" "+(i.municipio||"")+" "+(i.cnpj||"")+" "+(i.uf||"")).toLowerCase();
        if(!hay.includes(fReg.q)) return false; }
      return true;
    });
  }
  function desenha(){
    const rows=filtra();
    rows.sort((a,b)=>cmp(a[ordReg.k],b[ordReg.k])*ordReg.dir);
    const thead=table.querySelector("thead"); thead.innerHTML="";
    const tr=el("tr");
    COLS_REG.forEach(c=> tr.append(el("th",{class:c.l?"l":"",onclick:()=>{
      if(ordReg.k===c.k) ordReg.dir*=-1; else {ordReg.k=c.k;ordReg.dir=(["txt","name","grupo"].includes(c.t))?1:-1;} desenha();}},
      c.label+(ordReg.k===c.k?` ${ordReg.dir<0?"▼":"▲"}`:""), info(c.tip,"down"))));
    thead.append(tr);
    const tb=table.querySelector("tbody"); tb.innerHTML="";
    const frag=document.createDocumentFragment();
    rows.slice(0,1200).forEach(i=>frag.append(linhaReg(i)));
    tb.append(frag);
    byId("fcountR").textContent = `${fmtInt(rows.length)} instituições`+(rows.length>1200?" · exibindo 1200":"");
  }
  desenha();
}

function miniChip(txt,cor,title){
  const c=el("span",{class:"mini-chip",title:title||txt},txt);
  c.style.cssText="display:inline-block;font-size:10px;font-weight:600;padding:1px 6px;margin:1px 3px 1px 0;border-radius:4px;border:1px solid "+cor+";color:"+cor;
  return c;
}
function chipsArranjo(i){
  const wrap=el("span",{});
  if(i.pix) wrap.append(miniChip("PIX","var(--pos)","Participa do arranjo PIX"));
  if(i.rsfn) wrap.append(miniChip("STR"+(i.compe_cod?(" "+i.compe_cod):""),"#3987e5","No STR/TED (RSFN) · acesso "+(i.acesso||"")));
  if(i.rsfn_direto) wrap.append(miniChip("RSFN↗","#b07cff","Conexão direta à RSFN"));
  if(i.compe) wrap.append(miniChip("COMPE","var(--warn)","Participa da COMPE (compensação)"));
  if(!wrap.childNodes.length) wrap.append(el("span",{style:"color:var(--ink-3)"},"—"));
  return wrap;
}
const AUTORIZ_LBL={autorizada:["Autorizada","var(--pos)","Autorizada a funcionar pelo BCB"],
  nao_autorizada:["Não autoriz.","var(--warn)","Sujeita à autorização, ainda não autorizada (em adesão)"],
  nao_sujeita:["Não sujeita","var(--ink-3)","Instituição de pagamento não sujeita ao processo de autorização do BCB"]};
function chipsPartSpi(i){
  if(!i.no_pix_lista) return el("span",{style:"color:var(--ink-3)"},"—");
  const wrap=el("span",{});
  if(i.part_spi){ const dir=/^Dir/i.test(i.part_spi);
    wrap.append(miniChip("SPI "+(dir?"direta":"indireta"), dir?"#3987e5":"var(--ink-3)",
      dir?"Participante direto do SPI (liquida direto no Sistema de Pagamentos Instantâneos)":"Participante indireto do SPI (liquida por meio de um participante direto)")); }
  const a=AUTORIZ_LBL[i.autoriz]; if(a) wrap.append(miniChip(a[0],a[1],a[2]));
  if(!wrap.childNodes.length) wrap.append(el("span",{style:"color:var(--ink-3)"},"—"));
  return wrap;
}
function linhaReg(i){
  const tr=el("tr",{onclick:()=>abrirModal(i.cod)});
  COLS_REG.forEach(c=>{
    const v=i[c.k]; let node;
    if(c.t==="name") node=el("td",{class:"l"}, el("div",{class:"name-cell"},
        el("div",{},nomeLimpo(i.nome)), el("div",{class:"sub"},[i.tipo_desc,i.municipio].filter(Boolean).join(" · "))));
    else if(c.t==="grupo"){ const b=el("span",{class:"pill"},i.grupo); b.style.borderColor=grupoCor(i.grupo); b.style.color=grupoCor(i.grupo); node=el("td",{class:"l"},b); }
    else if(c.t==="seg") node=el("td",{class:"l"}, i.tem_financas?segBadge(i.seg):"–");
    else if(c.t==="rsfn") node=el("td",{class:"l"}, chipsArranjo(i));
    else if(c.t==="partspi") node=el("td",{class:"l"}, chipsPartSpi(i));
    else if(c.t==="txt") node=el("td",{class:"l"}, v||"–");
    else { const txt=c.t==="pct"?fmtPct(v):fmtR$(v); const cls=c.sign&&v!=null?(v<0?"neg":"pos"):"";
      node=el("td",{class:"num "+cls}, txt); }
    tr.append(node);
  });
  return tr;
}

// ================================================================ MODAL da instituição
let _modalCache = {};
async function abrirModal(cod){
  const ov=el("div",{class:"modal-overlay",onclick:e=>{if(e.target===ov)fecharModal();}});
  const modal=el("div",{class:"modal"});
  ov.append(modal); document.body.append(ov);
  requestAnimationFrame(()=>ov.classList.add("open"));
  modal.innerHTML='<div class="loading">Carregando instituição…</div>';
  const d = _modalCache[cod] || (_modalCache[cod] = await api.instituicao(cod));
  if(d.erro){ modal.innerHTML='<div class="empty">Instituição não encontrada.</div>'; return; }
  renderModal(modal, d);
}
function fecharModal(){
  const ov=document.querySelector(".modal-overlay");
  if(!ov) return;
  ov.classList.remove("open");
  setTimeout(()=>ov.remove(),180);
  if(location.hash.startsWith("#/instituicao/")) history.replaceState(null,"",location.pathname+"#/instituicoes");
}

function renderModal(modal, d){
  const c=d.cadastro;
  const kv=k=>{ const a=d.historico[k]; return a&&a.length?a[a.length-1].valor:null; };
  const temFin=Object.keys(d.relatorios).length>0;
  modal.innerHTML="";
  const head=el("div",{class:"modal-head"},
    el("button",{class:"close",onclick:fecharModal,title:"Fechar (Esc)"},"✕"),
    el("h2",{},nomeLimpo(c.nome)),
    el("div",{class:"modal-tags"},
      temFin?segTag(d.seg):null,
      tag(d.grupo, grupoCor(d.grupo)),
      tag(d.controle), tag((c.municipio||"")+" / "+(c.uf||"")),
      d.pix_participa?tag("PIX ✓","var(--pos)"):null,
      d.rsfn?tag("STR/TED ✓"+(d.rsfn.codigo?(" ·"+d.rsfn.codigo):""),"#3987e5"):null,
      d.rsfn&&d.rsfn.direto?tag("RSFN direto","#b07cff"):null,
      (d.pix_lista&&d.pix_lista.part_spi)?tag("SPI "+(/^Dir/i.test(d.pix_lista.part_spi)?"direto":"indireto"),"#2bb3c0"):null,
      d.pix_lista?(a=>a?tag(a[0],a[1]):null)(AUTORIZ_LBL[d.pix_lista.autoriz]):null,
      d.regime?tag(d.regime.tipo||"REGIME ESPECIAL","var(--neg)"):null,
      (d.penalidades&&d.penalidades.length)?tag(d.penalidades.length+" penalidade"+(d.penalidades.length>1?"s":""),"var(--warn)"):null,
      tag(c.situacao==="A"?"Ativa":(c.situacao||"?"), c.situacao==="A"?"var(--pos)":"var(--warn)"),
    ));
  const tabsEl=el("div",{class:"modal-tabs"});
  const body=el("div",{class:"modal-body"});
  modal.append(head,tabsEl,body);

  const abas=[
    ["Visão geral & Financeiro", ()=>abaFinanceiro(body,d,kv,temFin)],
    ["Identificação (CNPJ)", ()=>abaCnpj(body,d)],
    ["Taxas de juros", ()=>abaTaxas(body,d)],
    ["Tarifas de serviços", ()=>abaTarifasServico(body,d)],
    ["Fontes & Links", ()=>abaFontes(body,d)],
  ];
  abas.forEach(([nome,fn],ix)=>{
    const b=el("button",{class:ix===0?"on":"",onclick:()=>{
      [...tabsEl.children].forEach(x=>x.classList.remove("on")); b.classList.add("on"); fn();}},nome);
    tabsEl.append(b);
  });
  abas[0][1]();
}

function cardReclamacoes(d){
  const r=d.reclamacoes; if(!r) return null;
  const pct = r.reclamacoes? r.procedentes/r.reclamacoes : null;
  const card=el("div",{class:"card",style:"margin-bottom:16px"},
    el("h3",{},"Reclamações (ranking BCB)",
      info("Ranking trimestral de reclamações do BCB. O índice pondera as reclamações procedentes pela quantidade de clientes, para comparar instituições de portes diferentes — quanto maior, pior.","down"),
      r.periodo?el("span",{class:"muted",style:"font-weight:400;font-size:12px"},"  · "+r.periodo):""),
    el("div",{class:"deflist",style:"margin-top:10px"},
      defI("Índice", r.indice!=null?fmtNum(r.indice,2):"—","Índice de reclamações = (reclamações procedentes ÷ nº de clientes) × 1.000.000, no trimestre. Só instituições do 'Top 15' recebem índice; as demais aparecem só com as quantidades."),
      defI("Reclamações respondidas", fmtInt(r.reclamacoes),"Total de reclamações registradas contra a instituição e respondidas no trimestre."),
      defI("Procedentes", fmtInt(r.procedentes)+(pct!=null?` (${fmtNum(pct*100,0)}%)`:""),"Reclamações em que o BCB deu razão ao cliente (descumprimento de norma). O percentual é procedentes ÷ reclamações respondidas."),
      defI("Analisadas", fmtInt(r.analisadas),"Reclamações efetivamente analisadas pelo BCB no período."),
      defI("Clientes (CCS+SCR)", fmtInt(r.clientes),"Base de clientes usada no denominador do índice, estimada por CCS (Cadastro de Clientes do SFN) e SCR (Sistema de Informações de Crédito).")));
  // evolucao do indice por trimestre
  const hist=(r.historia||[]).filter(h=>h.indice!=null);
  if(hist.length>1){
    const row=el("div",{style:"margin-top:12px"});
    row.append(el("div",{class:"dk",style:"margin-bottom:4px"},"Evolução do índice ("+hist[0].periodo+" → "+hist[hist.length-1].periodo+")"),
      sparkline(hist.map(h=>h.indice),{w:220,h:34,cor:"var(--warn)"}),
      el("div",{style:"display:flex;justify-content:space-between;font-size:11px;color:var(--ink-3);margin-top:2px"},
        el("span",{},fmtNum(hist[0].indice,1)), el("span",{},fmtNum(hist[hist.length-1].indice,1))));
    card.append(row);
  }
  card.append(el("p",{class:"csub",style:"margin-top:10px"},"Fonte: ",
    htmlLink("https://www.bcb.gov.br/estabilidadefinanceira/rankingreclamacoes","BCB — Ranking de reclamações")));
  return card;
}
function def(k,v){ return el("div",{class:"def"}, el("div",{class:"dk"},k), el("div",{class:"dv"}, v==null?"—":v)); }
function defI(k,v,tip){ return el("div",{class:"def"}, el("div",{class:"dk"},k,info(tip)), el("div",{class:"dv"}, v==null?"—":v)); }

function cardSupervisao(d){
  if(!d.regime && !(d.penalidades&&d.penalidades.length)) return null;
  const card=el("div",{class:"card",style:"margin-bottom:16px;border-color:var(--warn)"});
  card.append(el("h3",{},"⚖ Supervisão & eventos",
    info("Alertas de supervisão sobre esta instituição: regime especial (liquidação, intervenção ou RAET decretados pelo BCB) e penalidades do processo administrativo sancionador. Só aparece quando há algum registro.","down")));
  if(d.regime){
    card.append(el("div",{style:"margin-top:8px;color:var(--neg);font-weight:600"},
      (d.regime.tipo||"Regime especial")+(d.regime.inicio?(" · desde "+d.regime.inicio):"")));
    if(d.regime.responsavel) card.append(el("div",{class:"csub"},"Responsável: "+d.regime.responsavel));
  }
  const pen=d.penalidades||[];
  if(pen.length){
    const soma=pen.reduce((s,p)=>s+(p.valor_multa||0),0);
    card.append(el("div",{style:"margin-top:8px"},
      el("b",{},fmtInt(pen.length)+" penalidade"+(pen.length>1?"s":"")+" no processo sancionador"),
      soma?el("span",{class:"csub"},"  ·  total em multas: "+fmtR$(soma)):null));
    const ult=pen[0];
    if(ult) card.append(el("div",{class:"csub"},"Mais recente: "+(ult.tipo_penalidade||"—")+
      (ult.data_decisao?(" ("+ult.data_decisao+")"):"")+(ult.situacao?(" — "+ult.situacao):"")));
  }
  card.append(el("p",{class:"csub",style:"margin-top:10px"},"Fontes: ",
    htmlLink("https://www.bcb.gov.br/estabilidadefinanceira/regimesespeciais","Regimes especiais"),
    " · ", htmlLink("https://www.bcb.gov.br/acessoinformacao/processadministrativosancionador","Processo sancionador")));
  return card;
}
function cardPagamentos(d){
  const p=d.pix_lista; if(!p) return null;
  const a=AUTORIZ_LBL[p.autoriz];
  const card=el("div",{class:"card",style:"margin-bottom:16px"},
    el("h3",{},"Participação em pagamentos (Lista do Pix)",
      info("Atributos da Lista de participantes ativos do Pix do BCB"+(p.pix_lista_data?(" — base "+p.pix_lista_data):"")+". Cruzada por CNPJ raiz.","down")),
    el("div",{class:"deflist",style:"margin-top:10px"},
      defI("Participação no SPI", p.part_spi||"—","Direta = liquida diretamente no SPI; Indireta = liquida por meio de um participante direto."),
      defI("Autorização", a?a[0]:"—", a?a[2]:""),
      defI("Tipo de instituição (BCB)", p.tipo_inst||"—","Classificação da instituição na lista do Pix (ex.: Instituição de Pagamento, Sociedade de Crédito Direto, Cooperativa…)."),
      defI("Modalidade no Pix", p.modalidade||"—","Papel no Pix: Provedor de Conta Transacional (oferece conta/Pix ao usuário), Iniciador (ITP), Liquidante Especial ou Ente Governamental."),
      defI("Participação no Pix", p.part_pix||"—","Obrigatória (instituições com mais de 500 mil contas ativas) ou Facultativa."),
      defI("Iniciador de pagamento (ITP)", p.iniciador?"Sim":"Não","Se oferece Iniciação de Transação de Pagamento (ex.: Pix por terceiro/open finance)."),
      defI("Situação", p.situacao||"—","Ativo em operação, ou etapa do processo de adesão (ex.: Etapa Homologatória).")));
  card.append(el("p",{class:"csub",style:"margin-top:10px"},"Fonte: ",
    htmlLink("https://www.bcb.gov.br/estabilidadefinanceira/participantespix","BCB — Lista de participantes do Pix")));
  return card;
}
function abaFinanceiro(body,d,kv,temFin){
  body.innerHTML="";
  const sup=cardSupervisao(d); if(sup) body.append(sup);
  const pag=cardPagamentos(d); if(pag) body.append(pag);
  const recl=cardReclamacoes(d); if(recl) body.append(recl);
  if(!temFin){
    body.append(el("div",{class:"card"},el("h3",{},"Sem demonstrativos no IF.data"),
      el("p",{style:"color:var(--ink-2);line-height:1.6"},"Esta instituição não reporta balanço na consolidação prudencial (comum em instituições de pagamento, consórcios, corretoras e algumas individuais). Veja a aba Identificação (CNPJ) para os dados cadastrais completos.")));
    return;
  }
  const ativo=kv("ativo"),pl=kv("pl"),lucro=kv("lucro");
  const roe=(pl&&lucro!=null)?lucro/pl:null;
  body.append(kpiRow([
    ["Ativo Total",fmtR$(ativo),"","Total de bens e direitos no balanço (IF.data), na data-base mais recente desta instituição."],
    ["Patrimônio Líquido",fmtR$(pl),"","Capital próprio = ativos menos passivos (IF.data)."],
    ["Lucro Líquido",fmtR$(lucro),"no período","Resultado líquido do período reportado no IF.data."],
    ["ROE",fmtPct(roe),"lucro / PL","Retorno sobre o Patrimônio Líquido = Lucro Líquido ÷ Patrimônio Líquido. Rentabilidade do capital próprio."],
    ["Basileia",fmtPct(kv("basileia")),"mín. 8%","Índice de Basileia = capital regulatório ÷ ativos ponderados pelo risco. Exigência mínima de 8%."],
    ["Crédito",fmtR$(kv("credito")),"","Saldo da carteira de crédito no balanço (IF.data)."],
  ]));
  body.append(secTitle("Séries históricas","Evolução das métricas ao longo das data-bases disponíveis no IF.data (normalmente trimestral)."),
    grid("g-2", card(h3i("Ativo Total","Evolução do Ativo Total por data-base (IF.data)."),el("div",{class:"chart sm",id:"mAtivo"})),
                card(h3i("Índice de Basileia","Evolução do Índice de Basileia. A linha de 8% é o mínimo regulatório."),el("div",{class:"chart sm",id:"mBas"}))),
    grid("g-2", card(h3i("Lucro Líquido","Evolução do resultado líquido por data-base."),el("div",{class:"chart sm",id:"mLucro"})),
                card(h3i("Patrimônio Líquido","Evolução do capital próprio por data-base."),el("div",{class:"chart sm",id:"mPl"}))),
    secTitle("Demonstrativos detalhados","Contas do balanço e da demonstração de resultado reportadas ao BCB, agrupadas por relatório do IF.data. Clique para expandir cada relatório."), relatoriosBloco(d));
  mserie("mAtivo","ativo",d.historico); mserie("mBas","basileia",d.historico,true);
  mserie("mLucro","lucro",d.historico); mserie("mPl","pl",d.historico);
}
function mserie(id,alias,hist,pct=false){
  const arr=(hist[alias]||[]).filter(p=>p.valor!=null);
  if(!arr.length){ byId(id).innerHTML='<div class="empty">sem histórico</div>'; return; }
  C.linhas(byId(id),[{nome:alias,pontos:arr.map(p=>({x:anomesLabel(p.anomes),y:p.valor}))}],{pct});
}

async function abaCnpj(body,d){
  body.innerHTML='<div class="loading">Consultando dados do CNPJ na Receita Federal…</div>';
  if(!d.cnpj8){ body.innerHTML='<div class="empty">CNPJ não disponível para esta instituição.</div>'; return; }
  let cj;
  try{ cj = d._cnpj || (d._cnpj = await api.cnpj(d.cnpj8)); }
  catch(e){ body.innerHTML='<div class="empty">Não foi possível consultar o CNPJ agora.</div>'; return; }
  if(cj.erro){ body.innerHTML=`<div class="card"><h3>Consulta de CNPJ</h3><p style="color:var(--ink-2)">${cj.erro}</p><p class="csub">CNPJ: ${cj.cnpj||d.cnpj_completo}</p></div>`; return; }
  const site = siteDe(cj);
  const defs=[
    ["Razão social", cj.razao_social],
    ["Nome fantasia", cj.nome_fantasia||"—"],
    ["CNPJ", formatarCnpj(cj._cnpj_formatado||d.cnpj_completo)],
    ["Situação cadastral", (cj.descricao_situacao_cadastral||"—")+(cj.data_situacao_cadastral?(" · "+cj.data_situacao_cadastral):"")],
    ["Natureza jurídica", cj.natureza_juridica||"—"],
    ["Atividade principal (CNAE)", cj.cnae_fiscal_descricao?`${cj.cnae_fiscal} — ${cj.cnae_fiscal_descricao}`:"—"],
    ["Porte", cj.porte||"—"],
    ["Capital social", cj.capital_social!=null?fmtR$(cj.capital_social):"—"],
    ["Início de atividade", cj.data_inicio_atividade||"—"],
    ["Telefone", cj.ddd_telefone_1||"—"],
    ["E-mail", cj.email||"—"],
    ["Site institucional", site?htmlLink(site):"não informado"],
    ["Endereço", endereco(cj)],
    ["Município / UF", `${cj.municipio||"—"} / ${cj.uf||"—"}`],
  ];
  body.innerHTML="";
  body.append(secTitle("Dados cadastrais (Receita Federal)",
    "Consulta ao vivo à base da Receita Federal (via BrasilAPI) pelo CNPJ raiz da instituição. São os dados oficiais do registro empresarial, independentes do cadastro do BCB."), defGrid(defs));
  const qsa=cj.qsa||[];
  if(qsa.length){
    body.append(secTitle(`Quadro de sócios e administradores (${qsa.length})`,
      "Quadro de Sócios e Administradores (QSA) informado à Receita Federal. Passe o mouse em cada nome para ver a qualificação (sócio, administrador, etc.)."),
      el("div",{class:"taglist"}, qsa.slice(0,60).map(s=>
        el("span",{class:"pill",title:s.qualificacao_socio||""}, s.nome_socio||s.nome||"—"))));
  }
  body.append(el("p",{class:"csub",style:"margin-top:16px"},
    "Fonte: ", htmlLink(cj._fonte||("https://brasilapi.com.br/api/cnpj/v1/"+d.cnpj_completo), "BrasilAPI / Receita Federal")));
}

function tabelaTaxas(linhas, colModalidade="Modalidade"){
  const wrap=el("div",{class:"tablewrap"});
  const tbl=el("table"); tbl.append(el("thead",{},el("tr",{},
    el("th",{class:"l"},colModalidade),
    thI("Taxa a.a.","Taxa de juros anual praticada pela instituição nesta modalidade."),
    thI("Taxa a.m.","Taxa de juros mensal equivalente."),
    thI("Ranking","Posição da instituição entre todas que reportam esta modalidade, ordenadas da menor para a maior taxa. #1 = pratica a menor taxa do mercado."))),el("tbody"));
  const tb=tbl.querySelector("tbody");
  linhas.forEach(t=>tb.append(el("tr",{},
    el("td",{class:"l"},t.modalidade),el("td",{class:"num"},fmtNum(t.taxa_ano,2)+"%"),
    el("td",{class:"num"},fmtNum(t.taxa_mes,2)+"%"),
    el("td",{class:"num"},t.posicao!=null?("#"+t.posicao):"—"))));
  wrap.append(tbl); return wrap;
}
function abaTaxas(body,d){
  body.innerHTML="";
  const credito=d.taxas_credito||[], imob=d.taxas||[];
  if(!credito.length && !imob.length){
    body.append(el("div",{class:"card"},el("h3",{},"Taxas praticadas"),
      el("p",{style:"color:var(--ink-2);line-height:1.6"},"Sem taxas de juros publicadas para este CNPJ nas bases do BCB. Nem toda instituição reporta taxas de crédito (ex.: algumas não operam crédito ao público)."),
      el("p",{class:"csub"},"Fonte: ",htmlLink("https://www.bcb.gov.br/estabilidadefinanceira/txjuros","BCB — Taxas de juros"))));
    return;
  }
  // modalidades de credito, agrupadas por segmento (PF / PJ)
  if(credito.length){
    const porSeg={};
    credito.forEach(t=>{ (porSeg[t.segmento||"—"]=porSeg[t.segmento||"—"]||[]).push(t); });
    const periodo=credito[0].periodo_ini?`${credito[0].periodo_ini} a ${credito[0].periodo_fim}`:"";
    body.append(secTitle("Taxas de juros de crédito por modalidade",
      "Taxas efetivamente praticadas por esta instituição em cada modalidade de crédito, divulgadas semanalmente pelo BCB. Agrupadas por segmento (PF = pessoa física, PJ = pessoa jurídica)."));
    body.append(el("p",{class:"csub",style:"margin:-6px 0 12px"},
      `Posição mais recente${periodo?` (semana de ${periodo})`:""}. Ranking = posição da instituição entre todas, da menor para a maior taxa.`));
    Object.keys(porSeg).sort().forEach(seg=>{
      const linhas=porSeg[seg].slice().sort((a,b)=>(a.taxa_ano??1e9)-(b.taxa_ano??1e9));
      body.append(el("h3",{style:"margin:16px 0 8px;font-size:14px"},seg),tabelaTaxas(linhas));
    });
  }
  // financiamento imobiliario (serie mensal)
  if(imob.length){
    body.append(secTitle("Financiamento imobiliário",
      "Série mensal das taxas de financiamento imobiliário praticadas por esta instituição (base taxaJuros/BCB)."),
      tabelaTaxas(imob.slice().sort((a,b)=>(a.taxa_ano??1e9)-(b.taxa_ano??1e9))));
  }
  body.append(el("p",{class:"csub",style:"margin-top:12px"},"Fonte: ",
    htmlLink("https://www.bcb.gov.br/estabilidadefinanceira/txjuros","BCB — Taxas de juros por instituição")));
}

async function abaTarifasServico(body,d){
  body.innerHTML='<div class="loading">Consultando tarifas de serviços no BCB…</div>';
  if(!d.cnpj8){ body.innerHTML='<div class="empty">CNPJ não disponível para consultar tarifas.</div>'; return; }
  let t;
  try{ t = d._tarifas || (d._tarifas = await api.tarifasIf(d.cnpj8)); }
  catch(e){ body.innerHTML='<div class="empty">Não foi possível consultar as tarifas agora.</div>'; return; }
  body.innerHTML="";
  const itens=(t&&t.itens)||[];
  if(t&&t.erro || !itens.length){
    body.append(el("div",{class:"card"},el("h3",{},"Tarifas de serviços"),
      el("p",{style:"color:var(--ink-2);line-height:1.6"},
        "Esta instituição não tem tarifário de serviços publicado no BCB para este CNPJ. "+
        "Nem toda instituição possui lista de tarifas padronizadas (ex.: algumas não captam do público)."),
      el("p",{class:"csub"},"Fonte: ",htmlLink("https://www.bcb.gov.br/estabilidadefinanceira/tarifas","BCB — Tarifas de serviços"))));
    return;
  }
  body.append(secTitle(`Tarifas de serviços padronizados (${itens.length})`,
    "Tarifário de serviços padronizados que a instituição informa ao BCB (consulta ao vivo por CNPJ). 'Valor máx.' é o teto que a instituição pode cobrar; a vigência indica desde quando o valor vale."));
  const wrap=el("div",{class:"tablewrap"});
  const tbl=el("table"); tbl.append(el("thead",{},el("tr",{},
    thI("Serviço","Serviço padronizado tarifado. Abaixo, a periodicidade de cobrança.","l"),
    thI("Unidade","Unidade de cobrança da tarifa (ex.: por evento, por mês).","l"),
    thI("Valor máx.","Teto que a instituição pode cobrar pelo serviço, conforme informado ao BCB."),
    thI("Vigência","Data a partir da qual o valor informado está em vigor.","l"))),el("tbody"));
  const tb=tbl.querySelector("tbody");
  itens.sort((a,b)=>(a.codigo||"").localeCompare(b.codigo||""));
  itens.forEach(it=>tb.append(el("tr",{},
    el("td",{class:"l"}, el("div",{class:"name-cell"},
      el("div",{},it.servico||"—"), el("div",{class:"sub"},it.periodicidade||""))),
    el("td",{class:"l"},it.unidade||"—"),
    el("td",{class:"num"}, it.tipo_valor==="Real"?fmtR$(it.valor_maximo):(fmtNum(it.valor_maximo,2)+(it.tipo_valor==="Percentual"?"%":""))),
    el("td",{class:"l"},it.vigencia||"—"))));
  wrap.append(tbl); body.append(wrap);
  body.append(el("p",{class:"csub",style:"margin-top:12px"},"Fonte: ",
    htmlLink("https://www.bcb.gov.br/estabilidadefinanceira/tarifas","BCB — Informes · Tarifas de serviços por instituição")));
}

function abaFontes(body,d){
  body.innerHTML="";
  const c8=d.cnpj8, cnpjf=d.cnpj_completo;
  const links=[
    ["IF.data (dados desta instituição no BCB)","https://www3.bcb.gov.br/ifdata/"],
    ["Consulta CNPJ (Receita Federal)", cnpjf?("https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/Cnpjreva_Solicitacao.asp"):null],
    ["CNPJ via BrasilAPI (JSON)", c8?("https://brasilapi.com.br/api/cnpj/v1/"+cnpjf):null],
    ["Procurar site institucional (web)", "https://www.google.com/search?q="+encodeURIComponent(nomeLimpo(d.cadastro.nome)+" site oficial")],
    ["Participantes da RSFN (STR)", d.rsfn?"https://www.bcb.gov.br/content/estabilidadefinanceira/str1/ParticipantesSTR.csv":null],
  ].filter(x=>x[1]);
  body.append(secTitle("Links diretos & comprovação das fontes",
    "Links oficiais para você conferir, na origem, cada dado exibido nesta instituição (BCB, Receita Federal e RSFN)."),
    el("div",{class:"deflist"}, links.map(([lbl,url])=>
      el("div",{class:"def"}, el("div",{class:"dk"},lbl), el("div",{class:"dv"}, htmlLink(url,url.length>52?url.slice(0,52)+"…":url))))));
  body.append(el("p",{class:"csub",style:"margin-top:16px"},
    "Todos os dados exibidos vêm de fontes públicas oficiais do Banco Central e da Receita Federal. Veja a seção ",
    htmlLink("#/fontes","Fontes de dados")," para a lista completa com links."));
}

// ================================================================ PAGAMENTOS
function cruzGrid(itens){
  return kpiRow(itens.map(([lab,val,sub,tip])=>[lab, fmtInt(val||0), sub||"", tip]));
}
async function viewPagamentos(){
  crumbs.textContent="Pagamentos — PIX, RSFN/STR & arranjos";
  const pg = estado.pagamentos || (estado.pagamentos = await api.pagamentos());
  const pa = estado.participacao || (estado.participacao = await api.participacao());
  const ult = pg.pix_serie[pg.pix_serie.length-1]||{};
  const pico = pg.pix_serie.reduce((a,b)=>(b.quantidade>(a.quantidade||0)?b:a),{});
  content.innerHTML="";
  const T=pa.totais||{}, X=pa.cruzamentos||{};
  content.append(
    kpiRow([
      ["Participantes do PIX", fmtInt(T.pix), "arranjo PIX"+(pa.pix_data?(" · "+pa.pix_data):""),
        "Instituições no diretório de participantes do PIX (por ISPB), na data divulgada pelo BCB."],
      ["No STR / TED", fmtInt(T.str), "participantes diretos do STR",
        "Participantes do STR (Sistema de Transferência de Reservas), onde a TED é liquidada — lista ParticipantesSTR.csv."],
      ["Conexão RSFN direta", fmtInt(T.rsfn_direto), "acesso tipo RSFN",
        "Participantes com conexão física direta à Rede do SFN (campo de acesso = 'RSFN'), distintos de quem acessa de forma indireta (via internet / liquidante)."],
      ["Na COMPE", fmtInt(T.compe), "compensação",
        "Participantes da COMPE (Centralizadora da Compensação de Cheques e outros papéis), identificados pelo código COMPE na lista do STR."],
    ]),
    secTitle("Matriz de participação nos arranjos (cruzamento por ISPB)",
      "Cruzamento, pelo identificador ISPB de cada instituição, de quem está em cada arranjo e nas interseções entre eles. É o pedido central: ver quem está e quem NÃO está em cada arranjo."),
    el("p",{class:"csub",style:"margin:-6px 0 12px;max-width:900px"},
      "Quem está em cada arranjo e as interseções. “STR/TED” são os participantes do Sistema de "+
      "Transferência de Reservas (onde roda a TED); “RSFN direta” é a conexão física direta à rede; "+
      "“PIX sem STR” são participantes do PIX que acessam de forma indireta (via liquidante)."),
    cruzGrid([
      ["No PIX e no STR/TED", X.pix_e_str, "em ambos","Instituições presentes nos dois arranjos ao mesmo tempo (ISPB no PIX e no STR)."],
      ["No PIX e RSFN direta", X.pix_e_rsfn_direto, "conexão direta + PIX","Estão no PIX e têm conexão física direta à RSFN."],
      ["No PIX, sem STR/TED", X.pix_sem_str, "participação PIX indireta","Participam do PIX mas não do STR — acessam de forma indireta, via um liquidante."],
      ["No STR/TED, fora do PIX", X.str_sem_pix, "só liquidação/TED","Estão no STR (TED) mas não oferecem PIX."],
      ["Na COMPE e no PIX", X.compe_e_pix, "compensação + PIX","Participam da COMPE e também do PIX."],
      ["STR indireto (não-RSFN)", X.str_indireto, "acesso via internet","Participantes do STR cujo acesso NÃO é conexão física direta (acesso via internet/indireto)."],
    ]),
    secTitle("PIX liquidados no SPI","Série diária de transações PIX liquidadas no Sistema de Pagamentos Instantâneos (SPI), da API de estatísticas do BCB."),
    card(h3i("Evolução diária (quantidade de transações)","Quantidade de PIX liquidados por dia no SPI."), el("div",{class:"chart lg",id:"pgPix"})),
    secTitle("Participantes da RSFN por tipo de acesso","Distribuição dos participantes do STR pelo tipo de acesso à rede (conexão direta 'RSFN' vs. acesso indireto/via internet)."),
    card(el("div",{class:"chart sm",id:"pgAcesso"})),
    secTitle(`Participantes da RSFN (${pg.rsfn_total})`,"Diretório completo do STR (ParticipantesSTR.csv do BCB): ISPB, código no sistema, tipo de acesso, participação na COMPE e data de início."),
    pagRsfnTable(pg.rsfn),
  );
  C.linhas(byId("pgPix"), [{nome:"PIX/dia",pontos:pg.pix_serie.map(d=>({x:d.data,y:d.quantidade}))}]);
  C.barH(byId("pgAcesso"), pg.rsfn_por_acesso.map(x=>({label:x.k,v:x.n,cor:"#4f93f0"})),{money:false});
}
function pagRsfnTable(rows){
  const wrap=el("div",{class:"filterbar"});
  const inp=el("input",{type:"search",placeholder:"Buscar participante / ISPB / código…",oninput:e=>render(e.target.value.toLowerCase())});
  wrap.append(inp);
  const tw=el("div",{class:"tablewrap"});
  const tbl=el("table"); tbl.append(el("thead",{},el("tr",{},
    thI("ISPB","Identificador de 8 dígitos da instituição no SPB (ISPB). É a chave que cruza todos os arranjos.","l"),
    thI("Cód.","Código COMPE (3 dígitos) da instituição, quando participa da compensação.","l"),
    el("th",{class:"l"},"Participante"),
    thI("Acesso","Tipo de acesso ao STR: 'RSFN' = conexão física direta à rede; demais = acesso indireto/via internet.","l"),
    thI("COMPE","Indica se a instituição participa da COMPE (compensação de cheques e outros papéis).","l"),
    thI("Desde","Data de início de participação no STR.","l"))),el("tbody"));
  tw.append(tbl);
  const box=el("div",{}); box.append(wrap,tw);
  function render(q=""){
    const tb=tbl.querySelector("tbody"); tb.innerHTML="";
    const frag=document.createDocumentFragment();
    rows.filter(r=>!q||((r.nome_reduzido+" "+r.ispb+" "+r.codigo+" "+r.nome_extenso).toLowerCase().includes(q)))
      .forEach(r=>frag.append(el("tr",{},
        el("td",{class:"l"},r.ispb),el("td",{class:"l"},r.codigo||"–"),
        el("td",{class:"l"},r.nome_extenso||r.nome_reduzido),
        el("td",{class:"l"},r.acesso||"–"),el("td",{class:"l"},r.participa_compe||"–"),el("td",{class:"l"},r.inicio||"–"))));
    tb.append(frag);
  }
  render(); return box;
}

// ================================================================ PRUDENCIAL
async function viewPrudencial(){
  crumbs.innerHTML='Prudencial & Saúde financeira <span class="muted">· segmentação S1–S5 e capital</span>';
  const ov = estado.prudencial || (estado.prudencial = await api.prudencial());
  const t=ov.totais; const s1=ov.por_segmento.find(s=>s.seg==="S1")||{ativo:0};
  const itens=(await getRegistro()).filter(i=>i.tem_financas);
  content.innerHTML="";
  content.append(
    el("div",{class:"csub",style:"margin-bottom:16px;max-width:760px"},"Visão prudencial do IF.data (consolidado). A segmentação S1–S5 é um recorte desta seção — não a organização do sistema, que vive em Instituições."),
    kpiRow([
      ["Instituições (prudencial)", fmtInt(t.n),"","Instituições que reportam balanço na consolidação prudencial do IF.data nesta data-base."],
      ["Ativo Total", fmtR$(t.ativo),"","Soma do Ativo Total das instituições do universo prudencial."],
      ["Patrimônio Líquido", fmtR$(t.pl),"","Soma do Patrimônio Líquido do universo prudencial."],
      ["Lucro Líquido", fmtR$(t.lucro),"","Soma do resultado líquido do período no universo prudencial."],
    ]),
    secTitle("Segmentação (Resolução CMN 4.553/2017)",
      "A segmentação S1–S5 classifica as instituições por porte (em relação ao PIB) e complexidade, para calibrar a regulação prudencial. S1 = maiores/sistêmicas; S5 = perfil simplificado. Aqui é um recorte, não a organização do sistema."),
    grid("g-3",
      card(h3i("Ativo por segmento","Quanto do ativo total está em cada segmento S1–S5. Normalmente o S1 (grandes bancos) concentra a maior parte."), el("div",{class:"chart",id:"prTm"})),
      card(h3i("Concentração no S1","Participação do segmento S1 no ativo total do sistema — mede a concentração nos maiores bancos."),el("div",{class:"csub"},"share no ativo"),el("div",{class:"chart sm",id:"prDonut"})),
    ),
    grid("g-2",
      card(h3i("Instituições por segmento","Quantas instituições há em cada segmento. Há muitas instituições pequenas (S4/S5) e poucas grandes (S1)."), el("div",{class:"chart",id:"prCount"})),
      card(h3i("Ativo por estado (top 12)","Ativo total somado por UF da sede — as 12 maiores. Reflete a concentração nas sedes de SP e do Sul/Sudeste."), el("div",{class:"chart",id:"prUf"})),
    ),
    secTitle("Ranking — maior Índice de Basileia (ativo > R$ 1 bi)",
      "Instituições com Ativo acima de R$ 1 bilhão ordenadas pelo maior Índice de Basileia (capital ÷ ativos ponderados pelo risco). O filtro de porte evita que instituições minúsculas com índices distorcidos dominem o ranking."),
    prBasileia(itens),
  );
  C.treemap(byId("prTm"), ov.por_segmento.map(s=>({label:s.seg,v:s.ativo,cor:SEG_COR[s.seg]})));
  C.donut(byId("prDonut"), s1.ativo, t.ativo, SEG_COR.S1);
  C.barH(byId("prCount"), ov.por_segmento.map(s=>({label:s.seg,v:s.n,cor:SEG_COR[s.seg]})),{money:false});
  C.barH(byId("prUf"), ov.por_uf.slice(0,12).map(u=>({label:u.uf,v:u.ativo,cor:"#4f93f0"})));
}
function prBasileia(itens){
  const rows=itens.filter(i=>i.basileia!=null&&(i.ativo||0)>=1e9).sort((a,b)=>b.basileia-a.basileia).slice(0,25);
  const wrap=el("div",{class:"tablewrap"});
  const tbl=el("table"); tbl.append(el("thead",{},el("tr",{},
    el("th",{class:"l"},"#"),el("th",{class:"l"},"Instituição"),
    thI("Seg","Segmento prudencial S1–S5 da instituição.","l"),
    thI("Basileia","Índice de Basileia = capital regulatório ÷ ativos ponderados pelo risco. Mínimo de 8%."),
    thI("Ativo","Ativo Total do balanço (IF.data). O ranking só inclui instituições acima de R$ 1 bilhão."))),el("tbody"));
  const tb=tbl.querySelector("tbody");
  rows.forEach((i,ix)=>tb.append(el("tr",{onclick:()=>abrirModal(i.cod)},
    el("td",{class:"l",html:`<b>${ix+1}</b>`}),el("td",{class:"l"},nomeLimpo(i.nome)),
    el("td",{class:"l"},segBadge(i.seg)),el("td",{class:"num"},fmtPct(i.basileia)),el("td",{class:"num"},fmtR$(i.ativo)))));
  wrap.append(tbl); return wrap;
}

// ================================================================ CONDUTA (reclamações)
async function viewConduta(){
  crumbs.innerHTML='Conduta & Reclamações <span class="muted">· ranking BCB</span>';
  const d = await api.conduta();
  const itens = d.itens;
  const comIndice = itens.filter(i=>i.indice!=null).sort((a,b)=>b.indice-a.indice);
  content.innerHTML="";
  content.append(
    el("div",{class:"csub",style:"margin-bottom:16px;max-width:820px"},
      `Ranking de reclamações do BCB — período ${d.periodo||""} (com histórico de ${(d.periodos||[]).length} trimestres). O índice pondera reclamações procedentes pela quantidade de clientes (quanto maior, pior). Só as instituições do "Top 15" recebem índice; as demais aparecem com as quantidades. Clique numa instituição para abrir o perfil completo; a coluna “Evolução” mostra a tendência do índice.`),
    kpiRow([
      ["Instituições no ranking", fmtInt(itens.length), d.periodo||"",
        "Total de instituições no ranking de reclamações do BCB no trimestre."],
      ["Pior índice", comIndice.length?fmtNum(comIndice[0].indice,2):"–", comIndice.length?nomeLimpo(comIndice[0].nome):"",
        "Maior índice de reclamações do período (pior colocada). Índice = reclamações procedentes ponderadas pela quantidade de clientes."],
      ["Total de reclamações", fmtInt(itens.reduce((s,i)=>s+(i.reclamacoes||0),0)), "respondidas no período",
        "Soma das reclamações respondidas de todas as instituições no trimestre."],
      ["Procedentes", fmtInt(itens.reduce((s,i)=>s+(i.procedentes||0),0)), "",
        "Soma das reclamações consideradas procedentes (BCB deu razão ao cliente) no trimestre."],
    ]),
    secTitle("Ranking por índice de reclamações",
      "Lista completa. Só o 'Top 15' recebe índice (maiores por nº de clientes); as demais aparecem só com as quantidades. Use os filtros e a busca; clique numa linha para abrir o perfil."),
    condutaTable(itens),
  );
}
// mini-sparkline SVG (sem dependencia) para a evolucao do indice
function sparkline(vals,{w=84,h=20,cor="var(--accent)"}={}){
  const v=vals.filter(x=>x!=null);
  if(v.length<2) return el("span",{class:"muted",style:"font-size:11px"},"–");
  const mn=Math.min(...v), mx=Math.max(...v), rg=(mx-mn)||1;
  const pts=v.map((x,i)=>`${(i/(v.length-1))*w},${h-((x-mn)/rg)*(h-3)-1.5}`).join(" ");
  const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");
  svg.setAttribute("width",w); svg.setAttribute("height",h); svg.style.display="block";
  const pl=document.createElementNS(svg.namespaceURI,"polyline");
  pl.setAttribute("points",pts); pl.setAttribute("fill","none");
  pl.setAttribute("stroke",cor); pl.setAttribute("stroke-width","1.5");
  pl.setAttribute("stroke-linejoin","round"); pl.setAttribute("stroke-linecap","round");
  svg.append(pl);
  // ponto final
  const last=pts.split(" ").pop().split(","); const c=document.createElementNS(svg.namespaceURI,"circle");
  c.setAttribute("cx",last[0]); c.setAttribute("cy",last[1]); c.setAttribute("r","2"); c.setAttribute("fill",cor);
  svg.append(c);
  return svg;
}
function condutaTable(itens){
  const maxIdx=comIndiceMax(itens);
  // posicao global por indice (pior = 1)
  const ranked=itens.filter(i=>i.indice!=null).sort((a,b)=>b.indice-a.indice);
  const pos=new Map(); ranked.forEach((i,ix)=>pos.set(i,ix+1));
  const bar=el("div",{class:"filterbar",style:"flex-wrap:wrap;gap:8px"});
  const inp=el("input",{type:"search",placeholder:"Buscar instituição…",oninput:()=>render()});
  // filtros de categoria
  const filtro={top:true,demais:true,soIndice:false};
  const mk=(lab,key)=>{const b=el("button",{class:"chip-tgl",onclick:()=>{filtro[key]=!filtro[key];b.classList.toggle("off",!filtro[key]);render();}},lab); if(!filtro[key])b.classList.add("off"); return b;};
  const cTop=mk("Top 15 (com índice)","top"), cDem=mk("Demais","demais"), cIdx=mk("Só com índice","soIndice");
  const fcount=el("span",{class:"fcount"});
  bar.append(cTop,cDem,cIdx,
    info("Top 15 = as 15 instituições com mais clientes, que recebem índice de reclamações. 'Demais' = todas as outras (só com quantidades). 'Só com índice' esconde as que não têm índice.","down"),
    withInfo(inp,"Busca pelo nome da instituição."),fcount);
  const wrap=el("div",{class:"tablewrap"});
  const tbl=el("table");
  let ordK="indice", ordD=-1;
  const cols=[["pos","#",false,"Posição no ranking por índice (pior = 1). Só instituições com índice são numeradas."],
    ["nome","Instituição","l","Nome da instituição e se está no Top 15 ou nas 'Demais'."],["indice","Índice",false,"Índice de reclamações = (procedentes ÷ clientes) × 1.000.000 no trimestre. A cor vai de verde (baixo) a vermelho (alto)."],
    ["reclamacoes","Reclamações",false,"Reclamações respondidas no trimestre."],["procedentes","Procedentes",false,"Reclamações em que o BCB deu razão ao cliente."],["pct_procedente","% proced.",false,"Percentual de procedência = procedentes ÷ reclamações respondidas."],
    ["clientes","Clientes",false,"Base de clientes (CCS+SCR) usada no denominador do índice."],["hist","Evolução do índice","l","Mini-gráfico da tendência do índice nos últimos trimestres disponíveis."]];
  tbl.append(el("thead"),el("tbody"));
  const box=el("div",{}); box.append(bar,wrap); wrap.append(tbl);
  function render(){
    const q=(inp.value||"").toLowerCase();
    const rows=itens.filter(i=>{
      const isTop=i.categoria&&i.categoria.startsWith("Top");
      if(isTop&&!filtro.top) return false;
      if(!isTop&&!filtro.demais) return false;
      if(filtro.soIndice&&i.indice==null) return false;
      return !q||nomeLimpo(i.nome).toLowerCase().includes(q);
    }).sort((a,b)=>{
      if(ordK==="pos"){let x=pos.get(a)||1e9,y=pos.get(b)||1e9;return (x-y)*ordD;}
      let x=a[ordK],y=b[ordK];if(x==null)x=-Infinity;if(y==null)y=-Infinity;
      return (typeof x==="string"?x.localeCompare(y,"pt-BR"):x-y)*ordD;});
    const thead=tbl.querySelector("thead"); thead.innerHTML="";
    const tr=el("tr");
    cols.forEach(([k,lab,l,tip])=>tr.append(el("th",{class:l?"l":"",onclick:()=>{
      if(ordK===k)ordD*=-1;else{ordK=k;ordD=(l&&k!=="hist")?1:-1;}render();}},lab+(ordK===k?(ordD<0?" ▼":" ▲"):""),info(tip,"down"))));
    thead.append(tr);
    const tb=tbl.querySelector("tbody"); tb.innerHTML="";
    const frag=document.createDocumentFragment();
    rows.forEach(i=>{
      const serie=(i.historia||[]).map(h=>h.indice);
      const r=el("tr",{class:i.cod?"row-click":"",title:i.cod?"Abrir instituição":"",
        onclick:i.cod?()=>abrirModal(i.cod):null},
        el("td",{class:"num",style:"color:var(--ink-3)"}, i.indice!=null?("#"+pos.get(i)):"–"),
        el("td",{class:"l"}, el("div",{class:"name-cell"}, el("div",{},nomeLimpo(i.nome)),
          el("div",{class:"sub"}, i.categoria&&i.categoria.startsWith("Top")?"Top 15":"Demais"))),
        el("td",{class:"num",style:i.indice!=null?`color:${corIndice(i.indice,maxIdx)};font-weight:600`:""}, i.indice!=null?fmtNum(i.indice,2):"–"),
        el("td",{class:"num"},fmtInt(i.reclamacoes)),
        el("td",{class:"num"},fmtInt(i.procedentes)),
        el("td",{class:"num"}, i.pct_procedente!=null?fmtNum(i.pct_procedente*100,0)+"%":"–"),
        el("td",{class:"num"},fmtInt(i.clientes)),
        el("td",{class:"l"}, sparkline(serie,{cor:i.indice!=null?corIndice(i.indice,maxIdx):"var(--accent)"})));
      frag.append(r);
    });
    tb.append(frag);
    fcount.textContent=`${rows.length} instituições`;
  }
  render();
  return box;
}
function comIndiceMax(itens){ return Math.max(1,...itens.filter(i=>i.indice!=null).map(i=>i.indice)); }
function corIndice(v,max){ const t=Math.min(1,v/max); return t>.66?"var(--neg)":t>.33?"var(--warn)":"var(--pos)"; }

// ================================================================ MACRO (Focus)
async function viewMacro(){
  crumbs.innerHTML='Indicadores Macro <span class="muted">· Focus (projeções) + séries observadas (SGS)</span>';
  const d = await api.macro();
  const P = d.principais||{};
  const unidade={Selic:"% a.a.",IPCA:"%",Cambio:"R$/US$","PIB Total":"%"};
  const titulo={Selic:"Selic (meta)",IPCA:"IPCA (inflação)",Cambio:"Câmbio (R$/US$)","PIB Total":"PIB"};
  content.innerHTML="";
  content.append(el("div",{class:"csub",style:"max-width:820px;margin-bottom:16px"},
    "Projeções do boletim Focus (mediana das expectativas de mercado), por ano de referência. Fonte: "+
    "Banco Central — Sistema de Expectativas de Mercado."));
  const descInd={
    Selic:"Projeção da taxa básica de juros (Selic) ao fim de cada ano, pela mediana do mercado no boletim Focus.",
    IPCA:"Projeção da inflação oficial (IPCA) acumulada em cada ano, pela mediana do Focus.",
    Cambio:"Projeção da taxa de câmbio R$/US$ ao fim de cada ano, pela mediana do Focus.",
    "PIB Total":"Projeção de crescimento real do PIB em cada ano, pela mediana do Focus."};
  const ordem=["Selic","IPCA","Cambio","PIB Total"];
  ordem.forEach(k=>{
    const blk=P[k]; if(!blk) return;
    content.append(secTitle(titulo[k]+"  ·  coleta "+(blk.data||""), descInd[k]));
    const proj=blk.proj.slice(0,5);
    content.append(kpiRow(proj.map(p=>[
      p.referencia, fmtNum(p.mediana,2)+" "+(unidade[k]||""),
      `mín ${fmtNum(p.minimo,2)} · máx ${fmtNum(p.maximo,2)}`,
      `Ano de referência ${p.referencia}. Valor = mediana das projeções do mercado; abaixo, o mínimo e o máximo projetados entre os respondentes do Focus na coleta de ${blk.data||"—"}.`])));
  });
  if(!Object.keys(P).length) content.append(el("div",{class:"empty"},"Sem dados do Focus."));
  // --- series observadas do SGS (Selic, inflacao, cambio, atividade) ---
  const series=d.series_sgs||[];
  if(series.length){
    content.append(secTitle("Indicadores observados (séries do BCB · SGS)",
      "Valores que de fato aconteceram (não projeções): meta Selic, inflação (IPCA e IGP-M), câmbio e PIB. Vêm do SGS (Sistema Gerenciador de Séries Temporais) do BCB."));
    content.append(el("p",{class:"csub",style:"margin:-6px 0 14px;max-width:860px"},
      "Valores efetivamente observados (diferente das projeções do Focus acima): meta Selic, inflação (IPCA e IGP-M), câmbio e atividade."));
    const sgsLbl=dt=>dt.length===10?(dt.slice(0,2)+"/"+dt.slice(3,5)+"/"+dt.slice(6,10)):dt;
    const porGrupo={};
    series.forEach(s=>{ (porGrupo[s.grupo]=porGrupo[s.grupo]||[]).push(s); });
    const render=[];
    Object.keys(porGrupo).forEach(g=>{
      content.append(el("h3",{style:"margin:14px 0 8px;font-size:14px"},g));
      const gr=grid("g-2");
      porGrupo[g].forEach(s=>{
        const id="sgs_"+s.codigo;
        const ult=s.ultimo?(s.tipo==="pct"?fmtNum(s.ultimo.valor,2)+"%":
                            s.tipo==="moeda_mi"?fmtR$(s.ultimo.valor*MI):fmtNum(s.ultimo.valor,4)):"";
        gr.append(card(el("h3",{},s.nome),
          el("div",{class:"csub"},s.unidade+(s.ultimo?"  ·  último: "+ult+" ("+sgsLbl(s.ultimo.data)+")":"")),
          el("div",{class:"chart sm",id})));
        render.push(s);
      });
      content.append(gr);
    });
    render.forEach(s=>{
      const pts=s.pontos.map(p=>({x:sgsLbl(p.data),
        y: s.tipo==="pct"?p.valor/100 : s.tipo==="moeda_mi"?p.valor*MI : p.valor}));
      C.linhas(byId("sgs_"+s.codigo),[{nome:s.nome,pontos:pts}],{pct:s.tipo==="pct"});
    });
    content.append(el("p",{class:"csub",style:"margin-top:14px"},"Fonte: ",
      htmlLink("https://www3.bcb.gov.br/sgspub/","BCB — SGS (Sistema Gerenciador de Séries Temporais)"),
      " · séries 432 (Selic), 433 e 13522 (IPCA), 189 (IGP-M), 1 e 21619 (câmbio), 4380 (PIB)."));
  }
}

// ================================================================ CRÉDITO (SGS)
const MI = 1e6;
function sgsLabel(d){ return d?(d.slice(3,5)+"/"+d.slice(6,10)):""; }  // dd/mm/aaaa -> mm/aaaa
async function viewCredito(){
  crumbs.innerHTML='Crédito do SFN <span class="muted">· séries agregadas (SGS)</span>';
  const d = estado.credito || (estado.credito = await api.credito());
  const S = Object.fromEntries((d.series||[]).map(s=>[s.codigo,s]));
  const ult = c => S[c]&&S[c].ultimo?S[c].ultimo.valor:null;
  content.innerHTML="";
  if(!d.series || !d.series.length){ content.append(el("div",{class:"empty"},"Sem dados de crédito no cache. Rode atualizar.bat.")); return; }
  const dataRef = S["20539"]?sgsLabel(S["20539"].ultimo.data):"";
  content.append(
    el("div",{class:"csub",style:"max-width:860px;margin-bottom:16px"},
      "Crédito agregado do Sistema Financeiro Nacional — séries mensais do SGS/BCB (livre + direcionado). "+
      "Valores de saldo em reais; juros e inadimplência em percentual. Referência: "+dataRef+"."),
    kpiRow([
      ["Saldo total da carteira", fmtR$(ult("20539")*MI), dataRef,
        "Saldo total da carteira de crédito do SFN (livre + direcionado), série mensal 20539 do SGS. Origem em R$ milhões, convertida para reais."],
      ["Crédito — Pessoas Físicas", fmtR$(ult("20541")*MI), "PF",
        "Saldo da carteira concedida a pessoas físicas (série 20541 do SGS)."],
      ["Crédito — Pessoas Jurídicas", fmtR$(ult("20540")*MI), "PJ",
        "Saldo da carteira concedida a pessoas jurídicas (série 20540 do SGS)."],
      ["Concessões no mês (livres)", fmtR$(ult("20634")*MI), dataRef,
        "Novo crédito concedido no mês com recursos livres (série 20634). É fluxo do mês, não saldo acumulado."],
      ["Taxa média de juros", fmtNum(ult("20714"),2)+"% a.a.", "total",
        "Taxa média de juros das operações de crédito do SFN (série 20714), em % ao ano."],
      ["Inadimplência", fmtNum(ult("21082"),2)+"%", "atraso > 90 dias",
        "Percentual da carteira com atraso superior a 90 dias (série 21082). É o principal indicador de risco do crédito."],
    ]),
    secTitle("Evolução do saldo da carteira","Como o estoque de crédito do SFN evoluiu ao longo do tempo (séries mensais do SGS)."),
    grid("g-2",
      card(h3i("Saldo total da carteira","Estoque total de crédito do SFN mês a mês (série 20539)."), el("div",{class:"csub"},"R$"), el("div",{class:"chart",id:"crTot"})),
      card(h3i("Pessoas Físicas × Pessoas Jurídicas","Comparação dos saldos de crédito a pessoas físicas (20541) e jurídicas (20540)."), el("div",{class:"csub"},"R$"), el("div",{class:"chart",id:"crPfPj"})),
    ),
    secTitle("Custo e risco do crédito","Preço (taxa de juros) e risco (inadimplência) do crédito no agregado do sistema."),
    grid("g-2",
      card(h3i("Taxa média de juros","Taxa média de juros do crédito do SFN, % ao ano (série 20714)."), el("div",{class:"csub"},"% ao ano"), el("div",{class:"chart",id:"crJuros"})),
      card(h3i("Inadimplência","Percentual da carteira em atraso acima de 90 dias (série 21082)."), el("div",{class:"csub"},"% da carteira (atraso > 90 dias)"), el("div",{class:"chart",id:"crInad"})),
    ),
    secTitle("Concessões mensais","Fluxo de novo crédito concedido a cada mês (recursos livres)."),
    card(h3i("Concessões de crédito (recursos livres)","Volume de crédito novo concedido por mês com recursos livres (série 20634)."), el("div",{class:"csub"},"R$ por mês"), el("div",{class:"chart lg",id:"crConc"})),
    el("p",{class:"csub",style:"margin-top:14px"},"Fonte: ",
      htmlLink("https://www3.bcb.gov.br/sgspub/","BCB — SGS (Sistema Gerenciador de Séries Temporais)"),
      " · séries 20539 / 20540 / 20541 / 20634 / 20714 / 21082."),
  );
  const serieR$ = c => ({nome:S[c].nome,pontos:S[c].pontos.map(p=>({x:sgsLabel(p.data),y:p.valor*MI}))});
  const seriePct = c => ({nome:S[c].nome,pontos:S[c].pontos.map(p=>({x:sgsLabel(p.data),y:p.valor/100}))});
  if(S["20539"]) C.linhas(byId("crTot"),[serieR$("20539")]);
  if(S["20541"]&&S["20540"]) C.linhas(byId("crPfPj"),[{nome:"Pessoas Físicas",pontos:S["20541"].pontos.map(p=>({x:sgsLabel(p.data),y:p.valor*MI}))},{nome:"Pessoas Jurídicas",pontos:S["20540"].pontos.map(p=>({x:sgsLabel(p.data),y:p.valor*MI}))}]);
  if(S["20714"]) C.linhas(byId("crJuros"),[seriePct("20714")],{pct:true});
  if(S["21082"]) C.linhas(byId("crInad"),[seriePct("21082")],{pct:true});
  if(S["20634"]) C.linhas(byId("crConc"),[serieR$("20634")]);
  // --- SCR: carteira por modalidade e UF ---
  const secScr=el("div",{}); content.append(secScr);
  secScr.append(secTitle("Carteira de crédito por modalidade e região (SCR)"), el("div",{class:"loading"},"Carregando…"));
  const scr = estado.scr || (estado.scr = await api.scr());
  secScr.innerHTML="";
  if(scr && scr.por_modalidade && scr.por_modalidade.length){
    const tt=scr.total||{};
    const baseLbl = scr.data_base? (String(scr.data_base).slice(4,6)+"/"+String(scr.data_base).slice(0,4)) : "";
    secScr.append(secTitle("Carteira de crédito por modalidade e região (SCR)",
      "O SCR (Sistema de Informações de Crédito) detalha a carteira ativa do SFN por modalidade, UF e tipo de cliente (PF/PJ). Base "+baseLbl+". Difere das séries agregadas do SGS acima por ser construído a partir das operações individuais."));
    secScr.append(el("p",{class:"csub",style:"margin:-6px 0 12px;max-width:880px"},
      `Carteira ativa do SFN detalhada pelo SCR (base ${baseLbl}): por modalidade de crédito, por UF e por tipo de cliente, `+
      "com inadimplência (vencido acima de 15 dias / carteira)."));
    secScr.append(kpiRow([
      ["Carteira total (SCR)", fmtR$(tt.carteira), baseLbl,"Saldo total da carteira ativa no SCR na base "+baseLbl+" (origem em R$ mil, convertida para reais)."],
      ["Pessoas Físicas", fmtR$(tt.pf), tt.carteira?fmtNum(100*tt.pf/tt.carteira,0)+"% do total":"","Parcela da carteira tomada por pessoas físicas, com o percentual do total."],
      ["Pessoas Jurídicas", fmtR$(tt.pj), tt.carteira?fmtNum(100*tt.pj/tt.carteira,0)+"% do total":"","Parcela da carteira tomada por pessoas jurídicas, com o percentual do total."],
      ["Inadimplência", fmtNum((tt.inadimplencia||0)*100,2)+"%", "vencido > 15 dias","Saldo vencido há mais de 15 dias ÷ carteira total. Critério do SCR (mais sensível que os 90 dias do SGS)."],
    ]));
    // tabela por modalidade
    secScr.append(el("h3",{style:"margin:16px 0 8px;font-size:14px"},"Por modalidade",
      info("Carteira dividida pelos tipos de operação (habitacional, cartão, consignado, rural, capital de giro, etc.).","down")));
    const w=el("div",{class:"tablewrap"});
    const tbl=el("table"); tbl.append(el("thead",{},el("tr",{},
      el("th",{class:"l"},"Modalidade"),
      thI("Carteira","Saldo ativo da modalidade (reais)."),
      thI("% PF","Fração da carteira da modalidade que é de pessoas físicas."),
      thI("Inadimplência","Vencido > 15 dias ÷ carteira da modalidade. Amarelo acima de 4%, vermelho acima de 8%."),
      thI("Operações","Número de operações de crédito na modalidade."))),el("tbody"));
    const tb=tbl.querySelector("tbody");
    scr.por_modalidade.forEach(m=>tb.append(el("tr",{},
      el("td",{class:"l"},m.modalidade),
      el("td",{class:"num"},fmtR$(m.carteira)),
      el("td",{class:"num"},m.carteira?fmtNum(100*m.pf/m.carteira,0)+"%":"—"),
      el("td",{class:"num",style:(m.inadimplencia>0.08?"color:var(--neg)":(m.inadimplencia>0.04?"color:var(--warn)":""))},
        fmtNum((m.inadimplencia||0)*100,2)+"%"),
      el("td",{class:"num"},fmtInt(m.operacoes)))));
    w.append(tbl); secScr.append(w);
    // por UF (top 12) em barras
    secScr.append(el("h3",{style:"margin:16px 0 8px;font-size:14px"},"Por UF (carteira)",
      info("Saldo da carteira por UF (as 12 maiores). Normalmente concentra-se onde há mais atividade econômica e sedes de tomadores.","down")),
      card(el("div",{class:"chart",id:"scrUf"})));
    C.barH(byId("scrUf"), scr.por_uf.slice(0,12).map(u=>({label:u.uf,v:u.carteira,cor:"#4f93f0"})),{money:true});
    secScr.append(el("p",{class:"csub",style:"margin-top:12px"},"Fonte: ",
      htmlLink("https://www.bcb.gov.br/estabilidadefinanceira/scr","BCB — SCR por sub-região"),
      " · carteira em reais (origem em R$ mil)."));
  }
  // --- taxas de juros por modalidade (ranking entre instituicoes) ---
  const secTx=el("div",{}); content.append(secTx);
  secTx.append(secTitle("Taxas de juros por modalidade"), el("div",{class:"loading"},"Carregando…"));
  const tm = estado.taxasMod || (estado.taxasMod = await api.taxasModalidades());
  secTx.innerHTML="";
  const mods=tm.modalidades||[];
  if(!mods.length){ secTx.append(secTitle("Taxas de juros por modalidade"), el("div",{class:"empty"},"Sem dados de taxas por modalidade no cache.")); return; }
  secTx.append(secTitle("Taxas de juros por modalidade",
    "Dispersão das taxas entre instituições em cada modalidade: dá para ver o quanto a mesma modalidade varia de banco para banco. Posição mais recente divulgada pelo BCB."));
  secTx.append(el("p",{class:"csub",style:"margin:-6px 0 12px;max-width:860px"},
    `Faixa de taxas praticadas por instituição em cada modalidade de crédito (posição mais recente — semana de ${tm.periodo||"—"}). `+
    "Compare a menor, a mediana e a maior taxa anual, além de quantas instituições reportam."));
  const porSeg={};
  mods.forEach(m=>{ (porSeg[m.segmento||"—"]=porSeg[m.segmento||"—"]||[]).push(m); });
  Object.keys(porSeg).sort().forEach(seg=>{
    secTx.append(el("h3",{style:"margin:16px 0 8px;font-size:14px"},seg));
    const wrap=el("div",{class:"tablewrap"});
    const tbl=el("table"); tbl.append(el("thead",{},el("tr",{},
      el("th",{class:"l"},"Modalidade"),
      thI("Instituições","Quantas instituições reportam taxa nesta modalidade (base do cálculo)."),
      thI("Menor a.a.","Menor taxa anual praticada entre as instituições (verde)."),
      thI("Mediana a.a.","Taxa anual mediana — metade das instituições cobra menos, metade cobra mais."),
      thI("Maior a.a.","Maior taxa anual praticada (vermelho)."))),el("tbody"));
    const tb=tbl.querySelector("tbody");
    porSeg[seg].slice().sort((a,b)=>(a.mediana??1e9)-(b.mediana??1e9)).forEach(m=>tb.append(el("tr",{},
      el("td",{class:"l"},m.modalidade),el("td",{class:"num"},fmtInt(m.n)),
      el("td",{class:"num",style:"color:var(--pos)"},m.min!=null?fmtNum(m.min,2)+"%":"—"),
      el("td",{class:"num"},m.mediana!=null?fmtNum(m.mediana,2)+"%":"—"),
      el("td",{class:"num",style:"color:var(--neg)"},m.max!=null?fmtNum(m.max,2)+"%":"—"))));
    wrap.append(tbl); secTx.append(wrap);
  });
  secTx.append(el("p",{class:"csub",style:"margin-top:12px"},"Fonte: ",
    htmlLink("https://www.bcb.gov.br/estabilidadefinanceira/txjuros","BCB — Taxas de juros por instituição (ConsultaUnificada)"),
    " · abra uma instituição para ver suas taxas em todas as modalidades."));
}

// ================================================================ SUPERVISÃO & EVENTOS
async function viewSupervisao(){
  crumbs.innerHTML='Supervisão & Eventos <span class="muted">· atos do BCB sobre instituições</span>';
  const d = estado.supervisao || (estado.supervisao = await api.supervisao());
  const reg=d.regimes||[];
  content.innerHTML="";
  content.append(
    el("div",{class:"csub",style:"max-width:880px;margin-bottom:16px"},
      "Atos e eventos do Banco Central sobre instituições: comunicados oficiais (cancelamento de "+
      "autorização, liquidação, intervenção, controle societário, dirigentes), instituições sob "+
      "regime especial e penalidades do processo sancionador. Clique numa instituição para abrir o perfil."));
  await eventosSecao(content);
  content.append(
    kpiRow([
      ["Em regime especial", fmtInt(d.regimes_total), "posição atual",
        "Instituições atualmente sob regime especial decretado pelo BCB: liquidação extrajudicial, intervenção ou RAET (regime de administração especial temporária)."],
      ["Penalidades (histórico)", fmtInt(d.penalidades_total), "processos sancionadores",
        "Total de penalidades no histórico do processo administrativo sancionador (dados abertos Gepad/BCB), para instituições e pessoas."],
      ["Multas aplicadas", fmtInt((d.penalidades_por_tipo||[]).find(t=>/MULTA/i.test(t.k))?.n||0), "tipo mais comum",
        "Quantidade de penalidades do tipo multa — o tipo mais comum no processo sancionador."],
    ]),
    secTitle("Instituições em regime especial",
      "Lista oficial de instituições sob liquidação, intervenção ou RAET. Clique numa linha para expandir os detalhes (liquidante, endereço, contatos) e abrir o perfil."),
  );
  // tabela de regimes (clique na linha expande os detalhes)
  content.append(el("p",{class:"csub",style:"margin:-6px 0 10px"},
    "Clique numa instituição para ver os detalhes (liquidante, endereço e contatos) e abrir o perfil."));
  const wrap=el("div",{class:"tablewrap"});
  const tbl=el("table"); tbl.append(el("thead",{},el("tr",{},
    el("th",{class:"l"},""),el("th",{class:"l"},"Instituição"),
    thI("Tipo","Tipo de regime especial: Liquidação extrajudicial, Intervenção ou RAET.","l"),
    thI("Início","Data em que o regime especial foi decretado.","l"),
    thI("Responsável / liquidante","Pessoa ou empresa nomeada pelo BCB para conduzir a liquidação/intervenção.","l"),
    thI("UF","UF da sede da instituição.","l"))),el("tbody"));
  const tb=tbl.querySelector("tbody");
  if(!reg.length) tb.append(el("tr",{},el("td",{class:"l",colspan:6},"Nenhuma instituição em regime especial.")));
  reg.forEach(r=>{
    const caret=el("td",{class:"l",style:"color:var(--ink-3);width:1%"},"▸");
    const tr=el("tr",{class:"row-click"},
      caret,
      el("td",{class:"l"}, el("div",{class:"name-cell"}, el("div",{},nomeLimpo(r.nome)),
        el("div",{class:"sub"}, r.cnpj?("CNPJ "+formatarCnpj(r.cnpj)):""))),
      el("td",{class:"l"}, el("span",{class:"pill",style:"border-color:var(--neg);color:var(--neg)"}, r.tipo||"—")),
      el("td",{class:"l",style:"white-space:nowrap"}, r.inicio||"—"),
      el("td",{class:"l"}, r.responsavel||"—"),
      el("td",{class:"l"}, r.uf||"—"));
    // linha de detalhe (oculta ate clicar)
    const det=el("tr",{class:"detail-row",style:"display:none"});
    const box=el("div",{class:"detail-box"});
    const g=el("div",{class:"detail-grid"});
    const put=(k,v)=>{ if(v) g.append(el("div",{}, el("div",{class:"dk"},k), el("div",{class:"dv"},v))); };
    put("CNPJ", r.cnpj?formatarCnpj(r.cnpj):null);
    put("Tipo de regime", r.tipo);
    put("Início", r.inicio);
    put("Responsável / liquidante", r.responsavel);
    put("Endereço", [r.endereco, r.municipio&&r.uf?`${r.municipio}/${r.uf}`:r.municipio||r.uf, r.cep?("CEP "+r.cep):null].filter(Boolean).join(" · "));
    put("E-mails", r.emails);
    put("Telefones", r.telefones);
    box.append(g);
    const acoes=el("div",{style:"margin-top:10px;display:flex;gap:14px;flex-wrap:wrap"});
    if(r.cod) acoes.append(el("a",{href:"javascript:void 0",style:"color:var(--accent);cursor:pointer;font-weight:600",onclick:()=>abrirModal(r.cod)},"Abrir perfil da instituição →"));
    acoes.append(htmlLink(`https://cnpj.biz/${(r.cnpj||"").replace(/\D/g,"")}`,"Consultar CNPJ ↗"));
    box.append(acoes);
    const dtd=el("td",{colspan:6}); dtd.append(box); det.append(dtd);
    tr.onclick=(e)=>{ if(e.target.closest("a"))return;
      const open=det.style.display!=="none"; det.style.display=open?"none":"table-row";
      caret.textContent=open?"▸":"▾"; };
    tb.append(tr, det);
  });
  wrap.append(tbl); content.append(wrap);
  content.append(el("p",{class:"csub",style:"margin-top:10px"},"Fonte: ",
    htmlLink("https://www.bcb.gov.br/estabilidadefinanceira/regimesespeciais","BCB — Regimes especiais")));

  // penalidades: resumo + recentes
  content.append(secTitle("Processo administrativo sancionador — penalidades",
    "Penalidades aplicadas pelo BCB ao fim de processos administrativos sancionadores (descumprimento de normas), por CNPJ/CPF. Fonte: dados abertos Gepad/BCB."));
  content.append(el("p",{class:"csub",style:"margin:-6px 0 12px;max-width:880px"},
    "Penalidades aplicadas pelo BCB a instituições e pessoas, por CNPJ/CPF. Resumo por tipo e as 300 decisões mais recentes."));
  content.append(grid("g-2",
    card(h3i("Por tipo de penalidade","Distribuição das penalidades por tipo (multa, inabilitação, advertência, etc.)."), barMini(d.penalidades_por_tipo||[])),
    card(h3i("Por situação","Situação atual de cada penalidade (ex.: definitiva, em recurso)."), barMini(d.penalidades_por_situacao||[])),
  ));
  const recentes=d.penalidades_recentes||[];
  const w2=el("div",{class:"tablewrap",style:"margin-top:14px"});
  const t2=el("table"); t2.append(el("thead",{},el("tr",{},
    el("th",{class:"l"},"Instituição / Pessoa"),
    thI("Decisão","Data da decisão que aplicou a penalidade.","l"),
    thI("Penalidade","Tipo de penalidade aplicada (multa, inabilitação, advertência, etc.).","l"),
    thI("Multa (R$)","Valor da multa, quando a penalidade for pecuniária."),
    thI("Situação","Situação atual da penalidade no processo.","l"))),el("tbody"));
  const tb2=t2.querySelector("tbody");
  recentes.forEach(p=>tb2.append(el("tr",{},
    el("td",{class:"l"}, el("div",{class:"name-cell"}, el("div",{},nomeLimpo(p.nome||"—")),
      el("div",{class:"sub"}, p.cnpj8?("raiz "+p.cnpj8):""))),
    el("td",{class:"l"}, p.data_decisao||"—"),
    el("td",{class:"l"}, p.tipo_penalidade||"—"),
    el("td",{class:"num"}, p.valor_multa!=null?fmtR$(p.valor_multa):"—"),
    el("td",{class:"l"}, p.situacao||"—"))));
  w2.append(t2); content.append(w2);
  content.append(el("p",{class:"csub",style:"margin-top:12px"},"Fonte: ",
    htmlLink("https://www.bcb.gov.br/acessoinformacao/processadministrativosancionador","BCB — Processo administrativo sancionador"),
    " · dados abertos (Gepad)."));
}
const EVENTO_COR={
  "Cancelamento de autorização":"var(--neg)", "Liquidação extrajudicial":"var(--neg)",
  "Intervenção / RAET":"var(--neg)", "Controle societário":"var(--warn)",
  "Autorização / funcionamento":"var(--pos)", "Dirigentes / órgãos":"var(--ink-3)",
};
async function eventosSecao(container){
  const sec=el("div",{}); container.append(sec);
  sec.append(secTitle("Eventos recentes — comunicados do BCB"),
    el("div",{class:"loading"},"Carregando comunicados…"));
  let d; try{ d = estado.eventos || (estado.eventos = await api.eventos()); }
  catch(e){ sec.innerHTML=""; return; }
  sec.innerHTML="";
  const itens=d.itens||[];
  if(!itens.length){ return; }
  sec.append(secTitle("Eventos recentes — comunicados do BCB",
    "Comunicados oficiais do BCB que tratam de instituições (ex.: intenção de cancelar autorização, liquidação, intervenção, mudança de controle). Classificados por palavra-chave a partir do texto do comunicado; os de política monetária (leilões, swap, TBF) são filtrados fora."));
  sec.append(el("p",{class:"csub",style:"margin:-6px 0 12px;max-width:880px"},
    `Comunicados oficiais do BCB sobre instituições (até o nº ${d.numero_max||""}). `+
    "Cada evento tem link direto para o comunicado. Deixamos de fora os comunicados de política "+
    "monetária (leilões, swap, TBF). “Dirigentes” (posse/eleição) vem desligado por ser rotineiro."));
  // filtros por categoria (Dirigentes off por padrao)
  const cats=(d.por_categoria||[]).map(c=>c.k);
  const ativo={}; cats.forEach(c=> ativo[c] = !/Dirigentes/.test(c));
  const bar=el("div",{class:"filterbar",style:"flex-wrap:wrap;gap:6px"});
  const busca=el("input",{type:"search",placeholder:"Buscar no assunto…",oninput:()=>render()});
  const fcount=el("span",{class:"fcount"});
  const chips=cats.map(c=>{
    const n=(d.por_categoria.find(x=>x.k===c)||{}).n||0;
    const b=el("button",{class:"chip-tgl",onclick:()=>{ativo[c]=!ativo[c];b.classList.toggle("off",!ativo[c]);render();}},
      `${c} (${n})`);
    if(!ativo[c]) b.classList.add("off");
    b.style.borderColor=EVENTO_COR[c]||"var(--line)";
    return b;
  });
  bar.append(...chips,
    info("Cada etiqueta liga/desliga uma categoria de evento. 'Dirigentes' (posse/eleição) vem desligada por ser rotineira e volumosa. O número entre parênteses é a quantidade de eventos da categoria.","down"),
    withInfo(busca,"Busca no texto do assunto do comunicado."), fcount);
  const wrap=el("div",{class:"tablewrap"}); const tbl=el("table");
  tbl.append(el("thead",{},el("tr",{},
    thI("Data","Data de publicação do comunicado no Diário Oficial / site do BCB.","l"),
    thI("Evento","Categoria do evento, classificada pelo assunto do comunicado.","l"),
    thI("Assunto","Resumo oficial do comunicado, como publicado pelo BCB.","l"),
    thI("Comunicado","Número do comunicado. Clique no link para abrir o comunicado oficial no site do BCB."))),el("tbody"));
  const tb=tbl.querySelector("tbody"); wrap.append(tbl);
  sec.append(bar,wrap);
  function render(){
    const q=(busca.value||"").toLowerCase();
    const rows=itens.filter(i=>ativo[i.categoria] && (!q || (i.assunto||"").toLowerCase().includes(q)));
    tb.innerHTML="";
    const frag=document.createDocumentFragment();
    rows.forEach(i=>frag.append(el("tr",{},
      el("td",{class:"l",style:"white-space:nowrap;color:var(--ink-2)"}, i.data||(i.data_texto||"").slice(0,10)),
      el("td",{class:"l"}, el("span",{class:"pill",style:`border-color:${EVENTO_COR[i.categoria]||"var(--line)"};color:${EVENTO_COR[i.categoria]||"var(--ink-2)"}`}, i.categoria)),
      el("td",{class:"l cell-wrap"}, i.assunto||"—"),
      el("td",{style:"white-space:nowrap"}, htmlLink(i.url, `Nº ${i.numero} ↗`)))));
    tb.append(frag);
    fcount.textContent=`${rows.length} eventos`;
  }
  render();
}
function barMini(itens){
  // mini-barras horizontais (sem ECharts) para distribuições categóricas
  const max=Math.max(1,...itens.map(i=>i.n));
  const box=el("div",{style:"margin-top:8px"});
  itens.slice(0,8).forEach(i=>{
    const row=el("div",{style:"display:flex;align-items:center;gap:8px;margin:4px 0"});
    row.append(el("div",{style:"flex:0 0 46%;font-size:12px;color:var(--ink-2);text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"},i.k),
      el("div",{style:`flex:0 0 ${Math.max(2,100*i.n/max*0.4)}px;height:12px;border-radius:3px;background:#3987e5`}),
      el("div",{class:"num",style:"font-size:12px"},fmtInt(i.n)));
    box.append(row);
  });
  return box;
}

// ================================================================ TARIFAS DE SERVIÇOS
async function viewTarifas(){
  crumbs.innerHTML='Tarifas de serviços <span class="muted">· por grupo e por instituição</span>';
  const d = estado.tarifasGrupos || (estado.tarifasGrupos = await api.tarifas());
  const grupos=d.grupos||[];
  content.innerHTML="";
  content.append(
    el("div",{class:"csub",style:"max-width:860px;margin-bottom:16px"},
      "Tarifas de serviços padronizados cobradas pelas instituições, publicadas no BCB. "+
      "Escolha um grupo consolidado para listar as instituições e, em cada uma, ver as tarifas (consulta ao vivo por CNPJ). "+
      "Você também pode abrir qualquer instituição pela busca no topo e ver a aba “Tarifas de serviços”."),
    secTitle("Grupos consolidados",
      "Agrupamentos de instituições usados pelo BCB para publicar tarifas (ex.: um conglomerado e suas controladas). Clique num grupo para listar as instituições e consultar o tarifário de cada uma."),
  );
  const grid=el("div",{class:"fonte-grid"});
  grupos.forEach(g=>{
    const cardEl=el("div",{class:"fonte-card",style:"cursor:pointer"},
      el("div",{class:"fh"}, el("h4",{},g.nome)),
      el("div",{class:"pill"},"grupo "+g.codigo),
      el("div",{class:"fd"},"Ver instituições e tarifas →"));
    cardEl.onclick=()=>abrirGrupoTarifas(g);
    grid.append(cardEl);
  });
  content.append(grid, el("div",{id:"grpTarifasBox",style:"margin-top:18px"}));
}
async function abrirGrupoTarifas(g){
  const box=byId("grpTarifasBox"); if(!box) return;
  box.innerHTML='<div class="loading">Consultando instituições do grupo no BCB…</div>';
  let d; try{ d=await api.tarifasGrupo(g.codigo); }catch(e){ box.innerHTML='<div class="empty">Não foi possível consultar agora.</div>'; return; }
  const itens=(d&&d.itens)||[];
  box.innerHTML="";
  box.append(secTitle(`Instituições — ${g.nome} (${itens.length})`));
  if(d.erro || !itens.length){ box.append(el("div",{class:"empty"},d.erro?("Consulta indisponível: "+d.erro):"Nenhuma instituição neste grupo.")); return; }
  const bar=el("div",{class:"filterbar"});
  const inp=el("input",{type:"search",placeholder:"Buscar instituição / CNPJ…",oninput:e=>render(e.target.value.toLowerCase())});
  const fc=el("span",{class:"fcount"});
  bar.append(inp,fc);
  const wrap=el("div",{class:"tablewrap"});
  const tbl=el("table"); tbl.append(el("thead",{},el("tr",{},
    el("th",{class:"l"},"Instituição"),el("th",{class:"l"},"CNPJ (raiz)"),el("th",{class:"l"},""))),el("tbody"));
  wrap.append(tbl); box.append(bar,wrap);
  function render(q=""){
    const tb=tbl.querySelector("tbody"); tb.innerHTML="";
    const rows=itens.filter(i=>!q||((i.nome||"")+" "+(i.cnpj8||"")).toLowerCase().includes(q));
    const frag=document.createDocumentFragment();
    rows.slice(0,800).forEach(i=>{
      const tr=el("tr",{onclick:()=>abrirTarifasModal(i.cnpj8,i.nome)},
        el("td",{class:"l"},i.nome||"—"),el("td",{class:"l"},i.cnpj8||"—"),
        el("td",{class:"l"}, el("span",{class:"pill"},"ver tarifas")));
      frag.append(tr);
    });
    tb.append(frag);
    fc.textContent=`${rows.length} instituições`+(rows.length>800?" · exibindo 800":"");
  }
  render();
}
async function abrirTarifasModal(cnpj8, nome){
  const ov=el("div",{class:"modal-overlay",onclick:e=>{if(e.target===ov)fecharModal();}});
  const modal=el("div",{class:"modal"});
  ov.append(modal); document.body.append(ov);
  requestAnimationFrame(()=>ov.classList.add("open"));
  modal.innerHTML='<div class="loading">Consultando tarifas no BCB…</div>';
  let t; try{ t=await api.tarifasIf(cnpj8); }catch(e){ modal.innerHTML='<div class="empty">Não foi possível consultar.</div>'; return; }
  const itens=(t&&t.itens)||[];
  modal.innerHTML="";
  modal.append(el("div",{class:"modal-head"},
    el("button",{class:"close",onclick:fecharModal,title:"Fechar (Esc)"},"✕"),
    el("h2",{},nome||("CNPJ "+cnpj8)),
    el("div",{class:"modal-tags"}, tag("CNPJ raiz "+cnpj8), tag(itens.length+" tarifas","var(--accent)"))));
  const body=el("div",{class:"modal-body"}); modal.append(body);
  if(t.erro || !itens.length){
    body.append(el("div",{class:"card"},el("h3",{},"Sem tarifário publicado"),
      el("p",{style:"color:var(--ink-2);line-height:1.6"},"Esta instituição não tem lista de tarifas de serviços publicada no BCB para este CNPJ.")));
  }else{
    const wrap=el("div",{class:"tablewrap"});
    const tbl=el("table"); tbl.append(el("thead",{},el("tr",{},
      el("th",{class:"l"},"Serviço"),el("th",{class:"l"},"Unidade"),el("th",{},"Valor máx."),el("th",{class:"l"},"Vigência"))),el("tbody"));
    const tb=tbl.querySelector("tbody");
    itens.sort((a,b)=>(a.codigo||"").localeCompare(b.codigo||""));
    itens.forEach(it=>tb.append(el("tr",{},
      el("td",{class:"l"},it.servico||"—"),el("td",{class:"l"},it.unidade||"—"),
      el("td",{class:"num"},it.tipo_valor==="Real"?fmtR$(it.valor_maximo):(fmtNum(it.valor_maximo,2)+(it.tipo_valor==="Percentual"?"%":""))),
      el("td",{class:"l"},it.vigencia||"—"))));
    wrap.append(tbl); body.append(wrap);
  }
  body.append(el("p",{class:"csub",style:"margin-top:12px"},"Fonte: ",
    htmlLink("https://www.bcb.gov.br/estabilidadefinanceira/tarifas","BCB — Informes · Tarifas de serviços por instituição")));
}

// ================================================================ FONTES
async function viewFontes(){
  crumbs.textContent="Fontes de dados";
  const d = estado.fontes || (estado.fontes = await api.fontes());
  content.innerHTML="";
  content.append(el("div",{class:"csub",style:"max-width:780px;margin-bottom:18px"},
    "Todos os dados do painel vêm de fontes públicas e oficiais. Cada fonte abaixo traz o link direto para a API e para a página do órgão, para você comprovar a origem e a veracidade."));
  const grid=el("div",{class:"fonte-grid"});
  d.fontes.forEach(f=>{
    const card=el("div",{class:"fonte-card"},
      el("div",{class:"fh"}, el("h4",{},f.nome,
        info(f.status==="integrado"
          ?"Fonte integrada: os dados estão coletados no cache local e aparecem no painel."
          :"Fonte parcial/mapeada: identificada e linkada, mas ainda não totalmente integrada (ver descrição).","down")),
        el("span",{class:"badge-status "+(f.status==="integrado"?"integrado":"proxima")}, f.status)),
      el("div",{class:"pill"},f.dominio),
      el("div",{class:"fd"},f.desc),
      el("div",{class:"flinks"}, htmlLink(f.url,"API / dados"), f.site?htmlLink(f.site,"Página oficial"):null));
    grid.append(card);
  });
  content.append(grid);
}

// ================================================================ EM BREVE
function viewEmBreve(titulo,desc,fonte,link){
  crumbs.textContent=titulo;
  content.innerHTML="";
  content.append(el("div",{class:"card",style:"max-width:720px"},
    el("h3",{},titulo+" — próxima onda"),
    el("p",{style:"color:var(--ink-2);line-height:1.6"},desc),
    el("p",{class:"csub"},"Fonte já mapeada: ",htmlLink(link,fonte)),
    el("p",{class:"csub"},"A infraestrutura de coleta/cache já está pronta para receber este domínio. Veja todas as fontes em ",htmlLink("#/fontes","Fontes de dados"),".")));
}

// ---------------------------------------------------------------- busca global
function setupBusca(){
  const inp=document.getElementById("globalSearch"), box=document.getElementById("gsResults");
  let t;
  inp.addEventListener("input",()=>{ clearTimeout(t); t=setTimeout(async()=>{
    const q=inp.value.trim().toLowerCase();
    if(q.length<2){ box.classList.remove("open"); return; }
    const itens=await getRegistro();
    const hits=itens.filter(i=>nomeLimpo(i.nome).toLowerCase().includes(q)).slice(0,14);
    box.innerHTML="";
    hits.forEach(i=>box.append(el("a",{href:"javascript:void 0",
      onclick:()=>{box.classList.remove("open");inp.value="";abrirModal(i.cod);}},
      el("span",{class:"nm"},nomeLimpo(i.nome)), el("span",{class:"pill"},i.grupo))));
    box.classList.toggle("open",hits.length>0);
  },150); });
  document.addEventListener("click",e=>{ if(!e.target.closest(".global-search")) box.classList.remove("open"); });
}

// ---- no celular, recolhe uma barra de filtros longa atrás de um botão (busca e contador ficam à vista)
function recolhivel(bar){
  bar.classList.add("recolhe");
  const btn=el("button",{class:"btn f-toggle",type:"button","aria-expanded":"false"});
  btn.textContent="Filtros ▾";
  btn.onclick=()=>{ const aberto=bar.classList.toggle("open");
    btn.setAttribute("aria-expanded",aberto); btn.textContent=aberto?"Ocultar filtros ▴":"Filtros ▾"; };
  bar.firstElementChild.after(btn);
}

// ---- menu lateral deslizante (telas estreitas)
function setupMenuMobile(){
  const btn=byId("navToggle");
  const set=aberto=>{ document.body.classList.toggle("nav-open",aberto); btn.setAttribute("aria-expanded",aberto); };
  btn.onclick=()=>set(!document.body.classList.contains("nav-open"));
  byId("navBackdrop").onclick=()=>set(false);
  window.addEventListener("hashchange",()=>set(false));
  document.addEventListener("keydown",e=>{ if(e.key==="Escape") set(false); });
}

// ---- ajusta a direção do balão "ⓘ" conforme o espaço disponível (evita corte)
function posicionarTip(){
  const ajusta=ic=>{
    const r=ic.getBoundingClientRect();
    // horizontal: o balão (~300px) cresce p/ a direita; se não couber, ancora à direita (cresce p/ a esquerda)
    ic.classList.toggle("left", (window.innerWidth - r.left) < 312);
    // vertical: prefere para baixo; se faltar espaço abaixo e houver acima, abre para cima
    const abaixo=window.innerHeight - r.bottom, acima=r.top;
    if(abaixo < 150 && acima > 150) ic.classList.remove("down");
    else ic.classList.add("down");
  };
  const h=e=>{ const ic=e.target.closest && e.target.closest(".info-i"); if(ic) ajusta(ic); };
  document.addEventListener("pointerover", h, true);
  document.addEventListener("focusin", h, true);
}

// ---------------------------------------------------------------- helpers
function byId(id){ return document.getElementById(id); }
function cmp(a,b){ if(a==null)a=-Infinity; if(b==null)b=-Infinity; return typeof a==="string"?a.localeCompare(b,"pt-BR"):a-b; }
function segBadge(s){ const b=el("span",{class:"seg-badge"},s); b.style.background=SEG_COR[s]||"#555"; return b; }
function segTag(s){ const t=el("span",{class:"pill",title:SEG_DESC[s]},"Seg "+s); t.style.borderColor=SEG_COR[s]; t.style.color=SEG_COR[s]; return t; }
function tag(txt,cor){ const t=el("span",{class:"pill"},txt); if(cor){t.style.borderColor=cor;t.style.color=cor;} return t; }
// ---- "ⓘ" de informação: ícone com tooltip explicando a lógica daquele dado/filtro
function info(tip, extraCls){
  if(!tip) return null;
  return el("span",{class:"info-i"+(extraCls?(" "+extraCls):""),tabindex:"0","data-tip":tip,
    title:tip,"aria-label":tip,onclick:e=>e.stopPropagation()},"i");
}
// envolve um nó (ex.: um <select>) com um ícone "ⓘ" ao lado
function withInfo(node, tip){
  if(!tip) return node;
  return el("span",{class:"f-field"}, node, info(tip,"down"));
}
// cabeçalho de card (h3) com "ⓘ"
function h3i(txt, tip){ return el("h3",{}, txt, info(tip, "down")); }
// cabeçalho de coluna de tabela com "ⓘ" (abre para baixo p/ não cortar no topo)
function thI(label, tip, cls, onclick){
  const th=el("th",{class:cls||"",onclick:onclick||null}, label, tip?info(tip,"down"):null);
  return th;
}
function secTitle(t, tip){ return el("div",{class:"section-title"}, t, info(tip,"down")); }
function card(...k){ return el("div",{class:"card"},k); }
function grid(c,...k){ return el("div",{class:"grid "+c},k); }
function kpiRow(items){ return el("div",{class:"kpi-row"}, items.map(([l,v,s,tip])=>
  el("div",{class:"kpi"}, el("div",{class:"k-lbl"},l,info(tip,"down")), el("div",{class:"k-val"},v), s?el("div",{class:"k-sub"},s):null))); }
function defGrid(defs){ return el("div",{class:"deflist"}, defs.map(([k,v])=>
  el("div",{class:"def"}, el("div",{class:"dk"},k), el("div",{class:"dv"}, v&&v.nodeType?v:document.createTextNode(v==null?"—":v))))); }
function htmlLink(url,label){ return el("a",{href:url,target:url.startsWith("#")?null:"_blank",rel:"noopener"}, label||url); }
function relatoriosBloco(d){
  const box=el("div",{});
  Object.entries(d.relatorios).forEach(([rel,contas])=>{
    const det=el("details",{class:"rel"}, el("summary",{},el("span",{},d.relatorios_nomes[rel]||("Relatório "+rel)),el("span",{class:"cnt"},contas.length+" contas")));
    const tbl=el("table",{class:"acct-table"}); let g=null;
    contas.forEach(ct=>{ if(ct.grupo&&ct.grupo!==g){ g=ct.grupo; tbl.append(el("tr",{},el("td",{class:"acct-grp",colspan:2},ct.grupo))); }
      tbl.append(el("tr",{},el("td",{},ct.coluna),el("td",{},fmtR$(ct.saldo)))); });
    det.append(tbl); box.append(det);
  });
  return box;
}
function siteDe(cj){
  if(cj.email && cj.email.includes("@")){ const dom=cj.email.split("@")[1];
    if(dom && !/(gmail|hotmail|outlook|yahoo|bol|uol)\./i.test(dom)) return "https://"+dom; }
  return null;
}
function endereco(cj){
  const p=[cj.descricao_tipo_de_logradouro,cj.logradouro,cj.numero].filter(Boolean).join(" ");
  return [p,cj.bairro,cj.cep].filter(Boolean).join(", ")||"—";
}
function formatarCnpj(c){ if(!c||c.length!==14) return c||"—";
  return `${c.slice(0,2)}.${c.slice(2,5)}.${c.slice(5,8)}/${c.slice(8,12)}-${c.slice(12)}`; }
