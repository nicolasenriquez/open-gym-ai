import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import crypto from 'node:crypto'
import { audit, createPlan, applyPlan, parseDocument, safePath, main } from './okf.mjs'

const sha = x => crypto.createHash('sha256').update(x).digest('hex')
const meta = { type: 'Custom Concept', title: 'A [title]', description: 'A concise description.' }
const concept = (body, extra = '') => `---\ntype: Guide\ntitle: Example\ndescription: A useful guide.\n${extra}---\n${body}`

function fixture(t, files = { 'docs/a.md': concept('# Example\n') }, protectedBodies = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'okf-test-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  const write = (p, value) => { const full = path.join(root, p); fs.mkdirSync(path.dirname(full), { recursive: true }); fs.writeFileSync(full, value) }
  write('scripts/docs/okf.config.json', JSON.stringify({ version: '0.2', bundle: 'docs', routing: [], directories: { docs: { title: 'Docs', description: 'Documentation.', owned: true } } }))
  write('scripts/docs/historical-bodies.json', JSON.stringify(protectedBodies))
  for (const [p, value] of Object.entries(files)) write(p, value)
  return { root, write, read: p => fs.readFileSync(path.join(root, p)), check: () => audit(root) }
}

test('metadata insertion preserves CRLF, exact body and missing trailing newline; second apply is a no-op', t => {
  const body = '# Original\r\n\r\nText with UTF-8: recuperación.'
  const f = fixture(t, { 'docs/a.md': body })
  const plan = createPlan(f.root, { 'docs/a.md': meta })
  assert.equal(applyPlan(f.root, plan).written, 2)
  assert.equal(parseDocument(f.read('docs/a.md')).body, body)
  const mtime = fs.statSync(path.join(f.root, 'docs/a.md')).mtimeMs
  assert.equal(applyPlan(f.root, plan).written, 0)
  const second = createPlan(f.root)
  assert.deepEqual(second.changes, [])
  assert.equal(applyPlan(f.root, second).written, 0)
  assert.equal(fs.statSync(path.join(f.root, 'docs/a.md')).mtimeMs, mtime)
  assert.deepEqual(f.check().findings, [])
})

test('existing YAML comments, nested extensions and body remain untouched', t => {
  const text = concept('# Example\n', '# Keep this comment\ncustom:\n  nested: [one, two]\n')
  const f = fixture(t, { 'docs/a.md': text })
  const plan = createPlan(f.root)
  applyPlan(f.root, plan)
  assert.equal(f.read('docs/a.md').toString(), text)
  assert.throws(() => createPlan(f.root, { 'docs/a.md': meta }), /existing frontmatter/)
})

test('read-only audit preserves content and mtimes, and returns stable findings', t => {
  const f = fixture(t)
  const before = f.read('docs/a.md')
  const mtime = fs.statSync(path.join(f.root, 'docs/a.md')).mtimeMs
  assert.deepEqual(f.check().findings, f.check().findings)
  assert.deepEqual(f.read('docs/a.md'), before)
  assert.equal(fs.statSync(path.join(f.root, 'docs/a.md')).mtimeMs, mtime)
})

test('stale plans reject edits, new concepts and policy changes before writing', t => {
  const f = fixture(t)
  let plan = createPlan(f.root)
  f.write('docs/a.md', concept('# Changed\n'))
  assert.throws(() => applyPlan(f.root, plan), /Stale plan/)
  assert.equal(fs.existsSync(path.join(f.root, 'docs/index.md')), false)
  plan = createPlan(f.root)
  f.write('docs/new.md', concept('# New\n'))
  assert.throws(() => applyPlan(f.root, plan), /Stale plan/)
  plan = createPlan(f.root)
  f.write('scripts/docs/historical-bodies.json', '{ }')
  assert.throws(() => applyPlan(f.root, plan), /Stale plan/)
})

test('tampered plan cannot inject prose, paths, removals or fabricated index text', t => {
  const f = fixture(t, { 'docs/a.md': '# Original\n' })
  const plan = createPlan(f.root, { 'docs/a.md': meta })
  const attack = structuredClone(plan)
  attack.changes[0].content += 'Injected text\n'
  attack.changes[0].after = sha(attack.changes[0].content)
  assert.throws(() => applyPlan(f.root, attack), /deterministic proposal/)
  const escape = structuredClone(plan)
  escape.changes[0].file = '../outside.md'
  assert.throws(() => applyPlan(f.root, escape), /deterministic proposal/)
  assert.equal(f.read('docs/a.md').toString(), '# Original\n')
})

