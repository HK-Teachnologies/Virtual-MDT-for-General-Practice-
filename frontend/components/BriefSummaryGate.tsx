'use client';

import { useEffect, useRef, useState } from 'react';
import {
  getBriefRun,
  prepareBriefSummary,
  releaseBriefSummary,
  updateBriefSummary,
} from '../lib/api';
import type { ApiBriefRun } from '../lib/types';

const LANGS = [
  { code: 'en', label: 'English' },
  { code: 'sw', label: 'Kiswahili' },
  { code: 'lg', label: 'Luganda' },
] as const;

type LangCode = (typeof LANGS)[number]['code'];

/** Overall patient message for one brief run: prepared on demand from
 * signed-off points only, released by a clinician. */
export default function BriefSummaryGate({
  runId,
  token,
}: {
  runId: string;
  token: string;
}) {
  const [run, setRun] = useState<ApiBriefRun | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<LangCode, string> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getBriefRun(token, runId).then(setRun).catch(() => setRun(null));
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [token, runId]);

  useEffect(() => {
    if (!preparing) return;
    timer.current = setInterval(async () => {
      try {
        const updated = await getBriefRun(token, runId);
        setRun(updated);
        if (updated.patient_summary?.en) {
          setPreparing(false);
          if (timer.current) clearInterval(timer.current);
        }
      } catch {
        /* keep polling */
      }
    }, 5000);
    const killer = setTimeout(() => {
      setPreparing(false);
      if (timer.current) clearInterval(timer.current);
      setError('Still preparing — reload the record to check.');
    }, 240000);
    return () => {
      if (timer.current) clearInterval(timer.current);
      clearTimeout(killer);
    };
  }, [preparing, token, runId]);

  async function prepare() {
    setBusy(true);
    setError(null);
    try {
      const res = await prepareBriefSummary(token, runId);
      setRun(res.run);
      if (!res.run.patient_summary?.en) setPreparing(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not prepare.');
    }
    setBusy(false);
  }

  async function save() {
    if (!draft) return;
    setBusy(true);
    setError(null);
    try {
      setRun(await updateBriefSummary(token, runId, draft));
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
      setRun(await releaseBriefSummary(token, runId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not release.');
    }
    setBusy(false);
  }

  const summary = run?.patient_summary;
  const released = run?.summary_status === 'released';

  return (
    <section className="panel summary-gate">
      <div className="brief-item-head">
        <strong>Patient message</strong>
        {summary?.en && (
          <span className={`badge badge-${released ? 'closed' : 'pending'}`}>
            {released ? 'Released to patient' : 'Draft — not visible to patient'}
          </span>
        )}
      </div>
      {!summary?.en ? (
        <div>
          <p className="muted">
            Draft the overall message from the approved and edited points above.
            Suggested and rejected points are never included.
          </p>
          {error && <p className="error">{error}</p>}
          <button className="btn" type="button" onClick={prepare} disabled={busy || preparing}>
            {preparing ? 'Preparing…' : busy ? 'Starting…' : 'Prepare patient summary'}
          </button>
        </div>
      ) : !editing ? (
        <div>
          <p>{summary.en}</p>
          <details>
            <summary>Kiswahili and Luganda versions</summary>
            {LANGS.filter((l) => l.code !== 'en').map((l) => (
              <p key={l.code}>
                <strong>{l.label}:</strong> {summary[l.code] || <span className="muted">—</span>}
              </p>
            ))}
          </details>
          {released && (
            <p className="muted">
              Released by {run?.released_by_name ?? 'a clinician'}
              {run?.released_at ? ` on ${run.released_at.slice(0, 10)}` : ''}
            </p>
          )}
          {error && <p className="error">{error}</p>}
          <div className="row">
            <button
              className="btn"
              type="button"
              onClick={() => {
                setDraft({ en: summary.en, sw: summary.sw, lg: summary.lg });
                setEditing(true);
              }}
              disabled={busy}
            >
              Edit message
            </button>
            {!released && (
              <button className="btn btn-primary" type="button" onClick={release} disabled={busy}>
                {busy ? 'Releasing…' : 'Release to patient'}
              </button>
            )}
          </div>
        </div>
      ) : (
        <div>
          {LANGS.map((l) => (
            <div className="field" key={l.code}>
              <label htmlFor={`brief-sum-${runId}-${l.code}`}>{l.label}</label>
              <textarea
                id={`brief-sum-${runId}-${l.code}`}
                rows={3}
                value={draft?.[l.code] ?? ''}
                onChange={(e) =>
                  setDraft((d) => (d ? { ...d, [l.code]: e.target.value } : d))
                }
              />
            </div>
          ))}
          {released && <p className="muted">Saving returns this message to draft.</p>}
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
    </section>
  );
}
