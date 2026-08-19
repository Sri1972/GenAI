import { ExternalLink, RefreshCw, Square, Zap } from 'lucide-react'
import { useRef } from 'react'
import { GenerateStep } from '../types'

const STEP_MESSAGES: Record<string, string> = {
  figma_api: 'Fetching Figma design data…',
  screenshot_start: 'Exporting Figma frames…',
  screenshot_done: 'Screenshots captured, analyzing design…',
  llm_analysis: 'Analyzing design patterns…',
  llm: 'AI agents generating your app…',
  llm_codegen: 'Writing code (this takes 2–5 minutes)…',
  write: 'Writing files to disk…',
  install: 'Installing packages…',
  start: 'Starting dev server…',
  qa: 'Running quality checks…',
}

interface Props { url: string | null; loading?: boolean; step?: GenerateStep; hasApp?: boolean }

export default function PreviewFrame({ url, loading, step, hasApp }: Props) {
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
            {hasApp ? (
              <>
                <div className="w-16 h-16 rounded-2xl bg-slate-100 border border-slate-200 flex items-center justify-center">
                  <Square size={28} className="text-slate-400" />
                </div>
                <div>
                  <div className="text-slate-600 font-semibold mb-1">App is not running</div>
                  <div className="text-slate-500 text-sm leading-relaxed max-w-xs">
                    Click the <span className="text-emerald-600 font-medium">▶ Start</span> button in the sidebar to launch this app.
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="w-16 h-16 rounded-2xl bg-slate-100 border border-slate-200 flex items-center justify-center">
                  <Zap size={28} className="text-slate-400" />
                </div>
                <div>
                  <div className="text-slate-600 font-semibold mb-1">No app generated yet</div>
                  <div className="text-slate-500 text-sm leading-relaxed max-w-xs">
                    Describe your app and click <span className="text-indigo-600 font-medium">Generate App</span> to build it.
                  </div>
                </div>
              </>
            )}
          </div>
        )}
        {loading && (
          <div className="absolute inset-0 bg-white/90 flex flex-col items-center justify-center gap-4">
            <div className="w-10 h-10 rounded-full border-2 border-slate-200 border-t-indigo-500 animate-spin" />
            <div className="text-center">
              <div className="text-slate-700 text-sm font-medium">
                {step ? (STEP_MESSAGES[step] || 'Building your app…') : 'Building your app…'}
              </div>
              <div className="text-slate-400 text-xs mt-1">Check the Build Log tab for detailed progress</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
