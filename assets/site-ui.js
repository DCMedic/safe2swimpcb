(()=>{
  const ready=fn=>document.readyState==='loading'?document.addEventListener('DOMContentLoaded',fn,{once:true}):fn();
  const pathLabel=()=>{
    const h1=document.querySelector('h1');
    if(h1)return h1.textContent.replace(/\s+/g,' ').trim().replace(/[.]$/,'');
    return document.title.split('|')[0].trim();
  };
  function ensureBeachNav(){
    if(window.KTGBeachNav){window.KTGBeachNav();return;}
    if(document.querySelector('script[data-ktg-beach-nav]'))return;
    const s=document.createElement('script');
    s.src='/assets/beach-nav.js';s.defer=true;s.dataset.ktgBeachNav='true';
    s.onload=()=>window.KTGBeachNav?.();document.head.appendChild(s);
  }
  function standardizeBrand(){
    const mark=document.querySelector('.brandmark');
    if(!mark)return;
    if(mark.tagName!=='A'){
      const a=document.createElement('a');a.className=mark.className;a.href='/';a.setAttribute('aria-label','Know the Gulf home');
      [...mark.childNodes].forEach(n=>a.appendChild(n));mark.replaceWith(a);
    }else if(!mark.getAttribute('aria-label'))mark.setAttribute('aria-label','Know the Gulf home');
  }
  function ensureBreadcrumb(){
    const main=document.querySelector('main.shell');
    const hero=main?.querySelector('.hero');
    if(!main||!hero||location.pathname==='/')return;
    let crumb=main.querySelector('.seo-breadcrumb');
    if(!crumb){
      crumb=document.createElement('nav');crumb.className='seo-breadcrumb ktg-standard-breadcrumb';crumb.setAttribute('aria-label','Breadcrumb');
      crumb.innerHTML=`<a href="/">Know the Gulf</a><span aria-hidden="true">›</span><span>${pathLabel()}</span>`;
      hero.insertAdjacentElement('afterend',crumb);
    }else crumb.setAttribute('aria-label','Breadcrumb');
  }
  function standardizeSafety(){
    document.querySelectorAll('.safety').forEach(x=>x.setAttribute('role','note'));
  }
  function standardizeFooter(){
    const main=document.querySelector('main.shell');if(!main)return;
    let f=main.querySelector('footer.footer');
    if(!f){f=document.createElement('footer');f.className='footer';main.appendChild(f);}
    f.innerHTML=`<div class="ktg-footer-grid"><div><strong>Know the Gulf</strong><div class="small">Florida Gulf Coast beach safety, conditions and provenance-aware planning data.</div></div><nav class="ktg-footer-links" aria-label="Footer"><a href="/">Home</a><a href="/guides/">Guides</a><a href="/florida-beach-flag-meanings/">Flag meanings</a><a href="/rip-current-safety/">Rip-current safety</a><a href="mailto:contact@knowthegulf.com">Contact</a></nav></div><div class="small ktg-footer-note">Informational planning only. Posted flags, lifeguards and local authorities always control.</div>`;
  }
  function accessibility(){
    const main=document.querySelector('main.shell');if(!main)return;
    main.id=main.id||'main-content';
    if(!document.querySelector('.ktg-skip-link')){
      const a=document.createElement('a');a.href='#main-content';a.className='ktg-skip-link';a.textContent='Skip to main content';document.body.prepend(a);
    }
  }
  ready(()=>{
    document.body.classList.add('ktg-standard-ui');
    accessibility();standardizeBrand();ensureBreadcrumb();ensureBeachNav();standardizeSafety();standardizeFooter();
  });
})();
