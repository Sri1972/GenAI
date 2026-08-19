// @ts-nocheck
/**
 * Notifications.skill.tsx — Notification center / inbox layout.
 *
 * Domain-agnostic — reads config from src/config/Notifications.config.ts
 * Works for: alerts, messages, system notifications, approval queues, etc.
 */
import { useState, useEffect, useMemo } from 'react'
import { config } from '../config/Notifications.config'

const _API = (import.meta as any).env?.VITE_API_BASE || ''

const ICONS: Record<string, (color: string) => JSX.Element> = {
  bell:     (c) => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke={c} strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" /></svg>,
  mail:     (c) => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke={c} strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" /></svg>,
  alert:    (c) => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke={c} strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" /></svg>,
  check:    (c) => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke={c} strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
  info:     (c) => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke={c} strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" /></svg>,
  warning:  (c) => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke={c} strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0 3.75h.008v.008H12v-.008zm9-3.75a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
  error:    (c) => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke={c} strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>,
  message:  (c) => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke={c} strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM2.25 12.76c0 1.6 1.123 2.994 2.707 3.227 1.068.157 2.148.279 3.238.364.466.037.893.281 1.153.671L12 21l2.652-3.978c.26-.39.687-.634 1.153-.671 1.09-.085 2.17-.207 3.238-.364 1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" /></svg>,
  calendar: (c) => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke={c} strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" /></svg>,
  user:     (c) => <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke={c} strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" /></svg>,
}

function getIcon(name: string, color: string) {
  const render = ICONS[name] || ICONS.bell
  return render(color)
}

function relativeTime(ts: string | number): string {
  const now = Date.now()
  const then = new Date(ts).getTime()
  if (isNaN(then)) return String(ts)
  const diff = Math.max(0, now - then)
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  return new Date(then).toLocaleDateString()
}

function Spinner() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
      <div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTopColor: '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}

