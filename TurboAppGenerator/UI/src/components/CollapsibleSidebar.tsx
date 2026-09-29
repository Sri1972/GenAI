import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface Props {
  children: React.ReactNode
}

export default function CollapsibleSidebar({ children }: Props) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-full flex-shrink-0">
      {/* Sidebar content -- h-full on both this wrapper and the <aside>
          rendered inside `children` is what makes each sidebar's own
          overflow-y-auto region actually scroll instead of growing to fit
          its content and getting clipped by an ancestor's overflow-hidden
          (confirmed live: without this, aside.scrollHeight just equals
          clientHeight -- there's nothing to scroll because nothing ever
          overflowed in the first place, it just silently grew taller than
          the viewport). */}
      <div
        className={`h-full overflow-hidden transition-all duration-200 ${collapsed ? 'w-0' : ''}`}
        style={collapsed ? { width: 0 } : undefined}
      >
        {children}
      </div>

      {/* Divider + toggle button */}
      <div className="relative flex-shrink-0 w-3 flex items-start justify-center">
        {/* Vertical line */}
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-px bg-slate-200" />
        {/* Toggle button — always visible */}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="relative z-20 mt-3 w-5 h-5 rounded-full bg-white border border-slate-300 shadow-sm flex items-center justify-center hover:bg-indigo-50 hover:border-indigo-300 transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={12} className="text-slate-600" /> : <ChevronLeft size={12} className="text-slate-600" />}
        </button>
      </div>
    </div>
  )
}
