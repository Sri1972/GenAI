import { useEffect, useState } from 'react'
import { Download, FileWarning, Loader2 } from 'lucide-react'
import * as XLSX from 'xlsx'
import { Agent } from '../hooks/contentAgentsApi'

export type ArtifactKind = 'html' | 'pdf' | 'image' | 'video' | 'audio' | 'xlsx' | 'pptx' | 'live' | 'other'

export interface Artifact {
  url: string
  title: string
  kind?: ArtifactKind
}

const EXT_KIND: Record<string, ArtifactKind> = {
  html: 'html', htm: 'html',
  pdf: 'pdf',
  png: 'image', jpg: 'image', jpeg: 'image', gif: 'image', webp: 'image', svg: 'image',
  mp4: 'video', webm: 'video', mov: 'video',
  mp3: 'audio', wav: 'audio', m4a: 'audio', ogg: 'audio',
  xlsx: 'xlsx', xlsm: 'xlsx',
  pptx: 'pptx',
}

// Only useful against a real filename/static-asset path that actually ends
// in an extension -- NOT the library/workflow download endpoints themselves
// (e.g. "/api/library/items/{id}/download" has no extension in the URL at
// all; the real extension only exists server-side). Kept as a fallback for
// any future direct-file URL, but every current call site instead passes
// `kind` explicitly via libraryItemArtifactKind below.
export function detectArtifactKind(url: string): ArtifactKind {
  const clean = url.split('?')[0].split('#')[0]
  const ext = clean.slice(clean.lastIndexOf('.') + 1).toLowerCase()
  return EXT_KIND[ext] || 'other'
}

// A creator agent's output format is fixed regardless of filename (its
// "filename" is actually an LLM-drafted title with no extension, e.g.
// "World Population by Country" -- there is nothing to detect an extension
// from). A reader agent's item.filename IS the real originally-uploaded
// filename (server.py sets it to `file.filename`), so that genuinely has an
// extension to detect from.
const CREATOR_FILE_KIND: Partial<Record<Agent, ArtifactKind>> = {
  excel_creator: 'xlsx', pdf_creator: 'pdf', ppt_creator: 'pptx',
  visualization_agent: 'html', video_creator: 'video',
}

export function libraryItemArtifactKind(agent: Agent, filename: string): ArtifactKind {
  return CREATOR_FILE_KIND[agent] ?? detectArtifactKind(filename)
}

export default function ArtifactPreview({ artifact }: { artifact: Artifact }) {
  const kind = artifact.kind ?? detectArtifactKind(artifact.url)

  if (kind === 'html' || kind === 'pdf' || kind === 'live') {
    return (
      <div className="relative h-full w-full">
        <iframe src={artifact.url} className="absolute inset-0 h-full w-full border-none" title={artifact.title} />
      </div>
    )
  }
  if (kind === 'image') {
    return (
      <div className="flex h-full w-full items-center justify-center overflow-auto bg-slate-50 p-3">
        <img src={artifact.url} alt={artifact.title} className="max-h-full max-w-full object-contain" />
      </div>
    )
  }
  if (kind === 'video') {
    return (
      <div className="flex h-full w-full items-center justify-center bg-slate-900 p-3">
        <video src={artifact.url} controls className="max-h-full max-w-full" />
      </div>
    )
  }
  if (kind === 'audio') {
    return (
      <div className="flex h-full w-full items-center justify-center p-6">
        <audio src={artifact.url} controls className="w-full" />
      </div>
    )
  }
  if (kind === 'xlsx') {
    return <XlsxPreview artifact={artifact} />
  }
  // 'pptx' and anything else with no native browser preview.
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-3 p-6 text-center">
      <FileWarning size={28} className="text-slate-400" />
      <p className="text-sm text-slate-500">
        No inline preview for this file type yet{kind === 'pptx' ? ' (PowerPoint)' : ''} — download it to view.
      </p>
      <a href={artifact.url} download
         className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500">
        <Download size={14} /> Download {artifact.title}
      </a>
    </div>
  )
}

const MAX_ROWS = 500

function XlsxPreview({ artifact }: { artifact: Artifact }) {
  const [sheetNames, setSheetNames] = useState<string[]>([])
  const [sheets, setSheets] = useState<XLSX.WorkBook['Sheets'] | null>(null)
  const [activeSheet, setActiveSheet] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setSheets(null)
    setActiveSheet(0)
    fetch(artifact.url)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.arrayBuffer() })
      .then((buf) => {
        if (cancelled) return
        const wb = XLSX.read(buf, { type: 'array' })
        setSheetNames(wb.SheetNames)
        setSheets(wb.Sheets)
        setLoading(false)
      })
      .catch((e) => { if (!cancelled) { setError(String(e?.message || e)); setLoading(false) } })
    return () => { cancelled = true }
  }, [artifact.url])

  if (loading) {
    return <div className="flex h-full w-full items-center justify-center text-slate-400"><Loader2 size={22} className="animate-spin" /></div>
  }
  if (error || !sheets) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center gap-3 p-6 text-center">
        <FileWarning size={28} className="text-slate-400" />
        <p className="text-sm text-slate-500">Couldn't preview this workbook{error ? `: ${error}` : '.'}</p>
        <a href={artifact.url} download className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500">
          <Download size={14} /> Download {artifact.title}
        </a>
      </div>
    )
  }

  const rows = XLSX.utils.sheet_to_json<string[]>(sheets[sheetNames[activeSheet]], { header: 1, raw: false, defval: '' })
  const shown = rows.slice(0, MAX_ROWS)

  return (
    <div className="flex h-full w-full flex-col">
      {sheetNames.length > 1 && (
        <div className="flex flex-shrink-0 gap-1 overflow-x-auto border-b border-slate-200 bg-slate-50 px-2 py-1.5">
          {sheetNames.map((name, i) => (
            <button
              key={name}
              onClick={() => setActiveSheet(i)}
              className={`flex-shrink-0 rounded-md px-2.5 py-1 text-xs font-medium ${
                i === activeSheet ? 'bg-indigo-100 text-indigo-700' : 'text-slate-500 hover:bg-slate-100'
              }`}
            >
              {name}
            </button>
          ))}
        </div>
      )}
      <div className="flex-1 overflow-auto">
        <table className="min-w-full border-collapse text-xs">
          <tbody>
            {shown.map((row, ri) => (
              <tr key={ri} className={ri === 0 ? 'bg-slate-100 font-semibold text-slate-700' : 'hover:bg-slate-50'}>
                {row.map((cell, ci) => (
                  <td key={ci} className="border border-slate-200 px-2 py-1 whitespace-nowrap text-slate-700">{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length > MAX_ROWS && (
          <p className="p-2 text-xs italic text-slate-400">... {rows.length - MAX_ROWS} more row(s) not shown</p>
        )}
      </div>
    </div>
  )
}
