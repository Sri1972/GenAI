import { useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface Props {
  children: React.ReactNode
}

export default function CollapsibleSidebar({ children }: Props) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex flex-shrink-0">
      {/* Sidebar content */}
      <div
        className={`overflow-hidden transition-all duration-200 ${collapsed ? 'w-0' : ''}`}
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
