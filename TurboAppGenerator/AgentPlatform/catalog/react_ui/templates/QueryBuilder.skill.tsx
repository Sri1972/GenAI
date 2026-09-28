// @ts-nocheck
/**
 * QueryBuilder.skill.tsx — Ad-hoc query tool built on the design system.
 *
 * This file is domain-agnostic. It reads project-specific values from
 * src/config/QueryBuilder.config.ts (tableName, pageTitle, pageSubtitle,
 * csvFilename) and discovers the table's real columns/types at runtime via
 * GET /api/metadata — it never hardcodes column names.
 *
 * Lets the user: pick which columns to show, compose AND-combined filter
 * conditions (field/operator/value), optionally sort, and run the query
 * against the REST API's server-side filtering
 * (GET /api/{table}?filter=col:op:val;...&sort=&order=&limit=200).
 *
 * Uses the mobility-global-ds component library (Button, Card, DataTable,
 * Dropdown, Input, Badge, Pagination, Alert) for all UI chrome.
 */
import { useState, useEffect, useMemo } from 'react'
import { Button, Card, DataTable, Dropdown, Input, Badge, Pagination, Alert } from 'mobility-global-ds'
import { config } from '../config/QueryBuilder.config'
import { apiMetadata, fetchTablePage } from '../hooks/useApi'

// ── Types ──────────────────────────────────────────────────────────────────

interface ColumnMeta {
  name: string
  type: string
  pk?: boolean
  nullable?: boolean
}

interface FilterCondition {
  id: number
  field: string
  operator: string
  value: string
}

type SortDir = 'asc' | 'desc'

interface QueryResult {
  data: Record<string, any>[]
  total: number
}

// ── Operator maps ────────────────────────────────────────────────────────────

const OPERATOR_LABELS: Record<string, string> = {
  eq: 'equals',
  ne: 'not equals',
  gt: 'greater than',
  lt: 'less than',
  gte: '≥',
  lte: '≤',
  like: 'contains',
  in: 'is one of',
}

const NUMERIC_TYPES = new Set(['INTEGER', 'REAL', 'NUMERIC', 'FLOAT', 'DOUBLE'])

function isNumericType(type: string | undefined): boolean {
  return !!type && NUMERIC_TYPES.has(type.toUpperCase())
}

function operatorsForField(columns: ColumnMeta[], field: string): string[] {
  const col = columns.find(c => c.name === field)
  if (!col) return ['eq', 'ne', 'like', 'in']
  return isNumericType(col.type)
    ? ['eq', 'ne', 'gt', 'lt', 'gte', 'lte', 'in']
    : ['eq', 'ne', 'like', 'in']
}

// ── CSV export ────────────────────────────────────────────────────────────────

