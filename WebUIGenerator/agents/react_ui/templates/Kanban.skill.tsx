// @ts-nocheck
import React, { useState, useEffect, useMemo } from 'react'
import { config } from '../config/Kanban.config'

const _API = import.meta.env.VITE_API_BASE || ''

/* ─────────────────────────── Types ─────────────────────────── */

interface Card {
  id: string | number
  [key: string]: any
}

interface Column {
  id: string
  title: string
  color: string
}

/* ─────────────────────────── Styles ─────────────────────────── */

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    background: '#F9FAFB',
  },
  header: {
    padding: '24px 32px 16px',
  },
  title: {
    fontSize: '24px',
    fontWeight: 700,
    color: '#111827',
    margin: 0,
  },
  subtitle: {
    fontSize: '14px',
    color: '#6B7280',
    marginTop: '4px',
  },
  filterBar: {
    display: 'flex',
    gap: '12px',
    padding: '0 32px 16px',
    alignItems: 'center',
    flexWrap: 'wrap' as const,
  },
  searchInput: {
    padding: '8px 14px',
    borderRadius: '8px',
    border: '1px solid #D1D5DB',
    fontSize: '14px',
    width: '260px',
    outline: 'none',
  },
  filterSelect: {
    padding: '8px 14px',
    borderRadius: '8px',
    border: '1px solid #D1D5DB',
    fontSize: '14px',
    background: '#FFF',
    cursor: 'pointer',
    outline: 'none',
  },
  board: {
    display: 'flex',
    gap: '16px',
    padding: '0 32px 32px',
    overflowX: 'auto' as const,
    flex: 1,
    alignItems: 'flex-start',
  },
  column: {
    minWidth: '300px',
    maxWidth: '340px',
    flex: '1 0 300px',
    borderRadius: '12px',
    background: '#F3F4F6',
    display: 'flex',
    flexDirection: 'column' as const,
    maxHeight: 'calc(100vh - 200px)',
  },
  columnHeader: {
    padding: '14px 16px',
    borderRadius: '12px 12px 0 0',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  columnTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#FFF',
  },
  columnCount: {
    fontSize: '12px',
    fontWeight: 600,
    background: 'rgba(255,255,255,0.3)',
    borderRadius: '10px',
    padding: '2px 8px',
    color: '#FFF',
  },
  cardList: {
    padding: '8px 10px',
    overflowY: 'auto' as const,
    flex: 1,
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '10px',
  },
  card: {
    background: '#FFFFFF',
    borderRadius: '10px',
    padding: '14px 16px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
    cursor: 'grab',
    transition: 'box-shadow 0.15s, transform 0.15s',
    border: '1px solid #E5E7EB',
  },
  cardDragging: {
    boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
    transform: 'rotate(2deg)',
    opacity: 0.9,
  },
  cardTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#111827',
    margin: 0,
  },
  cardSubtitle: {
    fontSize: '12px',
    color: '#6B7280',
    marginTop: '4px',
  },
  cardMeta: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginTop: '10px',
    flexWrap: 'wrap' as const,
  },
  badge: {
    fontSize: '11px',
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: '6px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.3px',
  },
  assignee: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '12px',
    color: '#374151',
  },
  avatar: {
    width: '22px',
    height: '22px',
    borderRadius: '50%',
    background: '#D1D5DB',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '10px',
    fontWeight: 700,
    color: '#4B5563',
  },
  dueDate: {
    fontSize: '11px',
    color: '#9CA3AF',
    marginLeft: 'auto',
  },
  dropZone: {
    border: '2px dashed #93C5FD',
    borderRadius: '10px',
    padding: '20px',
    textAlign: 'center' as const,
    color: '#93C5FD',
    fontSize: '13px',
  },
  loader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    fontSize: '16px',
    color: '#6B7280',
  },
  spinner: {
    width: '32px',
    height: '32px',
    border: '3px solid #E5E7EB',
    borderTopColor: config.accentColor || '#3B82F6',
    borderRadius: '50%',
    animation: 'kanban-spin 0.7s linear infinite',
  },
}

/* ─────────────────────────── Component ─────────────────────────── */

