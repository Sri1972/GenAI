import { useRef, useState } from 'react'
import { UploadCloud, FileCheck2 } from 'lucide-react'

export default function ContentFileDropzone({
  accept, onFile, label, compact = false, fileName,
}: {
  accept?: string
  onFile: (file: File) => void
  label?: string
  compact?: boolean
  fileName?: string | null
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragActive, setDragActive] = useState(false)

  function handleFiles(files: FileList | null) {
    if (files && files[0]) onFile(files[0])
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragActive(true) }}
      onDragLeave={() => setDragActive(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragActive(false)
        handleFiles(e.dataTransfer.files)
      }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
      className={`group cursor-pointer rounded-xl border-2 border-dashed text-center transition-all ${
        compact ? 'px-3 py-3' : 'px-6 py-8'
      } ${
        dragActive
          ? 'scale-[1.01] border-indigo-400 bg-indigo-50 shadow-[0_0_0_4px_rgba(99,102,241,0.12)]'
          : fileName
          ? 'border-emerald-300 bg-emerald-50'
          : 'border-slate-300 bg-slate-50 hover:border-indigo-300 hover:bg-indigo-50/40'
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      {fileName ? (
        <>
          <FileCheck2 size={compact ? 18 : 26} className="mx-auto mb-1.5 text-emerald-500" />
          <p className={`font-medium text-emerald-700 ${compact ? 'text-xs' : 'text-sm'}`}>{fileName}</p>
          <p className={`mt-0.5 text-slate-500 ${compact ? 'text-[10px]' : 'text-xs'}`}>Click or drop to replace</p>
        </>
      ) : (
        <>
          <UploadCloud
            size={compact ? 20 : 30}
            className={`mx-auto mb-1.5 transition-transform group-hover:-translate-y-0.5 ${
              dragActive ? 'text-indigo-500' : 'text-slate-400 group-hover:text-indigo-500'
            }`}
          />
          <p className={`text-slate-600 ${compact ? 'text-xs' : 'text-sm'}`}>
            <span className="font-medium text-indigo-600 underline decoration-indigo-300 underline-offset-2">
              Browse
            </span>{' '}
            {compact ? 'or drop file' : 'or drag & drop a file here'}
          </p>
          {label && !compact && <p className="mt-1 text-xs text-slate-500">{label}</p>}
        </>
      )}
    </div>
  )
}
