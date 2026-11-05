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
    await page.getByRole('button', {name:/^(Continuar sin cuenta|Ajustes)$/}).waitFor();
    if (await guest.isVisible()) await guest.click();
    await page.goto(base + '/#/coach/intake');
    await page.waitForURL('**/#/home');
    await page.getByRole('heading', {name:'openGym', exact:true}).waitFor();
    if (warnings.some(msg => msg.includes('navigate()'))) throw new Error('Navigation during render');
    await page.screenshot({path:'.playwright-cli/ui-fixes-coach.png'});
    const passed = ['coach-cold-redirect'];
    const assert = (condition, message) => { if (!condition) throw new Error(message); };
    const verifyModals = async p => {
      const viewport = p.viewportSize().width;
      const dialogs = p.locator('dialog[open]');
      const top = () => dialogs.last();
      const count = n => p.waitForFunction(n => document.querySelectorAll('dialog[open]').length === n, n);
      const focusInside = () => top().evaluate(el => el.contains(document.activeElement));
      const cycle = async () => {
        assert(await focusInside(), 'Initial focus outside top dialog');
        for (const key of ['Tab','Tab','Tab','Shift+Tab','Shift+Tab','Shift+Tab']) {
          await p.keyboard.press(key);
          if (!await focusInside()) {
            // Native dialogs may yield to browser chrome; no background document control may gain focus.
            assert(await p.evaluate(() => !document.hasFocus()), key + ' focused the background page');
            await top().getByRole('button').first().focus();
          }
        }
      };
      await p.getByRole('button',{name:'Minimizar',exact:true}).click();
      await p.getByRole('navigation').getByRole('button',{name:'Ejercicios',exact:true}).click();
      await p.getByRole('textbox',{name:'Buscar…',exact:true}).fill('squat');
      const opener = p.getByRole('button',{name:'sentadilla (squat) cuádriceps · peso corporal Plan',exact:true});
      await opener.focus();
      await opener.click();
      await count(1);
      await cycle();
      await p.locator('#tabbar button').first().focus();
      assert(await focusInside(), 'Background accepted focus');
      const parent = p.locator('#' + await top().getAttribute('id'));
      const add = parent.getByRole('button',{name:'Añadir a mi plan',exact:true});
      await add.click();
      await count(2);
      await cycle();
      await add.focus();
      assert(await focusInside(), 'Lower dialog accepted focus');
      await p.screenshot({path:`.playwright-cli/ui-fixes-${viewport}-stacked.png`});
      await p.keyboard.press('Escape');
      await count(1);
      assert(await add.evaluate(el => document.activeElement === el), 'Nested close lost opener focus');
      await add.click();
      await count(2);
      await p.goBack();
      await count(1);
      assert(p.url().endsWith('#/library'), 'Back escaped the sheet route');
      await top().locator('.mback').click({position:{x:8,y:8}});
      await count(0);
      assert(await opener.evaluate(el => document.activeElement === el), 'Final close lost opener focus');
      await opener.click();
      await count(1);
      await top().locator('.grab').hover();
      const grab = await top().locator('.grab').boundingBox();
      await p.mouse.move(grab.x + grab.width/2, grab.y + grab.height/2);
      await p.mouse.down();
      await p.mouse.move(grab.x + grab.width/2, grab.y + 140, {steps:8});
      await p.mouse.up();
      await count(0);
      passed.push(`modal-${viewport}-focus-stack-escape-back-backdrop-drag`);

      await p.goto(base + '/#/measurements');
      await p.getByRole('button',{name:'Registrar',exact:true}).click();
      await top().getByRole('button',{name:'Guardar',exact:true}).click();
      await top().locator('#toast').getByText('Introduce al menos una medida',{exact:true}).waitFor();
      await p.screenshot({path:`.playwright-cli/ui-fixes-${viewport}-modal-toast.png`});
      await p.keyboard.press('Escape');
      await count(0);
      passed.push(`modal-${viewport}-validation-toast`);

      await p.goto(base + '/#/workout');
      await p.getByRole('checkbox',{name:'Serie 1 hecha',exact:true}).check();
      await p.locator('#timer .tclock').click();
      await count(1);
      const wheel = top().getByRole('spinbutton').first();
      const before = await wheel.getAttribute('aria-valuenow');
      await wheel.press('ArrowUp');
      assert(await wheel.getAttribute('aria-valuenow') !== before, 'Duration wheel ignored ArrowUp');
      await top().getByRole('button',{name:'Listo',exact:true}).click();
      await count(0);
      passed.push(`modal-${viewport}-duration-keyboard-control`);

      await p.getByRole('button',{name:'Serie 2',exact:true}).click();
      await top().getByRole('button',{name:'Quitar esta serie',exact:true}).click();
      await count(0);
      // Pause the genuine Undo toast while opening a modal; its action must stay operable there.
      await p.locator('#toast').hover();
      await p.getByRole('button',{name:'Serie 1',exact:true}).click();
      await count(1);
      const undo = top().getByRole('button',{name:'Deshacer',exact:true});
      await undo.click();
      await p.keyboard.press('Escape');
      await count(0);
      assert(await p.getByRole('checkbox',{name:/^Serie \d hecha$/}).count() === 3, 'Undo did not restore the removed set');
      passed.push(`modal-${viewport}-undo-action`);
      await p.getByRole('checkbox',{name:'Serie 2 hecha',exact:true}).check();
      await p.getByRole('checkbox',{name:'Serie 3 hecha',exact:true}).check();
      await top().getByRole('button',{name:'Terminar entrenamiento',exact:true}).click();
      await p.getByRole('heading',{name:'¡Entrenamiento completado!',exact:true}).waitFor();
      await p.keyboard.press('Escape');
      assert(await dialogs.count() === 1, 'Escape closed locked finish summary');
      await p.goBack();
      await count(1);
      await cycle();
      await p.screenshot({path:`.playwright-cli/ui-fixes-${viewport}-locked-summary.png`});
      // Generate a synthetic photo fixture, then ingest it through the real upload UI.
      await p.screenshot({path:'.playwright-cli/ui-fixes-photo.png'});
      await top().locator('input[type=file]').setInputFiles('.playwright-cli/ui-fixes-photo.png');
      const summary = p.locator('#' + await top().getAttribute('id'));
      const photo = summary.getByRole('button',{name:'Foto o vídeo 1 de 1',exact:true});
      await photo.waitFor();
      await photo.click();
      await count(2);
      await cycle();
      await p.screenshot({path:`.playwright-cli/ui-fixes-${viewport}-media-viewer.png`});
      await top().getByRole('button',{name:'Cerrar',exact:true}).click();
      await count(1);
      assert(await photo.evaluate(el => document.activeElement === el), 'Viewer did not restore photo focus');
      await top().getByRole('button',{name:'¡Genial!',exact:true}).click();
      await count(0);
      passed.push(`modal-${viewport}-locked-summary-media-viewer`);
    };
    for (const key of ['Enter', 'Space']) {
      const context = await page.context().browser().newContext({locale:'es-ES', viewport:{width:key === 'Space' ? 390 : 1280, height:844}});
      let p;
      try {
        p = await context.newPage();
        const runtimeErrors = [];
        p.on('pageerror', error => runtimeErrors.push(error.message));
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
        await verifyModals(p);
        assert(runtimeErrors.length === 0, 'Runtime errors: ' + runtimeErrors.join('; '));
      } catch (error) {
        if (p) {
          await p.screenshot({path:'.playwright-cli/ui-fixes-FAIL.png'});
          throw new Error(String(error) + '\n' + p.url() + '\n' + await p.locator('body').innerText());
        }
        throw error;
      } finally { await context.close(); }
    }
    return {passed, warnings};
  } finally { page.off('console', onConsole); }
}
