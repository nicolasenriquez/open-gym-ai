// Run with playwright-cli run-code --filename=frontend/scripts/verify-ui-fixes.js
// Open a fresh named browser at the checkout's local Vite server first.
async page => {
  const base = await page.evaluate(() => location.origin);
  if (!/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(base)) throw new Error('Local verification only');
  const warnings = [];
  const onConsole = msg => { if (msg.type() === 'warning') warnings.push(msg.text()); };
  page.on('console', onConsole);
  try {
    await page.goto(base);
    const guest = page.getByRole('button', {name:'Continuar sin cuenta', exact:true});
    if (await guest.isVisible()) await guest.click();
    await page.goto(base + '/#/coach/intake');
    await page.waitForURL('**/#/home');
    await page.getByRole('heading', {name:'openGym', exact:true}).waitFor();
    if (warnings.some(msg => msg.includes('navigate()'))) throw new Error('Navigation during render');
    await page.screenshot({path:'.playwright-cli/ui-fixes-coach.png'});
    return {passed:['coach-cold-redirect'], warnings};
  } finally { page.off('console', onConsole); }
}
