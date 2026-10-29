'use client';

import { useState } from 'react';
import { releaseVisitSummary, updateVisitSummary } from '../lib/api';
import type { ApiVisit } from '../lib/types';

const LANG_LABELS = [
  { code: 'en', label: 'English' },
  { code: 'sw', label: 'Kiswahili' },
  { code: 'lg', label: 'Luganda' },
] as const;

type LangCode = (typeof LANG_LABELS)[number]['code'];

function releaseStamp(visit: ApiVisit): string | null {
  if (visit.summary_status !== 'released') return null;
  const who = visit.released_by_name ?? 'a clinician';
  const when = visit.released_at ? visit.released_at.slice(0, 10) : null;
  return `Released by ${who}${when ? ` on ${when}` : ''}`;
}

/** Clinician release gate for one visit's patient-facing summary. */
export default function VisitSummaryGate({
  visit,
  token,
  onApply,
}: {
  visit: ApiVisit;
  token: string;
  onApply: (v: ApiVisit) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<LangCode, string> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const summary = visit.patient_summary;
  const released = visit.summary_status === 'released';
  const stamp = releaseStamp(visit);

  function startEdit() {
    setDraft({
      en: summary?.en ?? '',
      sw: summary?.sw ?? '',
      lg: summary?.lg ?? '',
    });
    setEditing(true);
  }

  async function save() {
    if (!draft) return;
    setBusy(true);
    setError(null);
    try {
      onApply(await updateVisitSummary(token, visit.id, draft));
      setEditing(false);
      setDraft(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save.');
    }
    setBusy(false);
  }

  async function release() {
    setBusy(true);
    setError(null);
    try {
      onApply(await releaseVisitSummary(token, visit.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not release.');
    }
    setBusy(false);
  }

  return (
    <section className="panel summary-gate">
      <div className="brief-item-head">
        <strong>Patient summary</strong>
        <span className={`badge badge-${released ? 'closed' : 'pending'}`}>
          {released ? 'Released to patient' : 'Draft — not visible to patient'}
        </span>
      </div>
      {!editing ? (
        <div>
          <p>{summary?.en || <span className="muted">Summary being prepared…</span>}</p>
          {(summary?.sw || summary?.lg) && (
            <details>
              <summary>Kiswahili and Luganda versions</summary>
              {LANG_LABELS.filter((l) => l.code !== 'en').map((l) => (
                <p key={l.code}>
                  <strong>{l.label}:</strong> {summary?.[l.code] || <span className="muted">—</span>}
                </p>
              ))}
            </details>
          )}
          {stamp && <p className="muted">{stamp}</p>}
          <div className="row">
            <button className="btn" type="button" onClick={startEdit} disabled={busy || !summary?.en}>
              Edit summary
            </button>
            {!released && (
              <button
                className="btn btn-primary"
                type="button"
                onClick={release}
                disabled={busy || !summary?.en}
              >
                {busy ? 'Releasing…' : 'Release to patient'}
              </button>
            )}
          </div>
        </div>
      ) : (
        <div>
          {LANG_LABELS.map((l) => (
            <div className="field" key={l.code}>
              <label htmlFor={`sum-${visit.id}-${l.code}`}>{l.label}</label>
              <textarea
                id={`sum-${visit.id}-${l.code}`}
                rows={2}
                value={draft?.[l.code] ?? ''}
                onChange={(e) =>
                  setDraft((d) => (d ? { ...d, [l.code]: e.target.value } : d))
                }
              />
            </div>
          ))}
          {released && (
            <p className="muted">Saving returns this summary to draft.</p>
          )}
          {error && <p className="error">{error}</p>}
          <div className="row">
            <button className="btn btn-primary" type="button" onClick={save} disabled={busy}>
              {busy ? 'Saving…' : 'Save'}
            </button>
            <button
              className="btn"
              type="button"
              onClick={() => {
                setEditing(false);
                setDraft(null);
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      {error && !editing && <p className="error">{error}</p>}
    </section>
  );
}
