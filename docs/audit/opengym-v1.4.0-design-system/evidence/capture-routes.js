async page => {
  const dir = 'docs/audit/opengym-v1.4.0-design-system/evidence/';
  const routes = ['home', 'library', 'plan', 'workout', 'history', 'stats', 'settings', 'settings/look', 'settings/workout', 'settings/advanced', 'settings/alerts', 'settings/plan', 'settings/units', 'settings/equipment', 'settings/data', 'settings/about', 'settings/account', 'muscles', 'structural-balance', 'progress-photos', 'measurements', 'checkin', 'coach'];
  const results = [];
  for (const profile of [{name:'desktop',width:1440,height:900},{name:'mobile',width:390,height:844}]) {
    await page.setViewportSize({width:profile.width,height:profile.height});
    for (const route of routes) {
      await page.goto('http://localhost:8080/#/' + route);
      await page.locator('#app h1').first().waitFor({timeout:10000}).catch(() => {});
      await page.waitForTimeout(400);
      const name = route.replaceAll('/', '-') + '-' + profile.name + '-dark';
      await page.screenshot({path:dir + name + '.png', scale:'css'});
      results.push({name,route:page.url(),viewport:profile, snapshot:await page.locator('body').ariaSnapshot(), metrics:await page.evaluate(() => ({theme:document.documentElement.dataset.theme,accent:document.documentElement.dataset.accent,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,appWidth:document.querySelector('#app').getBoundingClientRect().width,bodyFont:getComputedStyle(document.body).fontFamily,bodySize:getComputedStyle(document.body).fontSize,appPadding:getComputedStyle(document.querySelector('#app')).padding,dialogCount:document.querySelectorAll('[role=dialog]').length}))});
    }
  }
  return results;
}
