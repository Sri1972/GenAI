import { useEffect, useRef, useState } from 'react'
import {
  CheckCircle2, XCircle, Loader2, Play, Download, Save, Database, FileSpreadsheet, FileText, Layers,
} from 'lucide-react'
import {
  createItem, downloadUrl, getItem, getRunStatus, runItem, updateFile,
  DataQualityItemDetail, DbType, DqRunStatus, Language, PARQUET_LANGUAGES, SourceKind,
} from '../hooks/dataQualityApi'
import ContentFileDropzone from '../components/ContentFileDropzone'
import ProgressLog from '../workflows/nodes/ProgressLog'

const POLL_INTERVAL_MS = 2000

const DB_TYPES: { id: DbType; label: string }[] = [
  { id: 'postgresql', label: 'PostgreSQL' },
  { id: 'mysql', label: 'MySQL' },
  { id: 'sqlserver', label: 'SQL Server' },
  { id: 'oracle', label: 'Oracle' },
  { id: 'sqlite', label: 'SQLite' },
]

const SOURCE_KINDS: { id: SourceKind; label: string; icon: typeof FileSpreadsheet }[] = [
  { id: 'excel', label: 'Excel file', icon: FileSpreadsheet },
  { id: 'delimited', label: 'Delimited file (CSV, etc.)', icon: FileText },
  { id: 'parquet', label: 'Parquet file', icon: Layers },
  { id: 'database', label: 'Database', icon: Database },
]

interface Props {
  activeItemId: string | null
  onSelect: (itemId: string | null) => void
  onChanged: () => void
}

