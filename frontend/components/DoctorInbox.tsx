'use client';

import { useEffect, useState } from 'react';
import {
  answerPatientQuestion,
  fetchPatientQuestionsForPatient,
  translateAnswerDraft,
} from '../lib/api';
import { useAuth } from '../lib/auth';
import type { ApiPatientQuestion } from '../lib/types';

function waitLabel(iso: string): string {
  const mins = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 60) return `waiting ${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 48) return `waiting ${hours}h`;
  return `waiting ${Math.floor(hours / 24)}d`;
}

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
  const [i18n, setI18n] = useState<Record<string, { sw: string; lg: string }>>({});
  const [translating, setTranslating] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPatientQuestionsForPatient(token, patientId)
      .then(setItems)
      .catch(() => setItems([]));
  }, [token, patientId]);

  async function translate(id: string) {
    const text = (drafts[id] ?? '').trim();
    if (!text || translating) return;
    setTranslating(id);
    setError(null);
    try {
      const t = await translateAnswerDraft(token, text);
      setI18n((m) => ({ ...m, [id]: { sw: t.sw, lg: t.lg } }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Translation failed.');
    }
    setTranslating(null);
  }

  async function send(id: string) {
    const text = (drafts[id] ?? '').trim();
    if (!text || busy) return;
    setBusy(true);
    setError(null);
    try {
      const t = i18n[id];
      const updated = await answerPatientQuestion(token, id, text, t?.sw ?? '', t?.lg ?? '');
      setItems((qs) => (qs ?? []).map((q) => (q.id === updated.id ? updated : q)));
      setDrafts((d) => ({ ...d, [id]: '' }));
      setI18n((m) => {
        const next = { ...m };
        delete next[id];
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not send the answer.');
    }
    setBusy(false);
  }

  if (items === null) return <p>Loading patient questions…</p>;
  const open = items
    .filter((q) => q.status === 'open')
    .sort((a, b) => a.created_at.localeCompare(b.created_at));
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
            <strong>Patient asks:</strong> {q.question}{' '}
            <span className="muted">({waitLabel(q.created_at)})</span>
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
                <label htmlFor={`doc-ans-${q.id}`}>Your answer (English)</label>
                <textarea
                  id={`doc-ans-${q.id}`}
                  rows={2}
                  value={drafts[q.id] ?? ''}
                  onChange={(e) => setDrafts((d) => ({ ...d, [q.id]: e.target.value }))}
                  placeholder="Type your answer to the patient."
                />
              </div>
              {i18n[q.id] ? (
                <>
                  <div className="field">
                    <label htmlFor={`doc-ans-sw-${q.id}`}>Kiswahili (check and edit)</label>
                    <textarea
                      id={`doc-ans-sw-${q.id}`}
                      rows={2}
                      value={i18n[q.id].sw}
                      onChange={(e) =>
                        setI18n((m) => ({ ...m, [q.id]: { ...m[q.id], sw: e.target.value } }))
                      }
                    />
                  </div>
                  <div className="field">
                    <label htmlFor={`doc-ans-lg-${q.id}`}>Luganda (check and edit)</label>
                    <textarea
                      id={`doc-ans-lg-${q.id}`}
                      rows={2}
                      value={i18n[q.id].lg}
                      onChange={(e) =>
                        setI18n((m) => ({ ...m, [q.id]: { ...m[q.id], lg: e.target.value } }))
                      }
                    />
                  </div>
                </>
              ) : (
                <div className="row">
                  <button
                    className="btn"
                    type="button"
                    onClick={() => translate(q.id)}
                    disabled={translating === q.id || !(drafts[q.id] ?? '').trim()}
                  >
                    {translating === q.id ? 'Translating…' : 'Translate to Kiswahili & Luganda'}
                  </button>
                </div>
              )}
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
                <strong>{q.answerer_name || 'Staff'} answered:</strong>{' '}
                {q.answer_text}
              </p>
              {(q.answer_i18n?.sw || q.answer_i18n?.lg) && (
                <details>
                  <summary>Translations sent</summary>
                  {q.answer_i18n?.sw && (
                    <p>
                      <strong>Kiswahili:</strong> {q.answer_i18n.sw}
                    </p>
                  )}
                  {q.answer_i18n?.lg && (
                    <p>
                      <strong>Luganda:</strong> {q.answer_i18n.lg}
                    </p>
                  )}
                </details>
              )}
            </div>
          ))}
        </details>
      )}
    </section>
  );
}
