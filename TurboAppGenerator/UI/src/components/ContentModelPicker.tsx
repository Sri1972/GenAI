import { useEffect, useState } from 'react'
import { Cpu, Loader2 } from 'lucide-react'
import { ModelChoice, listModels, selectModel } from '../hooks/contentAgentsApi'

// Governs which Bedrock Claude model ContentAgents' own Claude-Code-CLI
// subprocess calls use -- distinct from TurboAppGenerator's own global
// LiteLLM/Bedrock model picker in the header, so this stays local to these
// two tabs' own toolbars rather than merging into that one.
export default function ContentModelPicker() {
  const [choices, setChoices] = useState<ModelChoice[]>([])
  const [current, setCurrent] = useState('')
  const [switching, setSwitching] = useState(false)

  useEffect(() => {
    listModels().then((d) => { setChoices(d.choices); setCurrent(d.current) })
  }, [])

  async function handleChange(model: string) {
    setSwitching(true)
    const result = await selectModel(model)
    setSwitching(false)
    if (!('error' in result)) setCurrent(model)
  }

  if (choices.length === 0) return null

  return (
    <div className="ml-auto flex items-center gap-1.5 text-sm text-slate-500">
      {switching ? <Loader2 size={14} className="animate-spin" /> : <Cpu size={14} />}
      <select
        value={current}
        onChange={(e) => handleChange(e.target.value)}
        disabled={switching}
        title="Model used for this agent's Claude calls"
        className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 outline-none focus:border-indigo-500 disabled:opacity-50"
      >
        {choices.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
      </select>
    </div>
  )
}
