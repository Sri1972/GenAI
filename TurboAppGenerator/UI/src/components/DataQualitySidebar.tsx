import { useEffect, useState } from 'react'
import { AlertCircle, Check, FilePlus, Pencil, Trash2, X } from 'lucide-react'
import { deleteItem, listItems, renameItem, DataQualityItem } from '../hooks/dataQualityApi'
import ConfirmDialog from './ConfirmDialog'

const SOURCE_LABEL: Record<string, string> = { excel: 'Excel', delimited: 'Delimited file', parquet: 'Parquet', database: 'Database' }
const NAME_RE = /^[a-zA-Z0-9_-]+$/

interface Props {
  activeItemId: string | null
  onSelect: (itemId: string | null) => void
  refreshKey?: number
}

export default function DataQualitySidebar({ activeItemId, onSelect, refreshKey }: Props) {
  const [items, setItems] = useState<DataQualityItem[]>([])
  const [confirmId, setConfirmId] = useState<string | null>(null)
  const [deleteErr, setDeleteErr] = useState('')

  const [renaming, setRenaming] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [renameErr, setRenameErr] = useState('')

  const refresh = () => { listItems().then(r => { if ('items' in r) setItems(r.items) }) }

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 5000)
    return () => clearInterval(id)
  }, [refreshKey])

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

  function startRename(itemId: string, e: React.MouseEvent) {
    e.stopPropagation()
    setRenaming(itemId)
    setRenameValue(itemId)
    setRenameErr('')
  }

  function cancelRename() {
    setRenaming(null)
    setRenameValue('')
    setRenameErr('')
  }

  function validateName(v: string, oldName: string): string {
    if (!v.trim()) return 'Name required'
    if (/\s/.test(v)) return 'No spaces — use hyphens or underscores'
    if (!NAME_RE.test(v)) return 'Letters, numbers, hyphens, underscores only'
    if (v !== oldName && items.some(it => it.item_id === v)) return 'Name already exists'
    return ''
  }

  async function doRename(oldName: string) {
    const err = validateName(renameValue, oldName)
    if (err) { setRenameErr(err); return }
    if (renameValue === oldName) { cancelRename(); return }
    const result = await renameItem(oldName, renameValue)
    if ('error' in result) { setRenameErr(result.error); return }
    cancelRename()
    refresh()
    // The old item_id no longer exists on disk -- follow it to the new one
    // so the item view (if open) doesn't keep pointing at a 404.
    if (activeItemId === oldName) onSelect(result.item_id)
  }

  return (
    <>
      <aside className="w-56 h-full flex-shrink-0 bg-slate-50 border-r border-slate-200 flex flex-col overflow-hidden">
        <div className="px-3 pt-3 pb-2 flex-shrink-0">
          <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">
            Data Quality
          </div>
          <button
            onClick={() => onSelect(null)}
            className="w-full flex items-center justify-center gap-1.5 px-2.5 py-1.5 text-xs font-medium
                       bg-cyan-600 hover:bg-cyan-500 text-white rounded-md transition-colors"
          >
            <FilePlus size={13} /> New
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-1 border-t border-slate-200">
          {items.length === 0 && (
            <div className="px-4 py-6 text-xs text-slate-500 text-center">
              No checks generated yet.<br />Pick a source to get started.
            </div>
          )}

          {items.map(it => {
            const isActive = activeItemId === it.item_id
            const isRenaming = renaming === it.item_id
            return (
              <div key={it.item_id}>
                <div
                  onClick={() => !isRenaming && onSelect(it.item_id)}
                  style={isActive ? { boxShadow: 'inset -2px 0 0 #0891b2', background: 'rgba(8,145,178,0.08)' } : undefined}
                  className={`flex items-center gap-1.5 px-3 py-2 cursor-pointer transition-colors ${!isActive ? 'hover:bg-slate-100' : ''}`}
                >
                  {isRenaming ? (
                    <div className="flex-1 flex items-center gap-1 min-w-0" onClick={e => e.stopPropagation()}>
                      <input
                        className="flex-1 min-w-0 bg-white border border-cyan-400 rounded px-1.5 py-0.5 text-xs text-slate-800
                                   focus:outline-none focus:ring-1 focus:ring-cyan-500"
                        value={renameValue}
                        onChange={e => { setRenameValue(e.target.value); setRenameErr('') }}
                        onKeyDown={e => {
                          if (e.key === 'Enter') doRename(it.item_id)
                          if (e.key === 'Escape') cancelRename()
                        }}
                        autoFocus
                      />
                      <button onClick={() => doRename(it.item_id)} className="text-cyan-600 hover:text-cyan-700">
                        <Check size={12} />
                      </button>
                      <button onClick={cancelRename} className="text-slate-400 hover:text-slate-600">
                        <X size={12} />
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="flex-1 min-w-0">
                        <div className={`text-xs font-medium truncate ${isActive ? 'text-cyan-700' : 'text-slate-700'}`}>
                          {it.title}
                        </div>
                        <div className="text-[10px] text-slate-400 truncate">
                          {SOURCE_LABEL[it.source_kind] || it.source_kind} &middot; {it.language === 'python' ? 'Python' : 'Java'}
                        </div>
                      </div>
                      <button
                        onClick={e => startRename(it.item_id, e)}
                        title="Rename"
                        className="flex-shrink-0 p-1 rounded text-slate-400 hover:text-cyan-600 hover:bg-cyan-50 transition-colors"
                      >
                        <Pencil size={12} />
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); setConfirmId(it.item_id) }}
                        title="Delete"
                        className="flex-shrink-0 p-1 rounded text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                      >
                        <Trash2 size={12} />
                      </button>
                    </>
                  )}
                </div>
                {isRenaming && renameErr && (
                  <div className="pl-3 pr-3 pb-1.5 text-[11px] text-red-500 flex items-center gap-1">
                    <AlertCircle size={10} />{renameErr}
                  </div>
                )}
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
        title="Delete this Data Quality item?"
        message="The generated code and any run results will be permanently removed."
        details={['This cannot be undone.']}
        confirmLabel="Delete"
        danger
        onConfirm={() => confirmId && doDelete(confirmId)}
        onCancel={() => setConfirmId(null)}
      />
    </>
  )
}
