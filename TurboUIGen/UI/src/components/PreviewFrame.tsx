import { ExternalLink, RefreshCw, Zap } from 'lucide-react'
import { useRef } from 'react'

interface Props { url: string | null; loading?: boolean }

export default function PreviewFrame({ url, loading }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const reload = () => {
    if (iframeRef.current) iframeRef.current.src = iframeRef.current.src
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Browser chrome */}
      <div className="h-10 bg-slate-50 border-b border-slate-200 flex items-center px-4 gap-3 flex-shrink-0">
        <div className="flex gap-1.5">
          {['bg-red-500','bg-amber-500','bg-emerald-500'].map(c => (
            <div key={c} className={`w-2.5 h-2.5 rounded-full ${c} opacity-70`} />
          ))}
        </div>
        {url
          ? <div className="flex-1 bg-slate-100 border border-slate-300 rounded-md px-3 py-1 text-xs text-slate-600 flex items-center gap-2 min-w-0">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
              <span className="truncate">{url}</span>
            </div>
          : <div className="flex-1" />
        }
        {url && (
          <div className="flex gap-1">
            <button onClick={reload} className="btn-ghost p-1.5" title="Reload"><RefreshCw size={13} /></button>
            <button onClick={() => window.open(url, '_blank')} className="btn-ghost p-1.5" title="Open in new tab"><ExternalLink size={13} /></button>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 relative overflow-hidden">
        {url ? (
          <iframe ref={iframeRef} src={url} className="absolute inset-0 w-full h-full border-none" title="App Preview" />
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-5 text-center px-8">
            <div className="w-16 h-16 rounded-2xl bg-slate-100 border border-slate-200 flex items-center justify-center">
              <Zap size={28} className="text-slate-400" />
            </div>
            <div>
              <div className="text-slate-600 font-semibold mb-1">No app loaded</div>
              <div className="text-slate-500 text-sm leading-relaxed max-w-xs">
                Generate a new app from the <span className="text-indigo-600">Generate</span> page,
                or start an existing one from <span className="text-indigo-600">Projects</span>.
              </div>
            </div>
            <div className="flex flex-col gap-2 mt-2">
              {['React + TypeScript + Tailwind','React Router navigation','Recharts data visualisation','Vite hot-reload dev server'].map(f => (
                <div key={f} className="flex items-center gap-2 text-xs text-slate-600">
                  <span className="text-emerald-600">✓</span>{f}
                </div>
              ))}
            </div>
          </div>
        )}
        {loading && (
          <div className="absolute inset-0 bg-white/90 flex flex-col items-center justify-center gap-4">
            <div className="w-10 h-10 rounded-full border-2 border-slate-200 border-t-indigo-500 animate-spin" />
            <div className="text-slate-600 text-sm">Building your app — ~30–60 seconds…</div>
          </div>
        )}
      </div>
    </div>
  )
}
