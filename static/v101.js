(()=>{
 const body=document.body, toggle=document.querySelector('[data-sidebar-toggle]');
 const stored=localStorage.getItem('bos-sidebar-collapsed'); if(stored==='1') body.classList.add('sidebar-collapsed');
 if(toggle) toggle.addEventListener('click',()=>{body.classList.toggle('sidebar-collapsed');localStorage.setItem('bos-sidebar-collapsed',body.classList.contains('sidebar-collapsed')?'1':'0');toggle.textContent=body.classList.contains('sidebar-collapsed')?'›':'‹'});
 if(toggle&&body.classList.contains('sidebar-collapsed')) toggle.textContent='›';
 const backdrop=document.querySelector('[data-command-backdrop]'),input=document.querySelector('[data-command-input]'),items=[...document.querySelectorAll('[data-command-item]')],openers=[...document.querySelectorAll('[data-command-open]')]; let visible=[],index=0;
 const paint=()=>{items.forEach(x=>x.classList.remove('selected')); if(visible[index]) visible[index].classList.add('selected')};
 const filter=()=>{const q=(input?.value||'').trim().toLowerCase();visible=[];items.forEach(a=>{const match=!q||(a.textContent+' '+(a.dataset.keywords||'')).toLowerCase().includes(q);a.hidden=!match;if(match)visible.push(a)});index=0;paint()};
 const open=()=>{if(!backdrop)return;backdrop.hidden=false;if(input){input.value='';filter();setTimeout(()=>input.focus(),20)}};
 const close=()=>{if(backdrop)backdrop.hidden=true};
 openers.forEach(b=>b.addEventListener('click',open)); input?.addEventListener('input',filter); backdrop?.addEventListener('click',e=>{if(e.target===backdrop)close()});
 document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();open();return}if(backdrop&&!backdrop.hidden){if(e.key==='Escape'){close();return}if(e.key==='ArrowDown'){e.preventDefault();if(visible.length){index=(index+1)%visible.length;paint();visible[index].scrollIntoView({block:'nearest'})}}if(e.key==='ArrowUp'){e.preventDefault();if(visible.length){index=(index-1+visible.length)%visible.length;paint();visible[index].scrollIntoView({block:'nearest'})}}if(e.key==='Enter'&&visible[index]){e.preventDefault();visible[index].click()}}});
})();
