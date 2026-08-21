// Parse the builder's end-of-build ```turbo-summary {json}``` block out of an assistant message
// so it can render as a designed card and the raw fence never shows in the chat.

export interface TurboSummary {
  built?: string[]
  howToUse?: string
  assumed?: string[]
  next?: string[]
}

const FENCE = '```turbo-summary'

export function splitSummary(content: string): { text: string; summary: TurboSummary | null } {
  const open = content.indexOf(FENCE)
  if (open === -1) return { text: content, summary: null }

  const after = content.slice(open + FENCE.length)
  const close = after.indexOf('```')
  if (close === -1) {
    // still streaming — the block isn't closed yet; hide the partial fence
    return { text: content.slice(0, open).trimEnd(), summary: null }
  }

  const jsonStr = after.slice(0, close).trim()
  let summary: TurboSummary | null = null
  try {
    const parsed = JSON.parse(jsonStr)
    if (parsed && typeof parsed === 'object') summary = parsed as TurboSummary
  } catch { /* leave summary null on malformed json */ }

  const text = (content.slice(0, open) + after.slice(close + 3)).trim()
  return { text, summary }
}
