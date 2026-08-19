// @ts-nocheck
/**
 * Calendar.skill.tsx — Monthly calendar view with event display.
 *
 * Domain-agnostic — reads all config from src/config/Calendar.config.ts
 * Works for: meeting schedules, project deadlines, event planning, booking calendars.
 * Features: month navigation, event color-coding by category, day detail panel,
 *   category filter, today highlight, responsive layout.
 */
import React, { useState, useEffect, useMemo } from 'react'
import { config } from '../config/Calendar.config'

const _API = (import.meta as any).env?.VITE_API_BASE || ''

// ── Helpers ───────────────────────────────────────────────────────────────────

const DAYS_SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfMonth(year: number, month: number, weekStartsOn: number): number {
  const day = new Date(year, month, 1).getDay()
  return (day - weekStartsOn + 7) % 7
}

function isSameDay(d1: Date, d2: Date): boolean {
  return d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
}

function formatMonth(year: number, month: number): string {
  return new Date(year, month, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

function getEventColor(event: any, categoryField: string | null, categoryColors: Record<string, string>, defaultColor: string): string {
  if (!categoryField) return defaultColor
  const cat = event[categoryField]
  if (!cat) return defaultColor
  return categoryColors[cat] || defaultColor
}

function formatTime(timeStr: string | null): string {
  if (!timeStr) return ''
  try {
    const d = new Date(timeStr)
    if (isNaN(d.getTime())) return timeStr
    return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true })
  } catch {
    return timeStr
  }
}

// ── Day Cell ──────────────────────────────────────────────────────────────────

function DayCell({ day, isToday, events, accentColor, categoryField, categoryColors, defaultColor, onClick }: {
  day: number
  isToday: boolean
  events: any[]
  accentColor: string
  categoryField: string | null
  categoryColors: Record<string, string>
  defaultColor: string
  onClick: () => void
}) {
  const maxVisible = 3
  const visible = events.slice(0, maxVisible)
  const overflow = events.length - maxVisible

  return (
    <div
      onClick={onClick}
      style={{
        minHeight: 90,
        padding: '4px 6px',
        background: isToday ? `${accentColor}0A` : '#fff',
        border: isToday ? `2px solid ${accentColor}` : '1px solid #E5E7EB',
        borderRadius: 8,
        cursor: events.length > 0 ? 'pointer' : 'default',
        transition: 'box-shadow 0.15s',
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
      }}
      onMouseEnter={e => { if (events.length > 0) (e.currentTarget as HTMLElement).style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)' }}
      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.boxShadow = 'none' }}
    >
      <div style={{
        fontSize: 12,
        fontWeight: isToday ? 700 : 500,
        color: isToday ? accentColor : '#374151',
        width: 24,
        height: 24,
        borderRadius: '50%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: isToday ? accentColor : 'transparent',
        color: isToday ? '#fff' : '#374151',
      }}>
        {day}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1 }}>
        {visible.map((ev: any, i: number) => (
          <div key={i} style={{
            fontSize: 11,
            lineHeight: 1.3,
            padding: '2px 5px',
            borderRadius: 4,
            background: `${getEventColor(ev, categoryField, categoryColors, defaultColor)}18`,
            borderLeft: `3px solid ${getEventColor(ev, categoryField, categoryColors, defaultColor)}`,
            color: '#1F2937',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}>
            {ev[config.titleField]}
          </div>
        ))}
        {overflow > 0 && (
          <div style={{ fontSize: 10, color: '#6B7280', fontWeight: 500, paddingLeft: 4 }}>
            +{overflow} more
          </div>
        )}
      </div>
    </div>
  )
}

// ── Detail Panel ──────────────────────────────────────────────────────────────

