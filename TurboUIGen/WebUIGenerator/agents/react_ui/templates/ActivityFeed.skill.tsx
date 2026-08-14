// @ts-nocheck
/**
 * ActivityFeed.skill.tsx — Chronological activity feed / timeline page.
 *
 * Domain-agnostic — reads all config from src/config/ActivityFeed.config.ts
 * Works for: match results, audit logs, news feed, notifications, event history.
 * Features: date grouping, badge variant per item, search, filter dropdown,
 *   relative timestamps, expandable description, pagination.
 */
import React, { useState, useEffect, useMemo } from 'react'
import { config } from '../config/ActivityFeed.config'

const _API = (import.meta as any).env?.BASE_URL?.replace(/\/$/, '') || ''

// ── Helpers ───────────────────────────────────────────────────────────────────
function relativeTime(dateStr: string): string {
  try {
    const diff = Date.now() - new Date(dateStr).getTime()
    const s = Math.floor(diff / 1000)
    if (s < 60)  return 'just now'
    if (s < 3600) return `${Math.floor(s / 60)}m ago`
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`
    if (s < 86400 * 30) return `${Math.floor(s / 86400)}d ago`
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch { return dateStr }
}

function groupByDate(items: any[], dateField: string): { label: string; items: any[] }[] {
  const groups: Record<string, any[]> = {}
  for (const item of items) {
    const d = item[dateField] ? new Date(item[dateField]) : null
    const label = d
      ? d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
      : 'Unknown Date'
    ;(groups[label] = groups[label] ?? []).push(item)
  }
  return Object.entries(groups).map(([label, items]) => ({ label, items }))
}

const BADGE_STYLES: Record<string, { bg: string; color: string }> = {
  default: { bg: '#F3F4F6', color: '#374151' },
  success: { bg: '#D1FAE5', color: '#065F46' },
  warning: { bg: '#FEF3C7', color: '#92400E' },
  error:   { bg: '#FEE2E2', color: '#991B1B' },
  info:    { bg: '#DBEAFE', color: '#1E40AF' },
  accent:  { bg: '#EDE9FE', color: '#5B21B6' },
}

function Badge({ label, variant = 'default' }: { label: string; variant?: string }) {
  const st = BADGE_STYLES[variant] ?? BADGE_STYLES.default
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', padding: '2px 10px', borderRadius: 999, fontSize: 11, fontWeight: 600, background: st.bg, color: st.color }}>
      {label}
    </span>
  )
}

// ── Feed item ─────────────────────────────────────────────────────────────────
function FeedItem({ item, cfg }: { item: any; cfg: any }) {
  const [expanded, setExpanded] = useState(false)
  const title    = item[cfg.titleField]    ?? '—'
  const subtitle = cfg.subtitleField ? item[cfg.subtitleField] : null
  const badge    = cfg.badgeField ? item[cfg.badgeField] : null
  const badgeVariant = badge ? (cfg.badgeColors?.[badge] ?? 'default') : null
  const date     = cfg.dateField ? item[cfg.dateField] : null
  const detail   = cfg.detailField ? item[cfg.detailField] : null
  const icon     = cfg.iconField ? item[cfg.iconField] : (cfg.defaultIcon ?? '●')
  const accentColor = cfg.accentColorField ? item[cfg.accentColorField] : (cfg.defaultAccentColor ?? '#0064D2')
  const linkLabel   = cfg.linkLabelField ? item[cfg.linkLabelField] : null

  return (
    <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
      {/* Timeline dot */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0, marginTop: 3 }}>
        <div style={{ width: 32, height: 32, borderRadius: '50%', background: `${accentColor}18`, border: `2px solid ${accentColor}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>
          {icon}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, background: '#fff', borderRadius: 10, border: '1px solid #E5E7EB', padding: '12px 16px', minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#0D1B2A', lineHeight: 1.4 }}>{title}</div>
            {subtitle && <div style={{ fontSize: 13, color: '#6B7280', marginTop: 2 }}>{subtitle}</div>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            {badge && badgeVariant && <Badge label={badge} variant={badgeVariant} />}
            {date && <span style={{ fontSize: 11, color: '#9CA3AF', whiteSpace: 'nowrap' }}>{relativeTime(date)}</span>}
          </div>
        </div>

        {detail && (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.6, overflow: 'hidden', maxHeight: expanded ? 'none' : '3.2em' }}>
              {detail}
            </div>
            {detail.length > 120 && (
              <button onClick={() => setExpanded(p => !p)} style={{ background: 'none', border: 'none', padding: 0, marginTop: 4, fontSize: 12, color: '#0064D2', cursor: 'pointer', fontWeight: 500 }}>
                {expanded ? 'Show less' : 'Show more'}
              </button>
            )}
          </div>
        )}

        {/* Extra fields */}
        {cfg.metaFields && cfg.metaFields.length > 0 && (
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 10 }}>
            {cfg.metaFields.map((f: any) => item[f.field] != null && (
              <div key={f.field} style={{ fontSize: 12, color: '#6B7280' }}>
                <span style={{ fontWeight: 600, color: '#374151' }}>{f.label}: </span>
                {String(item[f.field])}
              </div>
            ))}
          </div>
        )}

        {linkLabel && (
          <div style={{ marginTop: 10 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#0064D2', cursor: 'pointer' }}>{linkLabel} →</span>
          </div>
        )}
      </div>
    </div>
  )
}

