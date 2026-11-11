(()=>{if(window.KTGBeachNav)window.KTGBeachNav();else if(!document.querySelector('script[data-ktg-beach-nav]')){const s=document.createElement('script');s.src='/assets/beach-nav.js';s.defer=true;s.dataset.ktgBeachNav='';document.head.appendChild(s)}})();

document.addEventListener('DOMContentLoaded',()=>{
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
