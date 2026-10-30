'use client';

import { useEffect, useState } from 'react';
import {
  answerPatientQuestion,
  fetchPatientQuestionsForPatient,
} from '../lib/api';
import { useAuth } from '../lib/auth';
import type { ApiPatientQuestion } from '../lib/types';

export default function DoctorInbox({
  patientId,
  token,
}: {
  patientId: string;
  token: string;
}) {
  const { user } = useAuth();
  // Only clinical staff answer; the non-clinical normal_user role is read-only.
  const canAnswer = (user?.role ?? '') !== 'normal_user';
  const [items, setItems] = useState<ApiPatientQuestion[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPatientQuestionsForPatient(token, patientId)
      .then(setItems)
      .catch(() => setItems([]));
  }, [token, patientId]);

  async function send(id: string) {
    const text = (drafts[id] ?? '').trim();
    if (!text || busy) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await answerPatientQuestion(token, id, text);
      setItems((qs) => (qs ?? []).map((q) => (q.id === updated.id ? updated : q)));
      setDrafts((d) => ({ ...d, [id]: '' }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not send the answer.');
    }
    setBusy(false);
  }

  if (items === null) return <p>Loading patient questions…</p>;
  const open = items.filter((q) => q.status === 'open');
  const answered = items.filter((q) => q.status !== 'open');

  return (
    <section className="panel">
      <h2>
        Questions from the patient{open.length > 0 ? ` (${open.length} to answer)` : ''}
      </h2>
      {items.length === 0 && <p className="muted">No questions from the patient.</p>}
      {error && <p className="error">{error}</p>}
      {open.map((q) => (
        <div key={q.id} className="brief-item">
          <p>
            <strong>Patient asks:</strong> {q.question}
          </p>
          {q.question_original && q.question_original !== q.question && (
            <details>
              <summary>Show original</summary>
              <p className="muted">{q.question_original}</p>
            </details>
          )}
          {canAnswer ? (
            <>
              <div className="field">
                <label htmlFor={`doc-ans-${q.id}`}>Your answer</label>
                <textarea
                  id={`doc-ans-${q.id}`}
                  rows={2}
                  value={drafts[q.id] ?? ''}
                  onChange={(e) =>
                    setDrafts((d) => ({ ...d, [q.id]: e.target.value }))
                  }
                  placeholder="Type your answer to the patient."
                />
              </div>
              <button
                className="btn btn-primary"
                type="button"
                onClick={() => send(q.id)}
                disabled={busy || !(drafts[q.id] ?? '').trim()}
              >
                {busy ? 'Sending…' : 'Send answer'}
              </button>
            </>
          ) : (
            <p className="muted">
              Your role is read-only here — a clinician will answer.
            </p>
          )}
        </div>
      ))}
      {answered.length > 0 && (
        <details>
          <summary>Answered ({answered.length})</summary>
          {answered.map((q) => (
            <div key={q.id} className="brief-item">
              <p className="muted">{q.question}</p>
              <p>
                <strong>{q.answerer_name || 'Staff'} answered:</strong> {q.answer_text}
              </p>
            </div>
          ))}
        </details>
      )}
    </section>
  );
}
