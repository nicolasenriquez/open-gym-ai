async page => {
  const dir = 'docs/audit/opengym-e2e-2026-10-20/evidence';
  const routes = ['home','plan','workout','stats','history','library','muscles','structural-balance','progress-photos','measurements','checkin','settings','settings/workout','settings/alerts','settings/plan','settings/units','settings/equipment','settings/look','settings/data','settings/about','settings/account','settings/advanced','settings/reminders','coach','coach/intake','coach/setup','admin'];
  const results = [];
  await page.setViewportSize({width:390,height:844});
  for (const route of routes) {
    await page.goto('http://localhost:8080/#/' + route);
    let heading = null;
    try { await page.locator('h1').waitFor({timeout:2500}); heading = await page.locator('h1').innerText(); }
    catch { /* A blank route is evidence, not a reason to lose the rest of the survey. */ }
    const text = await page.locator('body').innerText();
    const slug = route.replaceAll('/', '-');
    await page.screenshot({path: `${dir}/${slug}.png`, fullPage: true});
    results.push({route, actual:page.url(), heading, text});
  }
  return results;
}
