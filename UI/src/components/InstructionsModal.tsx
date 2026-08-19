/**
 * InstructionsModal — structured document upload + freeform editor.
 *
 * Edit mode provides four slots (PRD, TRD, Specs, Notes) that are combined
 * in order and emitted as a single markdown string via onChange.
 * Supports file browse and drag-and-drop for each slot.
 *
 * View mode shows the combined content read-only.
 */
import { useRef, useState, useCallback, useEffect } from 'react'
import { FileText, Upload, X, Check, Trash2 } from 'lucide-react'

// ── Section definitions ──────────────────────────────────────────────────────

const DOC_SECTIONS = [
  { key: 'prd', label: 'PRD', full: 'Product Requirements', color: 'emerald', desc: 'Product vision, user stories, acceptance criteria' },
  { key: 'trd', label: 'TRD', full: 'Technical Requirements', color: 'blue', desc: 'Architecture decisions, tech stack, constraints' },
  { key: 'specs', label: 'Specs', full: 'Technical Specifications', color: 'violet', desc: 'API contracts, data models, component specs' },
] as const

type DocKey = typeof DOC_SECTIONS[number]['key']

interface Docs { prd: string; trd: string; specs: string; notes: string }

// ── Markers for parsing combined string back into sections ───────────────────

const MARKERS: Record<DocKey | 'notes', string> = {
  prd: '## PRD — Product Requirements',
  trd: '## TRD — Technical Requirements',
  specs: '## Specs — Technical Specifications',
  notes: '## Additional Notes',
}

function combine(docs: Docs): string {
  const parts: string[] = []
  if (docs.prd.trim()) parts.push(`${MARKERS.prd}\n\n${docs.prd.trim()}`)
  if (docs.trd.trim()) parts.push(`${MARKERS.trd}\n\n${docs.trd.trim()}`)
  if (docs.specs.trim()) parts.push(`${MARKERS.specs}\n\n${docs.specs.trim()}`)
  if (docs.notes.trim()) parts.push(`${MARKERS.notes}\n\n${docs.notes.trim()}`)
  return parts.join('\n\n---\n\n')
}

function parse(value: string): Docs {
  const docs: Docs = { prd: '', trd: '', specs: '', notes: '' }
  if (!value.trim()) return docs

  const keys: (DocKey | 'notes')[] = ['prd', 'trd', 'specs', 'notes']
  const allMarkers = Object.values(MARKERS)

  for (let i = 0; i < keys.length; i++) {
    const marker = MARKERS[keys[i]]
    const idx = value.indexOf(marker)
    if (idx === -1) continue
    // Find end: next known marker or end of string
    let endIdx = value.length
    for (let j = i + 1; j < keys.length; j++) {
      const nextIdx = value.indexOf(MARKERS[keys[j]], idx + marker.length)
      if (nextIdx !== -1) { endIdx = nextIdx; break }
    }
    // Only treat --- as separator if followed by one of our markers
    let searchFrom = idx + marker.length
    while (searchFrom < endIdx) {
      const sepIdx = value.indexOf('\n\n---\n\n', searchFrom)
      if (sepIdx === -1 || sepIdx >= endIdx) break
      const afterSep = value.slice(sepIdx + 7).trimStart()
      if (allMarkers.some(m => afterSep.startsWith(m))) {
        endIdx = sepIdx
        break
      }
      searchFrom = sepIdx + 7
    }

    docs[keys[i]] = value.slice(idx + marker.length, endIdx).trim()
  }

  // If no markers found, treat entire content as notes (backward compat)
  if (!docs.prd && !docs.trd && !docs.specs && !docs.notes) {
    docs.notes = value
  }

  return docs
}

// ── Props ────────────────────────────────────────────────────────────────────

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

// ── Document Slot Component ──────────────────────────────────────────────────

