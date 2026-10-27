'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import { useAuth } from '../../lib/auth';

export default function Login() {
  const { user, loading, login, error } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace('/');
  }, [loading, user, router]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    const ok = await login(email.trim(), password);
    setBusy(false);
    if (ok) router.replace('/');
  }

  if (loading) return <p>Checking sign-in…</p>;

  return (
    <form className="auth-form panel" onSubmit={submit}>
      <h1>Sign in</h1>
      <p className="muted">
        Use your Virtual MDT account. The demo admin account comes from the backend&apos;s
        <code> ADMIN_EMAIL / ADMIN_PASSWORD</code>.
      </p>
      <div className="field">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          required
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      {error && <p className="error">{error}</p>}
      <button className="btn btn-primary" type="submit" disabled={busy}>
        {busy ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  );
}
