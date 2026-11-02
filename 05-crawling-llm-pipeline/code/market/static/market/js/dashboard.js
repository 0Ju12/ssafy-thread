/* Native SVG charting: no external JS chart dependencies. All market figures are data-derived. */
(()=>{
  'use strict';
  const NS='http://www.w3.org/2000/svg';
  const el=(tag,attrs={})=>{const node=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));return node;};
  const json=id=>{const node=document.getElementById(id);if(!node)return null;try{return JSON.parse(node.textContent)}catch{return null}};
  const fmt=(v,d=2)=>(v===null||v===undefined||v==='')?'—':Number(v).toLocaleString('ko-KR',{minimumFractionDigits:d,maximumFractionDigits:d});
  const marketSeries=json('mk-series-data')||[];
  const fxSeries=json('mk-fx-data')||[];
  const stockSeries=json('mk-stock-series')||[];
  let chartCounter=0;
  function plot(node,series,color='#5879ee'){
    if(!node)return;
    if(!Array.isArray(series)||series.length<2){node.innerHTML='<p class="mk-no-data">추이를 그리려면 서로 다른 시점의 실제 수집 기록이 2개 이상 필요합니다.</p>';return;}
    node.replaceChildren();
    const width=740,height=290,L=66,R=20,T=19,B=35;
    const vals=series.map(x=>Number(x.value)).filter(Number.isFinite);
    if(!vals.length)return;
    const min=Math.min(...vals),max=Math.max(...vals),span=Math.max(1,max-min),floor=min-span*.18,ceil=max+span*.22;
    const x=i=>L+(width-L-R)*i/Math.max(1,series.length-1);
    const y=v=>height-B-(Number(v)-floor)/(ceil-floor)*(height-T-B);
    const svg=el('svg',{viewBox:`0 0 ${width} ${height}`,preserveAspectRatio:'none','aria-hidden':'true'});
    const defs=el('defs'),gradId=`mk-gradient-${++chartCounter}`;
    const gradient=el('linearGradient',{id:gradId,x1:'0%',y1:'0%',x2:'0%',y2:'100%'});
    gradient.append(el('stop',{offset:'0%','stop-color':color,'stop-opacity':'0.27'}),el('stop',{offset:'100%','stop-color':color,'stop-opacity':'0.01'}));
    defs.append(gradient);svg.append(defs);
    for(let i=0;i<=4;i++){
      const value=floor+(ceil-floor)*i/4,gy=y(value);
      svg.append(el('line',{x1:L,x2:width-R,y1:gy,y2:gy,class:'mk-graph-grid'}));
      const label=el('text',{x:L-12,y:gy+3,'text-anchor':'end',class:'mk-graph-label'});label.textContent=fmt(value,value<100?2:0);svg.append(label);
    }
    const tickIndices=[0,Math.floor((series.length-1)/2),series.length-1];
    [...new Set(tickIndices)].forEach(i=>{
      const label=el('text',{x:x(i),y:height-12,'text-anchor':i===0?'start':i===series.length-1?'end':'middle',class:'mk-graph-label'});
      label.textContent=String(series[i].date||'').slice(5);svg.append(label);
    });
    const coords=series.map((p,i)=>[x(i),y(p.value)]);
    const path=coords.map((xy,i)=>(i?'L':'M')+xy[0].toFixed(1)+' '+xy[1].toFixed(1)).join(' ');
    svg.append(el('path',{d:path+` L ${x(series.length-1)} ${height-B} L ${x(0)} ${height-B} Z`,fill:`url(#${gradId})`}));
    svg.append(el('path',{d:path,class:'mk-path-line',stroke:color}));
    const dot=el('circle',{cx:x(series.length-1),cy:y(series[series.length-1].value),r:5,class:'mk-graph-dot'});svg.append(dot);
    const overlay=el('rect',{x:L,y:T,width:width-L-R,height:height-T-B,fill:'transparent'});svg.append(overlay);
    node.append(svg);
    const tooltip=document.createElement('div');tooltip.className='mk-tooltip';tooltip.hidden=true;node.append(tooltip);
    overlay.addEventListener('pointermove',ev=>{
      const bounds=svg.getBoundingClientRect();const ux=(ev.clientX-bounds.left)*width/bounds.width;
      const ix=Math.min(series.length-1,Math.max(0,Math.round((ux-L)/((width-L-R)/Math.max(1,series.length-1)))));
      dot.setAttribute('cx',x(ix));dot.setAttribute('cy',y(series[ix].value));
      tooltip.replaceChildren();const dat=document.createElement('span');dat.textContent=series[ix].date;
      const num=document.createElement('strong');num.textContent=fmt(series[ix].value);tooltip.append(dat,num);
      tooltip.style.left=Math.min(90,Math.max(13,100*x(ix)/width))+'%';tooltip.style.top=Math.max(22,100*y(series[ix].value)/height)+'%';tooltip.hidden=false;
    });
    overlay.addEventListener('pointerleave',()=>{tooltip.hidden=true;dot.setAttribute('cx',x(series.length-1));dot.setAttribute('cy',y(series[series.length-1].value));});
  }
  const byName=name=>marketSeries.find(s=>s.name===name);
  function selectMarket(name){
    const data=byName(name);
    document.querySelectorAll('[data-market-series]').forEach(b=>b.classList.toggle('active',b.dataset.marketSeries===name));
    plot(document.getElementById('mk-main-chart'),data?data.history:[]);
  }
  document.querySelectorAll('[data-market-series]').forEach(b=>b.addEventListener('click',()=>selectMarket(b.dataset.marketSeries)));
  if(document.getElementById('mk-main-chart'))selectMarket(marketSeries[0]?.name||'KOSPI');
  plot(document.getElementById('mk-fx-chart'),fxSeries,'#23a5a3');
  plot(document.getElementById('mk-stock-chart'),stockSeries);
  marketSeries.forEach(s=>{
    const target=document.querySelector('[data-spark="'+s.name+'"]');
    if(!target||!s.history?.length)return;
    const values=s.history.map(d=>Number(d.value)),mi=Math.min(...values),ma=Math.max(...values),scale=Math.max(1,ma-mi),w=240,h=34;
    const coords=values.map((v,i)=>`${i*w/Math.max(1,values.length-1)},${h-3-(v-mi)/scale*(h-8)}`);
    const svg=el('svg',{viewBox:`0 0 ${w} ${h}`,preserveAspectRatio:'none',role:'img','aria-label':s.name+' 변화 미니 차트'});
    svg.append(el('polyline',{points:coords.join(' '),fill:'none',stroke:s.change_pct<0?'#477de7':'#e65374','stroke-width':2.5,'stroke-linecap':'round','stroke-linejoin':'round'}));target.append(svg);
  });
  const ranks=json('mk-ranking-data');
  if(ranks){
    let mode='rise',market='ALL';
    const body=document.getElementById('mk-rank-body');
    const td=(tr,txt,klass)=>{const c=document.createElement('td');c.textContent=txt;if(klass)c.className=klass;tr.append(c);return c;};
    const render=()=>{
      if(!body)return;
      body.replaceChildren();
      const rows=ranks[mode]?.[market]||[];
      if(!rows.length){const tr=document.createElement('tr');td(tr,'해당 조건의 종목이 없습니다.','mk-table-empty').colSpan=7;body.append(tr);return;}
      rows.forEach((s,i)=>{
        const tr=document.createElement('tr');td(tr,String(i+1));
        let c=td(tr,'');const a=document.createElement('a');a.className='mk-stock-link';a.href=s.code?'/market/stocks/'+encodeURIComponent(s.code)+'/'+(window.THREAD_MARKET_DEMO?'?demo=1':''):'/?company='+encodeURIComponent(s.name)+'#search-title';a.textContent=s.name;c.append(a);const code=document.createElement('span');code.className='mk-stock-code';code.textContent=s.code||'코드 미확인';c.append(code);
        td(tr,s.market||'미분류');td(tr,fmt(s.price,0),'mk-align-right');
        c=td(tr,(s.change_pct>0?'+':'')+fmt(s.change_pct)+(s.change_pct==null?'':'%'),'mk-align-right');c.classList.add(s.change_pct<0?'mk-fall':'mk-rise');
        td(tr,fmt(s.value,0),'mk-align-right');
        c=td(tr,'','mk-align-right');const action=document.createElement('a');action.className='mk-analysis-link';action.href='/?company='+encodeURIComponent(s.name)+'#search-title';action.textContent='댓글 분석 ↗';c.append(action);
        body.append(tr);
      });
    };
    document.querySelectorAll('[data-rank]').forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.rank;document.querySelectorAll('[data-rank]').forEach(x=>x.classList.toggle('active',x===b));render();}));
    document.querySelectorAll('[data-market]').forEach(b=>b.addEventListener('click',()=>{market=b.dataset.market;document.querySelectorAll('[data-market]').forEach(x=>x.classList.toggle('active',x===b));render();}));
  }
})();
