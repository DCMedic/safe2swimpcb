document.addEventListener('DOMContentLoaded',()=>{
  const nav=document.querySelector('.location-links');
  if(nav){[['/navarre-beach/','Navarre Beach'],['/pensacola-beach/','Pensacola Beach']].forEach(([href,label])=>{if(!nav.querySelector(`a[href="${href}"]`)){const a=document.createElement('a');a.className='location-link';a.href=href;a.textContent=label;nav.appendChild(a)}})}
  const button=document.getElementById('moreMenuButton');
  const menu=document.getElementById('moreMenu');
  if(!button||!menu)return;
  const closeMenu=()=>{menu.hidden=true;button.setAttribute('aria-expanded','false')};
  const openMenu=()=>{menu.hidden=false;button.setAttribute('aria-expanded','true')};
  button.addEventListener('click',event=>{event.stopPropagation();if(menu.hidden)openMenu();else closeMenu()});
  menu.addEventListener('click',event=>{const item=event.target.closest('.menu-item');if(item)closeMenu()});
  document.addEventListener('click',event=>{if(!menu.hidden&&!menu.contains(event.target)&&event.target!==button)closeMenu()});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!menu.hidden){closeMenu();button.focus()}});
});
