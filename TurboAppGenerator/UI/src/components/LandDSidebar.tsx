import { useEffect, useState } from 'react'
import { AlertCircle, FilePlus, Trash2 } from 'lucide-react'
import { deleteItem, listItems, listPersonas, LandDItem, Persona } from '../hooks/landDApi'
import ConfirmDialog from './ConfirmDialog'

interface Props {
  activeItemId: string | null
  onSelect: (itemId: string | null) => void
  // Bumped by the page whenever a generate/regenerate/delete completes, so
  // this list refreshes without the page needing to know this sidebar's
  // internals -- same "parent bumps a counter, child refetches" pattern
  // used for ContentAgentsSidebar's own refresh triggers.
  refreshKey?: number
}

export default function LandDSidebar({ activeItemId, onSelect, refreshKey }: Props) {
  const [items, setItems] = useState<LandDItem[]>([])
  const [personas, setPersonas] = useState<Persona[]>([])
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [deleteErr, setDeleteErr] = useState('')

  const refresh = () => { listItems().then(r => { if ('items' in r) setItems(r.items) }) }

  useEffect(() => {
    listPersonas().then(r => { if ('personas' in r) setPersonas(r.personas) })
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 5000)
    return () => clearInterval(id)
  }, [refreshKey])

  const personaLabel = (id: string) => personas.find(p => p.id === id)?.label || id

  const doDelete = async (itemId: string) => {
    setConfirmId(null)
    setDeleteErr('')
    try {
      await deleteItem(itemId)
      if (activeItemId === itemId) onSelect(null)
      refresh()
    } catch {
      setDeleteErr('Delete failed.')
    }
  }

  return (
    <>
      <aside className="w-56 h-full flex-shrink-0 bg-slate-50 border-r border-slate-200 flex flex-col overflow-hidden">
        <div className="px-3 pt-3 pb-2 flex-shrink-0">
          <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">
            Tech L&amp;D
          </div>
          <button
            onClick={() => onSelect(null)}
            className="w-full flex items-center justify-center gap-1.5 px-2.5 py-1.5 text-xs font-medium
                       bg-sky-600 hover:bg-sky-500 text-white rounded-md transition-colors"
          >
            <FilePlus size={13} /> New
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-1 border-t border-slate-200">
          {items.length === 0 && (
            <div className="px-4 py-6 text-xs text-slate-500 text-center">
              Nothing generated yet.<br />Type a topic to get started.
            </div>
          )}

          {items.map(it => {
            const isActive = activeItemId === it.item_id
            return (
              <div
                key={it.item_id}
                onClick={() => onSelect(it.item_id)}
                style={isActive ? { boxShadow: 'inset -2px 0 0 #0284c7', background: 'rgba(2,132,199,0.08)' } : undefined}
                className={`flex items-center gap-1.5 px-3 py-2 cursor-pointer transition-colors ${!isActive ? 'hover:bg-slate-100' : ''}`}
              >
                <div className="flex-1 min-w-0">
                  <div className={`text-xs font-medium truncate ${isActive ? 'text-sky-700' : 'text-slate-700'}`}>
                    {it.title}
                  </div>
                  <div className="text-[10px] text-slate-400 truncate">{personaLabel(it.persona)}</div>
                </div>
                <button
                  onClick={e => { e.stopPropagation(); setConfirmId(it.item_id) }}
                  title="Delete"
                  className="flex-shrink-0 p-1 rounded text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            )
          })}

          {deleteErr && (
            <div className="flex items-center gap-1 px-3 py-1.5 text-xs text-red-500">
              <AlertCircle size={10} />{deleteErr}
            </div>
          )}
        </div>
      </aside>

      <ConfirmDialog
        open={!!confirmId}
        title="Delete this L&D item?"
        message="This document and its saved content will be permanently removed."
        details={['This cannot be undone.']}
        confirmLabel="Delete"
        danger
        onConfirm={() => confirmId && doDelete(confirmId)}
        onCancel={() => setConfirmId(null)}
      />
    </>
  )
}
