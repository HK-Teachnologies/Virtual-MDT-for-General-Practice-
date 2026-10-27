'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import { API_BASE } from '../../lib/api';
import { useAuth } from '../../lib/auth';

const FIELDS = ['specialty', 'facility', 'license_number', 'phone', 'bio'] as const;
type Field = (typeof FIELDS)[number];

const LABELS: Record<Field, string> = {
  specialty: 'Specialty',
  facility: 'Facility',
  license_number: 'License / registration number',
  phone: 'Phone',
  bio: 'Bio',
};

export default function Profile() {
  const { user, token, loading: authLoading } = useAuth();
  const router = useRouter();
  const [values, setValues] = useState<Record<Field, string>>({
    specialty: '',
    facility: '',
    license_number: '',
    phone: '',
    bio: '',
  });
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user || !token) return;
    fetch(`${API_BASE}/api/profile/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((profile) => {
        if (!profile) return;
        setValues({
          specialty: profile.specialty ?? '',
          facility: profile.facility ?? '',
          license_number: profile.license_number ?? '',
          phone: profile.phone ?? '',
          bio: profile.bio ?? '',
        });
      })
      .catch(() => {});
  }, [user, token]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE}/api/profile/me`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(values),
      });
      setStatus(res.ok ? 'Profile saved.' : 'Could not save the profile.');
    } catch {
      setStatus('Could not reach the server.');
    }
    setBusy(false);
  }

  if (authLoading || !user) return <p>Checking sign-in…</p>;

  return (
    <div>
      <h1>My profile</h1>
      <p className="muted">
        Signed in as {user.email} <span className="badge">{user.role}</span>
      </p>
      <form className="panel" onSubmit={submit}>
        {FIELDS.map((field) => (
          <div className="field" key={field}>
            <label htmlFor={field}>{LABELS[field]}</label>
            {field === 'bio' ? (
              <textarea
                id={field}
                rows={3}
                value={values[field]}
                onChange={(e) => setValues({ ...values, [field]: e.target.value })}
              />
            ) : (
              <input
                id={field}
                type="text"
                value={values[field]}
                onChange={(e) => setValues({ ...values, [field]: e.target.value })}
              />
            )}
          </div>
        ))}
        {status && <p>{status}</p>}
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save profile'}
        </button>
      </form>
    </div>
  );
}
