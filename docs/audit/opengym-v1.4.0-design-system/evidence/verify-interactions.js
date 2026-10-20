async page => {
  const dir='docs/audit/opengym-v1.4.0-design-system/evidence/';
  await page.setViewportSize({width:390,height:844});
  await page.goto('http://localhost:8080/#/library');
  await page.getByRole('textbox',{name:'Buscar…'}).fill('sentadilla');
  await page.getByRole('button',{name:'sentadilla (squat) cuádriceps · peso corporal Plan',exact:true}).click();
  const before=await page.evaluate(()=>({activeInModal:!!document.activeElement.closest('#modal-root'),dialogCount:document.querySelectorAll('[role=dialog]').length,activeTag:document.activeElement.tagName}));
  await page.keyboard.press('Tab');
  const after=await page.evaluate(()=>({activeInModal:!!document.activeElement.closest('#modal-root'),activeText:document.activeElement.textContent,outline:getComputedStyle(document.activeElement).outline}));
  await page.keyboard.press('Escape');
  const dismissed=await page.locator('.sheet').count()===0;
  await page.goto('http://localhost:8080/#/settings/look');
  await page.getByRole('button',{name:'Claro',exact:true}).click();
  const light=await page.evaluate(()=>({theme:document.documentElement.dataset.theme,acc:getComputedStyle(document.documentElement).getPropertyValue('--acc')}));
  await page.goto('http://localhost:8080/#/home');
  await page.screenshot({path:dir+'home-mobile-light.png'});
  await page.setViewportSize({width:1440,height:900});
  await page.screenshot({path:dir+'home-desktop-light.png'});
  await page.goto('http://localhost:8080/#/library');
  await page.screenshot({path:dir+'library-desktop-light.png'});
  const styles=await page.evaluate(()=>[...document.querySelectorAll('.btn.tinted')].slice(0,1).map(e=>({text:e.textContent,color:getComputedStyle(e).color,bg:getComputedStyle(e).backgroundColor,size:getComputedStyle(e).fontSize,weight:getComputedStyle(e).fontWeight})));
  return {before,after,dismissed,light,styles,guest:await page.evaluate(()=>({guest:localStorage.getItem('gym_guest')==='1',hasUser:!!localStorage.getItem('gym_user')}))};
}
