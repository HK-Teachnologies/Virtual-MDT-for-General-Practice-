'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { getPatients } from '../lib/api';
import { useAuth } from '../lib/auth';
import type { Patient } from '../lib/types';

export default function Home() {
  const { user, token, loading: authLoading } = useAuth();
  const router = useRouter();
  const [patients, setPatients] = useState<Patient[] | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (user) getPatients(token ?? undefined).then(setPatients);
  }, [user, token]);

  if (authLoading || !user) return <p>Checking sign-in…</p>;
  if (!patients) return <p>Loading patients…</p>;

  return (
    <div>
      <h1>Patients</h1>
      <p className="muted">
        Synthetic demo data only — no real patient data. Select a patient to capture today&apos;s
        case and prepare an MDT review.
      </p>
      <div className="card-grid">
        {patients.map((p) => (
          <Link key={p.id} className="card" href={`/patients/${p.id}`}>
            <h2>{p.name}</h2>
            <p>
              {p.age} years · {p.sex}
            </p>
            <p>{p.conditions.join(' · ')}</p>
            <p className="muted">{p.visits.length} visits on record</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
