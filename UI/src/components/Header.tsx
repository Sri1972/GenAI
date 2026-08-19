import { useEffect, useState } from 'react'
import { Layers, Zap, BookOpen } from 'lucide-react'

export type Tab = 'mockup' | 'webapp'

interface Props {
  activeTab: Tab
  onChange:  (t: Tab) => void
}

export default function Header({ activeTab, onChange }: Props) {
  const [storybookUrl, setStorybookUrl] = useState('http://localhost:6006')

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
            TurboUIGen
          </div>
          <div className="text-slate-500 text-xs mt-0.5">
            AI-powered UI &amp; Figma Wireframe Generator
          </div>
        </div>
        <div className="ml-auto">
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

      {/* Tab bar */}
      <div className="flex px-3 bg-white">
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
          label="UI App Creation"
          accent="indigo"
        />
      </div>
    </header>
  )
}

function TabButton({ active, onClick, icon, label, accent }: {
  active: boolean; onClick: () => void
  icon: React.ReactNode; label: string; accent: 'violet' | 'indigo'
}) {
  const activeClass = accent === 'violet'
    ? 'border-violet-600 text-violet-700'
    : 'border-blue-600 text-blue-700'

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
