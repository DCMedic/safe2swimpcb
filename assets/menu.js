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

const PCB_POLLING={timeZone:'America/Chicago',startMinutes:6*60+7,endMinutes:22*60+37,morningGraceMinutes:6*60+37};
function pcbLocalParts(date){const parts=new Intl.DateTimeFormat('en-US',{timeZone:PCB_POLLING.timeZone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(date);return Object.fromEntries(parts.map(part=>[part.type,part.value]))}
function pcbDateKey(date){const p=pcbLocalParts(date);return `${p.year}-${p.month}-${p.day}`}
function pcbMinutes(date){const p=pcbLocalParts(date);return Number(p.hour)*60+Number(p.minute)}
function pcbIsStale(lastVerifiedAt,staleAfterHours,now=new Date()){
  const verified=new Date(lastVerifiedAt);
  if(Number.isNaN(verified.getTime()))return true;
  const ageHours=(now.getTime()-verified.getTime())/36e5;
  if(ageHours<=Number(staleAfterHours||6))return false;
  const nowMinutes=pcbMinutes(now);
  const nowKey=pcbDateKey(now);
  const verifiedKey=pcbDateKey(verified);
  if(nowMinutes>PCB_POLLING.endMinutes&&verifiedKey===nowKey)return false;
  if(nowMinutes<PCB_POLLING.morningGraceMinutes){
    const previousKey=pcbDateKey(new Date(now.getTime()-24*36e5));
    if(verifiedKey===previousKey||verifiedKey===nowKey)return false;
  }
  return true;
}
async function applyPcbPollingAwareFreshness(){
  const canonical=document.querySelector('link[rel="canonical"]')?.href;
  const status=document.getElementById('flagFreshness');
  if(canonical!=='https://knowthegulf.com/'||!status)return;
  try{
    const response=await fetch('/data/current_flag.json',{cache:'no-store'});
    if(!response.ok)return;
    const current=await response.json();
    if(!current.last_verified_at)return;
    const verified=new Date(current.last_verified_at);
    const stale=pcbIsStale(current.last_verified_at,current.stale_after_hours);
    status.className='status'+(stale?' stale':'');
    const overnight=!stale&&((pcbMinutes(new Date())>PCB_POLLING.endMinutes)||(pcbMinutes(new Date())<PCB_POLLING.morningGraceMinutes));
    status.innerHTML=`Last verified by automation: <strong>${verified.toLocaleString()}</strong>${stale?' — status is stale; verify at the official source.':overnight?' — overnight polling pause; status carries forward until morning polling resumes.':''}`;
  }catch{}
}
document.addEventListener('DOMContentLoaded',()=>{applyPcbPollingAwareFreshness();setTimeout(applyPcbPollingAwareFreshness,1000)});