function DetailPanel({ date, events, onClose, categoryField, categoryColors, defaultColor }: {
  date: Date
  events: any[]
  onClose: () => void
  categoryField: string | null
  categoryColors: Record<string, string>
  defaultColor: string
}) {
  const dateLabel = date.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })

  return (
    <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: '100%', maxWidth: 400, background: '#fff', boxShadow: '-4px 0 24px rgba(0,0,0,0.12)', zIndex: 1000, display: 'flex', flexDirection: 'column', animation: 'slideIn 0.2s ease-out' }}>
      <style>{`@keyframes slideIn { from { transform: translateX(100%) } to { transform: translateX(0) } }`}</style>
      {/* Header */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid #E5E7EB', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#0D1B2A' }}>{dateLabel}</div>
          <div style={{ fontSize: 13, color: '#6B7280', marginTop: 2 }}>{events.length} event{events.length !== 1 ? 's' : ''}</div>
        </div>
        <button onClick={onClose} style={{ width: 32, height: 32, borderRadius: 8, border: '1px solid #E5E7EB', background: '#F9FAFB', cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6B7280' }}>
          ×
        </button>
      </div>
      {/* Events list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {events.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#9CA3AF', padding: 40, fontSize: 14 }}>No events on this day.</div>
        ) : events.map((ev: any, i: number) => {
          const color = getEventColor(ev, categoryField, categoryColors, defaultColor)
          return (
            <div key={i} style={{ padding: '14px 16px', borderRadius: 10, border: '1px solid #E5E7EB', borderLeft: `4px solid ${color}`, background: '#FAFAFA' }}>
              <div style={{ fontSize: 14, fontWeight: 600, color: '#0D1B2A' }}>{ev[config.titleField]}</div>
              {config.timeField && ev[config.timeField] && (
                <div style={{ fontSize: 12, color: '#6B7280', marginTop: 4 }}>{formatTime(ev[config.timeField])}</div>
              )}
              {categoryField && ev[categoryField] && (
                <span style={{ display: 'inline-block', marginTop: 6, fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 999, background: `${color}18`, color }}>
                  {ev[categoryField]}
                </span>
              )}
              {config.descriptionField && ev[config.descriptionField] && (
                <div style={{ fontSize: 13, color: '#374151', marginTop: 8, lineHeight: 1.5 }}>{ev[config.descriptionField]}</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Backdrop ──────────────────────────────────────────────────────────────────

function Backdrop({ onClick }: { onClick: () => void }) {
  return (
    <div onClick={onClick} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', zIndex: 999 }} />
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function CalendarPage() {
  const {
    tableName, pageTitle, pageSubtitle,
    dateField, titleField, categoryField, descriptionField, timeField,
    categoryColors, defaultColor, accentColor, weekStartsOn,
  } = config as any

  const [apiData, setApiData] = useState<any[] | null>(null)
  const [loading, setLoading] = useState(!!tableName)

  useEffect(() => {
    if (!tableName) return
    fetch(`${_API}/api/data/${tableName}?limit=2000`)
      .then(r => r.json())
      .then(j => { setApiData(j.data || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [tableName])

  const today = new Date()
  const [viewYear, setViewYear] = useState(today.getFullYear())
  const [viewMonth, setViewMonth] = useState(today.getMonth())
  const [selectedDay, setSelectedDay] = useState<Date | null>(null)
  const [categoryFilter, setCategoryFilter] = useState('All')

  // Navigation
  function prevMonth() {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11) }
    else setViewMonth(m => m - 1)
  }
  function nextMonth() {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0) }
    else setViewMonth(m => m + 1)
  }
  function goToToday() {
    setViewYear(today.getFullYear())
    setViewMonth(today.getMonth())
  }

  // Process events
  const events = useMemo(() => {
    const raw = apiData ?? []
    if (categoryFilter === 'All') return raw
    return raw.filter((ev: any) => categoryField && ev[categoryField] === categoryFilter)
  }, [apiData, categoryFilter, categoryField])

  // Group events by date key
  const eventsByDate = useMemo(() => {
    const map: Record<string, any[]> = {}
    for (const ev of events) {
      if (!ev[dateField]) continue
      try {
        const d = new Date(ev[dateField])
        const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
        ;(map[key] = map[key] || []).push(ev)
      } catch { /* skip invalid dates */ }
    }
    return map
  }, [events, dateField])

  // Category options
  const categoryOptions = useMemo(() => {
    if (!categoryField || !apiData) return []
    return [...new Set(apiData.map((ev: any) => ev[categoryField]).filter(Boolean))].sort()
  }, [apiData, categoryField])

  // Calendar grid
  const daysInMonth = getDaysInMonth(viewYear, viewMonth)
  const firstDayOffset = getFirstDayOfMonth(viewYear, viewMonth, weekStartsOn)

  // Ordered day names
  const orderedDays = useMemo(() => {
    const d = [...DAYS_SHORT]
    for (let i = 0; i < weekStartsOn; i++) d.push(d.shift()!)
    return d
  }, [weekStartsOn])

  // Selected day events
  const selectedEvents = useMemo(() => {
    if (!selectedDay) return []
    const key = `${selectedDay.getFullYear()}-${selectedDay.getMonth()}-${selectedDay.getDate()}`
    return eventsByDate[key] || []
  }, [selectedDay, eventsByDate])

  // Styles
  const s = {
    page: { padding: 24, display: 'flex', flexDirection: 'column' as const, gap: 20, background: '#F8FAFC', minHeight: '100%', fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' },
    h1: { fontSize: 26, fontWeight: 700, color: '#0D1B2A', margin: 0 },
    card: { background: '#fff', borderRadius: 12, border: '1px solid #E5E7EB', padding: '20px 24px' },
  }

  // Loading
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <div style={{ width: 32, height: 32, border: '3px solid #E5E7EB', borderTopColor: accentColor || '#0064D2', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      </div>
    )
  }

  return (
    <div style={s.page}>
      {/* Header */}
      <div>
        <h1 style={s.h1}>{pageTitle}</h1>
        {pageSubtitle && <p style={{ margin: '4px 0 0', fontSize: 14, color: '#6B7280' }}>{pageSubtitle}</p>}
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        {/* Month navigation */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={prevMonth} style={{ width: 34, height: 34, borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff', cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#374151' }}>
            ‹
          </button>
          <span style={{ fontSize: 16, fontWeight: 600, color: '#0D1B2A', minWidth: 160, textAlign: 'center' }}>
            {formatMonth(viewYear, viewMonth)}
          </span>
          <button onClick={nextMonth} style={{ width: 34, height: 34, borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff', cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#374151' }}>
            ›
          </button>
        </div>

        <button onClick={goToToday} style={{ height: 34, padding: '0 14px', borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff', cursor: 'pointer', fontSize: 13, fontWeight: 500, color: '#374151' }}>
          Today
        </button>

        {/* Category filter */}
        {categoryField && categoryOptions.length > 0 && (
          <select
            value={categoryFilter}
            onChange={e => setCategoryFilter(e.target.value)}
            style={{ height: 34, padding: '0 12px', borderRadius: 8, border: '1px solid #D1D5DB', fontSize: 13, background: '#fff', color: '#374151', marginLeft: 'auto' }}
          >
            <option value="All">All categories</option>
            {categoryOptions.map((cat: string) => <option key={cat} value={cat}>{cat}</option>)}
          </select>
        )}

        <span style={{ fontSize: 13, color: '#6B7280', marginLeft: categoryField ? 0 : 'auto' }}>
          {events.length} event{events.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Calendar grid */}
      <div style={s.card}>
        {/* Day headers */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4, marginBottom: 8 }}>
          {orderedDays.map(d => (
            <div key={d} style={{ textAlign: 'center', fontSize: 12, fontWeight: 600, color: '#6B7280', padding: '6px 0', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              {d}
            </div>
          ))}
        </div>

        {/* Day cells */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
          {/* Empty cells before first day */}
          {Array.from({ length: firstDayOffset }).map((_, i) => (
            <div key={`empty-${i}`} style={{ minHeight: 90, background: '#F9FAFB', borderRadius: 8, border: '1px solid #F3F4F6' }} />
          ))}
          {/* Day cells */}
          {Array.from({ length: daysInMonth }).map((_, i) => {
            const day = i + 1
            const cellDate = new Date(viewYear, viewMonth, day)
            const key = `${viewYear}-${viewMonth}-${day}`
            const dayEvents = eventsByDate[key] || []
            const isToday = isSameDay(cellDate, today)

            return (
              <DayCell
                key={day}
                day={day}
                isToday={isToday}
                events={dayEvents}
                accentColor={accentColor || '#0064D2'}
                categoryField={categoryField}
                categoryColors={categoryColors || {}}
                defaultColor={defaultColor || '#6B7280'}
                onClick={() => { if (dayEvents.length > 0) setSelectedDay(cellDate) }}
              />
            )
          })}
        </div>
      </div>

      {/* Detail panel */}
      {selectedDay && (
        <>
          <Backdrop onClick={() => setSelectedDay(null)} />
          <DetailPanel
            date={selectedDay}
            events={selectedEvents}
            onClose={() => setSelectedDay(null)}
            categoryField={categoryField}
            categoryColors={categoryColors || {}}
            defaultColor={defaultColor || '#6B7280'}
          />
        </>
      )}

      {/* Responsive style */}
      <style>{`
        @media (max-width: 640px) {
          [style*="grid-template-columns: repeat(7"] {
            font-size: 10px;
          }
        }
      `}</style>
    </div>
  )
}

export default CalendarPage