export default function DataQualityPage({ activeItemId, onSelect, onChanged }: Props) {
  // Create-form state
  const [sourceKind, setSourceKind] = useState<SourceKind>('excel')
  const [language, setLanguage] = useState<Language>('python')
  const [rules, setRules] = useState('')
  const [projectName, setProjectName] = useState('')
  const [projectNameErr, setProjectNameErr] = useState('')

  const [inputMode, setInputMode] = useState<'upload' | 's3'>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [s3Path, setS3Path] = useState('')
  const [hasHeader, setHasHeader] = useState(true)
  const [pastedColumns, setPastedColumns] = useState('')
  const [delimiter, setDelimiter] = useState(',')

  const [dbType, setDbType] = useState<DbType>('postgresql')
  const [host, setHost] = useState('')
  const [port, setPort] = useState('')
  const [database, setDatabase] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [table, setTable] = useState('')
  const [pastedSchema, setPastedSchema] = useState('')
  const [saveCredentials, setSaveCredentials] = useState(false)

  // Shared job state (generate + run both poll through this)
  const [busy, setBusy] = useState(false)
  const [log, setLog] = useState<string[] | undefined>(undefined)
  const [status, setStatus] = useState<{ text: string; error?: boolean } | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Open-item state
  const [item, setItem] = useState<DataQualityItemDetail | null>(null)
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null)
  const [fileText, setFileText] = useState('')
  const [runPassword, setRunPassword] = useState('')

  function stopPolling() {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }
  useEffect(() => stopPolling, [])

  useEffect(() => {
    stopPolling()
    setStatus(null)
    setLog(undefined)
    if (!activeItemId) { setItem(null); return }
    getItem(activeItemId).then(r => {
      if ('error' in r) { setStatus({ text: r.error, error: true }); return }
      setItem(r)
      setActiveFilePath(r.files[0]?.path ?? null)
      setFileText(r.files[0]?.content ?? '')
    })
  }, [activeItemId])

  useEffect(() => {
    if (item) {
      const f = item.files.find(f => f.path === activeFilePath)
      setFileText(f?.content ?? '')
    }
  }, [activeFilePath, item])

  function startPolling(runId: string, onDone: (result: DataQualityItemDetail) => void | Promise<void>) {
    const poll = async () => {
      const runStatus: DqRunStatus | { error: string } = await getRunStatus(runId)
      if (!('status' in runStatus)) {
        stopPolling(); setBusy(false); setStatus({ text: runStatus.error, error: true }); return
      }
      setLog(runStatus.log)
      if (runStatus.status === 'running') return
      stopPolling()
      setBusy(false)
      setLog(undefined)
      if (runStatus.status === 'error') {
        setStatus({ text: runStatus.error || 'Something went wrong.', error: true })
        return
      }
      setStatus(null)
      await onDone(runStatus.result!)
    }
    pollRef.current = setInterval(poll, POLL_INTERVAL_MS)
    poll()
  }

  const canGenerate = rules.trim() && projectName.trim() && (
    sourceKind === 'database' ? dbType && table.trim() && (dbType === 'sqlite' ? database.trim() : host.trim())
    : (inputMode === 'upload' ? !!file : s3Path.trim())
  )

  function selectSourceKind(kind: SourceKind) {
    setSourceKind(kind)
    // Parquet is Python-only -- see dataQualityApi.ts's PARQUET_LANGUAGES.
    if (kind === 'parquet' && !PARQUET_LANGUAGES.includes(language)) setLanguage('python')
  }

  // Becomes the folder name on disk -- mirrors ApiSidebar's own project-name
  // validation for the exact same reason (no spaces/special chars allowed).
  function validateProjectName(v: string): string {
    if (!v.trim()) return 'Project name required'
    if (/\s/.test(v)) return 'No spaces — use hyphens or underscores'
    if (!/^[a-zA-Z0-9_-]+$/.test(v)) return 'Letters, numbers, hyphens, underscores only'
    return ''
  }

  async function handleGenerate() {
    const nameErr = validateProjectName(projectName)
    if (nameErr) { setProjectNameErr(nameErr); return }
    if (!canGenerate || busy) return
    setBusy(true)
    setLog(undefined)
    setStatus({ text: 'Profiling the source and writing your data-quality check code...' })
    const started = await createItem({
      project_name: projectName, source_kind: sourceKind, language, rules,
      file: inputMode === 'upload' ? file || undefined : undefined,
      s3_path: inputMode === 's3' ? s3Path : undefined,
      has_header: hasHeader, pasted_columns: pastedColumns, delimiter,
      db_type: sourceKind === 'database' ? dbType : undefined,
      host, port, database, username, password, table, pasted_schema: pastedSchema, save_credentials: saveCredentials,
    })
    if ('error' in started) { setBusy(false); setStatus({ text: started.error, error: true }); return }
    startPolling(started.run_id, async (result) => {
      setRules(''); setProjectName(''); setProjectNameErr(''); setFile(null); setS3Path(''); setPastedColumns('')
      setHost(''); setPort(''); setDatabase(''); setUsername(''); setPassword(''); setTable(''); setPastedSchema('')
      onChanged()
      onSelect(result.item_id)
    })
  }

  async function handleRun() {
    if (!activeItemId || busy) return
    setBusy(true)
    setLog(undefined)
    setStatus({ text: 'Running the generated checks against your real data...' })
    const started = await runItem(activeItemId, runPassword || undefined)
    if ('error' in started) { setBusy(false); setStatus({ text: started.error, error: true }); return }
    startPolling(started.run_id, async (result) => {
      setItem(result)
      onChanged()
    })
  }

  async function handleSaveFile() {
    if (!activeItemId || !activeFilePath) return
    const result = await updateFile(activeItemId, activeFilePath, fileText)
    if ('error' in result) { setStatus({ text: result.error, error: true }); return }
    setItem(prev => prev && { ...prev, files: prev.files.map(f => f.path === activeFilePath ? { ...f, content: fileText } : f) })
    setStatus({ text: 'File saved.' })
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-6">
      {!activeItemId ? (
        // ── Create view ──────────────────────────────────────────────
        <div className="mx-auto max-w-4xl rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-1 text-sm font-semibold text-slate-800">Generate a data quality check</h2>
          <p className="mb-4 text-xs text-slate-500">
            Pick a data source, describe your rules in plain English, and pick a language.
          </p>

          <Field label="Project name">
            <input
              value={projectName}
              onChange={e => { setProjectName(e.target.value); setProjectNameErr('') }}
              placeholder="e.g. customer-email-checks"
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500"
            />
            <p className="mt-1 text-[11px] text-slate-400">
              Becomes the folder name on disk -- letters, numbers, hyphens, underscores only, no spaces.
            </p>
            {projectNameErr && <p className="mt-1 text-[11px] text-red-600">{projectNameErr}</p>}
          </Field>

          <Field label="Data source">
            <div className="grid grid-cols-4 gap-2">
              {SOURCE_KINDS.map(sk => (
                <button
                  key={sk.id}
                  onClick={() => selectSourceKind(sk.id)}
                  className={`flex flex-col items-center gap-1.5 rounded-lg border p-3 text-center transition-colors ${
                    sourceKind === sk.id ? 'border-cyan-500 bg-cyan-50' : 'border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  <sk.icon size={18} className={sourceKind === sk.id ? 'text-cyan-600' : 'text-slate-400'} />
                  <span className={`text-xs font-medium ${sourceKind === sk.id ? 'text-cyan-700' : 'text-slate-700'}`}>{sk.label}</span>
                </button>
              ))}
            </div>
          </Field>

          {sourceKind !== 'database' ? (
            <>
              <Field label="File">
                <div className="mb-2 flex gap-1.5 text-xs">
                  <button onClick={() => setInputMode('upload')} className={`px-2.5 py-1 rounded-md border ${inputMode === 'upload' ? 'border-cyan-500 bg-cyan-50 text-cyan-700' : 'border-slate-200 text-slate-500'}`}>Upload</button>
                  <button onClick={() => setInputMode('s3')} className={`px-2.5 py-1 rounded-md border ${inputMode === 's3' ? 'border-cyan-500 bg-cyan-50 text-cyan-700' : 'border-slate-200 text-slate-500'}`}>From S3</button>
                </div>
                {inputMode === 'upload' ? (
                  <ContentFileDropzone
                    accept={sourceKind === 'excel' ? '.xlsx,.xlsm' : sourceKind === 'parquet' ? '.parquet' : '.csv,.txt,.tsv'}
                    onFile={setFile}
                    fileName={file?.name}
                  />
                ) : (
                  <input
                    value={s3Path} onChange={e => setS3Path(e.target.value)}
                    placeholder="s3://my-bucket/path/to/file.csv"
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500"
                  />
                )}
              </Field>

              {sourceKind === 'delimited' && (
                <Field label="Delimiter">
                  <input
                    value={delimiter} onChange={e => setDelimiter(e.target.value)}
                    placeholder=","
                    className="w-24 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500"
                  />
                </Field>
              )}

              {sourceKind !== 'parquet' && (
                <>
                  <Field label="Header row">
                    <div className="flex gap-1.5 text-xs">
                      <button onClick={() => setHasHeader(true)} className={`px-2.5 py-1 rounded-md border ${hasHeader ? 'border-cyan-500 bg-cyan-50 text-cyan-700' : 'border-slate-200 text-slate-500'}`}>Has a header row</button>
                      <button onClick={() => setHasHeader(false)} className={`px-2.5 py-1 rounded-md border ${!hasHeader ? 'border-cyan-500 bg-cyan-50 text-cyan-700' : 'border-slate-200 text-slate-500'}`}>No header</button>
                    </div>
                  </Field>

                  {!hasHeader && (
                    <Field label="Paste the column names (comma, tab, or pipe separated)">
                      <input
                        value={pastedColumns} onChange={e => setPastedColumns(e.target.value)}
                        placeholder="id, email, age"
                        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500"
                      />
                    </Field>
                  )}
                </>
              )}
              {sourceKind === 'parquet' && (
                <p className="mb-3 text-[11px] text-slate-400">
                  Parquet's column names/types are embedded in the file -- no header or column list needed.
                </p>
              )}
            </>
          ) : (
            <>
              <Field label="Database type">
                <div className="grid grid-cols-5 gap-1.5">
                  {DB_TYPES.map(t => (
                    <button
                      key={t.id}
                      onClick={() => setDbType(t.id)}
                      className={`rounded-lg border px-2 py-2 text-xs font-medium transition-colors ${
                        dbType === t.id ? 'border-cyan-500 bg-cyan-50 text-cyan-700' : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </Field>

              {dbType === 'sqlite' ? (
                <Field label="Database file path (on this server)">
                  <input value={database} onChange={e => setDatabase(e.target.value)} placeholder="C:\path\to\mydb.sqlite"
                         className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500" />
                </Field>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-2">
                    <Field label="Host"><input value={host} onChange={e => setHost(e.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500" /></Field>
                    <Field label="Port"><input value={port} onChange={e => setPort(e.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500" /></Field>
                    <Field label="Database name"><input value={database} onChange={e => setDatabase(e.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500" /></Field>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Field label="Username"><input value={username} onChange={e => setUsername(e.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500" /></Field>
                    <Field label="Password"><input type="password" value={password} onChange={e => setPassword(e.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500" /></Field>
                  </div>
                </>
              )}

              <Field label="Table name">
                <input value={table} onChange={e => setTable(e.target.value)} className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500" />
              </Field>

              <Field label="Paste schema / CREATE TABLE / sample rows (optional -- used if a live connection isn't possible)">
                <textarea value={pastedSchema} onChange={e => setPastedSchema(e.target.value)} rows={4}
                          placeholder={'id: integer\nemail: text\namount: numeric'}
                          className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500" />
              </Field>

              {dbType !== 'sqlite' && (
                <label className="mb-3 flex items-center gap-1.5 text-xs text-slate-600">
                  <input type="checkbox" checked={saveCredentials} onChange={e => setSaveCredentials(e.target.checked)} />
                  Remember credentials for future runs of this item
                </label>
              )}
            </>
          )}

          <Field label="Data quality rules">
            <textarea
              value={rules} onChange={e => setRules(e.target.value)} rows={8}
              placeholder="e.g. email must never be empty; age must be between 0 and 120; id must be unique"
              className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500"
            />
          </Field>

          <Field label="Language">
            <div className="grid grid-cols-2 gap-2">
              {(['python', 'java'] as Language[]).map(l => {
                const disabled = sourceKind === 'parquet' && !PARQUET_LANGUAGES.includes(l)
                return (
                  <button
                    key={l}
                    onClick={() => !disabled && setLanguage(l)}
                    disabled={disabled}
                    title={disabled ? 'Parquet sources are Python-only -- Java Parquet support needs a heavy extra dependency not wired up here.' : undefined}
                    className={`rounded-lg border p-2.5 text-center text-sm font-medium transition-colors ${
                      disabled ? 'cursor-not-allowed border-slate-200 text-slate-300'
                      : language === l ? 'border-cyan-500 bg-cyan-50 text-cyan-700' : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {l === 'python' ? 'Python' : 'Java'}
                  </button>
                )
              })}
            </div>
          </Field>

          <button
            onClick={handleGenerate}
            disabled={busy || !canGenerate}
            className="mt-1 flex items-center gap-1.5 rounded-lg bg-cyan-600 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-40"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : null}
            Generate
          </button>

          {status && <p className={`mt-3 text-xs ${status.error ? 'text-red-600' : 'text-slate-500'}`}>{status.text}</p>}
          <ProgressLog log={log} />
        </div>
      ) : !item ? (
        <div className="mx-auto max-w-4xl rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-500">Loading...</div>
      ) : (
        // ── Item view ────────────────────────────────────────────────
        <div className="flex h-full gap-5">
          <div className="w-[360px] flex-shrink-0 overflow-y-auto">
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">{item.title}</p>
              <p className="mb-3 text-xs text-slate-500">
                {item.source_kind} &middot; {item.language === 'python' ? 'Python' : 'Java'}
              </p>
              <p className="mb-3 whitespace-pre-wrap rounded-lg bg-slate-50 p-2 text-xs text-slate-600">{item.rules}</p>

              {item.validation_error && (
                <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-700">
                  <strong>Generated code has a problem -- try editing a file and saving, or regenerate:</strong>
                  <pre className="mt-1 whitespace-pre-wrap">{item.validation_error.slice(0, 800)}</pre>
                </div>
              )}

              {item.source_kind === 'database' && !item.credentials_saved && (
                <Field label="DB password (not saved -- needed to run)">
                  <input type="password" value={runPassword} onChange={e => setRunPassword(e.target.value)}
                         className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-cyan-500" />
                </Field>
              )}

              <button
                onClick={handleRun}
                disabled={busy}
                title="Runs the generated code against the real data source and reports pass/fail."
                className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-cyan-600 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-500 disabled:opacity-40"
              >
                {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                Run checks
              </button>
              <p className="mt-1.5 text-[11px] text-slate-400">Large files/tables may take a while -- this isn't stuck.</p>

              {status && <p className={`mt-3 text-xs ${status.error ? 'text-red-600' : 'text-slate-500'}`}>{status.text}</p>}
              <ProgressLog log={log} />

              {item.last_result && (
                <div className="mt-4 border-t border-slate-100 pt-3">
                  {item.last_result.dq_result ? (
                    <>
                      <div className={`mb-2 flex items-center gap-1.5 text-sm font-semibold ${item.last_result.dq_result.passed ? 'text-emerald-600' : 'text-red-600'}`}>
                        {item.last_result.dq_result.passed ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                        {item.last_result.dq_result.passed ? 'All checks passed' : 'Some checks failed'}
                      </div>
                      <p className="mb-2 text-xs text-slate-500">{item.last_result.dq_result.summary}</p>
                      <div className="space-y-1.5">
                        {item.last_result.dq_result.checks.map((c, i) => (
                          <div key={i} className={`rounded-lg border p-2 text-xs ${c.passed ? 'border-emerald-200 bg-emerald-50' : 'border-red-200 bg-red-50'}`}>
                            <div className={`flex items-center gap-1 font-medium ${c.passed ? 'text-emerald-700' : 'text-red-700'}`}>
                              {c.passed ? <CheckCircle2 size={11} /> : <XCircle size={11} />} {c.name}
                            </div>
                            <div className="mt-0.5 text-slate-600">{c.detail}</div>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="text-xs text-amber-600">
                      Ran (exit code {item.last_result.returncode}), but no structured result line was found -- see the raw log below.
                    </p>
                  )}
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-slate-400 hover:text-slate-600">Raw output</summary>
                    <pre className="mt-1 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-900 p-2 text-[11px] text-slate-100">
                      {item.last_result.stdout}
                      {item.last_result.stderr && `\n--- stderr ---\n${item.last_result.stderr}`}
                    </pre>
                  </details>
                </div>
              )}
            </div>
          </div>

          <div className="min-w-0 flex-1 overflow-y-auto">
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Generated code</p>
                <a href={downloadUrl(item.item_id)} className="flex items-center gap-1 text-xs text-cyan-600 hover:underline">
                  <Download size={12} /> Download .zip
                </a>
              </div>
              <div className="mb-2 flex gap-1.5 overflow-x-auto border-b border-slate-100 pb-2">
                {item.files.map(f => (
                  <button
                    key={f.path}
                    onClick={() => setActiveFilePath(f.path)}
                    className={`flex-shrink-0 rounded-md px-2.5 py-1 text-xs font-mono transition-colors ${
                      activeFilePath === f.path ? 'bg-cyan-100 text-cyan-700' : 'text-slate-500 hover:bg-slate-100'
                    }`}
                  >
                    {f.path}
                  </button>
                ))}
              </div>
              <textarea
                value={fileText} onChange={e => setFileText(e.target.value)} rows={26}
                className="w-full resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-800 outline-none focus:border-cyan-500"
              />
              <button
                onClick={handleSaveFile}
                className="mt-3 flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
              >
                <Save size={14} /> Save file
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="mb-3 block">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>
      {children}
    </label>
  )
}
