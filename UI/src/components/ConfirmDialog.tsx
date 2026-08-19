import { AlertTriangle, X } from 'lucide-react'
import { useEffect, useRef } from 'react'

interface Props {
  open:        boolean
  title:       string
  message:     string
  confirmLabel?: string
  cancelLabel?:  string
  danger?:     boolean          // true → confirm button is red
  onConfirm:   () => void
  onCancel:    () => void
  /** Optional extra detail lines shown below the message */
  details?:    string[]
}

export default function ConfirmDialog({
  open, title, message, confirmLabel = 'Confirm', cancelLabel = 'Cancel',
  danger = false, onConfirm, onCancel, details,
}: Props) {
  const confirmRef = useRef<HTMLButtonElement>(null)

  // Focus confirm button when dialog opens, ESC to cancel
  useEffect(() => {
    if (!open) return
    confirmRef.current?.focus()
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onCancel])

  if (!open) return null

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(7, 10, 20, 0.75)' }}
      onClick={e => { if (e.target === e.currentTarget) onCancel() }}
    >
      {/* Dialog card */}
      <div
        className="w-full max-w-md rounded-2xl shadow-2xl overflow-hidden
                   border border-slate-200 bg-white"
        style={{ boxShadow: '0 24px 60px rgba(0,0,0,0.15)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200">
          <div className="flex items-center gap-2.5">
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
              danger ? 'bg-red-50' : 'bg-amber-50'
            }`}>
              <AlertTriangle size={16} className={danger ? 'text-red-600' : 'text-amber-600'} />
            </div>
            <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          </div>
          <button
            onClick={onCancel}
            className="p-1 rounded-md text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-colors">
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4">
          <p className="text-sm text-slate-700 leading-relaxed">{message}</p>
          {details && details.length > 0 && (
            <ul className="mt-3 space-y-1">
              {details.map((d, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-slate-600">
                  <span className={`mt-0.5 flex-shrink-0 ${danger ? 'text-red-500' : 'text-amber-500'}`}>•</span>
                  {d}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-2 px-5 py-4 border-t border-slate-200 bg-slate-50">
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-2 text-sm rounded-lg border border-slate-300
                       text-slate-700 hover:bg-slate-100 transition-colors font-medium">
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            className={`flex-1 px-4 py-2 text-sm rounded-lg font-medium transition-colors ${
              danger
                ? 'bg-red-600 hover:bg-red-500 text-white'
                : 'bg-indigo-600 hover:bg-indigo-500 text-white'
            }`}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
