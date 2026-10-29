'use client';

import { useState } from 'react';
import VoiceRecorder from './VoiceRecorder';
import { answerQuestion, getPatientToken } from '../lib/patient-auth';
import type { ApiFollowUp } from '../lib/types';

function AnswerForm({ q, token, onAnswered }: { q: ApiFollowUp; token: string; onAnswered: (q: ApiFollowUp) => void }) {
  const [text, setText] = useState('');
  const [audio, setAudio] = useState<Blob | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const file = audio ? new File([audio], 'answer.webm', { type: audio.type || 'audio/webm' }) : null;
      onAnswered(await answerQuestion(token, q.id, text.trim(), file));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not send your answer.');
    }
    setBusy(false);
  }

  return (
    <div>
      <label htmlFor={`ans-${q.id}`}>Your answer</label>
      <textarea
        id={`ans-${q.id}`}
        rows={3}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type your answer here, or record a voice note below."
      />
      <VoiceRecorder onRecording={setAudio} onClear={() => setAudio(null)} />
      {error && <p className="error">{error}</p>}
      <button className="btn btn-primary" type="button" onClick={submit} disabled={busy || (!text.trim() && !audio)}>
        {busy ? 'Sending…' : 'Send answer'}
      </button>
    </div>
  );
}

export default function PatientQuestions({
  initial,
  lang,
}: {
  initial: ApiFollowUp[];
  lang: 'en' | 'sw' | 'lg';
}) {
  const [questions, setQuestions] = useState(initial);
  const token = getPatientToken();
  const open = questions.filter((q) => q.status === 'open');
  const answered = questions.filter((q) => q.status !== 'open');

  function replace(updated: ApiFollowUp) {
    setQuestions((qs) => qs.map((q) => (q.id === updated.id ? updated : q)));
  }

  function wording(q: ApiFollowUp): string {
    return q.question_i18n?.[lang]?.trim() || q.question;
  }

  return (
    <section className="panel">
      <h2>Questions from your doctor{open.length > 0 ? ` (${open.length} to answer)` : ''}</h2>
      {questions.length === 0 && <p className="muted">No questions right now.</p>}
      {open.map((q) => (
        <div key={q.id} className="brief-item">
          <p><strong>{q.asker_name || 'Your doctor'} asks:</strong> {wording(q)}</p>
          {token && <AnswerForm q={q} token={token} onAnswered={replace} />}
        </div>
      ))}
      {answered.length > 0 && (
        <details>
          <summary>Answered ({answered.length})</summary>
          {answered.map((q) => (
            <div key={q.id} className="brief-item">
              <p className="muted">{wording(q)}</p>
              <p>{q.answer_text}</p>
              {q.answer_original && q.answer_original !== q.answer_text && (
                <details>
                  <summary>Show original</summary>
                  <p className="muted">{q.answer_original}</p>
                </details>
              )}
            </div>
          ))}
        </details>
      )}
    </section>
  );
}
