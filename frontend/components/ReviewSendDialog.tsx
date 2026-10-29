'use client';

import Link from 'next/link';
import { useEffect, useState, type FormEvent } from 'react';
import { API_BASE } from '../lib/api';
import { interactionLine, overdueCheckLine } from '../lib/sources';
import type { ApiReview, ApiSpecialty, BriefItem, MdtBrief } from '../lib/types';

export default function ReviewSendDialog({
  patientId,
  brief,
  items,
  token,
  onClose,
}: {
  patientId: string;
  brief: MdtBrief;
  items: BriefItem[];
  token: string;
  onClose: () => void;
}) {
  const [roster, setRoster] = useState<ApiSpecialty[] | null>(null);
  const [specIds, setSpecIds] = useState<string[]>([]);
  const [picks, setPicks] = useState<string[]>([]);
  const [pickUser, setPickUser] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<ApiReview | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/specialties/roster`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((list) => {
        if (list) {
          const specs = list as ApiSpecialty[];
          setRoster(specs);
          // Pre-select only the specialties this review is about, matched
          // by name. Unticked specialties are still listed for hand-picking.
          const wanted = new Set(
            (brief.specialties ?? []).map((s) => s.trim().toLowerCase()),
          );
          const matched = specs.filter((s) => wanted.has(s.name.trim().toLowerCase()));
          setSpecIds((matched.length > 0 ? matched : specs).map((s) => s.id));
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function toggleSpec(id: string) {
    setSpecIds((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]));
  }

  function toggleMember(specId: string, userId: string) {
    // Unchecking one member of a whole specialty converts the rest of that
    // specialty into individual picks, so nobody is notified by accident.
    const spec = roster?.find((s) => s.id === specId);
    if (spec && specIds.includes(specId)) {
      setSpecIds((prev) => prev.filter((s) => s !== specId));
      setPicks((prev) => [
        ...prev,
        ...spec.members.filter((m) => m.id !== userId).map((m) => m.id),
      ]);
      return;
    }
    setPicks((prev) => (prev.includes(userId) ? prev.filter((p) => p !== userId) : [...prev, userId]));
  }

  function addPick() {
    if (pickUser && !picks.includes(pickUser)) setPicks((prev) => [...prev, pickUser]);
    setPickUser('');
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/reviews`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          patient_id: patientId,
          specialty_ids: specIds,
          user_ids: picks,
          message: message.trim(),
          brief: {
            specialties: brief.specialties,
            items: items.map((i) => ({
              specialty: i.specialty,
              concern: i.concern,
              citation: i.citation,
              certainty: i.certainty,
              status: i.status,
            })),
            interactions: brief.interactions.map(interactionLine),
            overdue_checks: brief.overdueChecks.map(overdueCheckLine),
          },
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
        setError(
          body && typeof body.detail === 'string' ? body.detail : `Could not send (${res.status}).`,
        );
      } else {
        setSent((await res.json()) as ApiReview);
      }
    } catch {
      setError('Could not reach the server.');
    }
    setBusy(false);
  }

  if (sent) {
    return (
      <section className="panel">
        <h2>Review sent — pending</h2>
        <p>
          {sent.recipients.length} specialist{sent.recipients.length === 1 ? '' : 's'} notified by
          email with a link to open it.
        </p>
        <div className="row">
          <Link className="btn btn-primary" href={`/reviews/${sent.id}`}>
            Open the review
          </Link>
          <button className="btn" type="button" onClick={onClose}>
            Back to patient
          </button>
        </div>
      </section>
    );
  }

  const allUsers = new Map<string, { email: string; label: string }>();
  (roster ?? []).forEach((s) =>
    s.members.forEach((m) =>
      allUsers.set(m.id, { email: m.email, label: `${m.full_name ?? m.email} (${m.role})` }),
    ),
  );
  const pickedLabels = picks.map((id) => allUsers.get(id)).filter(Boolean);

  return (
    <section className="panel">
      <h2>Send for specialist review</h2>
      {!roster ? (
        <p>Loading specialties…</p>
      ) : roster.length === 0 ? (
        <p className="muted">
          No active specialties yet — ask an admin to add some under Admin → Specialties.
        </p>
      ) : (
        <form onSubmit={submit}>
          <p className="muted">
            Specialties from this review are pre-ticked — everyone in a ticked specialty
            is notified. Untick anyone to exclude them, or pick specific people below.
          </p>
          {roster.map((s) => (
            <div key={s.id} className="field">
              <label>
                <input
                  type="checkbox"
                  checked={specIds.includes(s.id)}
                  onChange={() => toggleSpec(s.id)}
                />{' '}
                <strong>{s.name}</strong> ({s.members.length} member{s.members.length === 1 ? '' : 's'})
              </label>
              {s.members.map((m) => {
                const whole = specIds.includes(s.id);
                const checked = whole || picks.includes(m.id);
                return (
                  <label key={m.id} style={{ display: 'block', marginLeft: '1.5rem' }}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleMember(s.id, m.id)}
                    />{' '}
                    {m.full_name ?? m.email} <span className="muted">({m.role})</span>
                  </label>
                );
              })}
            </div>
          ))}
          {pickedLabels.length > 0 && (
            <p className="muted">Individually picked: {pickedLabels.map((p) => p!.label).join(', ')}</p>
          )}
          <div className="field">
            <label htmlFor="pickuser">Also notify someone specific</label>
            <div className="row">
              <select id="pickuser" value={pickUser} onChange={(e) => setPickUser(e.target.value)}>
                <option value="">Select…</option>
                {Array.from(allUsers.entries())
                  .filter(([id]) => !picks.includes(id))
                  .map(([id, u]) => (
                    <option key={id} value={id}>
                      {u.label}
                    </option>
                  ))}
              </select>
              <button className="btn" type="button" onClick={addPick} disabled={!pickUser}>
                Add
              </button>
            </div>
          </div>
          <div className="field">
            <label htmlFor="reviewmsg">Message to specialists</label>
            <textarea
              id="reviewmsg"
              rows={3}
              placeholder="What do you need from them?"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />
          </div>
          {error && <p className="error">{error}</p>}
          <div className="row">
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? 'Sending…' : 'Send review'}
            </button>
            <button className="btn" type="button" onClick={onClose}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
