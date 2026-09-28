import { FileSpreadsheet, FileText, Image, Video, Globe, Presentation, BarChart3, Clapperboard, LucideIcon } from 'lucide-react'
import type { Agent } from '../hooks/contentAgentsApi'

export const AGENT_META: Record<Agent, { label: string; icon: LucideIcon; kind: 'library' | 'oneshot' }> = {
  excel_parser: { label: 'Excel Parser', icon: FileSpreadsheet, kind: 'library' },
  pdf_parser: { label: 'PDF Parser', icon: FileText, kind: 'library' },
  image_parser: { label: 'Image Parser', icon: Image, kind: 'library' },
  media_parser: { label: 'Video/Audio Parser', icon: Video, kind: 'library' },
  site_crawler: { label: 'Website Crawler', icon: Globe, kind: 'library' },
  excel_creator: { label: 'Excel Creator', icon: FileSpreadsheet, kind: 'library' },
  pdf_creator: { label: 'PDF Creator', icon: FileText, kind: 'library' },
  ppt_creator: { label: 'PPT Creator', icon: Presentation, kind: 'library' },
  visualization_agent: { label: 'Visualization Agent', icon: BarChart3, kind: 'library' },
  video_creator: { label: 'Video Creator', icon: Clapperboard, kind: 'library' },
}

const ORDER: Agent[] = [
  'excel_parser', 'pdf_parser', 'image_parser', 'media_parser', 'site_crawler',
  'excel_creator', 'pdf_creator', 'ppt_creator', 'visualization_agent', 'video_creator',
]

export default function ContentAgentsSidebar({ selected, onSelect }: { selected: Agent; onSelect: (a: Agent) => void }) {
  return (
    <aside className="w-56 flex-shrink-0 bg-slate-50 border-r border-slate-200 flex flex-col overflow-hidden">
      <div className="px-3 pt-3 pb-1 flex-shrink-0">
        <div className="text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">
          Utility Agents
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        <p className="mb-1.5 mt-2 px-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Readers</p>
        <div className="grid grid-cols-2 gap-1.5">
          {ORDER.slice(0, 5).map((a) => <AgentTile key={a} agent={a} selected={selected === a} onSelect={onSelect} />)}
        </div>
        <p className="mb-1.5 mt-4 px-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Creators</p>
        <div className="grid grid-cols-2 gap-1.5">
          {ORDER.slice(5).map((a) => <AgentTile key={a} agent={a} selected={selected === a} onSelect={onSelect} />)}
        </div>
      </div>
    </aside>
  )
}

// A Visio-stencil-style icon tile (icon in a colored chip, label below) --
// used both for click-to-select here and, via AgentTileContent below,
// for the drag-to-canvas palette in WorkflowSidebar.
function AgentTile({ agent, selected, onSelect }: { agent: Agent; selected: boolean; onSelect: (a: Agent) => void }) {
  return (
    <button
      onClick={() => onSelect(agent)}
      className={`flex flex-col items-center gap-1.5 rounded-xl border px-1.5 py-3 text-center transition-colors ${
        selected ? 'border-indigo-400 bg-indigo-50' : 'border-slate-200 bg-white hover:border-indigo-300 hover:bg-slate-50'
      }`}
    >
      <AgentTileContent agent={agent} active={selected} />
    </button>
  )
}

export function AgentTileContent({ agent, active }: { agent: Agent; active?: boolean }) {
  const { label, icon: Icon } = AGENT_META[agent]
  return (
    <>
      <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${active ? 'bg-indigo-100' : 'bg-slate-100'}`}>
        <Icon size={18} className={active ? 'text-indigo-600' : 'text-slate-500'} />
      </div>
      <span className={`text-[11px] leading-tight ${active ? 'text-indigo-700 font-medium' : 'text-slate-600'}`}>{label}</span>
    </>
  )
}
