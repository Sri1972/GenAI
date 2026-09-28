/**
 * InstructionsModal — structured document upload + freeform editor.
 *
 * Edit mode provides four slots (PRD, TRD, Specs, Notes) that are combined
 * in order and emitted as a single markdown string via onChange.
 * Supports file browse and drag-and-drop for each slot.
 * Supports import from Product Forge (external PDLC document generator).
 *
 * View mode shows the combined content read-only.
 */
import { useRef, useState, useCallback, useEffect } from 'react'
import { FileText, Upload, X, Check, Trash2, Download, Loader2 } from 'lucide-react'

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

// ── Product Forge Integration ────────────────────────────────────────────────
// Product Forge now runs in-process as part of this same server (see
// API/server.py's mount under prefix "/forge") rather than as a separate app
// on its own port — same-origin relative path, no separate host/port needed.

const PRODUCT_FORGE_URL = (import.meta as any).env?.VITE_PRODUCT_FORGE_URL || '/forge'

interface ForgeProject {
  session_id: string
  project_name: string
  product_idea: string
  folder_name: string
  status: string
  artifacts: string[]
  created_at: string
}

const ARTIFACT_SLOT_MAP: Record<string, keyof Docs> = {
  'PRD': 'prd',
  'TRD': 'trd',
  'SPECS': 'specs',
  'SOLUTION_DESIGN': 'specs',
}

const SLOT_LABELS: Record<string, string> = {
  'PRD': 'PRD',
  'TRD': 'TRD',
  'SPECS': 'Specs',
  'SOLUTION_DESIGN': 'Specs',
  'EPICS_AND_STORIES': 'Notes',
  'TASKS': 'Notes',
  'TEST_CASES': 'Notes',
  'REVIEW': 'Notes',
}

