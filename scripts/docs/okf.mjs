#!/usr/bin/env node
// Local documentation tooling. No network, runtime imports or prose generation.
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import yaml from 'js-yaml'
import MarkdownIt from 'markdown-it'
import GithubSlugger from 'github-slugger'

const ownRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const md = new MarkdownIt({ html: true })
const sort = (a, b) => a < b ? -1 : a > b ? 1 : 0
const hash = value => crypto.createHash('sha256').update(value).digest('hex')
const json = value => JSON.stringify(value, null, 2) + '\n'
const string = v => typeof v === 'string' && v.trim().length > 0
const mapping = v => v !== null && typeof v === 'object' && !Array.isArray(v)
const calendarDate = value => {
  if (typeof value !== 'string' || !/^\d{4}-\d\d-\d\d$/.test(value)) return false
  const [year, month, day] = value.split('-').map(Number)
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  return month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1]
}
const date = v => typeof v === 'string' && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(v) && calendarDate(v.slice(0, 10)) && !Number.isNaN(Date.parse(v))
const actor = v => string(v) && /^(?:human:.+|process:.+|[^\s/]+\/[^\s/]+)$/.test(v)
const reserved = p => ['index.md', 'log.md'].includes(path.basename(p))

function inside(root, target) {
  const rel = path.relative(root, target)
  return rel === '' || (!rel.startsWith('..' + path.sep) && rel !== '..' && !path.isAbsolute(rel))
}

