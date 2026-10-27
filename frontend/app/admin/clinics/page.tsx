'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import { API_BASE } from '../../../lib/api';
import { useAuth } from '../../../lib/auth';
import type { ApiClinic } from '../../../lib/types';

export default function AdminClinics() {
  const { user, token, loading: authLoading } = useAuth();
  const router = useRouter();
  const [clinics, setClinics] = useState<ApiClinic[] | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user || user.role !== 'admin' || !token) return;
    fetch(`${API_BASE}/api/clinics`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((list) => {
        if (list) setClinics(list as ApiClinic[]);
      })
      .catch(() => {});
  }, [user, token]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!token || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/clinics`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim() || undefined,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
        setError(
          body && typeof body.detail === 'string'
            ? body.detail
            : `Could not add the clinic (${res.status}).`,
        );
      } else {
        const created = (await res.json()) as ApiClinic;
        setClinics((prev) =>
          prev ? [...prev, created].sort((a, b) => a.name.localeCompare(b.name)) : [created],
        );
        setName('');
        setDescription('');
      }
    } catch {
      setError('Could not reach the server.');
    }
    setBusy(false);
  }

  async function toggleActive(clinic: ApiClinic) {
    if (!token) return;
    const res = await fetch(`${API_BASE}/api/clinics/${clinic.id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ active: !clinic.active }),
    });
    if (!res.ok) return;
    const updated = (await res.json()) as ApiClinic;
    // Deactivated clinics leave the selectable list; reactivated ones return.
    setClinics((prev) =>
      prev
        ? (updated.active
            ? [...prev.filter((c) => c.id !== updated.id), updated].sort((a, b) =>
                a.name.localeCompare(b.name),
              )
            : prev.filter((c) => c.id !== updated.id))
        : prev,
    );
  }

  if (authLoading || !user) return <p>Checking sign-in…</p>;

  if (user.role !== 'admin') {
    return (
      <div>
        <h1>Clinics</h1>
        <p>Admin access required.</p>
        <Link className="back-link" href="/">
          ← Back to patients
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1>Clinics</h1>
      <p className="muted">
        The master list staff pick from when adding a visit record. Deactivating
        keeps past records intact while removing the clinic from the list.
      </p>

      <section className="panel">
        <h2>Add clinic</h2>
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="name">Name</label>
            <input
              id="name"
              type="text"
              required
              placeholder="e.g. Dental"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="description">Description</label>
            <input
              id="description"
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          {error && <p className="error">{error}</p>}
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? 'Adding…' : 'Add clinic'}
          </button>
        </form>
      </section>

      {!clinics ? (
        <p>Loading clinics…</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Description</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {clinics.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.description ?? '—'}</td>
                <td>
                  <button className="link-btn" type="button" onClick={() => toggleActive(c)}>
                    Deactivate
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
