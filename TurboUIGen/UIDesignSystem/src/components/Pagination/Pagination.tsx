import React from 'react'
import { colors, usage, radius } from '../../tokens'

export interface PaginationProps {
  total: number
  page: number
  pageSize?: number
  onChange?: (page: number) => void
}

export function Pagination({ total, page, pageSize = 10, onChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  function getPages(): (number | '…')[] {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1)
    const pages: (number | '…')[] = [1]
    if (page > 3) pages.push('…')
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) pages.push(i)
    if (page < totalPages - 2) pages.push('…')
    pages.push(totalPages)
    return pages
  }

  const btnStyle = (active: boolean, disabled?: boolean): React.CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 36,
    height: 36,
    padding: '0 8px',
    border: `1.5px solid ${active ? colors.primary.forwardBlue : usage.border}`,
    borderRadius: radius.md,
    background: active ? colors.primary.forwardBlue : colors.neutral.white,
    color: active ? '#fff' : disabled ? usage.mutedText : usage.primaryText,
    fontWeight: active ? 700 : 400,
    fontSize: 14,
    cursor: disabled ? 'not-allowed' : 'pointer',
    fontFamily: 'Inter, sans-serif',
    opacity: disabled ? 0.5 : 1,
  })

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: 'Inter, sans-serif' }}>
      <button style={btnStyle(false, page === 1)} disabled={page === 1}
        onClick={() => onChange?.(page - 1)}>
        ‹
      </button>
      {getPages().map((p, i) =>
        p === '…' ? (
          <span key={`ellipsis-${i}`} style={{ padding: '0 4px', color: usage.mutedText }}>…</span>
        ) : (
          <button key={p} style={btnStyle(p === page)} onClick={() => onChange?.(p as number)}>
            {p}
          </button>
        )
      )}
      <button style={btnStyle(false, page === totalPages)} disabled={page === totalPages}
        onClick={() => onChange?.(page + 1)}>
        ›
      </button>
    </div>
  )
}