test('historical metadata insertion retains protected body; mutation and deletion block checks', t => {
  const body = '# History\n\n[Old](missing.md)\n'
  const f = fixture(t, { 'docs/a.md': body }, { 'docs/a.md': sha(body) })
  applyPlan(f.root, createPlan(f.root, { 'docs/a.md': meta }))
  assert.equal(parseDocument(f.read('docs/a.md')).body, body)
  assert.equal(f.check().findings.filter(x => x.rule === 'link-target')[0].severity, 'advisory')
  f.write('docs/a.md', concept('# Rewritten\n'))
  assert(f.check().findings.some(x => x.rule === 'historical-body' && x.severity === 'required'))
  fs.unlinkSync(path.join(f.root, 'docs/a.md'))
  assert(f.check().findings.some(x => x.rule === 'historical-missing'))
})

test('unknown types and extension fields are accepted, optional absent fields are not required', t => {
  const f = fixture(t, { 'docs/a.md': '---\ntype: Unknown Future Type\ntitle: A\ndescription: B\ncustom: value\n---\n# A\n' })
  applyPlan(f.root, createPlan(f.root))
  assert.deepEqual(f.check().findings, [])
})

for (const [name, text] of [
  ['null type', '---\ntype: null\n---\n# A\n'],
  ['numeric type', '---\ntype: 7\n---\n# A\n'],
  ['array type', '---\ntype: [Guide]\n---\n# A\n'],
  ['empty type', '---\ntype: ""\n---\n# A\n']
]) test(name + ' is a required official finding', t => {
  const f = fixture(t, { 'docs/a.md': text })
  assert(f.check().findings.some(x => x.rule === 'type' && x.origin === 'official'))
})

for (const [name, text] of [
  ['duplicate keys', '---\ntype: Guide\ntype: Other\n---\nBody'],
  ['unterminated YAML', '---\ntype: Guide\nBody'],
  ['multiple YAML documents', '---\ntype: Guide\n...\ntitle: Other\n---\nBody'],
  ['aliases', '---\ntype: &a Guide\ntitle: *a\n---\nBody'],
  ['custom tags', '---\ntype: !custom Guide\n---\nBody'],
  ['mixed endings', '# A\r\nText\n'],
  ['BOM', '\ufeff# A\n'],
  ['invalid UTF-8', Buffer.from([0xc3, 0x28])]
]) test(name + ' requires manual review', () => assert.throws(() => parseDocument(Buffer.from(text))))

test('links resolve references, nested parentheses, Unicode/spaces, HTML ids and duplicate headings', t => {
  const f = fixture(t, {
    'docs/a.md': concept('# Example\n\n[reference][r]\n[r]: <b (á).md#repetido-1>\n\n[explicit](b%20(%C3%A1).md#special)\n<img src="asset.png">\n\n~~~md\n[not a link](nonexistent.md)\n~~~\n`[inline](missing.md)`\n'),
    'docs/b (á).md': concept('# Repetido\n# Repetido\n<span id="special"></span>\n'),
    'docs/asset.png': Buffer.from('fixture')
  })
  applyPlan(f.root, createPlan(f.root))
  assert.deepEqual(f.check().findings, [])
})

test('local links allow repository references but detect case, missing anchors and encoded traversal', t => {
  const f = fixture(t, { 'docs/a.md': concept('# A\n[repo](../AGENTS.md#rules)\n[wrong](../agents.md)\n[anchor](#missing)\n[escape](../../outside.md)\n'), 'AGENTS.md': '# Rules\n' })
  const findings = f.check().findings
  assert.equal(findings.filter(x => x.rule === 'link-target').length, 2)
  assert.equal(findings.filter(x => x.rule === 'link-anchor').length, 1)
})

test('root bundle links and directory links resolve without converting external docs', t => {
  const f = fixture(t, { 'docs/a.md': concept('# A\n[root](/a.md#a)\n[package](../package/)\n'), 'package/README.md': '# Package\n' })
  applyPlan(f.root, createPlan(f.root))
  assert.deepEqual(f.check().findings, [])
})

