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
    const passed = ['coach-cold-redirect'];
    for (const key of ['Enter', 'Space']) {
      const context = await page.context().browser().newContext({locale:'es-ES'});
      try {
        const p = await context.newPage();
        await p.goto(base);
        await p.getByRole('button',{name:'Continuar sin cuenta',exact:true}).click();
        await p.getByRole('navigation').getByRole('button',{name:'Plan',exact:true}).click();
        await p.getByRole('button',{name:'Rutinas',exact:true}).click();
        await p.getByRole('button',{name:'Nueva rutina',exact:true}).click();
        await p.getByRole('textbox').fill('Keyboard routine');
        await p.getByRole('button',{name:'Añadir ejercicio',exact:true}).click();
        await p.getByRole('textbox',{name:/Buscar entre/}).fill('squat');
        await p.getByRole('button',{name:'Añadir «sentadilla (squat)»',exact:true}).click();
        await p.keyboard.press('Escape');
        await p.getByRole('navigation').getByRole('button',{name:'Empezar',exact:true}).click();
        const routine = p.getByRole('button',{name:/^Keyboard routine /});
        await routine.waitFor();
        let reached = false;
        for (let i = 0; i < 40; i++) {
          await p.keyboard.press('Tab');
          if (await routine.evaluate(el => document.activeElement === el)) { reached = true; break; }
        }
        if (!reached) throw new Error('Routine is not reachable by Tab');
        await p.keyboard.press(key);
        await p.getByRole('checkbox',{name:'Serie 1 hecha',exact:true}).waitFor();
        await p.screenshot({path:`.playwright-cli/ui-fixes-routine-${key}.png`});
        passed.push('routine-keyboard-' + key);
      } finally { await context.close(); }
    }
    return {passed, warnings};
  } finally { page.off('console', onConsole); }
}
