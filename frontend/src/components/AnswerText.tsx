import { Fragment, type ReactNode } from 'react'

/**
 * Model-written prose, rendered as a message a person would type.
 *
 * Paragraphs, "- " / "* " / "1. " lists, **bold**, inline `code` and fenced
 * code blocks — nothing else, and no HTML injection: every piece becomes a
 * React text node. The clean-up mirrors the server's `plain_answer`
 * (backend/core/formatting.py), so text still streaming in and messages stored
 * before the server cleaned them read the same as a finished answer. Both are
 * idempotent: code keeps its backticks and fences, so cleaning a stored answer
 * again changes nothing.
 */

const LENTICULAR = /【[^】\n]*】/g
const SOURCE_PAREN = /\s*[*_]*\(\s*(?:sources?|per|see)\s*:[^()\n]*\)[*_]*/gi
const SOURCE_LINE = /^(\s*)[*_>]*\s*\(?\s*[*_]*\s*(?:sources?|references?|citations?)\s*[*_]*\s*:\s*[*_]*\s*(.*)$/i
const LIST_ITEM = /^\s*(?:[-*+•●▪◦]|\d+[.)])\s+/
const LINK = /(?<![\w\]])\[([^[\]\n]+)\]\((?:[^()\s]|\([^()\s]*\))+\)/g
const REF_CHAIN = /(?:\[(?:\^?\d+(?:\s*[,–-]\s*\^?\d+)*|\^[\w-]+|\d+(?::\d+)?†[^\]\n]*)\])+/g
const RANGE = /^\[\d+\s*[–-]\s*\d+\]$/
const BRACKET = /\[([^[\]\n]{1,200})\]/g
const LABEL_COLON = /^\s*(?:source|sources|confluence|jira|slack|github|gitlab|repo|meeting|file|doc|document|upload|url|web|wiki|team answers?)\s*:/i
const CONNECTOR = /^\s*(?:jira\s+[A-Za-z][A-Za-z0-9]+-\d+\b|slack\s+#[\w-]+)/i
const REPO_SLUG = /^[\w.-]{2,}\/[\w.-]{2,}(?:\/[\w./-]*)?$/
const FILE_PATH = /^[\w./-]+\.[A-Za-z]{1,5}$/
const DOC_EXT = /\.(?:md|pdf|docx?|txt|ya?ml|json|csv|xlsx?|pptx?|html?)$/i
const RULE = /^\s*([-*_])(?:\s*\1){2,}\s*$/
const TABLE_SEP = /^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$/
const HEADING = /^\s*#{1,6}\s+(.*?)\s*#*\s*$/
const FENCE = /^\s*(`{3,}|~{3,})/

function isSourceLabel(inner: string): boolean {
  const s = inner.trim()
  if (!s) return false
  if (s.includes('›') || s.includes('†') || LABEL_COLON.test(s) || CONNECTOR.test(s)) return true
  if (REPO_SLUG.test(s) && /[-_.\d]/.test(s)) return true
  return FILE_PATH.test(s) && (s.includes('/') || DOC_EXT.test(s))
}

function cleanInline(line: string): string {
  const shelf: string[] = []
  let s = line.replace(/`([^`\n]+)`/g, (_m, code: string) => {
    shelf.push(code)
    return '\uE000' + (shelf.length - 1) + '\uE001'
  })
  s = s.replace(LENTICULAR, '').replace(SOURCE_PAREN, '').replace(LINK, '$1')
  s = s.replace(REF_CHAIN, (match: string, offset: number, whole: string) => {
    const before = offset > 0 ? whole[offset - 1] : ''
    const rest = whole.slice(offset + match.length)
    if (match.includes('†') || match.includes('^')) return ''
    if (/^[+*?{]/.test(rest)) return match                 // [0-9]+ is a pattern
    if (/[A-Za-z0-9_)\]]/.test(before)) {
      // arr[1] to read it is code; only a marker glued to a sentence end is a citation.
      return /^[.,;:!?]?\s*$|^[.,;:!?](?=\s)/.test(rest) ? '' : match
    }
    if (RANGE.test(match)) return /[.!?]\s*$/.test(whole.slice(0, offset)) ? '' : match
    return ''
  })
  s = s.replace(BRACKET, (match: string, inner: string) => (isSourceLabel(inner) ? '' : match))
  s = s.replace(/\*{3}(?=\S)([^*\n]+?)(?<=\S)\*{3}/g, '**$1**')
  s = s.replace(/_{3}(?=\S)([^_\n]+?)(?<=\S)_{3}/g, '**$1**')
  s = s.replace(/(^|[^*\w])\*(?![\s*])([^*\n]+?)(?<![\s*])\*(?![*\w])/g, '$1$2')
  s = s.replace(/(^|[^\w_])_(?![\s_])([^_\n]+?)(?<![\s_])_(?![\w_])/g, '$1$2')
  s = s.replace(/\*\*\s*\*\*/g, '')
  s = s.replace(/(\*\*[^*\n]*?)\s+\*\*(?=[\s.,;:!?]|$)/g, '$1**')
  s = s.replace(/[ \t]+([.,;:!?])(?=\s|$)/g, '$1')
  s = s.replace(/(\S)[ \t]{2,}/g, '$1 ')
  s = s.replace(/(?<![\w)\]])\(\s*\)/g, '')
  // Inline code comes back wrapped in backticks so the renderer can style it.
  return s.replace(/\uE000(\d+)\uE001/g, (_m, i: string) => '`' + (shelf[Number(i)] ?? '') + '`').trimEnd()
}

