'use client';

import type { MySummary, MySummaryVisit } from '../lib/types';

export type SummaryLang = 'en' | 'sw' | 'lg';

const LANGS = [
  { code: 'en', label: 'English' },
  { code: 'sw', label: 'Kiswahili' },
  { code: 'lg', label: 'Luganda' },
] as const;

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
              <strong>{v.visit_date}</strong>
              <p>{text || <span className="muted">Summary being prepared — check back soon.</span>}</p>
            </div>
          );
        })}
      </section>
    </>
  );
}
