'use client';

import { useEffect, useRef, useState } from 'react';
import {
  createReferralLetter,
  listReferralLetters,
  releaseReferralLetter,
} from '../lib/api';
import type { ApiReferralLetter } from '../lib/types';
import ReferralLetterForm from './ReferralLetterDialog';

/** Referral letters for one brief run: draft from signed-off points,
 * release so the patient can present the letter at any facility. */
export default function ReferralLetters({
  runId,
  token,
}: {
  runId: string;
  token: string;
}) {
  const [letters, setLetters] = useState<ApiReferralLetter[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    listReferralLetters(token, runId).then(setLetters).catch(() => setLetters([]));
  }, [token, runId]);

  useEffect(
    () => () => {
      if (copyTimer.current) clearTimeout(copyTimer.current);
    },
    [],
  );

  async function draft(data: {
    destination_facility: string;
    reason: string;
    additional_note: string;
  }) {
    setBusy(true);
    setError(null);
    try {
      const created = await createReferralLetter(token, runId, data);
      setLetters((ls) => [...(ls ?? []), created]);
      setCreating(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not draft the letter.');
    }
    setBusy(false);
  }

  async function release(id: string) {
    setBusy(true);
    setError(null);
    try {
      const updated = await releaseReferralLetter(token, id);
      setLetters((ls) => (ls ?? []).map((l) => (l.id === id ? updated : l)));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not release.');
    }
    setBusy(false);
  }

  async function copy(letter: ApiReferralLetter) {
    try {
      await navigator.clipboard.writeText(letter.letter_text);
      setCopiedId(letter.id);
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopiedId(null), 2500);
    } catch {
      setCopiedId(null);
    }
  }

  return (
    <section className="panel">
      <div className="brief-item-head">
        <strong>Referral letters</strong>
        {!creating && (
          <button className="btn" type="button" onClick={() => setCreating(true)}>
            New referral letter
          </button>
        )}
      </div>
      <p className="muted">
        Drafted only from approved and edited points. Release a letter and the
        patient can show it at the facility they attend — even a different one.
      </p>
      {creating && (
        <div>
          <ReferralLetterForm busy={busy} onDraft={draft} />
          <div className="row">
            <button className="btn" type="button" onClick={() => setCreating(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
      {error && <p className="error">{error}</p>}
      {letters === null && <p className="muted">Loading…</p>}
      {letters !== null && letters.length === 0 && !creating && (
        <p className="muted">No referral letters yet.</p>
      )}
      {(letters ?? []).map((l) => (
        <div key={l.id} className="brief-item">
          <div className="brief-item-head">
            <strong>To {l.destination_facility}</strong>
            <span className={`badge badge-${l.summary_status === 'released' ? 'closed' : 'pending'}`}>
              {l.summary_status === 'released' ? 'Released to patient' : 'Draft — not visible to patient'}
            </span>
          </div>
          <p className="muted">{l.reason}</p>
          <pre className="letter-preview">{l.letter_text}</pre>
          {l.summary_status === 'released' && (
            <p className="muted">
              Released by {l.released_by_name ?? 'a clinician'}
              {l.released_at ? ` on ${l.released_at.slice(0, 10)}` : ''}
            </p>
          )}
          <div className="row">
            <button className="btn" type="button" onClick={() => copy(l)}>
              {copiedId === l.id ? 'Copied' : 'Copy letter'}
            </button>
            {l.summary_status !== 'released' && (
              <button
                className="btn btn-primary"
                type="button"
                onClick={() => release(l.id)}
                disabled={busy}
              >
                {busy ? 'Releasing…' : 'Release to patient'}
              </button>
            )}
          </div>
        </div>
      ))}
    </section>
  );
}