function isEmptyLabel(rest: string): boolean {
  return !cleanInline(rest).replace(/[\s*_()[\],;.:—–-]/g, '')
}

/** Mid-stream, drop a marker or list number that is still being written, so it does not flash. */
function trimUnfinishedTail(text: string): string {
  const openFences = text.split('\n').filter((l) => FENCE.test(l)).length % 2 === 1
  if (openFences) return text
  return text
    .replace(/【[^】\n]*$/, '')
    .replace(/\[[^\]\n]*$/, '')
    .replace(/(^|\n)\s*\d+[.)]?\s*$/, '$1')
}

/** The answer with markers, bracketed source labels, tables and headings removed. */
export function cleanAnswer(text: string | null | undefined, live = false): string {
  if (!text) return ''
  const lines = (live ? trimUnfinishedTail(text) : text).replace(/\r\n/g, '\n').split('\n')
  const out: string[] = []
  let fence: string | null = null
  let skippingSources = false
  lines.forEach((original, i) => {
    let raw = original
    const opener = FENCE.exec(raw)
    if (fence !== null) {
      out.push(raw.trimEnd())
      if (opener && opener[1][0] === fence[0] && opener[1].length >= fence.length
          && !raw.trim().slice(opener[1].length).trim()) fence = null
      return
    }
    if (opener) { fence = opener[1]; skippingSources = false; out.push(raw.trimEnd()); return }

    if (skippingSources) {
      if (LIST_ITEM.test(raw)) return
      if (!raw.trim() && i + 1 < lines.length && LIST_ITEM.test(lines[i + 1])) return
      skippingSources = false
    }
    if (RULE.test(raw) || TABLE_SEP.test(raw)) return
    const source = SOURCE_LINE.exec(raw)
    if (source) {
      const rest = source[2].replace(/[)*_\s]+$/, '')
      if (isEmptyLabel(rest)) { skippingSources = true; return }
      const trailing = !lines.slice(i + 1).some((n) => n.trim())
      const hasBody = out.some((o) => o.trim())
      if (trailing && hasBody && rest.length <= 120 && !/[.!?]$/.test(rest)) return
      raw = source[1] + rest
    }
    let line: string
    const t = raw.trim()
    if (t.startsWith('|') && (t.match(/\|/g) ?? []).length >= 2) {
      const cells = t.replace(/^\||\|$/g, '').split('|').map((c) => c.trim()).filter(Boolean)
      line = cells.length ? cleanInline('- ' + cells.join(' — ')) : ''
    } else {
      const h = HEADING.exec(raw)
      if (h) {
        const title = cleanInline(h[1]).replace(/\*\*/g, '').trim()
        line = title ? `**${title}**` : ''
      } else {
        line = cleanInline(raw.replace(/^(\s*)(?:[*•●▪◦]|\+)\s+/, '$1- '))
      }
    }
    if (/^\s*(?:[-*]|\d+\.)\s*$/.test(line)) return
    out.push(line)
  })
  return out.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

