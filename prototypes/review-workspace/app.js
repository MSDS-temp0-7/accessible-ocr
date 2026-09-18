(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const fixture = window.REVIEW_FIXTURE;
  const all = fixture.pages.flatMap(page => page.blocks.map(block => ({...block, page:page.id})));
  const byId = id => all.find(block => block.id === id);
  const storageKey = 'accessible-ocr-review-prototype-v1';
  const typeNames = {text:'본문',table:'표',graph:'그래프',music:'악보'};
  const statusNames = {pending:'미확인',needs_review:'검수 필요',reviewed:'확인 완료'};
  const state = {page:1,selected:all[0].id,mode:'reader',source:false,query:'',type:'all',needsOnly:false,zoom:100,font:100,contrast:false,shortcuts:true,edits:{},history:[]};
  let storageOK = true, announceTimer;
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || 'null');
    if(saved && saved.documentId === fixture.id){
      for(const [id,value] of Object.entries(saved.edits || {})){
        if(byId(id) && value && typeof value==='object') state.edits[id]={...(typeof value.text==='string'?{text:value.text}:{}),...(Object.hasOwn(statusNames,value.status)?{status:value.status}:{})};
      }
      state.history=Array.isArray(saved.history)?saved.history.slice(-100):[];
      if([100,125,150,200].includes(saved.font))state.font=saved.font;
      state.contrast=saved.contrast===true;
    }
  }catch{storageOK=false}
  const status = b => state.edits[b.id]?.status || b.status;
  const content = b => state.edits[b.id]?.text ?? b.text;
  const pageBlocks = () => all.filter(b=>b.page===state.page);
  const visible = () => pageBlocks().filter(b=>(!state.query || (b.title+' '+content(b)).toLocaleLowerCase('ko').includes(state.query.toLocaleLowerCase('ko'))) && (state.type==='all'||state.type===b.type||(state.type==='visual'&&['table','graph'].includes(b.type))) && (!state.needsOnly||status(b)==='needs_review'));
  const esc = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function announce(message){clearTimeout(announceTimer);$('announcement').textContent='';announceTimer=setTimeout(()=>$('announcement').textContent=message,50)}
  function save(){try{localStorage.setItem(storageKey,JSON.stringify({documentId:fixture.id,edits:state.edits,history:state.history.slice(-100),font:state.font,contrast:state.contrast}));storageOK=true}catch{storageOK=false}$('saveState').textContent=storageOK?'이 브라우저에 검수 기록 저장':'브라우저 저장을 사용할 수 없습니다. 검수 기록 저장으로 파일을 받아 주세요.'}
  function record(action,b){state.history.push({at:new Date().toISOString(),action,id:b.id});save()}
  function renderNavigation(){
    $('pageNav').innerHTML=fixture.pages.map(p=>`<button class="page-link" data-page="${p.id}" ${state.page===p.id?'aria-current="page"':''}><span class="page-icon" aria-hidden="true">${p.id}</span><span class="page-name">${esc(p.title)}<small>${esc(p.subtitle)}</small></span></button>`).join('');
    const complete=all.filter(b=>status(b)==='reviewed').length,needs=all.filter(b=>status(b)==='needs_review').length;
    $('progressCount').textContent=`${complete} / ${all.length} 항목`;$('reviewProgress').max=all.length;$('reviewProgress').value=complete;$('pendingCount').textContent=`검수 필요 ${needs}개 · 미확인 ${all.length-complete-needs}개`;
    $('nextNeedsSidebar').disabled=needs===0;
  }
  function blockMarkup(b,index){
    const number=pageBlocks().findIndex(x=>x.id===b.id)+1;
    let body=`<p>${esc(content(b))}</p>`;
    if(b.rows)body+=`<details><summary>표를 행과 열로 읽기</summary><table><caption>예시 원본의 표 구조 · 인식 내용 수정과 별도로 대조합니다.</caption><thead><tr>${b.headers.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${b.rows.map(row=>`<tr>${row.map((cell,i)=>i===0?`<th scope="row">${esc(cell)}</th>`:`<td>${esc(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table></details>`;
    if(b.detail)body+=`<details><summary>${b.type==='music'?'마디별 읽기 펼치기':'축·수치 상세 읽기'}</summary><p>${esc(b.detail)}</p></details>`;
    return `<article class="result-block${state.selected===b.id?' is-selected':''}" data-block="${b.id}" aria-labelledby="title-${b.id}"><div class="block-topline"><span class="block-number" aria-hidden="true">${number}</span><span>${typeNames[b.type]}</span><span class="status-chip ${status(b)}">${statusNames[status(b)]}</span></div><h3 id="title-${b.id}" aria-label="${esc(b.title)}"><button class="block-select" data-select="${b.id}" ${state.selected===b.id?'aria-current="true"':''} aria-label="${number}번 ${esc(b.title)}, ${typeNames[b.type]}, ${statusNames[status(b)]}. 선택하고 원본 위치 확인">${esc(b.title)}</button></h3><div class="block-content">${body}</div>${b.reason&&status(b)==='needs_review'?`<p class="review-note">${esc(b.reason)}</p>`:''}${state.edits[b.id]?.text!==undefined?'<div class="edited-label">수정한 내용 · AI 인식 원문은 내용 수정에서 확인</div>':''}<div class="block-bottom"><span>${b.page}페이지 · ${number}번 영역</span><button class="quiet" data-show-source="${b.id}">원본에서 확인 <span aria-hidden="true">↗</span></button></div></article>`;
  }
  function renderReading(){
    const page=fixture.pages.find(p=>p.id===state.page),list=visible();
    $('pageCounter').textContent=`${state.page} / ${fixture.pages.length}쪽`;$('pageDescription').textContent=page.title;$('visibleCount').textContent=`${list.length}개 항목`;
    $('blockList').innerHTML=list.map(blockMarkup).join('');$('emptyState').hidden=list.length!==0;
    $('readingFooterLabel').textContent=`${state.page} / ${fixture.pages.length}페이지`;$('previousPage').disabled=state.page===1;$('nextPage').disabled=state.page===fixture.pages.length;
  }
  function renderSource(){
    const page=fixture.pages.find(p=>p.id===state.page);
    $('sourceImage').src=page.image;$('sourceImage').alt=`${state.page}페이지 예시 원본: ${page.title}. 대응하는 텍스트는 인식 결과 영역에서 읽을 수 있습니다.`;
    $('overlays').innerHTML=pageBlocks().map((b,i)=>{const [x,y,w,h]=b.bbox;return `<button class="region-button" data-region="${b.id}" aria-pressed="${state.selected===b.id}" aria-label="원본 ${i+1}번 영역, ${esc(b.title)}. 인식 결과 선택" style="left:${x/8}%;top:${y/11.2}%;width:${w/8}%;height:${h/11.2}%"><span aria-hidden="true">${i+1}</span></button>`}).join('');
    $('pageImage').style.width=state.zoom+'%';$('zoomLabel').textContent=state.zoom+'%';$('zoomOut').disabled=state.zoom===75;$('zoomIn').disabled=state.zoom===200;
  }
  function renderMode(){
    $('readerMode').setAttribute('aria-pressed',state.mode==='reader');$('reviewMode').setAttribute('aria-pressed',state.mode==='review');$('sourceToggle').setAttribute('aria-pressed',state.source);$('contrastBtn').setAttribute('aria-pressed',state.contrast);
    $('sourcePanel').hidden=!state.source;$('workspace').classList.toggle('with-source',state.source);$('reviewBar').hidden=state.mode!=='review';$('modeLabel').textContent=state.mode==='reader'?'READING / 읽기':'REVIEW / 교차 검수';document.title=(state.mode==='reader'?'문서 읽기':'교차 검수')+' · 접근형 OCR 시제품';
    document.body.classList.toggle('high-contrast',state.contrast);document.documentElement.style.setProperty('--body-size',18*state.font/100+'px');$('textSizeLabel').textContent=state.font+'%';$('textSizeBtn').setAttribute('aria-label',`글자 크기 ${state.font}퍼센트. 누르면 ${state.font===200?'100퍼센트로 돌아갑니다':'확대합니다'}`);
  }
  function renderSelection(){
    const b=byId(state.selected),isVisible=b&&visible().some(x=>x.id===b.id);
    $('selectionLabel').textContent=b?b.title:'선택한 항목 없음';$('selectionStatus').textContent=b?statusNames[status(b)]:'';
    ['editBtn','flagBtn','approveBtn'].forEach(id=>$(id).disabled=!isVisible);
    $('sourceHint').textContent=b?`${b.page}페이지 · ${pageBlocks().findIndex(x=>x.id===b.id)+1}번 ${typeNames[b.type]} 선택됨`:'항목을 선택하면 원본 위치가 강조됩니다.';
    document.querySelectorAll('[data-block]').forEach(el=>el.classList.toggle('is-selected',el.dataset.block===state.selected));
    document.querySelectorAll('[data-select]').forEach(el=>{if(el.dataset.select===state.selected)el.setAttribute('aria-current','true');else el.removeAttribute('aria-current')});
    document.querySelectorAll('[data-region]').forEach(el=>el.setAttribute('aria-pressed',el.dataset.region===state.selected));
  }
  function render(){renderNavigation();renderReading();renderSource();renderMode();renderSelection();$('saveState').textContent=storageOK?'이 브라우저에 검수 기록 저장':'브라우저 저장을 사용할 수 없습니다. 검수 기록을 파일로 저장해 주세요.'}
  function revealRegion(){if(!state.source)return;requestAnimationFrame(()=>{const node=document.querySelector(`[data-region="${state.selected}"]`);if(!node)return;const scroller=$('imageScroll'),r=node.getBoundingClientRect(),v=scroller.getBoundingClientRect();if(r.top<v.top+28||r.bottom>v.bottom-24)scroller.scrollTop+=r.top-v.top-45;if(r.left<v.left||r.right>v.right)scroller.scrollLeft+=r.left-v.left-20})}
  function select(id,{focus=false,showSource=false}={}){
    const b=byId(id);if(!b)return;
    const changedPage=state.page!==b.page;state.page=b.page;state.selected=id;
    if(showSource)state.source=true;
    if(!visible().some(x=>x.id===id)){state.query='';state.type='all';state.needsOnly=false;$('search').value='';$('typeFilter').value='all';$('needsOnly').checked=false;renderReading()}
    if(changedPage)render();else{renderMode();renderSelection()}
    if(focus){const button=document.querySelector(`[data-select="${id}"]`);button?.focus({preventScroll:true});button?.closest('article').scrollIntoView({block:'nearest',behavior:'instant'})}
    revealRegion();announce(`${b.page}페이지, ${b.title}, ${statusNames[status(b)]}${state.source?'. 원본 위치를 강조했습니다.':'. 선택했습니다.'}`);
  }
  function setPage(page){state.page=Math.max(1,Math.min(fixture.pages.length,page));state.selected=visible()[0]?.id??null;render();$('reading').focus({preventScroll:true});announce(`${state.page}페이지, ${fixture.pages[state.page-1].title}`)}
  function nextBlock(delta){const index=all.findIndex(b=>b.id===state.selected);const next=all[index+delta];if(next)select(next.id,{focus:true});else announce(delta>0?'마지막 항목입니다.':'첫 번째 항목입니다.')}
  function nextNeeds(){const start=all.findIndex(b=>b.id===state.selected);const ordered=[...all.slice(start+1),...all.slice(0,start+1)];const next=ordered.find(b=>status(b)==='needs_review');if(next)select(next.id,{focus:true});else announce('검수 필요 항목이 없습니다.')}
  function setStatus(value,advance=false){const b=byId(state.selected);if(!b||state.mode!=='review'||!visible().some(x=>x.id===b.id))return;state.edits[b.id]={...state.edits[b.id],status:value};record(value,b);const index=all.findIndex(x=>x.id===b.id);render();if(advance){const ordered=[...all.slice(index+1),...all.slice(0,index)];const next=ordered.find(x=>status(x)!=='reviewed');if(next){select(next.id,{focus:true});announce(`${b.title} 확인 완료. 다음 항목 ${next.title}.`)}else{$('reviewMode').focus();announce('모든 항목의 확인을 완료했습니다. 검수 기록을 저장할 수 있습니다.')}}else{document.querySelector(`[data-select="${b.id}"]`)?.focus();announce(`${b.title}, ${statusNames[value]}로 표시했습니다.`)}}
  function changeFilters(){const list=visible();if(!list.some(b=>b.id===state.selected))state.selected=list[0]?.id??null;renderReading();renderSelection();announce(`${list.length}개 항목이 검색되었습니다.`)}
  $('pageNav').addEventListener('click',event=>{const b=event.target.closest('[data-page]');if(b)setPage(Number(b.dataset.page))});
  $('blockList').addEventListener('click',event=>{const show=event.target.closest('[data-show-source]');if(show){select(show.dataset.showSource,{showSource:true});return}const button=event.target.closest('[data-select]');if(button){select(button.dataset.select);return}if(event.target.closest('summary,details,a,button,input'))return;const article=event.target.closest('[data-block]');if(article)select(article.dataset.block)});
  $('overlays').addEventListener('click',event=>{const b=event.target.closest('[data-region]');if(b)select(b.dataset.region,{focus:true})});
  $('readerMode').onclick=()=>{state.mode='reader';renderMode();announce('읽기 모드입니다. 수정 버튼을 숨겼습니다.')};
  $('reviewMode').onclick=()=>{state.mode='review';state.source=true;renderMode();revealRegion();announce('검수 모드입니다. 원본과 인식 결과를 나란히 볼 수 있습니다.')};
  $('sourceToggle').onclick=()=>{state.source=!state.source;renderMode();revealRegion();announce(state.source?'원본 이미지가 표시됩니다.':'원본 이미지를 숨겼습니다.')};
  $('search').oninput=event=>{state.query=event.target.value.trim();changeFilters()};$('typeFilter').onchange=event=>{state.type=event.target.value;changeFilters()};$('needsOnly').onchange=event=>{state.needsOnly=event.target.checked;changeFilters()};
  $('clearFilters').onclick=()=>{state.query='';state.type='all';state.needsOnly=false;$('search').value='';$('typeFilter').value='all';$('needsOnly').checked=false;changeFilters();$('search').focus()};
  $('previousPage').onclick=()=>setPage(state.page-1);$('nextPage').onclick=()=>setPage(state.page+1);$('nextNeedsSidebar').onclick=nextNeeds;
  $('textSizeBtn').onclick=()=>{const sizes=[100,125,150,200];state.font=sizes[(sizes.indexOf(state.font)+1)%sizes.length];renderMode();save();announce(`글자 크기 ${state.font}퍼센트`)};
  $('contrastBtn').onclick=()=>{state.contrast=!state.contrast;renderMode();save();announce(state.contrast?'고대비 화면입니다.':'기본 대비 화면입니다.')};
  function zoom(delta){state.zoom=Math.max(75,Math.min(200,state.zoom+delta));renderSource();renderSelection();revealRegion();announce(`원본 확대율 ${state.zoom}퍼센트`)}
  $('zoomOut').onclick=()=>zoom(-25);$('zoomIn').onclick=()=>zoom(25);$('fitSource').onclick=()=>{state.zoom=100;renderSource();renderSelection();revealRegion();announce('원본 이미지를 화면 너비에 맞췄습니다.')};
  $('helpBtn').onclick=()=>$('helpDialog').showModal();$('shortcutsEnabled').onchange=event=>state.shortcuts=event.target.checked;
  document.querySelectorAll('[data-close]').forEach(button=>button.onclick=()=>$(button.dataset.close).close());
  $('editBtn').onclick=()=>{const b=byId(state.selected);if(!b)return;$('editTitle').textContent=`${typeNames[b.type]} 인식 내용 수정`;$('editContext').textContent=`${b.page}페이지 · ${b.title}`;$('editText').value=content(b);$('originalText').textContent=b.text;$('editDialog').showModal();$('editText').focus()};
  $('editForm').onsubmit=event=>{event.preventDefault();const b=byId(state.selected),text=$('editText').value.trim();if(!text){$('editText').setCustomValidity('수정할 내용을 입력해 주세요.');$('editText').reportValidity();return}state.edits[b.id]={...state.edits[b.id],text,status:'needs_review'};record('edit',b);$('editDialog').close();render();$('editBtn').focus();announce('수정 내용을 저장했습니다. 원본과 대조한 뒤 확인 완료로 표시하세요.')};$('editText').oninput=()=>$('editText').setCustomValidity('');
  $('approveBtn').onclick=()=>setStatus('reviewed',true);$('flagBtn').onclick=()=>setStatus('needs_review');
  $('resetBtn').onclick=()=>{$('helpDialog').close();$('resetDialog').showModal()};$('confirmReset').onclick=()=>{state.edits={};state.history=[];save();$('resetDialog').close();render();$('helpBtn').focus();announce('예시 검수 기록을 초기화했습니다.')};
  $('exportBtn').onclick=()=>{const data={kind:'review-ui-prototype',isDemo:true,documentId:fixture.id,title:fixture.title,exportedAt:new Date().toISOString(),note:'화면 검토용 예시의 검수 기록입니다. DAISY 파일이 아닙니다.',elements:all.map(b=>({id:b.id,page:b.page,type:b.type,original_text:b.text,corrected_text:content(b),review_status:status(b),bbox:b.bbox})),history:state.history};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='예시문서-검수기록.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);announce('예시 문서의 검수 기록 JSON을 저장했습니다. DAISY 파일은 아닙니다.')};
  document.addEventListener('keydown',event=>{if(!state.shortcuts||document.querySelector('dialog[open]')||event.isComposing)return;const editing=event.target.matches('input,textarea,select,[contenteditable="true"]');if(event.ctrlKey&&event.key==='Enter'&&state.mode==='review'&&!editing){event.preventDefault();setStatus('reviewed',true);return}if(editing)return;if(event.altKey&&!event.ctrlKey&&!event.metaKey){if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();nextBlock(event.key==='ArrowDown'?1:-1)}else if(event.key.toLowerCase()==='n'){event.preventDefault();nextNeeds()}else if(['1','2','3'].includes(event.key)){event.preventDefault();if(event.key==='3'){state.source=true;renderMode()}$({'1':'outline','2':'reading','3':'sourcePanel'}[event.key]).focus()}}else if(event.key==='?'&&!event.ctrlKey&&!event.metaKey){event.preventDefault();$('helpDialog').showModal()}});
  render();
})();