export function KanbanBoard() {
  const [cards, setCards] = useState<Card[]>([])
  const [loading, setLoading] = useState(true)
  const [searchText, setSearchText] = useState('')
  const [priorityFilter, setPriorityFilter] = useState('')
  const [assigneeFilter, setAssigneeFilter] = useState('')
  const [draggedCardId, setDraggedCardId] = useState<string | number | null>(null)
  const [dragOverCol, setDragOverCol] = useState<string | null>(null)

  // Fetch cards from API
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetch(`${_API}/api/${config.tableName}`)
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled) {
          const rows = Array.isArray(data) ? data : data.data || data.rows || []
          setCards(rows.map((r: any, i: number) => ({ ...r, id: r.id ?? i })))
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  // Extract unique values for filters
  const uniquePriorities = useMemo(() => {
    if (!config.priorityField) return []
    const set = new Set(cards.map((c) => c[config.priorityField]).filter(Boolean))
    return Array.from(set) as string[]
  }, [cards])

  const uniqueAssignees = useMemo(() => {
    if (!config.assigneeField) return []
    const set = new Set(cards.map((c) => c[config.assigneeField]).filter(Boolean))
    return Array.from(set) as string[]
  }, [cards])

  // Filter cards
  const filteredCards = useMemo(() => {
    return cards.filter((card) => {
      // Text search
      if (searchText) {
        const text = searchText.toLowerCase()
        const title = (card[config.titleField] || '').toLowerCase()
        const subtitle = (card[config.subtitleField] || '').toLowerCase()
        if (!title.includes(text) && !subtitle.includes(text)) return false
      }
      // Priority filter
      if (priorityFilter && config.priorityField) {
        if (card[config.priorityField] !== priorityFilter) return false
      }
      // Assignee filter
      if (assigneeFilter && config.assigneeField) {
        if (card[config.assigneeField] !== assigneeFilter) return false
      }
      return true
    })
  }, [cards, searchText, priorityFilter, assigneeFilter])

  // Group cards by column
  const columnCards = useMemo(() => {
    const map: Record<string, Card[]> = {}
    config.columns.forEach((col) => { map[col.id] = [] })
    filteredCards.forEach((card) => {
      const colId = card[config.statusField]
      if (map[colId]) map[colId].push(card)
    })
    return map
  }, [filteredCards])

  /* ── Drag & Drop handlers ── */

  const handleDragStart = (e: React.DragEvent, cardId: string | number) => {
    setDraggedCardId(cardId)
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(cardId))
  }

  const handleDragOver = (e: React.DragEvent, colId: string) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDragOverCol(colId)
  }

  const handleDragLeave = () => {
    setDragOverCol(null)
  }

  const handleDrop = (e: React.DragEvent, targetColId: string) => {
    e.preventDefault()
    setDragOverCol(null)
    if (draggedCardId == null) return

    setCards((prev) =>
      prev.map((card) =>
        card.id === draggedCardId
          ? { ...card, [config.statusField]: targetColId }
          : card
      )
    )
    setDraggedCardId(null)
  }

  const handleDragEnd = () => {
    setDraggedCardId(null)
    setDragOverCol(null)
  }

  /* ── Helpers ── */

  const getInitials = (name: string) => {
    if (!name) return '?'
    return name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2)
  }

  const getPriorityColor = (priority: string) => {
    const colors = config.priorityColors as Record<string, string>
    return colors[priority?.toLowerCase()] || '#6B7280'
  }

  /* ── Render ── */

  if (loading) {
    return (
      <div style={styles.wrapper}>
        <style>{`@keyframes kanban-spin { to { transform: rotate(360deg); } }`}</style>
        <div style={styles.loader}>
          <div style={styles.spinner} />
        </div>
      </div>
    )
  }

  return (
    <div style={styles.wrapper}>
      <style>{`@keyframes kanban-spin { to { transform: rotate(360deg); } }`}</style>

      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.title}>{config.pageTitle}</h1>
        {config.pageSubtitle && <p style={styles.subtitle}>{config.pageSubtitle}</p>}
      </div>

      {/* Filter Bar */}
      <div style={styles.filterBar}>
        <input
          type="text"
          placeholder="Search cards..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          style={styles.searchInput}
        />
        {config.priorityField && uniquePriorities.length > 0 && (
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            style={styles.filterSelect}
          >
            <option value="">All Priorities</option>
            {uniquePriorities.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        )}
        {config.assigneeField && uniqueAssignees.length > 0 && (
          <select
            value={assigneeFilter}
            onChange={(e) => setAssigneeFilter(e.target.value)}
            style={styles.filterSelect}
          >
            <option value="">All Assignees</option>
            {uniqueAssignees.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        )}
      </div>

      {/* Board */}
      <div style={styles.board}>
        {config.columns.map((col: Column) => (
          <div
            key={col.id}
            style={styles.column}
            onDragOver={(e) => handleDragOver(e, col.id)}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, col.id)}
          >
            {/* Column Header */}
            <div style={{ ...styles.columnHeader, background: col.color }}>
              <span style={styles.columnTitle}>{col.title}</span>
              <span style={styles.columnCount}>{columnCards[col.id]?.length || 0}</span>
            </div>

            {/* Card List */}
            <div style={styles.cardList}>
              {dragOverCol === col.id && draggedCardId != null && (
                <div style={styles.dropZone}>Drop here</div>
              )}
              {(columnCards[col.id] || []).map((card) => (
                <div
                  key={card.id}
                  draggable
                  onDragStart={(e) => handleDragStart(e, card.id)}
                  onDragEnd={handleDragEnd}
                  style={{
                    ...styles.card,
                    ...(draggedCardId === card.id ? styles.cardDragging : {}),
                  }}
                >
                  <p style={styles.cardTitle}>{card[config.titleField]}</p>
                  {config.subtitleField && card[config.subtitleField] && (
                    <p style={styles.cardSubtitle}>{card[config.subtitleField]}</p>
                  )}
                  <div style={styles.cardMeta}>
                    {config.priorityField && card[config.priorityField] && (
                      <span
                        style={{
                          ...styles.badge,
                          color: getPriorityColor(card[config.priorityField]),
                          background: `${getPriorityColor(card[config.priorityField])}18`,
                        }}
                      >
                        {card[config.priorityField]}
                      </span>
                    )}
                    {config.assigneeField && card[config.assigneeField] && (
                      <span style={styles.assignee}>
                        <span style={styles.avatar}>
                          {getInitials(card[config.assigneeField])}
                        </span>
                        {card[config.assigneeField]}
                      </span>
                    )}
                    {config.dateField && card[config.dateField] && (
                      <span style={styles.dueDate}>{card[config.dateField]}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default KanbanBoard
