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

  function releaseLabel(byName: string | null, at: string | null): string {
    const who = byName ? `Dr. ${byName}` : 'Your doctor';
    const when = at ? ` on ${at.slice(0, 10)}` : '';
    return `Reviewed and shared by ${who}${when}.`;
  }

  return (
    <>
      <LangTabs lang={lang} onChange={onLang} />
      {(summary.summary?.en || summary.summary?.sw || summary.summary?.lg) && (
        <section className="panel">
          <h2>My visit summary</h2>
          <p>{overall || <span className="muted">Not available in this language yet.</span>}</p>
          <p className="muted">
            {releaseLabel(summary.summary_released_by_name, summary.summary_released_at)}{' '}
            This summary helps you remember your visit. Your doctor will explain more.
          </p>
        </section>
      )}
      <section className="panel">
        <h2>Visit history</h2>
        {ordered.length === 0 && <p className="muted">No visits recorded yet.</p>}
        {ordered.map((v) => {
          const line = byId.get(v.id);
          const text = line?.ready ? (line?.[lang] ?? '') : '';
          return (
            <div key={v.id} className="brief-item">
              <strong>{v.visit_date}</strong>
              {text ? (
                <>
                  <p>{text}</p>
                  <p className="muted">
                    {releaseLabel(line?.released_by_name ?? null, line?.released_at ?? null)}
                  </p>
                </>
              ) : (
                <p className="muted">Your doctor is preparing your summary.</p>
              )}
            </div>
          );
        })}
      </section>
    </>
  );
}
