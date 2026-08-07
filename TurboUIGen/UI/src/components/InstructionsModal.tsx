/**
 * InstructionsModal — rich Markdown instructions editor + viewer.
 *
 * Two modes:
 *   edit   — full-height textarea for typing/pasting MD content
 *   view   — read-only pre-formatted display (used in history items)
 */
import { FileText, X } from 'lucide-react'

interface EditProps {
  mode: 'edit'
  value: string
  onChange: (v: string) => void
  onClose: () => void
}

interface ViewProps {
  mode: 'view'
  value: string
  title?: string
  onClose: () => void
}

type Props = EditProps | ViewProps

export default function InstructionsModal(props: Props) {
  const { value, onClose } = props

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="w-[1360px] max-w-[95vw] h-[85vh] flex flex-col bg-white border border-slate-200 rounded-xl shadow-2xl">

        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200">
          <FileText size={14} className="text-indigo-600 flex-shrink-0" />
          <span className="text-sm font-semibold text-slate-800 flex-1">
            {props.mode === 'view' && props.title ? props.title : 'Detailed Instructions (Markdown)'}
          </span>
          {props.mode === 'edit' && (
            <span className="text-xs text-slate-500 mr-2">Markdown supported · Ctrl+Enter to close</span>
          )}
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-slate-700 transition-colors p-1 rounded"
          >
            <X size={15} />
          </button>
        </div>

        {/* Body */}
        {props.mode === 'edit' ? (
          <textarea
            autoFocus
            value={value}
            onChange={e => props.onChange(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) onClose() }}
            placeholder={`Paste detailed Markdown instructions here…\n\nExamples:\n# Feature Requirements\n- Use Highcharts for all charts (npm install highcharts)\n- Implement a drill-down bar chart on the Analytics page\n- Add a date-range picker filter using react-datepicker\n\n## Data\nUse realistic dummy data with 20+ rows per table…`}
            className="flex-1 min-h-0 p-4 bg-transparent text-sm text-slate-700 font-mono leading-relaxed resize-none outline-none placeholder-slate-400"
          />
        ) : (
          <pre className="flex-1 min-h-0 overflow-y-auto p-4 text-sm text-slate-700 font-mono leading-relaxed whitespace-pre-wrap break-words">
            {value || <span className="text-slate-500 italic">No instructions provided.</span>}
          </pre>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200">
          <span className="text-xs text-slate-500">
            {value.length > 0 ? `${value.length} chars · ${value.split('\n').length} lines` : 'Empty'}
          </span>
          {props.mode === 'edit' ? (
            <div className="flex gap-2">
              <button
                onClick={() => props.onChange('')}
                disabled={!value}
                className="text-xs text-slate-500 hover:text-slate-700 transition-colors px-3 py-1.5 rounded disabled:opacity-40"
              >
                Clear
              </button>
              <button
                onClick={onClose}
                className="btn-primary text-xs px-4 py-1.5"
              >
                Done
              </button>
            </div>
          ) : (
            <button onClick={onClose} className="btn-ghost text-xs px-4 py-1.5">Close</button>
          )}
        </div>
      </div>
    </div>
  )
}

/** Small badge/button that shows instruction state and opens the modal. */
export function InstructionsBadge({
  hasInstructions,
  onClick,
  disabled,
}: {
  hasInstructions: boolean
  onClick: () => void
  disabled?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={hasInstructions ? 'Edit detailed instructions' : 'Add detailed instructions (Markdown)'}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-medium transition-colors disabled:opacity-50 ${
        hasInstructions
          ? 'border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
          : 'border-slate-300 bg-white text-slate-500 hover:text-slate-700 hover:border-slate-400'
      }`}
    >
      <FileText size={11} />
      {hasInstructions ? 'Instructions ✓' : 'Instructions'}
    </button>
  )
}
