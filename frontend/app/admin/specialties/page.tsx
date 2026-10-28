'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import { API_BASE } from '../../../lib/api';
import { useAuth } from '../../../lib/auth';
import type { ApiSpecialty, User } from '../../../lib/types';

export default function AdminSpecialties() {
  const { user, token, loading: authLoading } = useAuth();
  const router = useRouter();
  const [specialties, setSpecialties] = useState<ApiSpecialty[] | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [managing, setManaging] = useState<ApiSpecialty | null>(null);
  const [addUserId, setAddUserId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user || user.role !== 'admin' || !token) return;
    const headers = { Authorization: `Bearer ${token}` };
    fetch(`${API_BASE}/api/specialties`, { headers })
      .then((res) => (res.ok ? res.json() : null))
      .then((list) => {
        if (list) setSpecialties(list as ApiSpecialty[]);
      })
      .catch(() => {});
    fetch(`${API_BASE}/api/auth/users`, { headers })
      .then((res) => (res.ok ? res.json() : null))
      .then((list) => {
        if (list) setUsers(list as User[]);
      })
      .catch(() => {});
  }, [user, token]);

  function refreshManaging(id: string) {
    if (!token) return;
    fetch(`${API_BASE}/api/specialties/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((doc) => {
        if (!doc) return;
        const updated = doc as ApiSpecialty;
        setManaging(updated);
        setSpecialties((prev) =>
          prev ? prev.map((s) => (s.id === updated.id ? { ...updated, members: s.members } : s)) : prev,
        );
      })
      .catch(() => {});
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!token || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/specialties`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: name.trim(), description: description.trim() || null }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
        setError(
          body && typeof body.detail === 'string' ? body.detail : `Could not add (${res.status}).`,
        );
      } else {
        const created = (await res.json()) as ApiSpecialty;
        setSpecialties((prev) => (prev ? [...prev, created] : [created]));
        setName('');
        setDescription('');
      }
    } catch {
      setError('Could not reach the server.');
    }
    setBusy(false);
  }

  async function toggleActive(spec: ApiSpecialty) {
    if (!token) return;
    const res = await fetch(`${API_BASE}/api/specialties/${spec.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ active: !spec.active }),
    });
    if (!res.ok) return;
    const updated = (await res.json()) as ApiSpecialty;
    setSpecialties((prev) => (prev ? prev.map((s) => (s.id === updated.id ? updated : s)) : prev));
  }

  async function addMember() {
    if (!token || !managing || !addUserId) return;
    const res = await fetch(`${API_BASE}/api/specialties/${managing.id}/members`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ user_id: addUserId }),
    });
    if (!res.ok) return;
    setAddUserId('');
    refreshManaging(managing.id);
  }

  async function removeMember(userId: string) {
    if (!token || !managing) return;
    const res = await fetch(
      `${API_BASE}/api/specialties/${managing.id}/members/${userId}`,
      { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } },
    );
    if (!res.ok) return;
    refreshManaging(managing.id);
  }

  if (authLoading || !user) return <p>Checking sign-in…</p>;

  if (user.role !== 'admin') {
    return (
      <div>
        <h1>Specialties</h1>
        <p>Admin access required.</p>
        <Link className="back-link" href="/">
          ← Back to patients
        </Link>
      </div>
    );
  }

  const memberIds = new Set((managing?.members ?? []).map((m) => m.id));
  const candidates = users.filter((u) => !memberIds.has(u.id));

  return (
    <div>
      <h1>Specialties</h1>
      <p className="muted">
        Review specialties route MDT reviews: everyone in a chosen specialty is
        notified unless the requester picks individuals instead.
      </p>

      <section className="panel">
        <h2>Add specialty</h2>
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="sname">Name</label>
            <input
              id="sname"
              type="text"
              required
              placeholder="e.g. HIV care"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="sdesc">Description</label>
            <input
              id="sdesc"
              type="text"
              placeholder="What this specialty covers"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          {error && <p className="error">{error}</p>}
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? 'Adding…' : 'Add specialty'}
          </button>
        </form>
      </section>

      {!specialties ? (
        <p>Loading specialties…</p>
      ) : specialties.length === 0 ? (
        <p className="muted">No specialties yet.</p>
      ) : (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Members</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {specialties.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.member_count}</td>
                  <td>{s.active ? 'Active' : 'Retired'}</td>
                  <td>
                    <button className="link-btn" type="button" onClick={() => setManaging(s)}>
                      Manage people
                    </button>{' '}
                    <button className="link-btn" type="button" onClick={() => toggleActive(s)}>
                      {s.active ? 'Retire' : 'Reactivate'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {managing && (
        <section className="panel">
          <h2>{managing.name} — people</h2>
          {(managing.members ?? []).length === 0 ? (
            <p className="muted">Nobody assigned yet.</p>
          ) : (
            <ul>
              {(managing.members ?? []).map((m) => (
                <li key={m.id}>
                  {m.full_name ?? m.email} ({m.email}, {m.role}){' '}
                  <button className="link-btn" type="button" onClick={() => removeMember(m.id)}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="field">
            <label htmlFor="adduser">Add a user</label>
            <select id="adduser" value={addUserId} onChange={(e) => setAddUserId(e.target.value)}>
              <option value="">Select…</option>
              {candidates.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.full_name ?? u.email} — {u.email} ({u.role})
                </option>
              ))}
            </select>
          </div>
          <div className="row">
            <button className="btn btn-primary" type="button" onClick={addMember} disabled={!addUserId}>
              Add to specialty
            </button>
            <button className="btn" type="button" onClick={() => setManaging(null)}>
              Done
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
