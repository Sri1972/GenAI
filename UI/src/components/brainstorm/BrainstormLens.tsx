import { useCallback, useEffect, useMemo, useState } from 'react'
import { roundtable, RoundtablePersona, CreateMeetingBody, EngagementMode, MeetingSummary, MeetingDetail, AgendaTemplate } from '../../hooks/useApi'
import { useRoundtableStream } from '../../hooks/useRoundtableStream'
import SetupScreen from './SetupScreen'
import RoomScreen from './RoomScreen'
import RecapScreen from './RecapScreen'
import TranscriptView from './TranscriptView'

type Screen = 'setup' | 'room' | 'recap' | 'transcript'

export default function BrainstormLens({ project, onBuildApp, defaultMode = 'collaborate' }: { project: string; onBuildApp?: (seed: string) => void; defaultMode?: EngagementMode }) {
  const [personas, setPersonas] = useState<RoundtablePersona[]>([])
  const [templates, setTemplates] = useState<AgendaTemplate[]>([])
  const [screen, setScreen] = useState<Screen>('setup')
  const [seats, setSeats] = useState<string[]>([])
  const [topic, setTopic] = useState('')
  const [duration, setDuration] = useState(12)
  const [toast, setToast] = useState<string | null>(null)
  const [meetings, setMeetings] = useState<MeetingSummary[]>([])
  const [viewing, setViewing] = useState<MeetingDetail | null>(null)
  const rt = useRoundtableStream(project)

  useEffect(() => { roundtable.personas().then(setPersonas).catch(() => {}) }, [])
  useEffect(() => { roundtable.agendaTemplates().then(setTemplates).catch(() => {}) }, [])

  const refreshMeetings = useCallback(() => {
    roundtable.meetings(project).then(setMeetings).catch(() => {})
  }, [project])
  useEffect(() => { refreshMeetings() }, [refreshMeetings])

  // move to recap once the meeting is done and a recap exists (and refresh history)
  useEffect(() => {
    if (rt.recap && !rt.running && screen === 'room') { setScreen('recap'); refreshMeetings() }
  }, [rt.recap, rt.running, screen, refreshMeetings])

  const openMeeting = useCallback(async (id: string) => {
    try { const d = await roundtable.meeting(project, id); setViewing(d); setScreen('transcript') } catch {}
  }, [project])

  const showToast = (m: string) => { setToast(m); setTimeout(() => setToast(null), 2400) }

  const pmap = useMemo(() => {
    const m: Record<string, RoundtablePersona> = {}
    personas.forEach(p => { m[p.id] = p }); return m
  }, [personas])

  const start = (body: CreateMeetingBody) => {
    setSeats(body.people); setTopic(body.topic); setDuration(body.duration_minutes ?? 12)
    setScreen('room')
    rt.start(body)
  }
  const runAgain = () => setScreen('setup')

  const buildApp = () => {
    const r = rt.recap
    if (!r || !onBuildApp) return
    const commitments = r.commitments.map(c => `- ${c.who}: ${c.what}`).join('\n')
    const open = r.still_open.join('; ')
    const seed =
      `Build the web app the team just decided on in the roundtable "${topic}".\n\n` +
      `Decision: ${r.decision}\n\n${r.argument}\n\n` +
      (commitments ? `Commitments made:\n${commitments}\n\n` : '') +
      (open ? `Still open (keep these in mind, but don't block on them): ${open}\n\n` : '') +
      `The full decision record is in this project's brief.md and artifacts/decisions/, and any ` +
      `reference materials are in inputs/ — read those first, then propose the screens you'll build and build them.`
    onBuildApp(seed)
  }

  return (
    <div className="h-full min-h-0 relative">
      {screen === 'setup' && <SetupScreen personas={personas} templates={templates} onStart={start} onToast={showToast} defaultMode={defaultMode} pastMeetings={meetings} onOpenMeeting={openMeeting} />}
      {screen === 'transcript' && viewing && <TranscriptView detail={viewing} pmap={pmap} onBack={() => setScreen('setup')} />}
      {screen === 'room' && (
        <RoomScreen st={rt} actions={rt} pmap={pmap} seats={seats} topic={topic} duration={duration} />
      )}
      {screen === 'recap' && rt.recap && (
        <RecapScreen
          recap={rt.recap} contributions={rt.turns.filter(t => t.who !== 'chair').length}
          peopleCount={seats.length} diagram={rt.diagram} drawing={rt.drawing} approved={rt.approved}
          pmap={pmap} onRunAgain={runAgain} onRead={() => setScreen('room')}
          onDraw={rt.drawDiagram} onApprove={rt.approveDiagram}
          onBuildApp={onBuildApp ? buildApp : undefined}
        />
      )}
      {rt.error && screen === 'room' && (
        <div className="rt" style={{ position: 'absolute', bottom: 90, left: '50%', transform: 'translateX(-50%)', background: 'oklch(0.28 0.015 70)', color: '#fff', fontSize: 13.5, padding: '10px 18px', borderRadius: 11 }}>
          {rt.error}
        </div>
      )}
      {toast && (
        <div style={{ position: 'absolute', bottom: 28, left: '50%', transform: 'translateX(-50%)', background: 'oklch(0.28 0.015 70)', color: '#fff', fontSize: 14, fontWeight: 500, padding: '12px 20px', borderRadius: 11, fontFamily: "'Instrument Sans', sans-serif" }}>
          {toast}
        </div>
      )}
    </div>
  )
}