function DocSlot({ section, content, onLoad, onClear }: {
  section: typeof DOC_SECTIONS[number]
  content: string
  onLoad: (text: string) => void
  onClear: () => void
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const hasContent = content.trim().length > 0

  const readFile = useCallback((file: File) => {
    const reader = new FileReader()
    reader.onload = () => onLoad(reader.result as string)
    reader.readAsText(file)
  }, [onLoad])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file && (file.name.endsWith('.md') || file.name.endsWith('.txt') || file.name.endsWith('.markdown'))) {
      readFile(file)
    }
  }, [readFile])

  const colorMap: Record<string, string> = {
    emerald: hasContent ? 'border-emerald-300 bg-emerald-50' : 'border-slate-200 bg-white',
    blue: hasContent ? 'border-blue-300 bg-blue-50' : 'border-slate-200 bg-white',
    violet: hasContent ? 'border-violet-300 bg-violet-50' : 'border-slate-200 bg-white',
  }
  const badgeColor: Record<string, string> = {
    emerald: 'bg-emerald-100 text-emerald-700',
    blue: 'bg-blue-100 text-blue-700',
    violet: 'bg-violet-100 text-violet-700',
  }

  return (
    <div
      className={`rounded-lg border-2 border-dashed p-3 transition-all ${
        dragOver ? 'border-indigo-400 bg-indigo-50/50' : colorMap[section.color]
      }`}
      onDrop={handleDrop}
      onDragOver={e => { e.preventDefault(); e.stopPropagation(); setDragOver(true) }}
      onDragLeave={e => { e.preventDefault(); e.stopPropagation(); setDragOver(false) }}
    >
      <input
        ref={fileRef}
        type="file"
        accept=".md,.txt,.markdown"
        onChange={e => { const f = e.target.files?.[0]; if (f) readFile(f); e.target.value = '' }}
        className="hidden"
      />

      <div className="flex items-center gap-2 mb-2">
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${badgeColor[section.color]}`}>
          {section.label}
        </span>
        <span className="text-xs font-medium text-slate-700">{section.full}</span>
        {hasContent && <Check size={12} className="text-emerald-600 ml-auto" />}
        {hasContent && (
          <button onClick={onClear} className="text-slate-400 hover:text-red-500 transition-colors" title="Remove">
            <Trash2 size={12} />
          </button>
        )}
      </div>

      {hasContent ? (
        <div className="text-xs text-slate-600">
          <span className="font-mono">{content.length.toLocaleString()} chars · {content.split('\n').length} lines</span>
          <pre className="mt-1.5 max-h-16 overflow-hidden text-[11px] text-slate-500 leading-tight whitespace-pre-wrap">
            {content.slice(0, 200)}{content.length > 200 ? '…' : ''}
          </pre>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <button
            onClick={() => fileRef.current?.click()}
            className="flex items-center gap-1 px-2 py-1 rounded border border-slate-300 bg-white text-[11px] text-slate-600 hover:border-slate-400 hover:text-slate-800 transition-colors"
          >
            <Upload size={10} />
            Browse
          </button>
          <span className="text-[11px] text-slate-400">{section.desc}</span>
        </div>
      )}
    </div>
  )
}

// ── Main Modal ───────────────────────────────────────────────────────────────

export default function InstructionsModal(props: Props) {
  const { value, onClose } = props

  // Internal structured state (edit mode only)
  const [docs, setDocs] = useState<Docs>(() => parse(value))

  // Sync external value → internal docs on mount / value changes from outside
  useEffect(() => {
    if (props.mode === 'edit') {
      setDocs(parse(value))
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const updateDoc = useCallback((key: keyof Docs, text: string) => {
    setDocs(prev => {
      const next = { ...prev, [key]: text }
      if (props.mode === 'edit') props.onChange(combine(next))
      return next
    })
  }, [props])

  const totalChars = value.length
  const totalLines = value.split('\n').length

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
            {props.mode === 'view' && props.title ? props.title : 'Project Instructions'}
          </span>
          {props.mode === 'edit' && (
            <span className="text-xs text-slate-500 mr-2">Upload documents in order: PRD → TRD → Specs</span>
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
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
            {/* Document upload slots */}
            <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/30">
              <div className="flex items-center gap-1.5 mb-2">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Document Uploads</span>
                <span className="text-[10px] text-slate-400">(parsed in order for LLM context: PRD → TRD → Specs)</span>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {DOC_SECTIONS.map(sec => (
                  <DocSlot
                    key={sec.key}
                    section={sec}
                    content={docs[sec.key]}
                    onLoad={text => updateDoc(sec.key, text)}
                    onClear={() => updateDoc(sec.key, '')}
                  />
                ))}
              </div>
            </div>

            {/* Freeform notes textarea */}
            <div className="flex-1 min-h-0 flex flex-col">
              <div className="px-4 pt-2 pb-1">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Additional Notes / Instructions</span>
              </div>
              <textarea
                autoFocus
                value={docs.notes}
                onChange={e => updateDoc('notes', e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) onClose() }}
                placeholder={`Type or paste additional instructions here…\n\nExamples:\n- Use Highcharts for all charts\n- Implement drill-down bar chart on Analytics page\n- Add date-range picker filter\n- Use realistic dummy data with 20+ rows per table`}
                className="flex-1 min-h-0 px-4 pb-4 bg-transparent text-sm text-slate-700 font-mono leading-relaxed resize-none outline-none placeholder-slate-400"
              />
            </div>
          </div>
        ) : (
          <pre className="flex-1 min-h-0 overflow-y-auto p-4 text-sm text-slate-700 font-mono leading-relaxed whitespace-pre-wrap break-words">
            {value || <span className="text-slate-500 italic">No instructions provided.</span>}
          </pre>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200">
          <span className="text-xs text-slate-500">
            {totalChars > 0
              ? `${totalChars.toLocaleString()} chars · ${totalLines} lines`
              : 'Empty'}
            {props.mode === 'edit' && (docs.prd || docs.trd || docs.specs) && (
              <span className="ml-2 text-slate-400">
                ({[docs.prd && 'PRD', docs.trd && 'TRD', docs.specs && 'Specs'].filter(Boolean).join(' + ')}
                {docs.notes.trim() ? ' + Notes' : ''})
              </span>
            )}
          </span>
          {props.mode === 'edit' ? (
            <div className="flex gap-2">
              <button
                onClick={() => { setDocs({ prd: '', trd: '', specs: '', notes: '' }); props.onChange('') }}
                disabled={!value}
                className="text-xs text-slate-500 hover:text-slate-700 transition-colors px-3 py-1.5 rounded disabled:opacity-40"
              >
                Clear All
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
