import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface Props {
  left: React.ReactNode
  right: React.ReactNode
  defaultLeftWidth?: number
  minLeft?: number
  maxLeft?: number
  className?: string
}

export default function ResizablePanels({
  left, right,
  defaultLeftWidth = 288,
  minLeft = 160,
  maxLeft = 560,
  className = '',
}: Props) {
  const [leftWidth, setLeftWidth] = useState(defaultLeftWidth)
  const [collapsed, setCollapsed] = useState(false)
  const dragging = useRef(false)
  const startX   = useRef(0)
  const startW   = useRef(0)
  const containerRef = useRef<HTMLDivElement>(null)

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (collapsed) return
    dragging.current = true
    startX.current   = e.clientX
    startW.current   = leftWidth
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    e.preventDefault()
  }, [leftWidth, collapsed])

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return
      const delta = e.clientX - startX.current
      const next  = Math.min(maxLeft, Math.max(minLeft, startW.current + delta))
      setLeftWidth(next)
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
  }, [maxLeft, minLeft])

  const toggleCollapse = () => setCollapsed(c => !c)
  const effectiveWidth = collapsed ? 0 : leftWidth

  return (
    <div ref={containerRef} className={`flex flex-1 min-h-0 ${className}`}>
      {/* Left panel */}
      <div
        style={{ width: effectiveWidth, minWidth: effectiveWidth, maxWidth: effectiveWidth }}
        className={`flex-shrink-0 flex flex-col overflow-hidden transition-all duration-200 ${collapsed ? 'opacity-0' : 'opacity-100'}`}
      >
        {left}
      </div>

      {/* Drag handle area + collapse toggle — always has a clickable width */}
      <div className="relative flex-shrink-0 w-3 flex items-start justify-center">
        {/* Draggable line */}
        <div
          onMouseDown={onMouseDown}
          className={`absolute inset-y-0 left-1/2 -translate-x-1/2 w-1 ${collapsed ? 'bg-slate-200' : 'bg-slate-200 hover:bg-indigo-500 cursor-col-resize'} transition-colors group`}
          title={collapsed ? '' : 'Drag to resize'}
        >
          {!collapsed && (
            <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 flex flex-col items-center justify-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              {[0,1,2].map(i => (
                <div key={i} className="w-1 h-1 rounded-full bg-indigo-500" />
              ))}
            </div>
          )}
        </div>
        {/* Collapse/Expand button — always visible */}
        <button
          onClick={toggleCollapse}
          className="relative z-10 mt-3 w-5 h-5 rounded-full bg-white border border-slate-300 shadow-sm flex items-center justify-center hover:bg-indigo-50 hover:border-indigo-300 transition-colors"
          title={collapsed ? 'Expand panel' : 'Collapse panel'}
        >
          {collapsed ? <ChevronRight size={12} className="text-slate-600" /> : <ChevronLeft size={12} className="text-slate-600" />}
        </button>
      </div>

      {/* Right panel */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        {right}
      </div>
    </div>
  )
}
