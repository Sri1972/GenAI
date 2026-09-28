import { useEffect, useRef } from 'react'

// Shared by ForgeNode/WebUiGeneratorNode -- both run for minutes with no
// natural pause point to report progress at otherwise, so this is what
// makes "is it actually doing something" visible directly on the canvas.
export default function ProgressLog({ log }: { log?: string[] }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight })
  }, [log?.length])

  if (!log || log.length === 0) return null

  return (
    <div ref={ref} className="mt-2 max-h-24 space-y-0.5 overflow-y-auto rounded-md border border-slate-200 bg-slate-50 p-1.5">
      {log.map((line, i) => (
        <p key={i} className="truncate text-[10px] text-slate-500" title={line}>{line}</p>
      ))}
    </div>
  )
}