export function Notifications() {
  const {
    tableName, pageTitle, pageSubtitle,
    titleField, messageField, timestampField, typeField, readField, priorityField,
    typeConfig = {},
    accentColor = '#0064D2',
  } = config as any

  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [readState, setReadState] = useState<Record<number, boolean>>({})
  const [activeFilter, setActiveFilter] = useState('All')
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  useEffect(() => {
    if (!tableName) { setLoading(false); return }
    fetch(`${_API}/api/data/${tableName}?limit=500`)
      .then(r => r.json())
      .then(j => {
        const items = j.data || []
        setData(items)
        // Initialize read state from data
        const initRead: Record<number, boolean> = {}
        items.forEach((item: any, i: number) => {
          if (readField) initRead[i] = Boolean(item[readField])
        })
        setReadState(initRead)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [tableName])

  const isRead = (i: number) => readState[i] ?? false

  const unreadCount = useMemo(() => data.filter((_, i) => !isRead(i)).length, [data, readState])

  const typeOptions = useMemo(() => {
    if (!typeField) return []
    const types = new Set(data.map(d => String(d[typeField] ?? '')).filter(Boolean))
    return Array.from(types)
  }, [data])

  const filtered = useMemo(() => {
    return data.map((item, i) => ({ item, idx: i })).filter(({ item, idx }) => {
      if (activeFilter === 'Unread') return !isRead(idx)
      if (activeFilter !== 'All' && typeField) return String(item[typeField]) === activeFilter
      return true
    })
  }, [data, activeFilter, readState])

  const markAsRead = (idx: number) => {
    setReadState(prev => ({ ...prev, [idx]: true }))
  }

  const markAllAsRead = () => {
    const allRead: Record<number, boolean> = {}
    data.forEach((_, i) => { allRead[i] = true })
    setReadState(allRead)
  }

  const handleClick = (idx: number) => {
    setExpandedIdx(expandedIdx === idx ? null : idx)
    markAsRead(idx)
  }

  if (loading) return <Spinner />

  const s = {
    page: { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 20, background: '#F8FAFC', minHeight: '100%', maxWidth: 800, margin: '0 auto', width: '100%' },
    header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' as const, gap: 12 },
    h1: { fontSize: 22, fontWeight: 700, color: '#0D1B2A', margin: 0, display: 'flex', alignItems: 'center', gap: 10 },
    subtitle: { fontSize: 13, color: '#6B7280', marginTop: 4 },
    badge: { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', minWidth: 22, height: 22, borderRadius: 999, background: accentColor, color: '#fff', fontSize: 11, fontWeight: 700, padding: '0 6px' },
    markAllBtn: { padding: '8px 14px', borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff', fontSize: 13, fontWeight: 500, color: '#374151', cursor: 'pointer' },
    tabs: { display: 'flex', gap: 6, flexWrap: 'wrap' as const, padding: '4px', background: '#fff', borderRadius: 10, border: '1px solid #E5E7EB' },
    tab: (active: boolean) => ({
      padding: '8px 14px', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: 'pointer', border: 'none',
      background: active ? accentColor : 'transparent',
      color: active ? '#fff' : '#6B7280',
      transition: 'all 0.15s',
    }),
    card: (read: boolean, expanded: boolean) => ({
      background: read ? '#fff' : '#FAFBFF',
      borderRadius: 12,
      border: '1px solid #E5E7EB',
      borderLeft: read ? '3px solid transparent' : `3px solid ${accentColor}`,
      padding: '16px 20px',
      cursor: 'pointer',
      transition: 'all 0.15s',
      boxShadow: expanded ? '0 4px 12px rgba(0,0,0,0.06)' : 'none',
    }),
    cardHeader: { display: 'flex', alignItems: 'flex-start', gap: 12 },
    iconWrap: (color: string) => ({
      width: 36, height: 36, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: `${color}15`, flexShrink: 0,
    }),
    cardTitle: (read: boolean) => ({ fontSize: 14, fontWeight: read ? 500 : 700, color: '#1F2937', margin: 0, lineHeight: 1.3 }),
    cardPreview: { fontSize: 13, color: '#6B7280', marginTop: 4, lineHeight: 1.4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const, maxWidth: '100%' },
    cardFull: { fontSize: 13, color: '#374151', marginTop: 8, lineHeight: 1.6, whiteSpace: 'pre-wrap' as const },
    timestamp: { fontSize: 11, color: '#9CA3AF', marginTop: 6, flexShrink: 0 },
    dot: { width: 8, height: 8, borderRadius: '50%', background: accentColor, flexShrink: 0, marginTop: 4 },
    empty: { textAlign: 'center' as const, padding: 60, color: '#9CA3AF', fontSize: 14 },
  }

  return (
    <div style={s.page}>
      {/* Header */}
      <div>
        <div style={s.header}>
          <div>
            <h1 style={s.h1}>
              {pageTitle}
              {unreadCount > 0 && <span style={s.badge}>{unreadCount}</span>}
            </h1>
            {pageSubtitle && <div style={s.subtitle}>{pageSubtitle}</div>}
          </div>
          {unreadCount > 0 && (
            <button style={s.markAllBtn} onClick={markAllAsRead}>Mark all as read</button>
          )}
        </div>
      </div>

      {/* Filter tabs */}
      <div style={s.tabs}>
        <button style={s.tab(activeFilter === 'All')} onClick={() => setActiveFilter('All')}>All</button>
        <button style={s.tab(activeFilter === 'Unread')} onClick={() => setActiveFilter('Unread')}>Unread</button>
        {typeOptions.map(t => (
          <button key={t} style={s.tab(activeFilter === t)} onClick={() => setActiveFilter(t)}>{t}</button>
        ))}
      </div>

      {/* Notification list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {filtered.length === 0 && (
          <div style={s.empty}>No notifications match this filter.</div>
        )}
        {filtered.map(({ item, idx }) => {
          const read = isRead(idx)
          const expanded = expandedIdx === idx
          const type = typeField ? String(item[typeField] ?? '') : ''
          const tc = (typeConfig as any)[type] || { icon: 'bell', color: '#6B7280' }
          const title = String(item[titleField] ?? '')
          const message = String(item[messageField] ?? '')
          const ts = item[timestampField] ?? ''

          return (
            <div key={idx} style={s.card(read, expanded)} onClick={() => handleClick(idx)}>
              <div style={s.cardHeader}>
                {/* Icon */}
                <div style={s.iconWrap(tc.color)}>
                  {getIcon(tc.icon, tc.color)}
                </div>

                {/* Content */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={s.cardTitle(read)}>{title}</div>
                  {!expanded && <div style={s.cardPreview}>{message}</div>}
                  {expanded && <div style={s.cardFull}>{message}</div>}
                  <div style={s.timestamp}>{relativeTime(ts)}</div>
                </div>

                {/* Unread dot */}
                {!read && <div style={s.dot} />}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default Notifications
