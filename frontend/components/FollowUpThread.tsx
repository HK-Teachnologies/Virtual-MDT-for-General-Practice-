'use client';

import { useEffect, useState } from 'react';
import { API_BASE, askFollowUp, fetchFollowUpThread } from '../lib/api';
import AuthedAudio from './AuthedAudio';
import type { ApiFollowUp } from '../lib/types';

export default function FollowUpThread({ patientId, token }: { patientId: string; token: string }) {
  const [thread, setThread] = useState<ApiFollowUp[] | null>(null);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFollowUpThread(token, patientId).then(setThread).catch(() => setThread([]));
  }, [token, patientId]);

  async function ask() {
    if (!question.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await askFollowUp(token, patientId, question.trim());
      setThread((t) => [...(t ?? []), created]);
      setQuestion('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not send the question.');
    }
    setBusy(false);
  }

  const openCount = (thread ?? []).filter((q) => q.status === 'open').length;

  return (
    <section className="panel">
      <h2>Follow-up questions{thread && openCount > 0 ? ` (${openCount} unanswered)` : ''}</h2>
      {thread === null && <p className="muted">Loading…</p>}
      {thread !== null && thread.length === 0 && (
        <p className="muted">No questions yet. Ask below and the patient answers in their portal.</p>
      )}
      {(thread ?? []).map((q) => (
        <div key={q.id} className="brief-item">
          <div className="brief-item-head">
            <strong>{q.asker_name || 'Staff'}</strong>
            <span className="badge">{q.status === 'open' ? 'Waiting for patient' : 'Answered'}</span>
          </div>
          <p>{q.question}</p>
          {q.status !== 'open' && (
            <>
              <p>{q.answer_text}</p>
              {q.has_audio && <AuthedAudio url={`${API_BASE}/api/followups/${q.id}/audio`} token={token} />}
            </>
          )}
        </div>
      ))}
      <div className="field">
        <label htmlFor="followup-ask">Ask the patient a follow-up question</label>
        <textarea
          id="followup-ask"
          rows={2}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Is the headache gone? Did the fever come back?"
        />
      </div>
      {error && <p className="error">{error}</p>}
      <button className="btn" type="button" onClick={ask} disabled={busy || !question.trim()}>
        {busy ? 'Sending…' : 'Send question'}
      </button>
    </section>
  );
}
