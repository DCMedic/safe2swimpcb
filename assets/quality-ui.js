(()=>{
  const ready=fn=>document.readyState==='loading'?document.addEventListener('DOMContentLoaded',fn,{once:true}):fn();
  function improveTouchTargets(){
    document.querySelectorAll('a.btn,button,.location-link,.tab,.menu-toggle').forEach(el=>el.classList.add('ktg-touch-target'));
  }
  function improveDenseMetrics(){
    document.querySelectorAll('.grid.metrics').forEach(g=>g.classList.add('ktg-metric-grid'));
    document.querySelectorAll('.card').forEach(c=>{if(c.querySelector('.grid.metrics'))c.classList.add('ktg-observation-card')});
  }
  ready(()=>{document.body.classList.add('ktg-quality-ui');improveTouchTargets();improveDenseMetrics()});
})();