const PAGE_SIZE = 20

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ActivityFeedPage() {
  const {
    dataExport, tableName, pageTitle, pageSubtitle,
    dateField, titleField, subtitleField, badgeField, badgeColors,
    detailField, iconField, defaultIcon, accentColorField, defaultAccentColor,
    metaFields, linkLabelField,
    searchFields = [], filterField = null,
  } = config as any

  const [apiData, setApiData] = useState<any[] | null>(null)
  const [apiLoading, setApiLoading] = useState(!!tableName)

  useEffect(() => {
    if (!tableName) return
    fetch(`${_API}/api/data/${tableName}?limit=500`)
      .then(r => r.json())
      .then(j => { setApiData(j.data || []); setApiLoading(false) })
      .catch(() => setApiLoading(false))
  }, [tableName])

  const [query,  setQuery]  = useState('')
  const [filter, setFilter] = useState('All')
  const [page,   setPage]   = useState(1)

  const data = useMemo(() => {
    const arr = (apiData ?? dataExport ?? []) as any[]
    return [...arr].sort((a, b) => {
      const da = dateField ? new Date(a[dateField]).getTime() : 0
      const db = dateField ? new Date(b[dateField]).getTime() : 0
      return db - da  // newest first
    })
  }, [apiData, dataExport])

  const filterOptions = useMemo(() => {
    if (!filterField) return []
    return [...new Set(data.map((r: any) => String(r[filterField])))].sort()
  }, [data, filterField])

  const filtered = useMemo(() => {
    let items = data
    if (filter !== 'All' && filterField) {
      items = items.filter((r: any) => String(r[filterField]) === filter)
    }
    if (query.trim()) {
      const q = query.toLowerCase()
      items = items.filter((r: any) =>
        (searchFields.length ? searchFields : [titleField]).some((f: string) =>
          String(r[f] ?? '').toLowerCase().includes(q)
        )
      )
    }
    return items
  }, [data, filter, query, filterField, searchFields, titleField])

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const paged  = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const groups = groupByDate(paged, dateField)

  const itemCfg = {
    dateField, titleField, subtitleField, badgeField, badgeColors,
    detailField, iconField, defaultIcon, accentColorField, defaultAccentColor,
    metaFields, linkLabelField,
  }

  const s = {
    page: { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 20, background: '#F8FAFC', minHeight: '100%' },
    h1:   { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    card: { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' },
  }

  if (apiLoading) return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}><div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTopColor: '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} /><style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style></div>

  return (
    <div style={s.page}>
      {/* Header */}
      <div>
        <h1 style={s.h1}>{pageTitle}</h1>
        {pageSubtitle && <p style={{ margin: '4px 0 0', fontSize: 14, color: '#6B7280' }}>{pageSubtitle}</p>}
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          value={query}
          onChange={e => { setQuery(e.target.value); setPage(1) }}
          placeholder="Search…"
          style={{ height: 38, padding: '0 14px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 13, flex: '1 1 200px', maxWidth: 320, outline: 'none', background: '#fff' }}
        />
        {filterField && (
          <select
            value={filter}
            onChange={e => { setFilter(e.target.value); setPage(1) }}
            style={{ height: 38, padding: '0 12px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 13, background: '#fff', color: '#374151' }}
          >
            <option value="All">All</option>
            {filterOptions.map((o: string) => <option key={o} value={o}>{o}</option>)}
          </select>
        )}
        <span style={{ fontSize: 13, color: '#6B7280', marginLeft: 'auto' }}>{filtered.length.toLocaleString()} items</span>
      </div>

      {/* Timeline */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {filtered.length === 0 ? (
          <div style={{ ...s.card, textAlign: 'center', padding: 40, color: '#9CA3AF' }}>No items match your filters.</div>
        ) : groups.map(group => (
          <div key={group.label} style={{ marginBottom: 24 }}>
            {/* Date group label */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
                {group.label}
              </span>
              <div style={{ flex: 1, height: 1, background: '#E5E7EB' }} />
            </div>
            {/* Timeline line + items */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {group.items.map((item: any, i: number) => (
                <FeedItem key={i} item={item} cfg={itemCfg} />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 6 }}>
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
            style={{ height: 32, padding: '0 12px', borderRadius: 6, border: '1px solid #D1D5DB', background: '#fff', cursor: page > 1 ? 'pointer' : 'not-allowed', opacity: page <= 1 ? 0.4 : 1 }}>‹</button>
          <span style={{ lineHeight: '32px', fontSize: 13, color: '#374151' }}>Page {page} of {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
            style={{ height: 32, padding: '0 12px', borderRadius: 6, border: '1px solid #D1D5DB', background: '#fff', cursor: page < totalPages ? 'pointer' : 'not-allowed', opacity: page >= totalPages ? 0.4 : 1 }}>›</button>
        </div>
      )}
    </div>
  )
}