export function renderInline(text: string, key: string): ReactNode[] {
  // Code first: a `**kwargs` inside backticks is neither a bold marker nor counted as one.
  const segments = text.split(/(`[^`\n]+`)/g).filter(Boolean)
  const isCode = (seg: string) => seg.length > 2 && seg.startsWith('`') && seg.endsWith('`')
  // Mid-stream, a bold can be opened and not yet closed; show it without the marker.
  const markers = segments.filter((seg) => !isCode(seg)).reduce((n, seg) => n + (seg.match(/\*\*/g) ?? []).length, 0)
  if (markers % 2 === 1) {
    for (let si = segments.length - 1; si >= 0; si--) {
      if (isCode(segments[si])) continue
      const at = segments[si].lastIndexOf('**')
      if (at >= 0) { segments[si] = segments[si].slice(0, at) + segments[si].slice(at + 2); break }
    }
  }
  const nodes: ReactNode[] = []
  segments.forEach((seg, si) => {
    if (isCode(seg)) {
      nodes.push(<code key={`${key}-${si}`} className="rounded bg-background/70 px-1 py-0.5 font-mono text-[0.9em]">{seg.slice(1, -1)}</code>)
      return
    }
    seg.split(/(\*\*[^*\n]+?\*\*)/g).filter(Boolean).forEach((part, pi) => {
      if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
        nodes.push(<strong key={`${key}-${si}-${pi}`} className="font-semibold">{part.slice(2, -2)}</strong>)
      } else {
        nodes.push(<Fragment key={`${key}-${si}-${pi}`}>{part}</Fragment>)
      }
    })
  })
  return nodes
}

export type Block =
  | { kind: 'p'; lines: string[] }
  | { kind: 'ul'; items: string[] }
  | { kind: 'ol'; items: string[]; start: number }
  | { kind: 'pre'; lines: string[] }

export function toBlocks(text: string): Block[] {
  const blocks: Block[] = []
  let current: Block | null = null
  let fence: string | null = null
  const flush = () => { if (current) blocks.push(current); current = null }
  for (const line of text.split('\n')) {
    const opener = FENCE.exec(line)
    if (fence !== null) {
      // Code is shown as written: no list, heading, bold or bracket rules inside it.
      if (opener && opener[1][0] === fence[0] && opener[1].length >= fence.length && !line.trim().slice(opener[1].length).trim()) {
        fence = null
        flush()
      } else if (current?.kind === 'pre') {
        current.lines.push(line)
      }
      continue
    }
    if (opener) { flush(); fence = opener[1]; current = { kind: 'pre', lines: [] }; continue }
    if (!line.trim()) { flush(); continue }
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line)
    const numbered = /^\s*(\d+)[.)]\s+(.*)$/.exec(line)
    if (bullet) {
      if (current?.kind !== 'ul') { flush(); current = { kind: 'ul', items: [] } }
      current.items.push(bullet[1])
    } else if (numbered) {
      if (current?.kind !== 'ol') { flush(); current = { kind: 'ol', items: [], start: Number(numbered[1]) || 1 } }
      current.items.push(numbered[2])
    } else {
      if (current?.kind !== 'p') { flush(); current = { kind: 'p', lines: [] } }
      current.lines.push(line.trim())
    }
  }
  flush()
  return blocks
}

export function AnswerText({ text, className = '', live = false }: {
  text: string | null | undefined
  className?: string
  /** The text is still streaming in: hide markers that are only half written. */
  live?: boolean
}) {
  const blocks = toBlocks(cleanAnswer(text, live))
  if (blocks.length === 0) return null
  return (
    <div className={`flex flex-col gap-2 break-words ${className}`}>
      {blocks.map((b, bi) => {
        if (b.kind === 'pre') {
          return (
            <pre key={bi} className="overflow-x-auto rounded-md bg-background/70 px-3 py-2 font-mono text-[0.85em] leading-relaxed">
              <code>{b.lines.join('\n')}</code>
            </pre>
          )
        }
        if (b.kind === 'ul') {
          return (
            <ul key={bi} className="list-disc space-y-1 pl-5">
              {b.items.map((item, ii) => <li key={ii}>{renderInline(item, `${bi}-${ii}`)}</li>)}
            </ul>
          )
        }
        if (b.kind === 'ol') {
          return (
            <ol key={bi} start={b.start} className="list-decimal space-y-1 pl-5">
              {b.items.map((item, ii) => <li key={ii}>{renderInline(item, `${bi}-${ii}`)}</li>)}
            </ol>
          )
        }
        return (
          <p key={bi}>
            {b.lines.map((line, li) => (
              <Fragment key={li}>
                {li > 0 && <br />}
                {renderInline(line, `${bi}-${li}`)}
              </Fragment>
            ))}
          </p>
        )
      })}
    </div>
  )
}
