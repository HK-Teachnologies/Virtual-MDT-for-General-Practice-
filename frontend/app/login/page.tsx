'use client';

import Link from 'next/link';
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
    <div className="login-split">
      <form className="login-form" onSubmit={submit}>
        <h1>Virtual Multidisciplinary Team (MDT)</h1>
        <p className="muted">
          A specialist team for every doctor, in every patient&apos;s language.
        </p>
        <h2>Sign in</h2>
        <p className="muted">Use your Virtual MDT account.</p>
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
        <p className="muted">
          Are you a patient? <Link href="/patient/login">Sign in with a one-time code</Link>
        </p>
      </form>
      <div className="login-side">
        <img
          src="/login-side.jpg"
          alt="Ugandan medical officer reviewing a patient case on a tablet"
        />
      </div>
    </div>
  );
}
