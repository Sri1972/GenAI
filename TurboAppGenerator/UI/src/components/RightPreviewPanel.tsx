import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'
import ArtifactPreview, { Artifact } from './ArtifactPreview'

interface Props {
  main: React.ReactNode
  artifact: Artifact | null
  onClose: () => void
  defaultWidth?: number
  minWidth?: number
  maxWidth?: number
}

// Same drag-to-resize/collapse interaction as ResizablePanels.tsx, but
// mirrored -- the fixed/resizable child sits on the RIGHT here (an artifact
// preview alongside the main content), where ResizablePanels always puts it
// on the left. Kept as its own component rather than a `side` prop on
// ResizablePanels, so this doesn't risk that component's existing behavior
// on ProjectDetailPage/ApiGeneratorPage/ProductForgePage.
export default function RightPreviewPanel({
  main, artifact, onClose,
  defaultWidth = 480, minWidth = 320, maxWidth = 800,
}: Props) {
  const [width, setWidth] = useState(defaultWidth)
  const [collapsed, setCollapsed] = useState(false)
  const dragging = useRef(false)
  const startX = useRef(0)
  const startW = useRef(0)

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (collapsed) return
    dragging.current = true
    startX.current = e.clientX
    startW.current = width
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    e.preventDefault()
  }, [width, collapsed])

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return
      const delta = startX.current - e.clientX
      setWidth(Math.min(maxWidth, Math.max(minWidth, startW.current + delta)))
    }
    const onUp = () => {
      if (!dragging.current) return
      dragging.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [minWidth, maxWidth])

  // Re-expand automatically when a new artifact arrives while collapsed --
  // otherwise clicking "Preview" on something would silently do nothing.
  useEffect(() => { if (artifact) setCollapsed(false) }, [artifact])

  if (!artifact) return <div className="flex flex-1 min-h-0">{main}</div>

  const effectiveWidth = collapsed ? 0 : width

  return (
    <div className="flex flex-1 min-h-0">
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">{main}</div>

      <div className="relative flex-shrink-0 w-3 flex items-start justify-center">
        <div
          onMouseDown={onMouseDown}
          className={`absolute inset-y-0 left-1/2 -translate-x-1/2 w-1 ${collapsed ? 'bg-slate-200' : 'bg-slate-200 hover:bg-indigo-500 cursor-col-resize'} transition-colors group`}
          title={collapsed ? '' : 'Drag to resize'}
        >
          {!collapsed && (
            <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 flex flex-col items-center justify-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              {[0, 1, 2].map((i) => <div key={i} className="w-1 h-1 rounded-full bg-indigo-500" />)}
            </div>
          )}
        </div>
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="relative z-10 mt-3 w-5 h-5 rounded-full bg-white border border-slate-300 shadow-sm flex items-center justify-center hover:bg-indigo-50 hover:border-indigo-300 transition-colors"
          title={collapsed ? 'Expand preview' : 'Collapse preview'}
        >
          {collapsed ? <ChevronLeft size={12} className="text-slate-600" /> : <ChevronRight size={12} className="text-slate-600" />}
        </button>
      </div>

      <div
        style={{ width: effectiveWidth, minWidth: effectiveWidth, maxWidth: effectiveWidth }}
        className={`flex-shrink-0 flex flex-col overflow-hidden border-l border-slate-200 bg-white transition-all duration-200 ${collapsed ? 'opacity-0' : 'opacity-100'}`}
      >
        <div className="h-10 flex items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-3 flex-shrink-0">
          <span className="truncate text-sm font-medium text-slate-700" title={artifact.title}>{artifact.title}</span>
          <button onClick={onClose} className="flex-shrink-0 rounded-md p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600" title="Close preview">
            <X size={14} />
          </button>
        </div>
        <div className="flex-1 min-h-0 overflow-hidden">
          <ArtifactPreview artifact={artifact} />
        </div>
      </div>
    </div>
  )
}
