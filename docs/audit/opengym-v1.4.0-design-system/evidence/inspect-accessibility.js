async page => {
  const out=[];
  for (const route of ['settings/alerts','settings/look','library']) {
    await page.goto('http://localhost:8080/#/'+route);
    await page.waitForTimeout(350);
    out.push({route, data:await page.evaluate(() => {
      const rect=e=>{const r=e.getBoundingClientRect();return {width:r.width,height:r.height}};
      return {switches:[...document.querySelectorAll('[role=switch]')].map(e=>({label:e.getAttribute('aria-label'),labelledby:e.getAttribute('aria-labelledby'),text:e.textContent,...rect(e)})),chips:[...document.querySelectorAll('.chip')].slice(0,3).map(e=>({text:e.textContent,...rect(e),before:getComputedStyle(e,'::before').inset})),fields:[...document.querySelectorAll('input')].map(e=>({placeholder:e.placeholder,label:e.getAttribute('aria-label'),type:e.type})),text:[...document.querySelectorAll('.dim,.muted,.sect-f,.btn')].slice(0,8).map(e=>({text:e.textContent.slice(0,80),color:getComputedStyle(e).color,background:getComputedStyle(e).backgroundColor,size:getComputedStyle(e).fontSize,weight:getComputedStyle(e).fontWeight})),viewport:document.querySelector('meta[name=viewport]').content};
    })});
  }
  await page.setViewportSize({width:768,height:1024});
  await page.goto('http://localhost:8080/#/library');
  await page.waitForTimeout(400);
  await page.screenshot({path:'docs/audit/opengym-v1.4.0-design-system/evidence/library-tablet-dark.png'});
  out.push({intermediate:await page.evaluate(()=>({width:innerWidth,appWidth:document.querySelector('#app').getBoundingClientRect().width,scrollWidth:document.documentElement.scrollWidth,tabWidth:document.querySelector('#tabbar').getBoundingClientRect().width}))});
  await page.emulateMedia({reducedMotion:'reduce'});
  out.push({reducedMotion:await page.evaluate(()=>({matches:matchMedia('(prefers-reduced-motion: reduce)').matches,viewAnimation:getComputedStyle(document.querySelector('#app')).animationName,buttonTransition:getComputedStyle(document.querySelector('button')).transitionDuration}))});
  await page.emulateMedia({reducedMotion:'no-preference'});
  return out;
}
