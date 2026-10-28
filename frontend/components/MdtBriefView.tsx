'use client';

import { useState } from 'react';
import type { BriefItem, MdtBrief } from '../lib/types';

export default function MdtBriefView({
  brief,
  onSend,
}: {
  brief: MdtBrief;
  onSend?: (items: BriefItem[]) => void;
}) {
  const [items, setItems] = useState<BriefItem[]>(brief.items);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [copied, setCopied] = useState(false);

  function setStatus(id: string, status: BriefItem['status']) {
    setItems((prev) => prev.map((i) => (i.id === id ? { ...i, status } : i)));
  }

  function startEdit(item: BriefItem) {
    setEditing(item.id);
    setDraft(item.concern);
  }

  function saveEdit(id: string) {
    if (!draft.trim()) return;
    setItems((prev) =>
      prev.map((i) => (i.id === id ? { ...i, concern: draft.trim(), status: 'edited' } : i)),
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
      ...brief.interactions.map((x) => `- ${x}`),
      '',
      'Overdue checks:',
      ...brief.overdueChecks.map((x) => `- ${x}`),
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
                <button className="btn btn-primary" type="button" onClick={() => saveEdit(item.id)}>
                  Save
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
                <button className="btn btn-primary" type="button" onClick={() => setStatus(item.id, 'approved')}>
                  Approve
                </button>
                <button className="btn" type="button" onClick={() => startEdit(item)}>
                  Edit
                </button>
                <button className="btn" type="button" onClick={() => setStatus(item.id, 'rejected')}>
                  Reject
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
            {brief.interactions.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3>Overdue checks</h3>
        <ul>
          {brief.overdueChecks.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
