import { useCallback, useEffect, useState } from 'react'
import {
  Plus, Zap, ArrowLeft, Pencil, Trash2, Check, X, ExternalLink, RefreshCw, Sparkles, Loader2,
} from 'lucide-react'
import { workspaces, WorkspaceWebapp } from '../../hooks/useApi'
import ChatPanel from '../agent/ChatPanel'

/** The UI-App lens inside a project: many auto-named prototypes, each an SDK-native chat build. */
export default function WebAppLens({ project, incoming, onConsumed, defaultMode = 'collaborate' }: {
  project: string
  incoming?: { app: WorkspaceWebapp; seed: string } | null
  onConsumed?: () => void
  defaultMode?: 'collaborate' | 'autopilot'
}) {
  const [apps, setApps] = useState<WorkspaceWebapp[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<WorkspaceWebapp | null>(null)
  const [seed, setSeed] = useState<string | undefined>()

  const refresh = useCallback(async () => {
    try { setApps(await workspaces.listWebapps(project)) } catch {}
    finally { setLoading(false) }
  }, [project])
  useEffect(() => { refresh() }, [refresh])

  // Handoff from the brainstorm: open the freshly-created prototype and seed its first message.
  useEffect(() => {
    if (incoming) {
      setSelected(incoming.app)
      setSeed(incoming.seed)
      onConsumed?.()
    }
  }, [incoming, onConsumed])

  const createNew = async () => {
    try {
      const w = await workspaces.createWebapp(project)
      await refresh()
      setSelected(w)
    } catch {}
  }

  if (selected) {
    return (
      <PrototypeView
        key={selected.key} project={project} app={selected} seed={seed} defaultMode={defaultMode}
        onBack={() => { setSelected(null); setSeed(undefined); refresh() }}
        onRenamed={w => setSelected(w)}
        onDeleted={() => { setSelected(null); setSeed(undefined); refresh() }}
      />
    )
  }

  return (
    <div className="h-full overflow-auto px-8 py-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-lg font-semibold text-slate-800">App prototypes</h2>
            <p className="text-sm text-slate-500">Each prototype is a conversational build that reads this project's reference files.</p>
          </div>
          <button onClick={createNew}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 shrink-0">
            <Plus size={15} /> New prototype
          </button>
        </div>

        {loading ? (
          <div className="py-12 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin mx-auto" /></div>
        ) : apps.length === 0 ? (
          <div className="border border-dashed border-slate-300 rounded-xl py-14 text-center">
            <Zap className="w-8 h-8 mx-auto mb-3 text-slate-300" />
            <p className="text-sm text-slate-500">No prototypes yet.</p>
            <button onClick={createNew} className="text-violet-600 text-sm font-medium hover:underline mt-1">Start your first one</button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {apps.map(a => (
              <button key={a.key} onClick={() => setSelected(a)}
                className="group text-left bg-white border border-slate-200 rounded-xl p-4 hover:border-violet-300 hover:shadow-sm transition-all">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-lg bg-violet-50 grid place-items-center shrink-0">
                    <Zap className="w-4 h-4 text-violet-600" />
                  </div>
                  <div className="min-w-0">
                    <div className="font-medium text-slate-800 text-sm truncate">{a.appId}</div>
                    <div className="text-xs text-slate-400 truncate">Open to build & preview</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function PrototypeView({ project, app, seed, defaultMode, onBack, onRenamed, onDeleted }: {
  project: string; app: WorkspaceWebapp; seed?: string; defaultMode?: 'collaborate' | 'autopilot'
  onBack: () => void; onRenamed: (w: WorkspaceWebapp) => void; onDeleted: () => void
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [iframeKey, setIframeKey] = useState(0)
  const [opening, setOpening] = useState(true)
  const [renaming, setRenaming] = useState(false)
  const [renameVal, setRenameVal] = useState(app.appId)
  const [renameErr, setRenameErr] = useState('')

  // Reopen: boot the app's servers if it already has a real build; skeletons stay on the empty state.
  useEffect(() => {
    let cancelled = false
    setOpening(true)
    fetch(`/api/agent/${encodeURIComponent(app.key)}/open`, { method: 'POST' })
      .then(r => (r.ok ? r.json() : null))
      .then(st => {
        if (cancelled) return
        if (st?.hasApp && st?.previewUrl) { setPreviewUrl(st.previewUrl); setIframeKey(k => k + 1) }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setOpening(false) })
    return () => { cancelled = true }
  }, [app.key])

  const doRename = async () => {
    const v = renameVal.trim()
    if (!v || v === app.appId) { setRenaming(false); return }
    try {
      const w = await workspaces.renameWebapp(project, app.appId, v)
      setRenaming(false); setRenameErr('')
      onRenamed(w)
    } catch (e: any) { setRenameErr(e?.message || 'Rename failed') }
  }

  const doDelete = async () => {
    if (!confirm(`Delete prototype "${app.appId}"? This removes its files permanently.`)) return
    try { await workspaces.deleteWebapp(project, app.appId); onDeleted() } catch {}
  }

  const effectivePreview = previewUrl || app.previewUrl

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Prototype bar */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-200 bg-white">
        <button onClick={onBack} title="All prototypes" className="p-1.5 rounded hover:bg-slate-100 text-slate-500"><ArrowLeft size={15} /></button>
        {renaming ? (
          <div className="flex items-center gap-1.5">
            <input autoFocus value={renameVal} onChange={e => { setRenameVal(e.target.value); setRenameErr('') }}
              onKeyDown={e => { if (e.key === 'Enter') doRename(); if (e.key === 'Escape') setRenaming(false) }}
              className="border border-violet-300 rounded px-2 py-1 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-violet-200" />
            <button onClick={doRename} className="text-emerald-600 hover:text-emerald-700"><Check size={15} /></button>
            <button onClick={() => setRenaming(false)} className="text-slate-400 hover:text-slate-600"><X size={15} /></button>
            {renameErr && <span className="text-xs text-red-500">{renameErr}</span>}
          </div>
        ) : (
          <>
            <Zap size={15} className="text-violet-600" />
            <span className="font-semibold text-slate-700 text-sm">{app.appId}</span>
            <button onClick={() => { setRenameVal(app.appId); setRenaming(true) }} title="Rename"
              className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-600"><Pencil size={12} /></button>
          </>
        )}
        <button onClick={doDelete} title="Delete prototype"
          className="ml-auto p-1.5 rounded hover:bg-red-50 text-slate-400 hover:text-red-600"><Trash2 size={14} /></button>
      </div>

      {/* Chat | Preview */}
      <div className="flex-1 min-h-0 flex">
        <div className="w-[40%] min-w-[360px] max-w-[520px] border-r border-slate-200 flex flex-col min-h-0">
          <ChatPanel project={app.key} onPreview={setPreviewUrl} initialMessage={seed} defaultMode={defaultMode} />
        </div>
        <div className="flex-1 min-w-0 flex flex-col min-h-0 bg-slate-100">
          <div className="px-4 py-2 border-b border-slate-200 bg-white flex items-center gap-3">
            <div className="flex gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
            </div>
            <span className="text-xs text-slate-400 font-mono truncate">{effectivePreview}</span>
            <button onClick={() => setIframeKey(k => k + 1)} title="Reload"
              className="ml-auto p-1.5 rounded hover:bg-slate-100 text-slate-500"><RefreshCw className="w-3.5 h-3.5" /></button>
            <a href={effectivePreview} target="_blank" rel="noopener" title="Open in new tab"
              className="p-1.5 rounded hover:bg-slate-100 text-slate-500"><ExternalLink className="w-3.5 h-3.5" /></a>
          </div>
          <div className="flex-1 min-h-0">
            {previewUrl
              ? <iframe key={iframeKey} src={effectivePreview} className="w-full h-full border-0" title="Preview" />
              : opening
                ? <div className="h-full grid place-items-center text-slate-400"><div className="text-center"><RefreshCw className="w-6 h-6 mx-auto mb-2 animate-spin" /><p className="text-sm">Starting…</p></div></div>
                : <div className="h-full grid place-items-center text-slate-400"><div className="text-center"><Sparkles className="w-8 h-8 mx-auto mb-2 text-slate-300" /><p className="text-sm">Describe the app in the chat and I'll build it live.</p></div></div>}
          </div>
        </div>
      </div>
    </div>
  )
}