test('safe paths reject traversal, drives, UNC, backslashes and Windows reserved names', t => {
  const f = fixture(t)
  for (const p of ['../a.md', 'docs/../a.md', '/tmp/a.md', 'C:/a.md', '\\\\host\\share', 'docs\\a.md', 'docs/con.md', 'docs/a.', 'docs/a?.md', 'docs/a*.md', 'docs/a|b.md']) assert.throws(() => safePath(f.root, p))
})

test('symlinks/junctions and hardlinks cannot alias writable documents', t => {
  const f = fixture(t)
  const external = fs.mkdtempSync(path.join(os.tmpdir(), 'okf-outside-'))
  t.after(() => fs.rmSync(external, { recursive: true, force: true }))
  fs.symlinkSync(external, path.join(f.root, 'docs/alias'), process.platform === 'win32' ? 'junction' : 'dir')
  assert.throws(() => safePath(f.root, 'docs/alias/a.md'), /Symlink/)
  fs.linkSync(path.join(f.root, 'docs/a.md'), path.join(f.root, 'docs/linked.md'))
  assert.throws(() => safePath(f.root, 'docs/linked.md'), /Hardlink/)
})

test('concurrent application lock blocks writes', t => {
  const f = fixture(t)
  const plan = createPlan(f.root)
  f.write('scripts/docs/.okf.lock', 'other process')
  assert.throws(() => applyPlan(f.root, plan), /EEXIST/)
  assert.equal(fs.existsSync(path.join(f.root, 'docs/index.md')), false)
})

test('nested indexes require explicit directory ownership and cover every concept', t => {
  const f = fixture(t, { 'docs/a.md': concept('# A\n'), 'docs/sub/b.md': concept('# B\n') })
  assert(f.check().findings.some(x => x.rule === 'directory'))
  const config = JSON.parse(f.read('scripts/docs/okf.config.json'))
  config.directories['docs/sub'] = { title: 'Sub', description: 'Nested documents.', owned: true }
  f.write('scripts/docs/okf.config.json', JSON.stringify(config))
  applyPlan(f.root, createPlan(f.root))
  assert.match(f.read('docs/index.md').toString(), /sub\/index.md/)
  assert.match(f.read('docs/sub/index.md').toString(), /b.md/)
  assert.deepEqual(f.check().findings, [])
})

test('root and child reserved frontmatter rules and log order are separate from concepts', t => {
  const f = fixture(t, { 'docs/a.md': concept('# A\n'), 'docs/log.md': '# History\n## 2026-01-01\n* One\n## 2026-02-01\n* Two\n', 'docs/index.md': '---\ntype: Guide\n---\n# Index\n' })
  const rules = f.check().findings.map(x => x.rule)
  assert(rules.includes('log-dates'))
  assert(rules.includes('index'))
})

test('optional metadata families are validated only when present', t => {
  const f = fixture(t, { 'docs/a.md': concept('# A\n', 'generated: {by: unknown, at: yesterday}\nverified: {by: process:test, at: yesterday}\nsources: [{title: missing-resource}]\nstale_after: tomorrow\n') })
  for (const rule of ['generated', 'verified', 'sources', 'stale_after']) assert(f.check().findings.some(x => x.rule === rule && x.origin === 'official'))
})

test('a failed second replacement rolls back only our first output and releases the lock', t => {
  const body = '# Original\n'
  const f = fixture(t, { 'docs/a.md': body })
  const plan = createPlan(f.root, { 'docs/a.md': meta })
  const rename = fs.renameSync
  let calls = 0
  try {
    fs.renameSync = (...args) => {
      if (++calls === 2) throw Object.assign(Error('Injected EBUSY'), { code: 'EBUSY' })
      return rename(...args)
    }
    assert.throws(() => applyPlan(f.root, plan), /Injected EBUSY.*recovery journal/)
  } finally { fs.renameSync = rename }
  assert.equal(f.read('docs/a.md').toString(), body)
  assert.equal(fs.existsSync(path.join(f.root, 'docs/index.md')), false)
  assert.equal(fs.existsSync(path.join(f.root, 'scripts/docs/.okf.lock')), false)
})

