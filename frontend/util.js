// Constantes de dominio e formatacao

export const SEGS = ["S1","S2","S3","S4","S5","NA"];
export const SEG_COR = {S1:"#3987e5",S2:"#e2692f",S3:"#1aa978",S4:"#e0a52a",S5:"#dd6499",NA:"#6b6a66"};
export const SEG_DESC = {
  S1:"≥ 10% do PIB ou atividade internacional relevante",
  S2:"porte entre 1% e 10% do PIB",
  S3:"porte entre 0,1% e 1% do PIB",
  S4:"porte abaixo de 0,1% do PIB",
  S5:"cooperativas / não-bancárias de perfil simplificado",
  NA:"não segmentada (ex.: instituição de pagamento)"
};
export const TCB_LBL = {
  B1:"Banco comercial/múltiplo c/ carteira comercial, Caixa",
  B2:"Banco múltiplo s/ carteira comercial, invest., câmbio",
  B3S:"Cooperativa de crédito singular", B3C:"Cooperativa central de crédito",
  B4:"Banco de desenvolvimento / fomento",
  N1:"Não-bancária de crédito", N2:"Mercado de capitais",
  N3:"Administradora de consórcio", N4:"Instituição de pagamento"
};
export const TC_LBL = {1:"Público",2:"Privado Nacional",3:"Estrangeiro",4:"Estrangeiro"};

// Hierarquia de tipos (grupo -> cor) e rótulos de tipo
export const GRUPO_COR = {
  "Bancos":"#3987e5", "Cooperativas":"#1aa978", "Credito nao-bancario":"#e0a52a",
  "Mercado de capitais":"#6250d6", "Consorcios":"#dd6499", "Pagamentos":"#e2692f",
  "Outras":"#6b6a66"
};
export function grupoCor(g){ return GRUPO_COR[g] || "#6b6a66"; }

// metricas em percentual (fracao -> %)
export const PCT = new Set(["basileia","capital_n1","alavancagem","imobilizacao"]);

const nf = new Intl.NumberFormat("pt-BR");
export function fmtInt(v){ return v==null?"–":nf.format(Math.round(v)); }
export function fmtNum(v,d=0){ return v==null?"–":v.toLocaleString("pt-BR",{maximumFractionDigits:d}); }
export function fmtPct(frac,d=1){ return frac==null?"–":(frac*100).toLocaleString("pt-BR",{maximumFractionDigits:d})+"%"; }

// valores do Olinda ja vem em REAIS
export function fmtR$(v){
  if(v==null) return "–";
  const a=Math.abs(v), s=v<0?"-":"";
  if(a>=1e12) return s+"R$ "+(a/1e12).toLocaleString("pt-BR",{maximumFractionDigits:2})+" tri";
  if(a>=1e9)  return s+"R$ "+(a/1e9 ).toLocaleString("pt-BR",{maximumFractionDigits:2})+" bi";
  if(a>=1e6)  return s+"R$ "+(a/1e6 ).toLocaleString("pt-BR",{maximumFractionDigits:2})+" mi";
  if(a>=1e3)  return s+"R$ "+(a/1e3 ).toLocaleString("pt-BR",{maximumFractionDigits:0})+" mil";
  return s+"R$ "+nf.format(Math.round(a));
}
export function fmtMetric(alias,v){ return PCT.has(alias)?fmtPct(v):fmtR$(v); }

export function nomeLimpo(n){ return (n||"").replace(/\s*-\s*PRUDENCIAL\s*$/i,"").trim(); }
export function anomesLabel(a){ if(!a) return ""; return a.slice(4,6)+"/"+a.slice(0,4); }

export function el(tag, attrs={}, ...kids){
  const n=document.createElement(tag);
  for(const[k,v] of Object.entries(attrs)){
    if(k==="class") n.className=v;
    else if(k==="html") n.innerHTML=v;
    else if(k.startsWith("on")) n.addEventListener(k.slice(2),v);
    else if(v!=null) n.setAttribute(k,v);
  }
  for(const kid of kids.flat()){ if(kid!=null) n.append(kid.nodeType?kid:document.createTextNode(kid)); }
  return n;
}
