'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent } from 'react';
import { createPatient, getPatients } from '../lib/api';
import { useAuth } from '../lib/auth';
import type { ApiPatient } from '../lib/types';

export default function Home() {
  const { user, token, loading: authLoading } = useAuth();
  const router = useRouter();
  const [patients, setPatients] = useState<ApiPatient[] | null>(null);
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [sex, setSex] = useState('');
  const [district, setDistrict] = useState('');
  const [address, setAddress] = useState('');
  const [dob, setDob] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (user && token) getPatients(token).then(setPatients);
  }, [user, token]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!token || !fullName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createPatient(token, {
        full_name: fullName.trim(),
        phone: phone.trim() || undefined,
        email: email.trim() || undefined,
        sex: sex || undefined,
        district: district.trim() || undefined,
        address: address.trim() || undefined,
        date_of_birth: dob || undefined,
      });
      setPatients((prev) => (prev ? [created, ...prev] : [created]));
      setFullName('');
      setPhone('');
      setEmail('');
      setSex('');
      setDistrict('');
      setAddress('');
      setDob('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not register the patient.');
    }
    setBusy(false);
  }

  if (authLoading || !user) return <p>Checking sign-in…</p>;

  return (
    <div>
      <h1>Patients</h1>
      <p className="muted">
        Register a patient, then open their record to capture visits, photos, and notes.
      </p>

      <section className="panel">
        <h2>Register patient</h2>
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="fullName">Full name</label>
            <input
              id="fullName"
              type="text"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="phone">Phone</label>
            <input
              id="phone"
              type="text"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="email">Email (for one-time-code sign-in)</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="sex">Sex</label>
            <select id="sex" value={sex} onChange={(e) => setSex(e.target.value)}>
              <option value="">Select…</option>
              <option value="Male">Male</option>
              <option value="Female">Female</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="district">District</label>
            <input
              id="district"
              type="text"
              placeholder="e.g. Wakiso"
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="address">Area of residence (village / parish)</label>
            <input
              id="address"
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="dob">Date of birth</label>
            <input
              id="dob"
              type="date"
              value={dob}
              onChange={(e) => setDob(e.target.value)}
            />
          </div>
          {error && <p className="error">{error}</p>}
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? 'Registering…' : 'Register patient'}
          </button>
        </form>
      </section>

      {!patients ? (
        <p>Loading patients…</p>
      ) : patients.length === 0 ? (
        <p className="muted">No patients registered yet.</p>
      ) : (
        <div className="card-grid">
          {patients.map((p) => (
            <Link key={p.id} className="card" href={`/patients/${p.id}`}>
              <h2>{p.full_name}</h2>
              <p>{p.phone ?? 'No phone on record'}</p>
              <p>{p.email ?? 'No email on record'}</p>
              <p>{p.district ?? 'No district on record'}</p>
              <p className="muted">{p.visits.length} visits on record</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
