import ReactMarkdown from 'react-markdown'

// Chat-friendly markdown renderer. Styles elements explicitly (no typography plugin
// dependency) so bold/italic/lists/code/headings render cleanly inside a chat bubble.
export default function Markdown({ children, muted = false }: { children: string; muted?: boolean }) {
  const base = muted ? 'text-slate-400' : 'text-slate-700'
  return (
    <div className={`text-sm leading-relaxed ${base} space-y-2 break-words`}>
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="whitespace-pre-wrap">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-slate-900">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => <ul className="list-disc pl-5 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="marker:text-slate-400">{children}</li>,
          h1: ({ children }) => <h1 className="text-base font-semibold text-slate-900 mt-1">{children}</h1>,
          h2: ({ children }) => <h2 className="text-sm font-semibold text-slate-900 mt-1">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-semibold text-slate-800 mt-1">{children}</h3>,
          a: ({ children, href }) => <a href={href} target="_blank" rel="noopener noreferrer" className="text-violet-600 underline">{children}</a>,
          blockquote: ({ children }) => <blockquote className="border-l-2 border-slate-200 pl-3 text-slate-500 italic">{children}</blockquote>,
          hr: () => <hr className="border-slate-200 my-2" />,
          code: ({ inline, children }: any) =>
            inline
              ? <code className="bg-slate-100 text-violet-700 rounded px-1 py-0.5 text-[0.85em] font-mono">{children}</code>
              : <code className="block bg-slate-900 text-slate-100 rounded-lg p-3 my-1 overflow-x-auto text-xs font-mono">{children}</code>,
          pre: ({ children }) => <pre className="overflow-x-auto">{children}</pre>,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
