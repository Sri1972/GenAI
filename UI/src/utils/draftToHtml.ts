// Renders a draft wireframe (DraftResult) into a self-contained HTML document
// string for an <iframe srcDoc>. Restored util: converts the draft's markdown
// into styled HTML with a light, dependency-free markdown pass.

interface DraftLike {
  markdown?: string
  title?: string
  pageCount?: number
  architecture?: Record<string, any>
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function inline(s: string): string {
  return s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
}

// Minimal, safe markdown → HTML (headings, lists, code fences, hr, paragraphs).
function markdownToHtml(md: string): string {
  const lines = escapeHtml(md).split('\n')
  const out: string[] = []
  let inList = false
  let inCode = false
  const closeList = () => { if (inList) { out.push('</ul>'); inList = false } }

  for (const raw of lines) {
    const line = raw.replace(/\s+$/, '')
    if (/^```/.test(line)) {
      if (inCode) { out.push('</pre>'); inCode = false }
      else { closeList(); out.push('<pre>'); inCode = true }
      continue
    }
    if (inCode) { out.push(line); continue }
    if (/^\s*[-*]\s+/.test(line)) {
      if (!inList) { out.push('<ul>'); inList = true }
      out.push('<li>' + inline(line.replace(/^\s*[-*]\s+/, '')) + '</li>')
      continue
    }
    closeList()
    const h = line.match(/^(#{1,6})\s+(.*)$/)
    if (h) { const lvl = h[1].length; out.push(`<h${lvl}>${inline(h[2])}</h${lvl}>`); continue }
    if (/^\s*---\s*$/.test(line)) { out.push('<hr/>'); continue }
    if (line.trim() === '') { out.push(''); continue }
    out.push('<p>' + inline(line) + '</p>')
  }
  if (inCode) out.push('</pre>')
  closeList()
  return out.join('\n')
}

export function draftToHtml(draft: DraftLike | null | undefined): string {
  if (!draft) return '<html><body style="font-family:Inter,sans-serif;padding:24px;color:#64748b">No draft available.</body></html>'

  let bodyHtml: string
  if (draft.markdown && draft.markdown.trim()) {
    bodyHtml = markdownToHtml(draft.markdown)
  } else if (draft.architecture) {
    bodyHtml = '<pre>' + escapeHtml(JSON.stringify(draft.architecture, null, 2)) + '</pre>'
  } else {
    bodyHtml = '<p style="color:#64748b">This draft has no preview content.</p>'
  }

  const title = escapeHtml(draft.title || 'Draft Wireframe')
  const meta = draft.pageCount ? `<p class="meta">${draft.pageCount} page${draft.pageCount === 1 ? '' : 's'}</p>` : ''

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
  :root { color-scheme: light; }
  body { font-family: Inter, system-ui, sans-serif; color: #1e293b; margin: 0; padding: 32px 40px; line-height: 1.6; background: #f8fafc; }
  h1 { font-size: 1.6rem; margin: 0 0 4px; color: #0f172a; }
  h2 { font-size: 1.25rem; margin: 1.6rem 0 .5rem; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: .3rem; }
  h3 { font-size: 1.05rem; margin: 1.2rem 0 .4rem; color: #334155; }
  h4, h5, h6 { margin: 1rem 0 .3rem; color: #475569; }
  p { margin: .5rem 0; }
  ul { margin: .4rem 0 .8rem 1.2rem; padding: 0; }
  li { margin: .2rem 0; }
  code { background: #eef2ff; color: #4338ca; padding: 1px 5px; border-radius: 4px; font-size: .9em; }
  pre { background: #0f172a; color: #e2e8f0; padding: 14px 16px; border-radius: 8px; overflow-x: auto; font-size: .85rem; }
  pre code { background: none; color: inherit; padding: 0; }
  hr { border: none; border-top: 1px solid #e2e8f0; margin: 1.5rem 0; }
  a { color: #4f46e5; }
  .meta { color: #64748b; font-size: .85rem; margin: 0 0 1.2rem; }
</style>
</head>
<body>
<h1>${title}</h1>
${meta}
${bodyHtml}
</body>
</html>`
}
