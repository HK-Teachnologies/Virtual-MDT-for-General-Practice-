'use client';

import { useState } from 'react';
import { interactionLine, overdueCheckLine, sourceLabel } from '../lib/sources';
import type { BriefItem, MdtBrief } from '../lib/types';

export default function MdtBriefView({
  brief,
  onSend,
  persistItem,
}: {
  brief: MdtBrief;
  onSend?: (items: BriefItem[]) => void;
  persistItem?: (id: string, status: BriefItem['status'], editedText?: string) => Promise<void>;
}) {
  const [items, setItems] = useState<BriefItem[]>(brief.items);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [copied, setCopied] = useState(false);
  const [signOffError, setSignOffError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  async function setStatus(id: string, status: BriefItem['status']) {
    setSignOffError(null);
    if (persistItem) {
      setSavingId(id);
      try {
        await persistItem(id, status);
      } catch {
        setSignOffError('Could not save that change — try again.');
        setSavingId(null);
        return;
      }
      setSavingId(null);
    }
    setItems((prev) => prev.map((i) => (i.id === id ? { ...i, status } : i)));
  }

  function startEdit(item: BriefItem) {
    setEditing(item.id);
    setDraft(item.concern);
  }

  async function saveEdit(id: string) {
    if (!draft.trim()) return;
    const concern = draft.trim();
    setSignOffError(null);
    if (persistItem) {
      setSavingId(id);
      try {
        await persistItem(id, 'edited', concern);
      } catch {
        setSignOffError('Could not save that change — try again.');
        setSavingId(null);
        return;
      }
      setSavingId(null);
    }
    setItems((prev) =>
      prev.map((i) => (i.id === id ? { ...i, concern, status: 'edited' } : i)),
    );
    setEditing(null);
  }

  async function copyReferral() {
    const approved = items.filter((i) => i.status === 'approved' || i.status === 'edited');
    const lines = [
      'VIRTUAL MDT BRIEF (clinician-reviewed)',
      `Specialties: ${brief.specialties.join(', ')}`,
      '',
      ...approved.map((i) => `- [${i.specialty}] ${i.concern} (certainty: ${i.certainty}; ${i.citation})`),
      '',
      'Flagged interactions:',
      ...brief.interactions.map(interactionLine),
      '',
      'Overdue checks:',
      ...brief.overdueChecks.map(overdueCheckLine),
    ];
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const approvedCount = items.filter((i) => i.status === 'approved' || i.status === 'edited').length;

  return (
    <div className="brief">
      <div className="brief-head">
        <p className="muted">
          {brief.specialties.join(' · ')} — {approvedCount} of {items.length} points approved
        </p>
        <button className="btn" type="button" onClick={copyReferral}>
          {copied ? 'Referral summary copied' : 'Copy referral summary'}
        </button>
        {onSend && (
          <button className="btn btn-primary" type="button" onClick={() => onSend(items)}>
            Send for specialist review
          </button>
        )}
      </div>

      {signOffError && <p className="error">{signOffError}</p>}
      {items.map((item) => (
        <article key={item.id} className={`brief-item status-${item.status}`}>
          <div className="brief-item-head">
            <strong>{item.specialty}</strong>
            <span className="badge">{item.status === 'suggested' ? 'AI-suggested' : `clinician-${item.status}`}</span>
            <span className="badge">certainty: {item.certainty}</span>
          </div>
          {editing === item.id ? (
            <div className="field">
              <textarea rows={4} value={draft} onChange={(e) => setDraft(e.target.value)} />
              <div className="row">
                <button className="btn btn-primary" type="button" onClick={() => saveEdit(item.id)} disabled={savingId === item.id}>
                  {savingId === item.id ? 'Saving…' : 'Save'}
                </button>
                <button className="btn" type="button" onClick={() => setEditing(null)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              <p>{item.concern}</p>
              <p className="citation">{item.citation}</p>
              <div className="row">
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={() => setStatus(item.id, 'approved')}
                  disabled={savingId === item.id || item.status === 'approved'}
                >
                  {savingId === item.id ? 'Saving…' : item.status === 'approved' ? 'Approved' : 'Approve'}
                </button>
                <button className="btn" type="button" onClick={() => startEdit(item)} disabled={savingId === item.id}>
                  Edit
                </button>
                <button
                  className="btn"
                  type="button"
                  onClick={() => setStatus(item.id, 'rejected')}
                  disabled={savingId === item.id || item.status === 'rejected'}
                >
                  {item.status === 'rejected' ? 'Rejected' : 'Reject'}
                </button>
              </div>
            </>
          )}
        </article>
      ))}

      <section>
        <h3>Flagged interactions</h3>
        {brief.interactions.length === 0 ? (
          <p className="muted">None flagged.</p>
        ) : (
          <ul>
            {brief.interactions.map((x, n) => {
              const badge = sourceLabel(x.source_type);
              return (
                <li key={`${x.drugs.join('+')}-${n}`}>
                  {x.drugs.length > 0 && <strong>{x.drugs.join(' + ')}</strong>}
                  {x.drugs.length > 0 && ' — '}
                  {x.concern}{' '}
                  {badge && <span className="badge">{badge}</span>}
                  {x.citation && <p className="citation">{x.citation}</p>}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section>
        <h3>Overdue checks</h3>
        {brief.overdueChecks.length === 0 ? (
          <p className="muted">Nothing overdue.</p>
        ) : (
          <ul>
            {brief.overdueChecks.map((x, n) => {
              const badge = sourceLabel(x.source_type);
              return (
                <li key={`${x.check}-${n}`}>
                  <strong>{x.check}</strong>
                  {x.last_done && <span className="muted"> — last done: {x.last_done}</span>}{' '}
                  {badge && <span className="badge">{badge}</span>}
                  {x.citation && <p className="citation">{x.citation}</p>}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
