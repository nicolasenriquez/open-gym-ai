// Synthetic operator client for full_timing: real UI/HTTP; the harness alone rewinds the isolated DB.
import assert from 'node:assert/strict';
import { createServer, request } from 'node:http';
import { readFile, writeFile, chmod } from 'node:fs/promises';
import { extname, resolve } from 'node:path';
import { createHash } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import { chromium } from 'playwright';

const credential=JSON.parse(await readFile('/run/client/credential.json','utf8'));
const binding=JSON.parse(await readFile('/run/client/binding.json','utf8'));
const root=resolve('public'), evidence='/evidence';
const web=createServer(async(req,res)=>{
  if(req.url.startsWith('/api/')) {
    const upstream=request({hostname:'rehearsal-api',port:3000,path:req.url,method:req.method,headers:req.headers},answer=>{
      res.writeHead(answer.statusCode,answer.headers);answer.pipe(res);
    });
    upstream.on('error',()=>{res.writeHead(502);res.end();});req.pipe(upstream);return;
  }
  try {
    const path=resolve(root,'.'+new URL(req.url,'http://localhost').pathname);
    if(!path.startsWith(root+'/')&&path!==root)throw new Error();
    const file=path===root?resolve(root,'index.html'):path;
    const body=await readFile(file);
    res.writeHead(200,{'Content-Type':{'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.woff2':'font/woff2'}[extname(file)]||'application/octet-stream'});res.end(body);
  }catch{res.writeHead(404);res.end();}
});
await new Promise(done=>web.listen(8080,'127.0.0.1',done));
const browser=await chromium.launch();
try {
  const context=await browser.newContext({locale:'es-ES',viewport:{width:1280,height:900}});
  const page=await context.newPage();page.setDefaultTimeout(15000);
  const until=async(fn,message)=>{for(let i=0;i<200;i++){if(await fn())return;await delay(100);}throw new Error(message);};
  const button=name=>page.getByRole('button',{name,exact:true});
  const local=()=>page.evaluate(()=>({state:JSON.parse(localStorage.getItem('gym_state_v1')||'null'),dirty:localStorage.getItem('gym_dirty'),base:JSON.parse(localStorage.getItem('gym_sync')||'null')}));
  const clean=()=>until(async()=>(await local()).dirty!=='1','client remained dirty');
  const sync=async()=>{await page.goto('http://localhost:8080/#/settings/account');await page.getByText('Sincronizar ahora',{exact:true}).click();};
  const theme=async(name)=>{await page.goto('http://localhost:8080/#/settings/look');await button(name).click();};
  const remote=async()=>{const response=await context.request.get('http://localhost:8080/api/v1/data');assert.equal(response.status(),200);return response.json();};
  await page.goto('http://localhost:8080/#/settings/account');
  await page.getByText('Iniciar sesión con contraseña',{exact:true}).click();
  await page.getByPlaceholder('Nombre o correo',{exact:true}).fill(credential.identifier);
  await page.getByPlaceholder('Contraseña',{exact:true}).fill(credential.password);
  await page.locator('#modal-root').getByRole('button',{name:'Iniciar sesión',exact:true}).click();
  await page.getByPlaceholder('Contraseña',{exact:true}).waitFor({state:'hidden'});
  await until(async()=>(await local()).state.lang==='es' && (await local()).base.wid,'initial restored state not loaded');
  await theme('Oscuro');await until(async()=>(await remote()).state.theme==='dark','theme not persisted');await clean();
  await context.setOffline(true);await button('Claro').click();
  await page.waitForFunction(()=>localStorage.getItem('gym_dirty')==='1');
  const pending=await local();assert.equal(pending.state.theme,'light');
  await writeFile(`${evidence}/dirty.json`,JSON.stringify({base:pending.base.rev}),{mode:0o600});
  await until(async()=>{try{return JSON.parse(await readFile(`${evidence}/rewound.json`,'utf8')).ready;}catch{return false;}},'fixture did not restore branch');
  await context.setOffline(false);await sync();await clean();
  const reconciled=await remote();
  assert.equal(reconciled.state.theme,'light');
  assert.ok(reconciled.state._wids.includes('rehearsal-restored-branch'));
  assert.ok(reconciled.state.workouts.some(workout=>workout.id==='rehearsal-restored-workout'));
  let lost=false;
  await page.route('**/api/v1/data',async route=>{
    if(route.request().method()!=='PUT'||lost)return route.continue();
    const response=await route.fetch();assert.equal(response.status(),200);lost=true;await route.abort('failed');
  });
  await theme('Oscuro');await until(()=>lost,'no lost reply');
  await page.getByText(/Tus cambios.*dispositivo|Tus cambios.*aquí/).first().waitFor();
  assert.equal((await local()).dirty,'1');
  assert.equal((await remote()).state.theme,'dark');
  await page.unroute('**/api/v1/data');await sync();await clean();await page.reload();
  await page.getByText('Sincronizar ahora',{exact:true}).waitFor({state:'visible'});
  const final=await local(), stored=await remote();
  assert.equal(final.state.theme,'dark');assert.equal(final.base.wid,stored.state._wid);
  assert.ok(final.state.workouts.some(workout=>workout.id==='rehearsal-restored-workout'));
  await page.screenshot({path:`${evidence}/client.png`,animations:'disabled'});await chmod(`${evidence}/client.png`,0o600);
  const observed={uid:credential.uid,rev:stored.rev,wid:stored.state._wid,theme:stored.state.theme,sha256:createHash('sha256').update(JSON.stringify(stored.state)).digest('hex')};
  await writeFile(`${evidence}/observed.json`,JSON.stringify(observed),{mode:0o600});
  const artifacts=[];
  for(const name of ['client.png','observed.json'])artifacts.push({name,sha256:createHash('sha256').update(await readFile(`${evidence}/${name}`)).digest('hex')});
  await writeFile(`${evidence}/verification.json`,JSON.stringify({...binding,completed:true,observation:observed,checks:{dirty_preserved:true,lineage_reconciled:true,lost_reply_reconciled:true,persisted:true},artifacts}),{mode:0o600});
  console.log('REHEARSAL_CLIENT_DIRTY_LINEAGE_LOST_REPLY_RELOAD_PASS');
}catch(error){
  console.error(String(error?.message??'REHEARSAL_CLIENT_FAILED').replaceAll(credential.password,'[redacted]').replaceAll(credential.identifier,'[redacted]'));process.exitCode=1;
}finally{await browser.close();await new Promise(done=>web.close(done));}
