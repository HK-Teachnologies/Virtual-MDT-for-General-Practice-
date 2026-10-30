'use client';

import { useState } from 'react';
import VoiceRecorder from './VoiceRecorder';
import { askDoctor, getPatientToken } from '../lib/patient-auth';
import type { ApiPatientQuestion } from '../lib/types';

// Fixed safety notice, shown in the patient's chosen language. The Kiswahili
// and Luganda wordings are drafts — have native speakers check them.
const NOTICE: Record<'en' | 'sw' | 'lg', string> = {
  en: 'Your doctor will reply here, usually within a few days. If you feel very unwell, have bleeding, chest pain, difficulty breathing, a seizure, or thoughts of harming yourself, go to the nearest health facility now.',
  sw: 'Daktari wako atajibu hapa, kwa kawaida ndani ya siku chache. Ikiwa unajisikia vibaya sana, unavuja damu, una maumivu ya kifua, unapumua kwa shida, una kifafa, au una mawazo ya kujidhuru, nenda kwenye kituo cha afya kilicho karibu nawe sasa hivi.',
  lg: 'Musawo wo ajja kuddamu wano, ebiseera ebisinga mu nnaku ntono. Bw’owulira obulwadde obw’amaanyi, olugulu olw’omusaayi, obulumi mu kifuba, obuzibu mu kussa, ekikolo, oba endowooza ez’okwetta, genda ku ddwaliro erisinga okuba okumpi naawe kati.',
};

export default function PatientAskDoctor({
  initial,
  lang,
}: {
  initial: ApiPatientQuestion[];
  lang: 'en' | 'sw' | 'lg';
}) {
  const [items, setItems] = useState(initial);
  const [draft, setDraft] = useState('');
  const [audio, setAudio] = useState<Blob | null>(null);
  const [voiceKey, setVoiceKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = getPatientToken();
  const open = items.filter((q) => q.status === 'open');

  function answerIn(q: ApiPatientQuestion): string {
    return q.answer_i18n?.[lang]?.trim() || q.answer_text;
  }

  async function send() {
    if (!token || busy || (!draft.trim() && !audio)) return;
    setBusy(true);
    setError(null);
    try {
      const file = audio
        ? new File([audio], 'question.webm', { type: audio.type || 'audio/webm' })
        : null;
      const created = await askDoctor(token, draft.trim(), file);
      setItems((qs) => [...qs, created]);
      setDraft('');
      setAudio(null);
      setVoiceKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not send your question.');
    }
    setBusy(false);
  }

  return (
    <section className="panel">
      <h2>
        Ask the doctor{open.length > 0 ? ` (${open.length} waiting for an answer)` : ''}
      </h2>
      <p className="notice">{NOTICE[lang]}</p>
      <p className="muted">
        A clinician reads every question and answers on your record. Type below,
        or record a voice note in English, Kiswahili, or Luganda.
      </p>
      {items.map((q) => (
        <div key={q.id} className="brief-item">
          <p>
            <strong>You asked:</strong> {q.question}
          </p>
          {q.question_original && q.question_original !== q.question && (
            <details>
              <summary>Show original</summary>
              <p className="muted">{q.question_original}</p>
            </details>
          )}
          {q.answer_text ? (
            <p>
              <strong>{q.answerer_name || 'Doctor'} answered:</strong> {answerIn(q)}
            </p>
          ) : (
            <p className="muted">Waiting for the doctor&apos;s answer.</p>
          )}
        </div>
      ))}
      <div className="field">
        <label htmlFor="ask-doctor">Your question</label>
        <textarea
          id="ask-doctor"
          rows={2}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="For example: can I take my pills with food?"
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
          {busy ? 'Sending…' : 'Send question'}
        </button>
      </div>
    </section>
  );
}