function ProductForgeImport({ onImport }: { onImport: (docs: Partial<Docs>) => void }) {
  const [projects, setProjects] = useState<ForgeProject[]>([])
  const [loading, setLoading] = useState(false)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState(false)
  const [selectedProject, setSelectedProject] = useState<ForgeProject | null>(null)
  const [checkedArtifacts, setCheckedArtifacts] = useState<Set<string>>(new Set())
  const [importedSlots, setImportedSlots] = useState<Set<string>>(new Set())

  const fetchProjects = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${PRODUCT_FORGE_URL}/api/export/projects`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setProjects(data.projects || [])
      setExpanded(true)
      setSelectedProject(null)
      setImportedSlots(new Set())
    } catch (e: any) {
      setError(e.message?.includes('Failed to fetch') || e.message?.includes('NetworkError')
        ? 'Could not reach Product Forge — check the Product Forge tab for its status'
        : `Error: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }, [])

  const selectProject = useCallback((project: ForgeProject) => {
    setSelectedProject(project)
    const defaults = new Set(project.artifacts.filter(a => ['PRD', 'TRD', 'SPECS', 'SOLUTION_DESIGN'].includes(a)))
    setCheckedArtifacts(defaults)
    setImportedSlots(new Set())
  }, [])

  const toggleArtifact = useCallback((name: string) => {
    setCheckedArtifacts(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }, [])

  const importSelected = useCallback(async () => {
    if (!selectedProject) return
    setImporting(true)
    setError('')
    try {
      const res = await fetch(`${PRODUCT_FORGE_URL}/api/export/project/${selectedProject.session_id}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const artifacts: Record<string, string> = data.artifacts || {}

      const docs: Partial<Docs> = {}
      const filled = new Set<string>()

      for (const name of checkedArtifacts) {
        const content = artifacts[name]
        if (!content) continue

        const slot = ARTIFACT_SLOT_MAP[name]
        if (slot) {
          docs[slot] = content
          filled.add(slot)
        } else {
          docs.notes = (docs.notes || '') + (docs.notes ? '\n\n---\n\n' : '') + `## ${name}\n\n${content}`
          filled.add('notes')
        }
      }

      onImport(docs)
      setImportedSlots(filled)
    } catch (e: any) {
      setError(`Import failed: ${e.message}`)
    } finally {
      setImporting(false)
    }
  }, [selectedProject, checkedArtifacts, onImport])

  return (
    <div className="rounded-lg border-2 border-indigo-200 bg-indigo-50/50 overflow-hidden">
      {/* Header button */}
      <button
        onClick={expanded ? () => { setExpanded(false); setSelectedProject(null) } : fetchProjects}
        disabled={loading}
        className="w-full flex items-center gap-3 px-4 py-3 text-sm font-semibold text-indigo-700 hover:bg-indigo-100/60 transition-colors"
      >
        {loading
          ? <Loader2 size={16} className="animate-spin text-indigo-500" />
          : <Download size={16} className="text-indigo-500" />
        }
        <span>Import from Product Forge</span>
        <span className="text-[11px] font-normal text-indigo-400 ml-1">— pull PRD / TRD / Specs from your PDLC pipeline</span>
        {projects.length > 0 && expanded && (
          <span className="ml-auto text-[11px] bg-indigo-200 text-indigo-700 px-2 py-0.5 rounded-full font-medium">
            {projects.length} project{projects.length !== 1 ? 's' : ''}
          </span>
        )}
      </button>

      {error && (
        <div className="px-4 pb-3">
          <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1.5">{error}</p>
        </div>
      )}

      {/* Project list (step 1) */}
      {expanded && !selectedProject && projects.length > 0 && (
        <div className="border-t border-indigo-200 max-h-48 overflow-y-auto bg-white">
          {projects.map(p => (
            <button
              key={p.session_id}
              onClick={() => selectProject(p)}
              className="w-full text-left px-4 py-3 hover:bg-indigo-50 transition-colors border-b border-slate-100 last:border-b-0"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-slate-800 truncate flex-1">
                  {p.project_name || p.product_idea.slice(0, 60)}
                </span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                  p.status === 'complete' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                }`}>
                  {p.status}
                </span>
              </div>
              <div className="flex gap-1.5 mt-1.5">
                {p.artifacts.map(a => (
                  <span key={a} className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-600 font-medium">{a}</span>
                ))}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Artifact selection (step 2) */}
      {expanded && selectedProject && (
        <div className="border-t border-indigo-200 bg-white px-4 py-3">
          {/* Project name + back */}
          <div className="flex items-center gap-2 mb-3">
            <button
              onClick={() => { setSelectedProject(null); setImportedSlots(new Set()) }}
              className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
            >
              ← Back
            </button>
            <span className="text-sm font-semibold text-slate-800 truncate">
              {selectedProject.project_name || selectedProject.product_idea.slice(0, 50)}
            </span>
          </div>

          {/* Artifact checkboxes */}
          <div className="space-y-2 mb-3">
            {selectedProject.artifacts.map(name => {
              const slot = SLOT_LABELS[name] || 'Notes'
              const isChecked = checkedArtifacts.has(name)
              return (
                <label key={name} className="flex items-center gap-3 px-3 py-2 rounded-md border border-slate-200 hover:border-indigo-300 cursor-pointer transition-colors">
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => toggleArtifact(name)}
                    className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span className="text-sm font-medium text-slate-700 flex-1">{name}</span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                    slot === 'PRD' ? 'bg-emerald-100 text-emerald-700' :
                    slot === 'TRD' ? 'bg-blue-100 text-blue-700' :
                    slot === 'Specs' ? 'bg-violet-100 text-violet-700' :
                    'bg-slate-100 text-slate-600'
                  }`}>
                    → {slot}
                  </span>
                </label>
              )
            })}
          </div>

          {/* Import button + confirmation */}
          <div className="flex items-center gap-3">
            <button
              onClick={importSelected}
              disabled={importing || checkedArtifacts.size === 0}
              className="flex items-center gap-2 px-4 py-2 rounded-md bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {importing ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
              Import {checkedArtifacts.size} artifact{checkedArtifacts.size !== 1 ? 's' : ''}
            </button>

            {importedSlots.size > 0 && (
              <div className="flex items-center gap-2">
                <Check size={14} className="text-emerald-600" />
                <span className="text-xs text-emerald-700 font-medium">
                  Imported to: {[...importedSlots].map(s => s === 'prd' ? 'PRD' : s === 'trd' ? 'TRD' : s === 'specs' ? 'Specs' : 'Notes').join(', ')}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {expanded && !selectedProject && projects.length === 0 && !loading && !error && (
        <div className="px-4 pb-3 border-t border-indigo-200 bg-white">
          <p className="text-xs text-slate-500 py-3 text-center">No projects found in Product Forge. Start a project in the <span className="font-mono text-indigo-600">Product Forge</span> tab</p>
        </div>
      )}
    </div>
  )
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

  const handleForgeImport = useCallback((imported: Partial<Docs>) => {
    setDocs(prev => {
      const next = { ...prev, ...imported }
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
              <div className="mt-3">
                <ProductForgeImport onImport={handleForgeImport} />
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
      {hasInstructions ? 'Instructions added' : 'Instructions'}
    </button>
  )
}
