import { useEffect, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { api } from '../hooks/useApi'

// Mounted in-process on this same server (see server.py) — always available
// whenever TurboAppGenerator itself is running, same as any other tab.
// No start/stop of its own; the only thing checked here is whether the
// mount itself succeeded, so a real problem shows a clear message instead
// of a blank/broken iframe.
export default function ProductForgePage() {
  const [error, setError] = useState<string | null>(null)
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    api.getForgeStatus()
      .then(s => setError(s.installed ? null : s.error || 'Product Forge is not available'))
      .catch(() => setError('Could not reach the server'))
      .finally(() => setChecked(true))
  }, [])

  if (!checked) return null

  if (error) {
    return (
      <div className="flex-1 h-full flex flex-col items-center justify-center gap-4 text-center px-8">
        <div className="w-16 h-16 rounded-2xl bg-red-50 border border-red-200 flex items-center justify-center">
          <AlertCircle size={28} className="text-red-400" />
        </div>
        <div>
          <div className="text-slate-700 font-semibold mb-1">Product Forge isn't available</div>
          <div className="text-slate-500 text-sm leading-relaxed max-w-md font-mono">{error}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
      {/* Plain iframe, no browser-chrome/URL bar — that affordance (from
          PreviewFrame, used elsewhere for actually-separate running apps)
          made this look like an embedded external thing again, which is
          exactly what merging it into this same server/process was meant
          to stop being true. Same origin, same process — just an iframe. */}
      <iframe src="/forge/" className="flex-1 w-full border-none" title="Product Forge" />
    </div>
  )
}
