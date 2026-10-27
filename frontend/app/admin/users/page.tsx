'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import { API_BASE } from '../../../lib/api';
import { useAuth } from '../../../lib/auth';
import type { User } from '../../../lib/types';

const ROLE_OPTIONS = [
  ['admin', 'Admin'],
  ['doctor', 'Doctor'],
  ['medical_officer', 'Medical officer'],
  ['clinical_officer', 'Clinical officer'],
  ['nurse', 'Nurse'],
  ['midwife', 'Midwife'],
  ['pharmacist', 'Pharmacist'],
  ['normal_user', 'Normal user'],
] as const;

export default function AdminUsers() {
  const { user, token, loading: authLoading } = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState<User[] | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [role, setRole] = useState<string>('doctor');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user || user.role !== 'admin' || !token) return;
    fetch(`${API_BASE}/api/auth/users`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((list) => {
        if (list) setUsers(list as User[]);
      })
      .catch(() => {});
  }, [user, token]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          email: email.trim(),
          password,
          full_name: fullName.trim() || undefined,
          role,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { detail?: unknown } | null;
        setError(
          body && typeof body.detail === 'string'
            ? body.detail
            : `Could not add the user (${res.status}).`,
        );
      } else {
        const created = (await res.json()) as User;
        setUsers((prev) => (prev ? [...prev, created] : [created]));
        setEmail('');
        setPassword('');
        setFullName('');
        setRole('doctor');
      }
    } catch {
      setError('Could not reach the server.');
    }
    setBusy(false);
  }

  if (authLoading || !user) return <p>Checking sign-in…</p>;

  if (user.role !== 'admin') {
    return (
      <div>
        <h1>Users</h1>
        <p>Admin access required.</p>
        <Link className="back-link" href="/">
          ← Back to patients
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1>Users</h1>

      <section className="panel">
        <h2>Add user</h2>
        <p className="muted">
          Only admins can add users. New staff sign in with these credentials on the login page.
        </p>
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Temporary password</label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="fullName">Full name</label>
            <input
              id="fullName"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="role">Role</label>
            <select id="role" value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLE_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          {error && <p className="error">{error}</p>}
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? 'Adding…' : 'Add user'}
          </button>
        </form>
      </section>

      {!users ? (
        <p>Loading users…</p>
      ) : (
        <>
          <p className="muted">{users.length} registered accounts.</p>
          <table className="data-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Name</th>
                <th>Role</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.email}</td>
                  <td>{u.full_name ?? '—'}</td>
                  <td>
                    <span className="badge">{u.role}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
