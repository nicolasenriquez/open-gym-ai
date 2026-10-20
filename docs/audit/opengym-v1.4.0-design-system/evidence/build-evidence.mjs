import fs from 'node:fs'
import { execFileSync } from 'node:child_process'
const dir = 'docs/audit/opengym-v1.4.0-design-system/evidence/'
const git = (...args) => execFileSync('git', args, { encoding: 'utf8', maxBuffer: 8e6 })
const files = git('ls-tree', '-r', '--name-only', 'v1.4.0', 'frontend/src').trim().split('\n').filter(f => /\.(jsx|js)$/.test(f) && !f.includes('.test.'))
const texts = new Map(files.map(f => [f, git('show', 'v1.4.0:' + f)]))
const rows = []
for (const [file, text] of texts) {
  if (!file.startsWith('frontend/src/components/')) continue
  const name = file.split('/').pop().replace(/\.jsx$/, '')
  const declarations = text.split('\n').flatMap((line,i) => /^(export |function |const .*forwardRef)/.test(line) ? [`${i+1}: ${line}`] : [])
  const consumers = [...texts].filter(([p,s]) => p !== file && s.split('\n').some(line => /^import /.test(line) && new RegExp('[/\\\\]' + name + '\\.(jsx|js)').test(line))).map(([p]) => p)
  rows.push({file, declarations, consumers, status:'SOURCE_ONLY unless explicitly confirmed in 02-source-inventory.md'})
}
fs.writeFileSync(dir+'component-reference.v1.4.0.json', JSON.stringify(rows,null,2)+'\n')
const lum = c => c.map(v => {v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0)
const ratio=(a,b)=>(Math.max(lum(a),lum(b))+.05)/(Math.min(lum(a),lum(b))+.05)
const green=[52,199,89],white=[255,255,255],bg=[242,242,247]
const tint=green.map((v,i)=>v*.16+bg[i]*.84)
const contrast={method:'WCAG 2 sRGB relative luminance. Tinted color composited over light page background; not a pixel/whole-app conformance scan.',greenOnWhite:ratio(green,white),greenOnLightPage:ratio(green,bg),greenOnTintedLightPage:ratio(green,tint),whiteOnLightGreen:ratio(white,green),blackOnLightGreen:ratio([0,0,0],green)}
fs.writeFileSync(dir+'contrast-calculations.json',JSON.stringify(contrast,null,2)+'\n')
const routes=JSON.parse(fs.readFileSync(dir+'route-observations.json','utf8'))
const extra={
 'login': ['/', 'frontend/src/views/Login.jsx', 'Unauthenticated login'],
 'exercise-detail':['/library','frontend/src/sheets.jsx ExerciseDetail; components/Modals.jsx; components/Media.jsx','Exercise detail sheet, squat'],
 'exercise-picker':['/plan/r/<disposable-id>','frontend/src/sheets.jsx ExercisePicker; components/Modals.jsx','Search in Add exercise sheet'],
 'routine-edit':['/plan/r/<disposable-id>','frontend/src/views/RoutineEdit.jsx','Disposable routine editor; mobile empty, desktop one exercise'],
 'workout-active':['/workout','frontend/src/views/Workout.jsx; components/WorkoutChips.jsx','Disposable single-exercise session; dark captures include one completed set'],
 'workout-rest':['/workout','frontend/src/views/Workout.jsx; components/RestTimer.jsx','One marked set; running rest'],
 'workout-finish-confirm':['/workout','frontend/src/sheets.jsx; components/Modals.jsx','Nothing logged yet confirmation; not saved'],
 'library-search':['/library','frontend/src/views/Library.jsx','Search sentadilla, 431 results'],
 'library-filter':['/library','frontend/src/views/Library.jsx','Search sentadilla plus piernas, 388 results'],
}
const sourceFor=r=> r.startsWith('settings')?'frontend/src/views/Settings.jsx':({'home':'Home','library':'Library','plan':'Plan','workout':'Workout','history':'History','stats':'Stats','muscles':'Muscles','structural-balance':'StructuralBalance','progress-photos':'ProgressPhotos','measurements':'Measurements','checkin':'CheckIn','coach':'Home (redirect; CoachChat access blocked)' }[r] ? 'frontend/src/views/'+({'home':'Home','library':'Library','plan':'Plan','workout':'Workout','history':'History','stats':'Stats','muscles':'Muscles','structural-balance':'StructuralBalance','progress-photos':'ProgressPhotos','measurements':'Measurements','checkin':'CheckIn','coach':'Home'}[r])+'.jsx':'See source inventory')
let md='# Screenshot register\n\nAll images: actual localhost:8080 runtime reporting **v1.4.1**, Edge 155 / Chromium, session `opengym-audit`, Spanish, guest except login. Viewports are CSS pixels, not physical touch-device emulation. No v1.4.0 runtime screenshots are claimed. Dates are file capture times.\n\n| Screenshot | Actual route | Viewport | Theme | State | Source | Capture UTC |\n|---|---|---|---|---|---|---|\n'
for(const file of fs.readdirSync(dir).filter(f=>f.endsWith('.png')).sort()) {
 const b=fs.readFileSync(dir+file), w=b.readUInt32BE(16),h=b.readUInt32BE(20)
 const name=file.slice(0,-4),observed=routes.find(x=>x.name===name)
 const prefix=name.replace(/-(desktop|mobile|tablet)-(dark|light)$/,'')
 const e=extra[prefix]
 const route=observed?observed.route.replace('http://localhost:8080/#',''):e?e[0]:prefix==='library'?'/library':prefix==='home'?'/home':'/'+prefix.replace('settings-','settings/')
 const source=e?e[1]:sourceFor(prefix)
 const state=e?e[2]:prefix==='coach'?'Redirected to Home, NOT Coach evidence':prefix==='workout'?'Start chooser, no session':prefix.startsWith('settings')?'Initial settings page; lower rows in DOM snapshot':prefix==='library'?'Initial exercise list':prefix==='home'&&name.endsWith('light')?'Disposable routine exists and session running':'Initial empty-profile page / read-only controls'
 md+=`| [${file}](${file}) | \`${route}\` | ${w} × ${h} | ${name.endsWith('light')?'Light':'Dark'} | ${state} | ${source} | ${fs.statSync(dir+file).mtime.toISOString()} |\n`
}
fs.writeFileSync(dir+'screenshots.md',md)
console.log(`Components: ${rows.length}; screenshots: ${fs.readdirSync(dir).filter(f=>f.endsWith('.png')).length}; contrast: ${JSON.stringify(contrast)}`)
