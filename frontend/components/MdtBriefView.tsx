'use client';

import { useEffect, useRef, useState } from 'react';
import { API_BASE } from '../lib/api';
import { interactionLine, modelLine, overdueCheckLine, sourceLabel } from '../lib/sources';
import type { BriefItem, CitedLabel, MdtBrief } from '../lib/types';

function CiteChips({ cites, token }: { cites: CitedLabel[]; token: string | null }) {
  const [error, setError] = useState(false);
  if (cites.length === 0) return null;
  async function openCite(cite: CitedLabel) {
    setError(false);
    if (!token || !cite.doc_id) {
      setError(true);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/mdt/guidelines/${cite.doc_id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        setError(true);
        return;
      }
      const url = URL.createObjectURL(await res.blob());
      window.open(`${url}#page=${cite.page ?? 1}`, '_blank', 'noopener');
    } catch {
      setError(true);
    }
  }
  return (
    <p className="cite-chips">
      {cites.map((c, n) => (
        <button
          key={n}
          className="link-btn cite-chip"
          type="button"
          title={c.doc_id ? `Open ${c.label} in the guideline PDF` : c.label}
          onClick={() => openCite(c)}
        >
          📄 {c.label}
        </button>
      ))}
      {error && <span className="error"> Could not open the guideline file.</span>}
    </p>
  );
}

export default function MdtBriefView({
  brief,
  onSend,
  persistItem,
  token,
}: {
  brief: MdtBrief;
  onSend?: (items: BriefItem[]) => void;
  persistItem?: (id: string, status: BriefItem['status'], editedText?: string) => Promise<void>;
  token?: string | null;
}) {
  const [items, setItems] = useState<BriefItem[]>(brief.items);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [copied, setCopied] = useState(false);
  const [signOffError, setSignOffError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (copyTimer.current) clearTimeout(copyTimer.current);
    },
    [],
  );

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
      ...approved.map((i) => {
        const source = sourceLabel(i.source_type);
        return `- [${i.specialty}] ${i.concern}${i.question ? ` Question: ${i.question}` : ''}${source ? ` (${source}; ${i.citation})` : ` (${i.citation})`}`;
      }),
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
      if (copyTimer.current) clearTimeout(copyTimer.current);
      copyTimer.current = setTimeout(() => setCopied(false), 2500);
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
            {sourceLabel(item.source_type) && (
              <span className="badge">{sourceLabel(item.source_type)}</span>
            )}
            {item.urgent && <span className="badge badge-urgent">Urgent</span>}
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
              {item.question && (
                <p>
                  <strong>Question: </strong>
                  {item.question}
                </p>
              )}
              <p className="citation">{item.citation}</p>
              <CiteChips cites={item.cited_labels ?? []} token={token ?? null} />
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
                  <CiteChips cites={x.cited_labels ?? []} token={token ?? null} />
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {brief.removed.length > 0 && (
        <details className="removed-points">
          <summary>Removed by self-check ({brief.removed.length})</summary>
          <ul>
            {brief.removed.map((r, n) => (
              <li key={n}>
                <span className="muted">[{r.kind}]</span> {r.text}
                {r.sub && <p className="muted">{r.sub}</p>}
                <p className="citation">Why removed: {r.reason}</p>
              </li>
            ))}
          </ul>
        </details>
      )}

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
                  <CiteChips cites={x.cited_labels ?? []} token={token ?? null} />
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <p className="muted">{modelLine(brief.model, brief.prompt_version)}</p>
    </div>
  );
}
