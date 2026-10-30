'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import { getPatientToken, requestOtp, verifyOtp } from '../../../lib/patient-auth';

export default function PatientLogin() {
  const router = useRouter();
  const [step, setStep] = useState<'identifier' | 'code'>('identifier');
  const [identifier, setIdentifier] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (getPatientToken()) router.replace('/patient/me');
  }, [router]);

  async function sendCode(e: FormEvent) {
    e.preventDefault();
    if (!identifier.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await requestOtp(identifier.trim());
      setStep('code');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send the code.');
    }
    setBusy(false);
  }

  async function signIn(e: FormEvent) {
    e.preventDefault();
    if (!code.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await verifyOtp(identifier.trim(), code.trim());
      router.replace('/patient/me');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed.');
    }
    setBusy(false);
  }

  return (
    <div className="login-split">
      <div className="login-form">
        <h1>Patient sign in</h1>
        {step === 'identifier' ? (
          <form onSubmit={sendCode}>
            <p className="muted">
              Enter the email address or phone number on your record. We will send
              you a one-time code.
            </p>
            <div className="field">
              <label htmlFor="identifier">Email or phone</label>
              <input
                id="identifier"
                type="text"
                required
                autoComplete="username"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
              />
            </div>
            {error && <p className="error">{error}</p>}
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? 'Sending…' : 'Send code'}
            </button>
          </form>
        ) : (
          <form onSubmit={signIn}>
            <p className="muted">
              We sent a 6-digit code to the email on your record. It expires in 10 minutes.
            </p>
            <div className="field">
              <label htmlFor="code">One-time code</label>
              <input
                id="code"
                type="text"
                required
                inputMode="numeric"
                autoComplete="one-time-code"
                placeholder="e.g. 743590"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </div>
            {error && <p className="error">{error}</p>}
            <div className="row">
              <button className="btn btn-primary" type="submit" disabled={busy}>
                {busy ? 'Signing in…' : 'Sign in'}
              </button>
              <button
                className="btn"
                type="button"
                onClick={() => {
                  setStep('identifier');
                  setError(null);
                }}
              >
                Use a different address
              </button>
            </div>
          </form>
        )}
        <p className="muted">
          <Link href="/patient/guide">How to use this portal</Link>
        </p>
        <p className="muted">
          Staff? <Link href="/login">Sign in here</Link>
        </p>
      </div>
      <div className="login-side">
        <img
          src="/login-side.jpg"
          alt="Ugandan medical officer reviewing a patient case on a tablet"
        />
      </div>
    </div>
  );
}
