// Helpers de grafico (ECharts) com tema escuro consistente
import { fmtR$, fmtPct, SEG_COR } from "./util.js";

const INK="#f1f0ec", INK2="#b9b8b0", MUTED="#85847e", LINE="rgba(255,255,255,.08)";
const AX = { axisLine:{lineStyle:{color:LINE}}, axisLabel:{color:MUTED,fontSize:11},
             splitLine:{lineStyle:{color:LINE}}, axisTick:{show:false} };
const BASE = {
  backgroundColor:"transparent",
  textStyle:{fontFamily:"system-ui,-apple-system,Segoe UI,sans-serif",color:INK},
  grid:{left:8,right:16,top:16,bottom:8,containLabel:true},
  tooltip:{backgroundColor:"#1b1b20",borderColor:"rgba(255,255,255,.14)",
           textStyle:{color:INK,fontSize:12},confine:true},
};

const _inst = new WeakMap();
function mount(elm){
  let c=_inst.get(elm);
  if(!c){ c=echarts.init(elm,null,{renderer:"canvas"}); _inst.set(elm,c);
    new ResizeObserver(()=>c.resize()).observe(elm); }
  return c;
}

export function barH(elm, items, {money=true, pct=false}={}){
  const c=mount(elm);
  const cats=items.map(i=>i.label), vals=items.map(i=>i.v);
  const cols=items.map(i=>i.cor||"#3987e5");
  const fmt=pct?fmtPct:(money?fmtR$:(v=>v.toLocaleString("pt-BR")));
  c.setOption({...BASE,
    tooltip:{...BASE.tooltip,formatter:p=>`${p.name}<br><b>${fmt(p.value)}</b>`},
    xAxis:{type:"value",...AX,axisLabel:{...AX.axisLabel,formatter:v=>money&&!pct?abbr(v):fmt(v)}},
    yAxis:{type:"category",data:cats,inverse:true,...AX,axisLabel:{...AX.axisLabel,color:INK2}},
    series:[{type:"bar",data:vals.map((v,i)=>({value:v,itemStyle:{color:cols[i]}})),
      barWidth:"62%",itemStyle:{borderRadius:[0,4,4,0]},
      label:{show:true,position:"right",color:INK2,fontSize:11,formatter:p=>fmt(p.value)}}]},true);
}

export function linhas(elm, series, {pct=false}={}){
  const c=mount(elm);
  const fmt=pct?fmtPct:fmtR$;
  const cores=["#3987e5","#e0a52a","#1aa978","#dd6499"];
  c.setOption({...BASE,
    tooltip:{...BASE.tooltip,trigger:"axis",
      formatter:ps=>ps[0].axisValueLabel+"<br>"+ps.map(p=>`${p.marker}${p.seriesName}: <b>${fmt(p.value)}</b>`).join("<br>")},
    legend:series.length>1?{data:series.map(s=>s.nome),textStyle:{color:INK2},top:0,right:0}:undefined,
    xAxis:{type:"category",data:series[0].pontos.map(p=>p.x),...AX},
    yAxis:{type:"value",...AX,axisLabel:{...AX.axisLabel,formatter:v=>pct?(v*100).toFixed(0)+"%":abbr(v)}},
    series:series.map((s,i)=>({name:s.nome,type:"line",smooth:true,symbol:"circle",symbolSize:6,
      data:s.pontos.map(p=>p.y),lineStyle:{width:2,color:cores[i%4]},itemStyle:{color:cores[i%4]},
      areaStyle:series.length===1?{color:"rgba(57,135,229,.12)"}:undefined}))},true);
}

export function treemap(elm, items){
  const c=mount(elm);
  c.setOption({...BASE,
    tooltip:{...BASE.tooltip,formatter:p=>`${p.name}<br><b>${fmtR$(p.value)}</b>`},
    series:[{type:"treemap",roam:false,nodeClick:false,breadcrumb:{show:false},
      data:items.map(i=>({name:i.label,value:i.v,itemStyle:{color:i.cor}})),
      label:{color:"#0b0b0b",fontWeight:700,fontSize:13,formatter:p=>`${p.name}\n${abbr(p.value)}`},
      itemStyle:{borderColor:"#0c0c0e",borderWidth:2,gapWidth:2},
      levels:[{itemStyle:{borderWidth:0}}]}]},true);
}

export function donut(elm, value, total, cor="#3987e5"){
  const c=mount(elm);
  const pct=total?value/total:0;
  c.setOption({...BASE,
    series:[{type:"pie",radius:["68%","88%"],silent:true,label:{show:false},
      data:[{value:value,itemStyle:{color:cor}},{value:Math.max(0,total-value),itemStyle:{color:"#232329"}}]}],
    graphic:{type:"text",left:"center",top:"center",
      style:{text:(pct*100).toFixed(1)+"%",fill:INK,fontSize:24,fontWeight:700,fontFamily:"system-ui"}}},true);
}

function abbr(v){
  const a=Math.abs(v);
  if(a>=1e12) return (v/1e12).toFixed(1)+" tri";
  if(a>=1e9)  return (v/1e9 ).toFixed(0)+" bi";
  if(a>=1e6)  return (v/1e6 ).toFixed(0)+" mi";
  if(a>=1e3)  return (v/1e3 ).toFixed(0)+" mil";
  return String(v);
}