function exportCSV(rows: Record<string, any>[], columns: string[], filename: string) {
  const headers = columns.join(',')
  const lines = rows.map(row =>
    columns.map(c => {
      const v = row[c] ?? ''
      const s = String(v).replace(/"/g, '""')
      return /[,"\n]/.test(s) ? `"${s}"` : s
    }).join(',')
  )
  const csv = [headers, ...lines].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

// ── Component ────────────────────────────────────────────────────────────────

const RESULT_PAGE_SIZE = 50
let _nextConditionId = 1

export default function QueryBuilderPage() {
  const { tableName, pageTitle, pageSubtitle, csvFilename } = config as any

  const [metaLoading, setMetaLoading] = useState(true)
  const [metaError, setMetaError] = useState<string | null>(null)
  const [columns, setColumns] = useState<ColumnMeta[]>([])

  const [pickedColumns, setPickedColumns] = useState<string[]>([])
  const [conditions, setConditions] = useState<FilterCondition[]>([])
  const [sortField, setSortField] = useState<string>('')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  const [result, setResult] = useState<QueryResult | null>(null)
  const [queryLoading, setQueryLoading] = useState(false)
  const [queryError, setQueryError] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  // Discover table columns from /api/metadata
  useEffect(() => {
    if (!tableName) {
      setMetaError('No tableName configured for this page.')
      setMetaLoading(false)
      return
    }
    apiMetadata()
      .then(j => {
        const table = (j.tables ?? []).find((t: any) => t.table === tableName)
        if (!table) {
          setMetaError(`Table '${tableName}' was not found in /api/metadata.`)
          setMetaLoading(false)
          return
        }
        const cols: ColumnMeta[] = table.columns ?? []
        setColumns(cols)
        setPickedColumns(cols.map(c => c.name))
        setMetaLoading(false)
      })
      .catch(() => {
        setMetaError('Failed to load table metadata from /api/metadata.')
        setMetaLoading(false)
      })
  }, [tableName])

  const columnOptions = useMemo(
    () => columns.map(c => ({ value: c.name, label: c.name })),
    [columns]
  )

  const addCondition = () => {
    const defaultField = columns[0]?.name ?? ''
    setConditions(prev => [
      ...prev,
      { id: _nextConditionId++, field: defaultField, operator: operatorsForField(columns, defaultField)[0], value: '' },
    ])
  }

  const removeCondition = (id: number) => {
    setConditions(prev => prev.filter(c => c.id !== id))
  }

  const updateCondition = (id: number, patch: Partial<FilterCondition>) => {
    setConditions(prev => prev.map(c => {
      if (c.id !== id) return c
      const next = { ...c, ...patch }
      // If field changed, make sure the operator is still valid for the new field's type
      if (patch.field !== undefined) {
        const validOps = operatorsForField(columns, patch.field)
        if (!validOps.includes(next.operator)) next.operator = validOps[0]
      }
      return next
    }))
  }

  const toggleColumn = (name: string) => {
    setPickedColumns(prev =>
      prev.includes(name) ? prev.filter(c => c !== name) : [...prev, name]
    )
  }

  const runQuery = () => {
    if (!tableName) return
    setQueryLoading(true)
    setQueryError(null)
    setPage(1)

    const filterStr = conditions
      .filter(c => c.field && c.operator && c.value.trim() !== '')
      .map(c => `${c.field}:${c.operator}:${c.value.trim()}`)
      .join(';')

    const params: Record<string, string | number> = { limit: 200 }
    if (filterStr) params.filter = filterStr
    if (sortField) {
      params.sort = sortField
      params.order = sortDir
    }

    fetchTablePage(tableName, params)
      .then(res => {
        setResult(res)
        setQueryLoading(false)
      })
      .catch(err => {
        setQueryError(err.message || 'Query failed.')
        setQueryLoading(false)
      })
  }

  const displayColumns = pickedColumns.length > 0 ? pickedColumns : columns.map(c => c.name)

  const pageCount = result ? Math.max(1, Math.ceil(result.data.length / RESULT_PAGE_SIZE)) : 1
  const safePage = Math.min(page, pageCount)
  const pageRows = result
    ? result.data.slice((safePage - 1) * RESULT_PAGE_SIZE, safePage * RESULT_PAGE_SIZE)
    : []

  const tableColumns = displayColumns.map(name => ({
    key: name,
    header: name,
    render: (value: any) => (value == null || value === '' ? '—' : String(value)),
  }))

  // ── Render ──────────────────────────────────────────────────────────────

  const s = {
    page: { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 20, minHeight: '100%' },
    heading: { fontSize: 28, fontWeight: 700, margin: 0 },
    sub: { fontSize: 14, color: '#6B7280', marginTop: 4 },
    row: { display: 'flex', flexWrap: 'wrap' as const, gap: 12, alignItems: 'flex-end' },
    conditionRow: { display: 'flex', flexWrap: 'wrap' as const, gap: 10, alignItems: 'flex-end', padding: '10px 0', borderBottom: '1px solid #F1F5F9' },
    checkboxWrap: { display: 'flex', flexWrap: 'wrap' as const, gap: 14 },
    checkboxItem: { display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' as const },
    footerBar: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 },
  }

  if (metaLoading) {
    return (
      <div style={s.page}>
        <h1 style={s.heading}>{pageTitle}</h1>
        <Card><span style={{ fontSize: 13, color: '#6B7280' }}>Loading table schema…</span></Card>
      </div>
    )
  }

  if (metaError) {
    return (
      <div style={s.page}>
        <h1 style={s.heading}>{pageTitle}</h1>
        <Alert variant="error" title="Could not load query builder" message={metaError} />
      </div>
    )
  }

  return (
    <div style={s.page}>
      {/* Header */}
      <div>
        <h1 style={s.heading}>{pageTitle}</h1>
        {pageSubtitle && <p style={s.sub}>{pageSubtitle}</p>}
      </div>

      {/* Column picker */}
      <Card title="Columns" subtitle="Choose which columns to include in the results">
        <div style={s.checkboxWrap}>
          {columns.map(col => (
            <label key={col.name} style={s.checkboxItem}>
              <input
                type="checkbox"
                checked={pickedColumns.includes(col.name)}
                onChange={() => toggleColumn(col.name)}
              />
              {col.name}
            </label>
          ))}
        </div>
      </Card>

      {/* Filter builder */}
      <Card title="Filters" subtitle="All conditions are combined with AND">
        <div>
          {conditions.length === 0 && (
            <div style={{ fontSize: 13, color: '#9CA3AF', paddingBottom: 12 }}>
              No conditions yet — click "+ Add condition" to filter your query.
            </div>
          )}
          {conditions.map(cond => {
            const ops = operatorsForField(columns, cond.field)
            return (
              <div key={cond.id} style={s.conditionRow}>
                <div style={{ minWidth: 180 }}>
                  <Dropdown
                    label="Field"
                    options={columnOptions}
                    value={cond.field}
                    onChange={val => updateCondition(cond.id, { field: val })}
                  />
                </div>
                <div style={{ minWidth: 160 }}>
                  <Dropdown
                    label="Operator"
                    options={ops.map(op => ({ value: op, label: OPERATOR_LABELS[op] ?? op }))}
                    value={cond.operator}
                    onChange={val => updateCondition(cond.id, { operator: val })}
                  />
                </div>
                <div style={{ minWidth: 200 }}>
                  <Input
                    label="Value"
                    placeholder={cond.operator === 'in' ? 'comma,separated,values' : 'value'}
                    value={cond.value}
                    onChange={e => updateCondition(cond.id, { value: e.target.value })}
                  />
                </div>
                <Button variant="ghost" size="sm" onClick={() => removeCondition(cond.id)}>Remove</Button>
              </div>
            )
          })}
        </div>
        <div style={{ marginTop: 14 }}>
          <Button variant="secondary" size="sm" onClick={addCondition}>+ Add condition</Button>
        </div>
      </Card>

      {/* Sort + run */}
      <Card title="Sort & run">
        <div style={s.row}>
          <div style={{ minWidth: 180 }}>
            <Dropdown
              label="Sort by"
              placeholder="No sort"
              options={columnOptions}
              value={sortField}
              onChange={val => setSortField(val)}
            />
          </div>
          <div style={{ minWidth: 140 }}>
            <Dropdown
              label="Direction"
              options={[{ value: 'asc', label: 'Ascending' }, { value: 'desc', label: 'Descending' }]}
              value={sortDir}
              onChange={val => setSortDir(val as SortDir)}
            />
          </div>
          <Button variant="primary" onClick={runQuery} loading={queryLoading} disabled={queryLoading}>
            Run Query
          </Button>
        </div>
      </Card>

      {queryError && <Alert variant="error" title="Query failed" message={queryError} />}

      {/* Results */}
      {result === null ? (
        <Card>
          <div style={{ textAlign: 'center', padding: '24px 0', color: '#9CA3AF', fontSize: 13 }}>
            Build a query above and click "Run Query" to see results here.
          </div>
        </Card>
      ) : (
        <Card>
          <div style={s.footerBar}>
            <Badge label={`${result.data.length.toLocaleString()} rows`} variant="info" />
            <Button
              variant="secondary"
              size="sm"
              onClick={() => exportCSV(result.data, displayColumns, csvFilename ?? 'query-results.csv')}
            >
              Export CSV
            </Button>
          </div>
          <div style={{ marginTop: 12 }}>
            <DataTable
              columns={tableColumns}
              rows={pageRows}
              striped
              emptyMessage="No rows match your query."
            />
          </div>
          {result.data.length > RESULT_PAGE_SIZE && (
            <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end' }}>
              <Pagination
                total={result.data.length}
                page={safePage}
                pageSize={RESULT_PAGE_SIZE}
                onChange={setPage}
              />
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
export { QueryBuilderPage as QueryBuilder }
