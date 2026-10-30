'use client';

import { useState } from 'react';
import VoiceRecorder from './VoiceRecorder';
import { askPortalChat, getPatientToken } from '../lib/patient-auth';

type Msg = { from: 'you' | 'guide'; text: string; urgent?: boolean };

export default function PatientChat({ lang }: { lang: 'en' | 'sw' | 'lg' }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState('');
  const [audio, setAudio] = useState<Blob | null>(null);
  const [voiceKey, setVoiceKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = getPatientToken();

  async function send() {
    if (!token || busy || (!draft.trim() && !audio)) return;
    setBusy(true);
    setError(null);
    setMessages((m) => [...m, { from: 'you', text: draft.trim() || '(voice note)' }]);
    try {
      const file = audio
        ? new File([audio], 'question.webm', { type: audio.type || 'audio/webm' })
        : null;
      const reply = await askPortalChat(token, draft.trim(), lang, file);
      setMessages((m) => [...m, { from: 'guide', text: reply.reply, urgent: reply.urgent }]);
      setDraft('');
      setAudio(null);
      setVoiceKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The guide has no answer right now.');
    }
    setBusy(false);
  }

  return (
    <section className="panel">
      <h2>Ask about your care</h2>
      <p className="muted">
        I am a clinic guide, not a doctor: I can explain your record and point
        you to the right clinic, but I cannot diagnose. Type below, or record
        a voice note in English, Kiswahili, or Luganda.
      </p>
      {messages.map((m, i) => (
        <div key={i} className="brief-item">
          <p>
            <strong>{m.from === 'you' ? 'You' : 'Guide'}:</strong> {m.text}
          </p>
          {m.urgent && <span className="badge badge-urgent">Urgent — go now</span>}
        </div>
      ))}
      <div className="field">
        <label htmlFor="guide-chat">Your question</label>
        <textarea
          id="guide-chat"
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="For example: which clinic should I visit for a headache?"
        />
      </div>
      <VoiceRecorder key={voiceKey} onRecording={setAudio} onClear={() => setAudio(null)} />
      {error && <p className="error">{error}</p>}
      <div className="row">
        <button
          className="btn btn-primary"
          type="button"
          onClick={send}
          disabled={busy || (!draft.trim() && !audio)}
        >
          {busy ? 'Asking…' : 'Ask'}
        </button>
      </div>
    </section>
  );
}
