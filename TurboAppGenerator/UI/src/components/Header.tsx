import { useEffect, useRef, useState } from 'react'
import { Layers, Zap, Server, BookOpen, Bot, Plug, Hammer, Workflow, ChevronDown, AlertTriangle, GraduationCap, ShieldCheck } from 'lucide-react'
import AgentsSkillsModal from './AgentsSkillsModal'
import { useModelCtx } from '../App'

export type Tab = 'workflow' | 'forge' | 'mockup' | 'webapp' | 'api' | 'mcp' | 'utility_agents' | 'data_quality' | 'land_d'

interface Props {
  activeTab: Tab
  onChange:  (t: Tab) => void
}

export default function Header({ activeTab, onChange }: Props) {
  const [storybookUrl, setStorybookUrl] = useState('http://localhost:6006')
  const [showAgentsSkills, setShowAgentsSkills] = useState(false)

  useEffect(() => {
    fetch('/api/ds-info')
      .then(r => r.json())
      .then(d => { if (d.storybook_url) setStorybookUrl(d.storybook_url) })
      .catch(() => {})
  }, [])

  return (
    <header className="flex-shrink-0 bg-white border-b border-slate-200" style={{boxShadow:'0 1px 4px rgba(0,0,0,0.06)'}}>
      {/* Brand row — white background so Mobility Global logo looks correct */}
      <div className="flex items-center gap-3 px-5 py-3 border-b border-slate-100">
        <img
          src="/logo.png"
          alt="Mobility Global"
          className="h-9 w-auto flex-shrink-0"
          onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
        />
        <div className="w-px h-7 bg-slate-200 flex-shrink-0" />
        <div>
          <div className="text-slate-800 font-bold text-sm tracking-tight leading-none">
            TurboAppGenerator
          </div>
          <div className="text-slate-500 text-xs mt-0.5">
            AI-powered App, API &amp; Figma Wireframe Generator
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <ModelPicker />
          <button
            onClick={() => setShowAgentsSkills(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-md transition-colors"
          >
            <Bot size={12} />
            Agents &amp; Skills
          </button>
          <a
            href={storybookUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-violet-700 bg-violet-50 hover:bg-violet-100 border border-violet-200 rounded-md transition-colors"
          >
            <BookOpen size={12} />
            Storybook
          </a>
        </div>
      </div>

      {showAgentsSkills && <AgentsSkillsModal onClose={() => setShowAgentsSkills(false)} />}

      {/* Tab bar */}
      <div className="flex px-3 bg-white">
        <TabButton
          active={activeTab === 'workflow'}
          onClick={() => onChange('workflow')}
          icon={<Workflow size={13} />}
          label="Workflow"
          accent="teal"
        />
        <TabButton
          active={activeTab === 'forge'}
          onClick={() => onChange('forge')}
          icon={<Hammer size={13} />}
          label="Product Forge"
          accent="rose"
        />
        <TabButton
          active={activeTab === 'mockup'}
          onClick={() => onChange('mockup')}
          icon={<Layers size={13} />}
          label="Figma Mockup"
          accent="violet"
        />
        <TabButton
          active={activeTab === 'webapp'}
          onClick={() => onChange('webapp')}
          icon={<Zap size={13} />}
          label="Web UI"
          accent="indigo"
        />
        <TabButton
          active={activeTab === 'api'}
          onClick={() => onChange('api')}
          icon={<Server size={13} />}
          label="Web API"
          accent="emerald"
        />
        <TabButton
          active={activeTab === 'mcp'}
          onClick={() => onChange('mcp')}
          icon={<Plug size={13} />}
          label="MCP"
          accent="amber"
        />
        <TabButton
          active={activeTab === 'utility_agents'}
          onClick={() => onChange('utility_agents')}
          icon={<Bot size={13} />}
          label="Utility Agents"
          accent="teal"
        />
        <TabButton
          active={activeTab === 'data_quality'}
          onClick={() => onChange('data_quality')}
          icon={<ShieldCheck size={13} />}
          label="Data Quality"
          accent="cyan"
        />
        <TabButton
          active={activeTab === 'land_d'}
          onClick={() => onChange('land_d')}
          icon={<GraduationCap size={13} />}
          label="Tech L&D"
          accent="sky"
        />
      </div>
    </header>
  )
}

function ModelPicker() {
  const { models, usingFallback, selecting, selectError, selectModel } = useModelCtx()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [])

  if (!models) return null

  const current = models.current
  const currentLabel =
    [...models.litellm, ...models.bedrock].find(m => m.id === current.model)?.label
    || current.model

  const pick = async (provider: string, model: string) => {
    setOpen(false)
    await selectModel(provider, model)
  }

  return (
    <div className="relative" ref={ref}>
      <div className="flex items-center gap-1.5">
        <button
          onClick={() => setOpen(o => !o)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-md transition-colors"
        >
          <span
            className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
              selecting ? 'bg-slate-300' : selectError ? 'bg-red-500' : 'bg-emerald-500'
            }`}
          />
          {currentLabel}
          <ChevronDown size={12} />
        </button>
        {usingFallback && (
          <span className="flex items-center gap-1 text-[11px] text-amber-700" title="A LiteLLM call timed out or failed, so this fell back to Bedrock.">
            <AlertTriangle size={11} />
            Using Bedrock fallback
          </span>
        )}
      </div>

      {open && (
        <div className="absolute right-0 mt-1 w-56 bg-white border border-slate-200 rounded-md shadow-lg py-1 z-50 text-xs">
          <div className="px-3 pt-1.5 pb-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wide">LiteLLM</div>
          {models.litellm.map(m => (
            <button
              key={m.id}
              onClick={() => pick('litellm', m.id)}
              className={`w-full text-left px-3 py-1.5 hover:bg-slate-50 ${
                current.provider === 'litellm' && current.model === m.id ? 'text-indigo-700 font-medium' : 'text-slate-700'
              }`}
            >
              {m.label}
            </button>
          ))}
          {models.bedrock.length > 0 && (
            <>
              <div className="px-3 pt-2 pb-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wide border-t border-slate-100 mt-1">Bedrock</div>
              {models.bedrock.map(m => (
                <button
                  key={m.id}
                  onClick={() => pick('bedrock', m.id)}
                  className={`w-full text-left px-3 py-1.5 hover:bg-slate-50 ${
                    current.provider === 'bedrock' && current.model === m.id ? 'text-indigo-700 font-medium' : 'text-slate-700'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </>
          )}
          {selectError && (
            <div className="px-3 py-1.5 mt-1 border-t border-slate-100 text-red-600 text-[11px] leading-relaxed">
              {selectError}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function TabButton({ active, onClick, icon, label, accent }: {
  active: boolean; onClick: () => void
  icon: React.ReactNode; label: string; accent: 'violet' | 'indigo' | 'emerald' | 'amber' | 'rose' | 'teal' | 'sky' | 'cyan'
}) {
  const accentMap = {
    violet: 'border-violet-600 text-violet-700',
    indigo: 'border-blue-600 text-blue-700',
    emerald: 'border-emerald-600 text-emerald-700',
    amber: 'border-amber-600 text-amber-700',
    rose: 'border-rose-600 text-rose-700',
    teal: 'border-teal-600 text-teal-700',
    sky: 'border-sky-600 text-sky-700',
    cyan: 'border-cyan-600 text-cyan-700',
  }
  const activeClass = accentMap[accent]

  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
        active
          ? activeClass
          : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
      }`}
    >
      {icon} {label}
    </button>
  )
}
