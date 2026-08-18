import { Check, Copy, ExternalLink, Layers, RefreshCw } from 'lucide-react'
import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'

export default function SandpackPreviewPage() {
  const { name } = useParams<{ name: string }>()
  const [copied, setCopied] = useState(false)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const appUrl = `/app/${name}/`
  const shareUrl = window.location.href

  const copyLink = () => {
    navigator.clipboard.writeText(shareUrl).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const reload = () => {
    if (iframeRef.current) iframeRef.current.src = iframeRef.current.src
  }

  return (
    <div className="flex flex-col h-screen bg-white overflow-hidden">
      {/* Header */}
      <div className="h-11 flex-shrink-0 bg-slate-50 border-b border-slate-200 flex items-center px-4 gap-3">
        <div className="flex gap-1.5">
          {['bg-red-500', 'bg-amber-500', 'bg-emerald-500'].map(c => (
            <div key={c} className={`w-2.5 h-2.5 rounded-full ${c} opacity-70`} />
          ))}
        </div>

        <div className="flex items-center gap-1.5 text-slate-500 text-xs font-semibold">
          <Layers size={13} className="text-indigo-400" />
          TurboUIGen
        </div>

        <span className="text-slate-400 text-xs">·</span>
        <span className="text-slate-600 text-xs font-mono truncate max-w-xs">{name}</span>

        <div className="flex-1 bg-slate-100 border border-slate-200 rounded-md px-3 py-1 text-xs text-slate-500 mx-2 truncate">
          {appUrl}
        </div>

        <button onClick={reload} className="p-1.5 rounded-md text-slate-500 hover:text-slate-700 transition-colors" title="Reload">
          <RefreshCw size={13} />
        </button>

        <button onClick={copyLink}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition-colors">
          {copied ? <><Check size={12} /> Copied!</> : <><Copy size={12} /> Copy Link</>}
        </button>

        <button onClick={() => window.open(appUrl, '_blank')}
          className="p-1.5 rounded-md text-slate-500 hover:text-slate-700 transition-colors" title="Open in new tab">
          <ExternalLink size={13} />
        </button>
      </div>

      {/* iframe */}
      <div className="flex-1 min-h-0 relative overflow-hidden">
        <iframe
          ref={iframeRef}
          src={appUrl}
          className="absolute inset-0 w-full h-full border-none"
          title={`Preview — ${name}`}
        />
      </div>
    </div>
  )
}