// Validate every existing ancestor, not just the final file (junctions included).
export function safePath(root, relative) {
  if (!string(relative) || relative.includes('\\') || /[<>:"|?*\x00-\x1f]/.test(relative) || relative.startsWith('/') || relative.split('/').some(x => !x || x === '.' || x === '..' || /[. ]$/.test(x) || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(x))) throw Error(`Unsafe path: ${relative}`)
  const base = fs.realpathSync(root)
  const full = path.resolve(base, relative)
  if (!inside(base, full)) throw Error(`Outside repository: ${relative}`)
  let parent = base
  for (const part of relative.split('/')) {
    parent = path.join(parent, part)
    if (!fs.existsSync(parent)) {
      // existsSync returns false for dangling symlinks.
      try { if (fs.lstatSync(parent).isSymbolicLink()) throw Error(`Symlink: ${relative}`) } catch (e) { if (e.code !== 'ENOENT') throw e }
      continue
    }
    const stat = fs.lstatSync(parent)
    if (stat.isSymbolicLink() || !inside(base, fs.realpathSync(parent))) throw Error(`Symlink/junction: ${relative}`)
    if (stat.isFile() && stat.nlink > 1) throw Error(`Hardlink: ${relative}`)
  }
  return full
}

export function parseDocument(bytes) {
  if (bytes.length > 5 * 1024 * 1024) throw Error('Markdown exceeds local 5 MiB safety limit')
  const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  if (bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) throw Error('UTF-8 BOM: review manually')
  const crlf = text.includes('\r\n')
  if (/\r(?!\n)/.test(text) || (crlf && /(?<!\r)\n/.test(text))) throw Error('Mixed line endings: review manually')
  const eol = crlf ? '\r\n' : '\n'
  if (!text.startsWith('---' + eol)) return { text, body: text, meta: null, prefix: '', eol }
  const end = text.indexOf(eol + '---', 3 + eol.length)
  if (end < 0 || ![eol, ''].includes(text.slice(end + eol.length + 3, end + eol.length + 3 + eol.length))) throw Error('Unterminated/ambiguous frontmatter')
  const source = text.slice(3 + eol.length, end)
  if (Buffer.byteLength(source) > 65536) throw Error('Frontmatter exceeds 64 KiB')
  // Inspect parsed nodes: punctuation inside strings/comments is ordinary data.
  // Reject anchor definitions before aliases can be reused; JSON_SCHEMA rejects custom tags.
  const meta = yaml.load(source, {
    schema: yaml.JSON_SCHEMA,
    json: false,
    listener(event, state) {
      if (event === 'close' && state.anchor !== null) throw Error('YAML aliases/anchors require manual review')
    }
  })
  if (!mapping(meta)) throw Error('Frontmatter must be a mapping')
  const offset = end + eol.length + 3 + (text.slice(end + eol.length + 3).startsWith(eol) ? eol.length : 0)
  return { text, body: text.slice(offset), meta, prefix: text.slice(0, offset), eol }
}

function walk(root, dir = 'docs') {
  const entries = fs.readdirSync(safePath(root, dir), { withFileTypes: true }).sort((a, b) => sort(a.name, b.name))
  const result = []
  const names = new Set()
  for (const entry of entries) {
    const rel = dir + '/' + entry.name
    safePath(root, rel)
    if (names.has(entry.name.toLowerCase())) throw Error(`Case collision: ${rel}`)
    names.add(entry.name.toLowerCase())
    if (entry.isDirectory()) result.push(...walk(root, rel))
    else if (entry.isFile() && /\.md$/i.test(entry.name)) {
      if (!entry.name.endsWith('.md') || (/^(index|log)\.md$/i.test(entry.name) && !['index.md', 'log.md'].includes(entry.name))) throw Error(`Nonportable Markdown name: ${rel}`)
      result.push(rel)
    }
  }
  return result
}

function load(root) {
  const configBytes = fs.readFileSync(safePath(root, 'scripts/docs/okf.config.json'))
  const config = JSON.parse(configBytes)
  if (config.version !== '0.2' || config.bundle !== 'docs' || !mapping(config.directories) || !Array.isArray(config.routing)) throw Error('Unsupported OKF configuration')
  for (const [dir, entry] of Object.entries(config.directories)) {
    safePath(root, dir)
    if ((dir !== 'docs' && !dir.startsWith('docs/')) || !mapping(entry) || !string(entry.title) || !string(entry.description) || /[\r\n]/.test(entry.title + entry.description) || typeof entry.owned !== 'boolean') throw Error(`Invalid directory metadata/ownership: ${dir}`)
  }
  const historyBytes = fs.readFileSync(safePath(root, 'scripts/docs/historical-bodies.json'))
  const history = JSON.parse(historyBytes)
  if (!mapping(history)) throw Error('Invalid historical body manifest')
  return { config, history, policyHash: hash(Buffer.concat([configBytes, historyBytes])) }
}

function readDocs(root) {
  return walk(root).map(file => {
    const bytes = fs.readFileSync(safePath(root, file))
    return { file, bytes, sha256: hash(bytes) }
  })
}

function validateMeta(meta, add) {
  if (!meta || !string(meta.type)) add('official', 'type', 'Concept needs non-empty string type')
  if (!meta) return
  for (const key of ['title', 'description']) if (!string(meta[key]) || /[\r\n]/.test(meta[key])) add('local', key, `${key} must be a non-empty single line`)
  if ('tags' in meta && (!Array.isArray(meta.tags) || meta.tags.some(x => !string(x)))) add('local', 'tags', 'Use an array of non-empty strings')
  if ('status' in meta && !['draft', 'stable', 'deprecated'].includes(meta.status)) add('official', 'status', 'Unknown lifecycle status')
  for (const key of ['stale_after']) if (key in meta && !date(meta[key])) add('official', key, 'Expected ISO datetime with UTC offset')
  const window = (v, key) => { if (!mapping(v) || !date(v.from) || !date(v.to) || Date.parse(v.from) > Date.parse(v.to)) add('official', key, 'Invalid usage window') }
  if ('usage_window' in meta) window(meta.usage_window, 'usage_window')
  if ('sources' in meta) {
    if (!Array.isArray(meta.sources)) add('official', 'sources', 'Expected sources array')
    else for (const source of meta.sources) {
      if (!mapping(source) || !string(source.resource)) { add('official', 'sources', 'Source requires resource'); continue }
      if ('author' in source && !string(source.author)) add('local', 'sources.author', 'Author must be a string')
      if ('last_modified' in source && !date(source.last_modified)) add('official', 'sources.last_modified', 'Invalid datetime')
      if ('usage_window' in source) window(source.usage_window, 'sources.usage_window')
      if ('usage_count' in source && (!Number.isFinite(source.usage_count) || source.usage_count < 0)) add('local', 'sources.usage_count', 'Expected non-negative count')
    }
  }
  if ('generated' in meta && (!mapping(meta.generated) || !actor(meta.generated.by) || ('at' in meta.generated && !date(meta.generated.at)))) add('official', 'generated', 'Invalid generated actor/datetime')
  if ('verified' in meta) {
    const events = Array.isArray(meta.verified) ? meta.verified : [meta.verified]
    if (!events.length || events.some(v => !mapping(v) || !actor(v.by) || !date(v.at))) add('official', 'verified', 'Invalid verification event')
  }
  if (meta.type === 'Attested Computation') {
    if (!string(meta.runtime)) add('official', 'runtime', 'Attested Computation requires runtime')
    for (const key of ['executor', 'attester']) if (!mapping(meta[key]) || !string(meta[key].resource)) add('local', key, `Explicit ${key}.resource required for local computation profile`)
    if ('parameters' in meta && (!Array.isArray(meta.parameters) || meta.parameters.some(p => !mapping(p) || !string(p.name) || !string(p.type) || typeof p.required !== 'boolean'))) add('local', 'parameters', 'Invalid parameter contract')
  }
}

function markdown(body) {
  const tokens = md.parse(body, {})
  const links = []
  const anchors = new Set()
  const slugger = new GithubSlugger()
  const inlineText = token => (token.children || []).map(t => ['text', 'code_inline', 'image'].includes(t.type) ? t.content : t.type === 'softbreak' ? ' ' : '').join('')
  const visit = token => {
    if (['link_open', 'image'].includes(token.type)) links.push(token.attrGet(token.type === 'image' ? 'src' : 'href'))
    if (['html_inline', 'html_block'].includes(token.type)) {
      const html = token.content.replace(/<!--[\s\S]*?(?:-->|$)/g, '')
      for (const tag of html.matchAll(/<[a-z][\w:-]*(?:[^"'<>]|"[^"]*"|'[^']*')*>/gi)) {
        const attributes = tag[0].replace(/^<[a-z][\w:-]*/i, '')
        for (const attr of attributes.matchAll(/([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g)) {
          const key = attr[1].toLowerCase()
          const value = md.utils.unescapeAll(attr[2] ?? attr[3] ?? attr[4] ?? '')
          if (key === 'id' || (key === 'name' && /^<a(?:\s|>)/i.test(tag[0]))) anchors.add(value)
          if (key === 'href' || key === 'src') links.push(value)
          if (key === 'srcset') links.push(...value.split(',').map(v => v.trim().split(/\s+/)[0]))
        }
      }
    }
    for (const child of token.children || []) visit(child)
  }
  tokens.forEach((t, i) => { if (t.type === 'heading_open') anchors.add(slugger.slug(inlineText(tokens[i + 1]))); visit(t) })
  return { links: links.filter(Boolean), anchors, tokens }
}

function portableTarget(root, full) {
  if (!inside(root, full)) return false
  let current = root
  for (const part of path.relative(root, full).split(path.sep).filter(Boolean)) {
    if (!fs.existsSync(current) || !fs.statSync(current).isDirectory()) return false
    if (!fs.readdirSync(current).includes(part)) return false
    current = path.join(current, part)
    if (fs.lstatSync(current).isSymbolicLink()) return false
  }
  return fs.existsSync(current)
}

export function audit(root = ownRoot) {
  root = fs.realpathSync(root)
  const { config, history, policyHash } = load(root)
  const docs = readDocs(root)
  const findings = []
  const parsed = new Map()
  const addFor = (file, severity = 'required') => (origin, rule, message) => findings.push({ file, severity, origin, rule, message })
  for (const doc of docs) {
    const add = addFor(doc.file)
    try {
      const parsedDoc = parseDocument(doc.bytes)
      parsed.set(doc.file, parsedDoc)
      if (path.basename(doc.file) === 'index.md') {
        if (parsedDoc.meta && (doc.file !== 'docs/index.md' || Object.keys(parsedDoc.meta).some(k => k !== 'okf_version'))) add('official', 'index', 'Only root index may have okf_version frontmatter')
        if (doc.file === 'docs/index.md' && parsedDoc.meta?.okf_version !== '0.2') add('local', 'version', 'Root index must declare "0.2"')
        if (markdown(parsedDoc.body).tokens.some(t => !['heading_open', 'heading_close', 'inline', 'bullet_list_open', 'bullet_list_close', 'list_item_open', 'list_item_close', 'paragraph_open', 'paragraph_close'].includes(t.type))) add('local', 'index-structure', 'Index must use headings and bullet links')
      } else if (path.basename(doc.file) === 'log.md') {
        if (parsedDoc.meta) add('local', 'log', 'Log has no concept frontmatter')
        const dates = [...parsedDoc.body.matchAll(/^## (.+)$/gm)].map(m => m[1].trim())
        if (dates.some(d => !calendarDate(d)) || dates.some((d, i) => i && dates[i - 1] < d)) add('local', 'log-dates', 'Log needs ISO date headings, newest first')
      } else validateMeta(parsedDoc.meta, add)
      if (history[doc.file] && hash(Buffer.from(parsedDoc.body)) !== history[doc.file]) add('local', 'historical-body', 'Historical body changed; restore or document separately, never reseal silently')
    } catch (e) { add('local', 'parse', e.message) }
  }
  for (const file of Object.keys(history)) if (!docs.some(d => d.file === file)) addFor(file)('local', 'historical-missing', 'Protected historical file is missing')
  const directorySet = new Set(['docs'])
  for (const doc of docs) { let dir = path.posix.dirname(doc.file); while (dir !== '.') { directorySet.add(dir); dir = path.posix.dirname(dir) } }
  for (const dir of [...directorySet].sort(sort)) {
    if (!config.directories[dir]) addFor(dir)('local', 'directory', 'Register directory title/description and index ownership')
    if (!docs.some(d => d.file === dir + '/index.md')) addFor(dir + '/index.md')('local', 'index-missing', 'Directory needs an index')
  }
  for (const file of config.routing) {
    if (file.startsWith('docs/')) throw Error('Routing entries must be outside bundle')
    parsed.set(file, parseDocument(fs.readFileSync(safePath(root, file))))
  }
  const anchorCache = new Map()
  let linkCount = 0
  for (const [file, doc] of parsed) {
    for (const href of markdown(doc.body).links) {
      if (/^(?:https?:|mailto:|tel:|data:)/i.test(href) || href.startsWith('//')) continue
      linkCount++
      const add = addFor(file, history[file] ? 'advisory' : 'required')
      try {
        if (/^[a-z][a-z\d+.-]*:/i.test(href)) { add('local', 'link-scheme', 'Unsupported local link scheme'); continue }
        const split = href.indexOf('#')
        const rawPath = (split < 0 ? href : href.slice(0, split)).split('?')[0]
        const fragment = split < 0 ? '' : decodeURIComponent(href.slice(split + 1))
        const decoded = decodeURIComponent(rawPath)
        if (decoded.includes('\\') || decoded.includes('\0')) throw Error('Unsafe link path')
        // OKF root links resolve at bundle root; controls outside it use repository root.
        const base = rawPath.startsWith('/') ? path.join(root, file.startsWith('docs/') ? 'docs' : '') : path.dirname(path.join(root, file))
        let target = decoded ? path.resolve(base, decoded.replace(/^\/+/, '')) : path.join(root, file)
        if (!portableTarget(root, target)) { add('local', 'link-target', `Missing/nonportable target: ${href}`); continue }
        if (fs.statSync(target).isDirectory()) {
          const candidate = ['index.md', 'README.md'].map(p => path.join(target, p)).find(p => fs.existsSync(p))
          if (!candidate && fragment) { add('local', 'link-anchor', `Directory has no document for fragment: ${href}`); continue }
          target = candidate || target
          if (!portableTarget(root, target)) { add('local', 'link-target', `Missing/nonportable directory document: ${href}`); continue }
        }
        if (fragment && /\.md$/i.test(target)) {
          if (!anchorCache.has(target)) anchorCache.set(target, markdown(parseDocument(fs.readFileSync(target)).body).anchors)
          if (!anchorCache.get(target).has(fragment)) add('local', 'link-anchor', `Missing anchor: ${href}`)
        }
      } catch (e) { add('local', 'link', `${href}: ${e.message}`) }
    }
  }
  const rendered = renderIndexes(docs, parsed, directorySet, config)
  for (const [file, text] of rendered) {
    const current = docs.find(d => d.file === file)
    if (current && current.bytes.toString('utf8') !== text) addFor(file)('local', 'index-stale', 'Owned index differs from deterministic inventory')
  }
  return { root, config, history, policyHash, docs, parsed, directorySet, findings, rendered, linkCount }
}

const label = text => text.replace(/[\[\]\\]/g, '\\$&').replace(/[\r\n]/g, ' ')
const url = text => text.split('/').map(x => encodeURIComponent(x)).join('/')

function renderIndexes(docs, parsed, directories, config) {
  const result = new Map()
  for (const dir of [...directories].sort(sort)) {
    const entry = config.directories[dir]
    if (!entry) continue
    const file = dir + '/index.md'
    const eol = parsed.get(file)?.eol || '\n'
    const lines = dir === 'docs' ? ['---', 'okf_version: "0.2"', '---', '# ' + entry.title, ''] : ['# ' + entry.title, '']
    const concepts = docs.filter(d => path.posix.dirname(d.file) === dir && !reserved(d.file))
    if (dir === 'docs' && Array.isArray(config.rootOrder)) {
      const rank = file => { const i = config.rootOrder.indexOf(path.posix.basename(file)); return i < 0 ? config.rootOrder.length : i }
      concepts.sort((a, b) => rank(a.file) - rank(b.file) || sort(a.file, b.file))
    }
    const groups = new Map()
    for (const doc of concepts) {
      const meta = parsed.get(doc.file)?.meta
      if (!string(meta?.title) || !string(meta?.description)) continue
      const group = dir === 'docs' ? (config.rootGroups?.[path.posix.basename(doc.file)] || 'Otros documentos') : 'Documentos'
      if (!groups.has(group)) groups.set(group, [])
      groups.get(group).push(`- [${label(meta.title)}](${url(path.posix.basename(doc.file))}) - ${meta.description}`)
    }
    for (const [group, entries] of groups) lines.push('## ' + group, '', ...entries, '')
    const children = [...directories].filter(p => p !== dir && path.posix.dirname(p) === dir).sort(sort)
    if (children.length) {
      lines.push('## Carpetas', '')
      for (const child of children) { const item = config.directories[child]; if (item) lines.push(`- [${label(item.title)}](${url(path.posix.basename(child))}/index.md) - ${item.description}`) }
      lines.push('')
    }
    if (docs.some(d => d.file === dir + '/log.md')) lines.push('## Historial', '', '- [Registro](log.md) - Cambios documentales de esta carpeta.', '')
    result.set(file, lines.join(eol))
  }
  return result
}

function snapshot(state) { return { policy: state.policyHash, files: state.docs.map(d => ({ file: d.file, sha256: d.sha256 })) } }

export function createPlan(root = ownRoot, metadata = {}) {
  if (!mapping(metadata)) throw Error('Metadata proposals must be a path-keyed mapping')
  const state = audit(root)
  const unsafe = state.findings.filter(f => ['parse', 'historical-body', 'historical-missing'].includes(f.rule))
  if (unsafe.length) throw Error(`Manual review required before planning: ${json(unsafe)}`)
  const changes = []
  const virtual = new Map(state.parsed)
  for (const [file, meta] of Object.entries(metadata)) {
    const doc = state.docs.find(d => d.file === file)
    if (!doc || reserved(file)) throw Error(`Not a concept in inventory: ${file}`)
    const parsed = state.parsed.get(file)
    if (!parsed) throw Error(`Cannot transform invalid document: ${file}`)
    if (parsed.meta) throw Error(`Edit existing frontmatter manually to preserve it: ${file}`)
    const errors = []
    validateMeta(meta, (...args) => errors.push(args))
    if (errors.length) throw Error(`Invalid proposed metadata: ${file}: ${json(errors)}`)
    const header = '---' + parsed.eol + yaml.dump(meta, { schema: yaml.JSON_SCHEMA, lineWidth: -1, noRefs: true }).replace(/\n/g, parsed.eol) + '---' + parsed.eol
    const content = header + parsed.text
    changes.push({ file, before: doc.sha256, after: hash(content), reason: 'add-metadata-preserve-body', content })
    virtual.set(file, parseDocument(Buffer.from(content)))
  }
  for (const [file, content] of renderIndexes(state.docs, virtual, state.directorySet, state.config)) {
    const doc = state.docs.find(d => d.file === file)
    if (doc?.sha256 === hash(content)) continue
    // Existing indexes must be explicitly declared as owned. Their bytes remain in the plan for review.
    if (state.config.directories[path.posix.dirname(file)]?.owned !== true) throw Error(`Index ownership not granted: ${file}`)
    changes.push({ file, before: doc?.sha256 || null, after: hash(content), reason: 'generate-owned-index', content })
  }
  changes.sort((a, b) => sort(a.file, b.file))
  return { format: 1, version: '0.2', snapshot: snapshot(state), metadata, changes }
}

function atomicWrite(full, bytes) {
  const temp = full + '.okf-' + crypto.randomUUID() + '.tmp'
  try {
    fs.writeFileSync(temp, bytes, { flag: 'wx' })
    fs.renameSync(temp, full)
  } finally { if (fs.existsSync(temp)) fs.unlinkSync(temp) }
}

export function applyPlan(root = ownRoot, plan) {
  root = fs.realpathSync(root)
  if (plan?.format !== 1 || plan.version !== '0.2' || !Array.isArray(plan.changes)) throw Error('Unsupported plan')
  const lock = safePath(root, 'scripts/docs/.okf.lock')
  const fd = fs.openSync(lock, 'wx')
  let recovery
  const completed = []
  try {
    const state = audit(root)
    const expectedAfter = new Map(plan.snapshot.files.map(d => [d.file, d.sha256]))
    for (const c of plan.changes) expectedAfter.set(c.file, c.after)
    const afterSnapshot = { policy: plan.snapshot.policy, files: [...expectedAfter].sort((a, b) => sort(a[0], b[0])).map(([file, sha256]) => ({ file, sha256 })) }
    if (json(snapshot(state)) === json(afterSnapshot)) return { written: 0 }
    if (json(snapshot(state)) !== json(plan.snapshot)) throw Error('Stale plan: inventory, content or policy changed; generate a new plan')
    const expected = createPlan(root, plan.metadata)
    if (json(expected) !== json(plan)) throw Error('Plan differs from deterministic proposal; regenerate and review')
    const current = new Map(state.docs.map(d => [d.file, d]))
    const prepared = plan.changes.map(c => {
      if (!c.file.startsWith('docs/') || !c.file.endsWith('.md')) throw Error(`Outside write scope: ${c.file}`)
      const full = safePath(root, c.file)
      if (!fs.existsSync(path.dirname(full))) throw Error('Create/classify documentary directories before planning')
      if (state.history[c.file] && hash(Buffer.from(parseDocument(Buffer.from(c.content)).body)) !== state.history[c.file]) throw Error(`Historical body change: ${c.file}`)
      return { ...c, full, original: current.get(c.file)?.bytes || null }
    })
    if (!prepared.length) return { written: 0 }
    // Persistent journal belongs outside the bundle; retained only on failure for manual recovery.
    recovery = fs.mkdtempSync(path.join(os.tmpdir(), 'opengym-okf-recovery-'))
    const journal = prepared.map((c, i) => { if (c.original) fs.writeFileSync(path.join(recovery, `${i}.before`), c.original); return { file: c.file, before: c.before, after: c.after, backup: c.original ? `${i}.before` : null } })
    fs.writeFileSync(path.join(recovery, 'journal.json'), json(journal))
    for (const c of prepared) {
      safePath(root, c.file)
      const actual = fs.existsSync(c.full) ? hash(fs.readFileSync(c.full)) : null
      if (actual !== c.before) throw Error(`Concurrent edit: ${c.file}`)
      atomicWrite(c.full, Buffer.from(c.content))
      completed.push(c)
    }
    return { written: completed.length }
  } catch (error) {
    // Revert only our exact outputs; preserve any subsequent edit and its recovery copy.
    for (const c of completed.reverse()) {
      try {
        safePath(root, c.file)
        if (hash(fs.readFileSync(c.full)) !== c.after) continue
        if (c.original) atomicWrite(c.full, c.original)
        else fs.unlinkSync(c.full)
      } catch { /* Recovery journal retains the original bytes. */ }
    }
    if (recovery) error.message += `; recovery journal: ${recovery}`
    throw error
  } finally {
    fs.closeSync(fd)
    fs.unlinkSync(lock)
  }
}

export function main(args = process.argv.slice(2), root = ownRoot) {
  const [command, ...rest] = args
  const options = {}
  const allowed = { check: ['--json'], plan: ['--out', '--metadata'], apply: ['--plan'] }
  const seen = new Set()
  for (let i = 0; i < rest.length; i++) {
    if (!allowed[command]?.includes(rest[i]) || seen.has(rest[i])) throw Error(`Invalid/duplicate option for ${command}: ${rest[i]}`)
    seen.add(rest[i])
    if (rest[i] === '--json') options.json = true
    else if (['--out', '--plan', '--metadata'].includes(rest[i]) && rest[i + 1] && !rest[i + 1].startsWith('--')) options[rest[i].slice(2)] = rest[++i]
    else throw Error(`Unknown/incomplete option: ${rest[i]}`)
  }
  if (command === 'check') {
    const state = audit(root)
    const report = { version: '0.2', concepts: state.docs.filter(d => !reserved(d.file)).length, indexes: state.docs.filter(d => path.basename(d.file) === 'index.md').length, localLinks: state.linkCount, findings: state.findings }
    console.log(options.json ? json(report) : `${report.concepts} concepts, ${report.indexes} indexes, ${report.localLinks} local links\n${report.findings.map(f => `${f.severity} [${f.origin}/${f.rule}] ${f.file}: ${f.message}`).join('\n') || 'OK'}`)
    return state.findings.some(f => f.severity === 'required') ? 1 : 0
  }
  if (command === 'plan') {
    if (!options.out) throw Error('plan requires --out <temporary-file.json>')
    const requested = path.resolve(options.out)
    const output = path.join(fs.realpathSync(path.dirname(requested)), path.basename(requested))
    if (inside(fs.realpathSync(root), output)) throw Error('Write plan reports outside the repository')
    const metadata = options.metadata ? JSON.parse(fs.readFileSync(options.metadata, 'utf8')) : {}
    const plan = createPlan(root, metadata)
    fs.writeFileSync(output, json(plan), { flag: 'wx' })
    console.log(`${plan.changes.length} proposed changes: ${output}`)
    return 0
  }
  if (command === 'apply') {
    if (!options.plan) throw Error('apply requires --plan <reviewed-file.json>')
    console.log(json(applyPlan(root, JSON.parse(fs.readFileSync(options.plan, 'utf8')))))
    return 0
  }
  throw Error('Usage: node scripts/docs/okf.mjs check [--json] | plan --out FILE [--metadata FILE] | apply --plan FILE')
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try { process.exitCode = main() } catch (error) { console.error(error.message); process.exitCode = 2 }
}
