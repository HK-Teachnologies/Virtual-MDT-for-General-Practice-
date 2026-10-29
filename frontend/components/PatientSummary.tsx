'use client';

import { useEffect, useState } from 'react';
import type { MySummary, MySummaryVisit } from '../lib/types';

export type SummaryLang = 'en' | 'sw' | 'lg';

const LANGS = [
  { code: 'en', label: 'English' },
  { code: 'sw', label: 'Kiswahili' },
  { code: 'lg', label: 'Luganda' },
] as const;

function pickVoice(lang: string): SpeechSynthesisVoice | null {
  const voices = window.speechSynthesis.getVoices();
  return (
    voices.find((v) => v.lang.toLowerCase().startsWith(lang)) ??
    voices.find((v) => v.lang.toLowerCase().startsWith('en')) ??
    null
  );
}

export function LangTabs({ lang, onChange }: { lang: SummaryLang; onChange: (l: SummaryLang) => void }) {
  return (
    <div className="row tabs">
      {LANGS.map((l) => (
        <button
          key={l.code}
          className={lang === l.code ? 'btn btn-primary' : 'btn'}
          type="button"
          onClick={() => onChange(l.code)}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}

export function ListenButton({ text, lang }: { text: string; lang: SummaryLang }) {
  const [speaking, setSpeaking] = useState(false);
  const [noVoice, setNoVoice] = useState(false);

  useEffect(() => {
    window.speechSynthesis?.getVoices();
    return () => window.speechSynthesis?.cancel();
  }, []);

  function listen() {
    if (!('speechSynthesis' in window) || !text) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    const voice = pickVoice(lang);
    if (voice) {
      utter.voice = voice;
      utter.lang = voice.lang;
      setNoVoice(lang === 'lg' && !voice.lang.toLowerCase().startsWith('lg'));
    } else {
      setNoVoice(true);
    }
    utter.onend = () => setSpeaking(false);
    utter.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utter);
  }

  function stop() {
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  }

  return (
    <span>
      {!speaking ? (
        <button className="btn" type="button" onClick={listen}>
          🔊 Listen
        </button>
      ) : (
        <button className="btn" type="button" onClick={stop}>
          ⏹ Stop
        </button>
      )}
      {noVoice && (
        <p className="muted">
          Your device has no Luganda voice, so this is read with the closest available
          voice. The written Luganda text is complete.
        </p>
      )}
    </span>
  );
}

export default function PatientSummary({
  summary,
  visits,
  recordVisits,
  lang,
  onLang,
}: {
  summary: MySummary;
  visits: MySummaryVisit[];
  recordVisits: { id: string; visit_date: string }[];
  lang: SummaryLang;
  onLang: (l: SummaryLang) => void;
}) {
  const overall = summary.summary?.[lang] ?? '';
  const byId = new Map(visits.map((v) => [v.visit_id, v]));
  const ordered = [...recordVisits].sort((a, b) => b.visit_date.localeCompare(a.visit_date));

  return (
    <>
      <LangTabs lang={lang} onChange={onLang} />
      {(summary.summary?.en || summary.summary?.sw || summary.summary?.lg) && (
        <section className="panel">
          <h2>My visit summary</h2>
          <p>{overall || <span className="muted">Not available in this language yet.</span>}</p>
          {overall && (
            <div className="row">
              <ListenButton text={overall} lang={lang} />
            </div>
          )}
          <p className="muted">This summary helps you remember your visit. Your doctor will explain more.</p>
        </section>
      )}
      <section className="panel">
        <h2>Visit history</h2>
        {ordered.length === 0 && <p className="muted">No visits recorded yet.</p>}
        {ordered.map((v) => {
          const line = byId.get(v.id);
          const text = line?.[lang] ?? '';
          return (
            <div key={v.id} className="brief-item">
              <div className="row">
                <strong>{v.visit_date}</strong>
                {text && <ListenButton text={text} lang={lang} />}
              </div>
              <p>{text || <span className="muted">Summary being prepared — check back soon.</span>}</p>
            </div>
          );
        })}
      </section>
    </>
  );
}
