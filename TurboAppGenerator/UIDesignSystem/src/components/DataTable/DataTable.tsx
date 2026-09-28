import React from 'react'
import { colors, usage, components } from '../../tokens'

export interface Column<T = Record<string, unknown>> {
  key: string
  header: string
  width?: number | string
  render?: (value: unknown, row: T) => React.ReactNode
  align?: 'left' | 'center' | 'right'
}

export interface DataTableProps<T = Record<string, unknown>> {
  columns: Column<T>[]
  rows: T[]
  striped?: boolean
  loading?: boolean
  emptyMessage?: string
}

export function DataTable<T extends Record<string, unknown>>({
  columns, rows, striped = true, loading = false, emptyMessage = 'No data available',
}: DataTableProps<T>) {
  return (
    <div style={{
      fontFamily: 'Inter, sans-serif',
      border: `1px solid ${usage.border}`,
      borderRadius: 8,
      overflow: 'hidden',
    }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: colors.neutral.lightGray }}>
              {columns.map(col => (
                <th key={col.key} style={{
                  height: 44,
                  padding: '0 16px',
                  textAlign: col.align ?? 'left',
                  fontSize: 12,
                  fontWeight: 700,
                  color: usage.primaryText,
                  textTransform: 'uppercase',
                  letterSpacing: 0.5,
                  borderBottom: `1px solid ${usage.border}`,
                  width: col.width,
                  whiteSpace: 'nowrap',
                }}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length} style={{ height: components.tableRowHeight * 3, textAlign: 'center', color: usage.mutedText, fontSize: 14 }}>
                  Loading…
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} style={{ height: components.tableRowHeight * 3, textAlign: 'center', color: usage.mutedText, fontSize: 14 }}>
                  {emptyMessage}
                </td>
              </tr>
            ) : rows.map((row, i) => (
              <tr key={i} style={{
                background: striped && i % 2 === 1 ? colors.neutral.lightGray : colors.neutral.white,
                transition: 'background 0.1s',
              }}>
                {columns.map(col => (
                  <td key={col.key} style={{
                    height: components.tableRowHeight,
                    padding: '0 16px',
                    textAlign: col.align ?? 'left',
                    fontSize: 14,
                    color: usage.primaryText,
                    borderBottom: `1px solid ${usage.divider}`,
                  }}>
                    {col.render ? col.render(row[col.key], row) : String(row[col.key] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
