import { useEffect, useRef, useState } from 'react'
import { Send, RotateCcw } from 'lucide-react'
import { sendChatMessage, endChat } from '../hooks/contentAgentsApi'

interface Message { role: 'user' | 'assistant'; text: string }

export default function ContentChatPanel({
  chatId, initialAnswer, onNewChat,
}: { chatId: string; initialAnswer: string; onNewChat: () => void }) {
  const [messages, setMessages] = useState<Message[]>([{ role: 'assistant', text: initialAnswer }])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight })
  }, [messages, thinking])

  async function send() {
    const text = input.trim()
    if (!text || thinking) return
    setMessages((m) => [...m, { role: 'user', text }])
    setInput('')
    setThinking(true)
    try {
      const data = await sendChatMessage(chatId, text)
      const answer = 'answer' in data ? data.answer : `[error] ${data.error || data.detail}`
      setMessages((m) => [...m, { role: 'assistant', text: answer }])
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', text: `[error] ${String(err)}` }])
    } finally {
      setThinking(false)
    }
  }

  async function handleNewChat() {
    await endChat(chatId).catch(() => {})
    onNewChat()
  }

  return (
    <div className="mt-4 flex flex-col rounded-xl border border-slate-200 bg-white">
      <div ref={logRef} className="max-h-[420px] min-h-[160px] overflow-y-auto p-4">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`mb-3 max-w-[85%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
              m.role === 'user' ? 'ml-auto bg-indigo-50 text-slate-800' : 'bg-slate-100 text-slate-700'
            }`}
          >
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              {m.role === 'user' ? 'You' : 'Assistant'}
            </span>
            {m.text}
          </div>
        ))}
        {thinking && (
          <div className="mb-3 max-w-[85%] rounded-xl bg-slate-50 px-3.5 py-2.5 text-sm italic text-slate-400">
            Thinking…
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 border-t border-slate-200 p-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Ask a question..."
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 outline-none focus:border-indigo-500"
        />
        <button
          onClick={send}
          disabled={thinking}
          className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          <Send size={14} /> Send
        </button>
        <button
          onClick={handleNewChat}
          className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
        >
          <RotateCcw size={14} /> New chat
        </button>
      </div>
    </div>
  )
}
