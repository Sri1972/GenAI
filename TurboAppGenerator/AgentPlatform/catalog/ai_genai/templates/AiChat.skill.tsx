// @ts-nocheck
/**
 * AiChat.skill.tsx — Generic three-panel AI chat interface.
 *
 * Domain-agnostic — reads config from src/config/AiChat.config.ts
 * Works for: AI concierge, customer support, FAQ assistant, help desk, etc.
 * Layout: persona selector | chat window | context panel
 * All responses come from the config data file — no live API call.
 */
import { useState, useRef, useEffect, useMemo } from 'react'
import { config } from '../config/AiChat.config'

interface Message {
  role: 'user' | 'assistant'
  text: string
  ts: number
}

function Avatar({ name, color, size = 40 }: { name: string; color: string; size?: number }) {
  const init = name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%', background: color,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      color: '#fff', fontWeight: 700, fontSize: size * 0.38, flexShrink: 0,
    }}>{init}</div>
  )
}

export default function AiChatPage() {
  const { pageTitle, pageSubtitle, personas, responses, fallbackResponse, exportCaption } = config

  const [selectedId, setSelectedId] = useState(personas[0]?.id ?? '')
  const [messages, setMessages]     = useState<Message[]>([])
  const [input, setInput]           = useState('')
  const [typing, setTyping]         = useState(false)
  const messagesEndRef               = useRef<HTMLDivElement>(null)

  const persona = useMemo(() => personas.find((p: any) => p.id === selectedId) ?? personas[0], [selectedId])

  useEffect(() => {
    setMessages([{
      role: 'assistant',
      text: `Hello! I'm ${persona?.name ?? 'your assistant'}. ${persona?.description ?? 'How can I help you today?'}`,
      ts: Date.now(),
    }])
  }, [selectedId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing])

  const send = (question: string) => {
    if (!question.trim()) return
    const userMsg: Message = { role: 'user', text: question, ts: Date.now() }
    setMessages(m => [...m, userMsg])
    setInput('')
    setTyping(true)

    setTimeout(() => {
      const key = question.trim()
      const found = (responses as Record<string, string>)[key]
        ?? Object.entries(responses as Record<string, string>).find(([k]) => k.toLowerCase().includes(key.toLowerCase().slice(0, 20)))?.[1]
      const reply = found ?? (fallbackResponse ?? "That's a great question! Let me look into that for you.")
      setMessages(m => [...m, { role: 'assistant', text: reply, ts: Date.now() }])
      setTyping(false)
    }, 800)
  }

  const exportChat = () => {
    const text = messages.map(m => `[${m.role.toUpperCase()}] ${m.text}`).join('\n\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `chat-${persona?.name ?? 'export'}-${new Date().toISOString().slice(0, 10)}.txt`
    a.click()
  }

  const s = {
    page:     { display: 'flex', flexDirection: 'column' as const, height: '100vh', background: '#F8FAFC' },
    header:   { padding: '16px 24px', background: '#fff', borderBottom: '1px solid #E5E7EB' },
    body:     { display: 'flex', flex: 1, overflow: 'hidden' },
    panel:    { background: '#fff', borderRight: '1px solid #E5E7EB', overflow: 'auto', flexShrink: 0 },
    pItem:    { display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', cursor: 'pointer', borderBottom: '1px solid #F1F5F9', transition: 'background 0.1s' },
    chat:     { display: 'flex', flexDirection: 'column' as const, flex: 1, overflow: 'hidden' },
    msgs:     { flex: 1, overflow: 'auto', padding: '16px 24px', display: 'flex', flexDirection: 'column' as const, gap: 12 },
    inputRow: { padding: '12px 16px', borderTop: '1px solid #E5E7EB', display: 'flex', gap: 8, background: '#fff' },
    input:    { flex: 1, height: 44, padding: '0 14px', borderRadius: 22, border: '1.5px solid #D1D5DB', fontSize: 14, outline: 'none', color: '#374151' },
    sendBtn:  { height: 44, padding: '0 20px', borderRadius: 22, border: 'none', background: '#0064D2', color: '#fff', fontWeight: 600, fontSize: 14, cursor: 'pointer' },
    ctx:      { width: 220, background: '#F9FAFB', borderLeft: '1px solid #E5E7EB', padding: 16, overflow: 'auto', flexShrink: 0 },
  }

  const bubbleStyle = (role: string) => ({
    maxWidth: '70%',
    padding: '10px 14px',
    borderRadius: role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
    background: role === 'user' ? '#0064D2' : '#F1F5F9',
    color: role === 'user' ? '#fff' : '#374151',
    fontSize: 14,
    lineHeight: 1.5,
    alignSelf: role === 'user' ? 'flex-end' : 'flex-start',
  })

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#0D1B2A' }}>{pageTitle}</h1>
        {pageSubtitle && <p style={{ margin: '2px 0 0', fontSize: 13, color: '#6B7280' }}>{pageSubtitle}</p>}
      </div>

      <div style={s.body}>
        {/* Persona selector */}
        <div style={{ ...s.panel, width: 220 }}>
          <div style={{ padding: '12px 16px 8px', fontSize: 11, fontWeight: 700, color: '#9CA3AF', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Select Assistant</div>
          {personas.map((p: any) => (
            <div
              key={p.id}
              style={{ ...s.pItem, background: selectedId === p.id ? `${p.accentColor}15` : 'transparent', borderLeft: selectedId === p.id ? `3px solid ${p.accentColor}` : '3px solid transparent' }}
              onClick={() => setSelectedId(p.id)}
            >
              <Avatar name={p.name} color={p.accentColor} size={36} />
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>{p.name}</div>
                <div style={{ fontSize: 11, color: '#9CA3AF' }}>{p.role}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Chat */}
        <div style={s.chat}>
          <div style={s.msgs}>
            {messages.map((m, i) => (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: m.role === 'user' ? 'flex-end' : 'flex-start', gap: 4 }}>
                {m.role === 'assistant' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                    <Avatar name={persona?.name ?? 'AI'} color={persona?.accentColor ?? '#0064D2'} size={24} />
                    <span style={{ fontSize: 11, color: '#9CA3AF', fontWeight: 600 }}>{persona?.name}</span>
                  </div>
                )}
                <div style={bubbleStyle(m.role)}>{m.text}</div>
              </div>
            ))}
            {typing && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Avatar name={persona?.name ?? 'AI'} color={persona?.accentColor ?? '#0064D2'} size={24} />
                <div style={{ padding: '10px 14px', borderRadius: '18px 18px 18px 4px', background: '#F1F5F9' }}>
                  <span style={{ color: '#9CA3AF', fontSize: 18 }}>•••</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggested prompts */}
          {persona?.prompts && persona.prompts.length > 0 && (
            <div style={{ padding: '8px 16px', borderTop: '1px solid #F1F5F9', display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {persona.prompts.slice(0, 4).map((p: any) => (
                <button
                  key={p.id}
                  onClick={() => send(p.question)}
                  style={{ padding: '4px 12px', borderRadius: 14, border: `1px solid ${persona.accentColor}40`, background: `${persona.accentColor}10`, color: persona.accentColor, fontSize: 12, cursor: 'pointer', fontWeight: 500 }}
                >{p.label}</button>
              ))}
            </div>
          )}

          {/* Input */}
          <div style={s.inputRow}>
            <input
              style={s.input}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send(input)}
              placeholder={`Ask ${persona?.name ?? 'the assistant'} a question…`}
              disabled={typing}
            />
            <button style={s.sendBtn} onClick={() => send(input)} disabled={typing || !input.trim()}>Send</button>
          </div>
        </div>

        {/* Context panel */}
        <div style={s.ctx}>
          <div style={{ marginBottom: 16 }}>
            <Avatar name={persona?.name ?? 'AI'} color={persona?.accentColor ?? '#0064D2'} size={48} />
            <div style={{ marginTop: 8, fontWeight: 700, fontSize: 14, color: '#0D1B2A' }}>{persona?.name}</div>
            <div style={{ fontSize: 12, color: '#6B7280', marginTop: 2 }}>{persona?.role}</div>
            {persona?.description && <p style={{ fontSize: 12, color: '#9CA3AF', marginTop: 8, lineHeight: 1.5 }}>{persona.description}</p>}
          </div>
          <button
            onClick={exportChat}
            style={{ width: '100%', padding: '8px 0', borderRadius: 8, border: '1px solid #D1D5DB', background: '#fff', fontSize: 13, fontWeight: 500, cursor: 'pointer', color: '#374151', marginBottom: 8 }}
          >Export Chat</button>
          {exportCaption && <p style={{ fontSize: 11, color: '#9CA3AF', lineHeight: 1.5 }}>{exportCaption}</p>}
        </div>
      </div>
    </div>
  )
}
