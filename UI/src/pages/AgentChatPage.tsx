import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Sparkles, ExternalLink, RefreshCw } from 'lucide-react'
import ChatPanel from '../components/agent/ChatPanel'

function slugify(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9-]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') || 'app'
}

export default function AgentChatPage() {
  const { name } = useParams()
  const [draftName, setDraftName] = useState('')
  const [project, setProject] = useState<string | null>(name ?? null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [iframeKey, setIframeKey] = useState(0)
  const [opening, setOpening] = useState(!!name)   // reopening an existing project

  // Reopening an existing project: bring its Vite/API servers back up (no wipe — the
  // backend only starts servers for a project that already has a real app) and then show
  // its live preview. A never-built skeleton returns hasApp=false → stays on the "describe
  // it" state instead of loading a broken iframe.
  useEffect(() => {
    if (!name) return
    let cancelled = false
    setOpening(true)
    fetch(`/api/agent/${encodeURIComponent(name)}/open`, { method: 'POST' })
      .then(r => (r.ok ? r.json() : null))
      .then(st => {
        if (cancelled) return
        if (st?.hasApp && st?.previewUrl) {
          setPreviewUrl(st.previewUrl)
          setIframeKey(k => k + 1)   // load once the server is confirmed up
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setOpening(false) })
    return () => { cancelled = true }
  }, [name])

  const startNew = () => { if (draftName.trim()) setProject(slugify(draftName)) }

  if (!project) {
    return (
      <div className="flex-1 grid place-items-center bg-slate-50">
        <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl p-8 text-center shadow-sm">
          <div className="w-14 h-14 rounded-2xl bg-violet-100 grid place-items-center mx-auto mb-4">
            <Sparkles className="w-7 h-7 text-violet-600" />
          </div>
          <h2 className="text-lg font-semibold text-slate-800 mb-1">New conversational build</h2>
          <p className="text-sm text-slate-500 mb-5">Name your project, then chat with the agent to build and refine it.</p>
          <div className="flex gap-2">
            <input
              value={draftName} onChange={e => setDraftName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && startNew()}
              placeholder="e.g. sales-dashboard"
              className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-200"
            />
            <button onClick={startNew} disabled={!draftName.trim()}
              className="px-4 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 disabled:opacity-40">
              Start
            </button>
          </div>
        </div>
      </div>
    )
  }

  const effectivePreview = previewUrl || `/app/${project}/`

  return (
    <div className="flex-1 min-h-0 flex">
      {/* Left: chat */}
      <div className="w-[42%] min-w-[380px] max-w-[560px] border-r border-slate-200 flex flex-col min-h-0">
        <div className="px-4 py-3 border-b border-slate-200 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-violet-600" />
          <span className="font-semibold text-slate-700 text-sm">{project}</span>
          <span className="text-xs text-slate-400 ml-auto">SDK-native builder</span>
        </div>
        <ChatPanel project={project} onPreview={setPreviewUrl} />
      </div>

      {/* Right: live preview */}
      <div className="flex-1 min-w-0 flex flex-col min-h-0 bg-slate-100">
        <div className="px-4 py-2.5 border-b border-slate-200 bg-white flex items-center gap-3">
          <div className="flex gap-1.5">
            <span className="w-3 h-3 rounded-full bg-red-400" />
            <span className="w-3 h-3 rounded-full bg-amber-400" />
            <span className="w-3 h-3 rounded-full bg-emerald-400" />
          </div>
          <span className="text-xs text-slate-400 font-mono truncate">{effectivePreview}</span>
          <button onClick={() => setIframeKey(k => k + 1)} title="Reload preview"
            className="ml-auto p-1.5 rounded hover:bg-slate-100 text-slate-500"><RefreshCw className="w-3.5 h-3.5" /></button>
          <a href={effectivePreview} target="_blank" rel="noopener" title="Open in new tab"
            className="p-1.5 rounded hover:bg-slate-100 text-slate-500"><ExternalLink className="w-3.5 h-3.5" /></a>
        </div>
        <div className="flex-1 min-h-0">
          {previewUrl
            ? <iframe key={iframeKey} src={effectivePreview} className="w-full h-full border-0" title="Preview" />
            : opening
              ? (
                <div className="h-full grid place-items-center text-center text-slate-400">
                  <div>
                    <RefreshCw className="w-7 h-7 mx-auto mb-3 text-slate-300 animate-spin" />
                    <p className="text-sm">Starting your app…</p>
                  </div>
                </div>
              )
              : (
                <div className="h-full grid place-items-center text-center text-slate-400">
                  <div>
                    <Sparkles className="w-8 h-8 mx-auto mb-3 text-slate-300" />
                    <p className="text-sm">No app here yet.</p>
                    <p className="text-xs mt-1">Describe what you'd like in the chat and I'll build it live.</p>
                  </div>
                </div>
              )}
        </div>
      </div>
    </div>
  )
}