test('a failed temporary write leaves original documents untouched', t => {
  const f = fixture(t)
  const original = f.read('docs/a.md')
  const plan = createPlan(f.root)
  const write = fs.writeFileSync
  try {
    fs.writeFileSync = (file, ...args) => {
      if (String(file).endsWith('.tmp')) throw Object.assign(Error('Injected ENOSPC'), { code: 'ENOSPC' })
      return write(file, ...args)
    }
    assert.throws(() => applyPlan(f.root, plan), /ENOSPC/)
  } finally { fs.writeFileSync = write }
  assert.deepEqual(f.read('docs/a.md'), original)
  assert.equal(fs.existsSync(path.join(f.root, 'docs/index.md')), false)
})

test('the planner refuses to generate around altered or missing historical evidence', t => {
  const f = fixture(t, { 'docs/a.md': concept('# Rewritten\n') }, { 'docs/a.md': sha('# Original\n') })
  assert.throws(() => createPlan(f.root), /Manual review/)
  fs.unlinkSync(path.join(f.root, 'docs/a.md'))
  assert.throws(() => createPlan(f.root), /Manual review/)
})

test('literal YAML punctuation, comments and block scalars are not treated as aliases', () => {
  const text = concept('# Example\n', 'note: "Use !important, *literal* and &write."\n# &comment is not an anchor\nexample: |\n  *literal* is text here\n')
  assert.equal(parseDocument(Buffer.from(text)).meta.note, 'Use !important, *literal* and &write.')
})

test('impossible calendar dates fail lifecycle and log validation', t => {
  const f = fixture(t, { 'docs/a.md': concept('# A\n', 'stale_after: "2026-02-30T12:00:00Z"\n'), 'docs/log.md': '# History\n## 2026-02-30\n- Impossible\n' })
  assert(f.check().findings.some(x => x.rule === 'stale_after'))
  assert(f.check().findings.some(x => x.rule === 'log-dates'))
})

test('HTML comments neither create links nor satisfy explicit anchors', t => {
  const f = fixture(t, { 'docs/a.md': concept('# A\n<!-- <a id="ghost" href="missing.md">Example</a> -->\n[anchor](#ghost)\n') })
  const findings = f.check().findings
  assert.equal(findings.filter(x => x.rule === 'link-target').length, 0)
  assert(findings.some(x => x.rule === 'link-anchor'))
})

test('unquoted HTML links and escaped HTML fragments are checked', t => {
  const f = fixture(t, { 'docs/a.md': concept('# A\n<a href=missing.md>Broken</a>\n<a id="a&amp;b"></a><a href="#a&amp;b">Valid</a>\n<a title=\'href="not-a-link.md"\' href="#a">Quoted text</a>\n') })
  const findings = f.check().findings
  assert(findings.some(x => x.rule === 'link-target' && x.message.includes('missing.md')))
  assert.equal(findings.filter(x => x.rule === 'link-target').length, 1)
  assert.equal(findings.filter(x => x.rule === 'link-anchor').length, 0)
})

test('valid leap days remain accepted, including offset timestamps', t => {
  const f = fixture(t, { 'docs/a.md': concept('# A\n', 'stale_after: "2028-02-29T12:00:00-03:00"\n'), 'docs/log.md': '# History\n## 2028-02-29\n- Valid\n' })
  assert.equal(f.check().findings.filter(x => ['stale_after', 'log-dates'].includes(x.rule)).length, 0)
})

test('plan output cannot enter the repository through an external junction', t => {
  const f = fixture(t)
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'okf-report-'))
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }))
  fs.symlinkSync(f.root, path.join(dir, 'alias'), process.platform === 'win32' ? 'junction' : 'dir')
  assert.throws(() => main(['plan', '--out', path.join(dir, 'alias', 'report.json')], f.root), /outside the repository/)
  assert.equal(fs.existsSync(path.join(f.root, 'report.json')), false)
})

test('CLI rejects options for another command and duplicate options', t => {
  const f = fixture(t)
  assert.throws(() => main(['check', '--out', 'ignored.json'], f.root), /option/i)
  assert.throws(() => main(['apply', '--plan', 'one.json', '--plan', 'two.json'], f.root), /option/i)
})

test('directory metadata must be complete before an index can be generated', t => {
  const f = fixture(t)
  const config = JSON.parse(f.read('scripts/docs/okf.config.json'))
  delete config.directories.docs.title
  f.write('scripts/docs/okf.config.json', JSON.stringify(config))
  assert.throws(() => createPlan(f.root), /directory/i)
})
