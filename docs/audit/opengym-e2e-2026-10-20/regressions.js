async page => {
  const dir = 'docs/audit/opengym-e2e-2026-10-20/evidence/';
  const warnings = [];
  const listener = msg => { if (['error','warning'].includes(msg.type())) warnings.push(msg.text()); };
  page.on('console', listener);
  const result = {};
  await page.goto('http://localhost:8080/#/coach/intake');
  // A bounded observed wait gives a redirect a chance, without assuming a heading exists.
  try { await page.locator('h1').waitFor({timeout:3000}); } catch {}
  result.coach = {url:page.url(),headings:await page.locator('h1').allTextContents(),snapshot:await page.locator('body').ariaSnapshot()};
  await page.screenshot({path:dir+'bug-coach-intake.png'});
  await page.goto('http://localhost:8080/#/library');
  await page.getByRole('textbox',{name:'Buscar…',exact:true}).fill('squat');
  await page.getByRole('button',{name:'sentadilla (squat) cuádriceps · peso corporal Plan',exact:true}).click();
  await page.locator('#modal-root').getByRole('button',{name:'Añadir a mi plan',exact:true}).waitFor();
  result.sheet = {dialogs:await page.getByRole('dialog').count(),before:await page.evaluate(()=>({inside:!!document.activeElement.closest('#modal-root'),tag:document.activeElement.tagName}))};
  await page.keyboard.press('Tab');
  result.sheet.after = await page.evaluate(()=>({inside:!!document.activeElement.closest('#modal-root'),tag:document.activeElement.tagName,text:document.activeElement.textContent}));
  await page.screenshot({path:dir+'bug-modal-keyboard.png'});
  await page.keyboard.press('Escape');
  await page.goto('http://localhost:8080/#/workout');
  result.chooser = await page.getByText('E2E CLI Routine',{exact:true}).evaluate(el=>{
    const row = el.closest('[onclick],.row,.list-row,.lrow') || el.parentElement.parentElement;
    return {html:row.outerHTML,role:row.getAttribute('role'),tabindex:row.getAttribute('tabindex')};
  });
  result.warnings = warnings;
  page.off('console',listener);
  return result;
}
