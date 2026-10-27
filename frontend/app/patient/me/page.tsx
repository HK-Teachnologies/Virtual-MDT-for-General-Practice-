'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import VisitCard from '../../../components/VisitCard';
import type { ApiPatient } from '../../../lib/types';
import { clearPatientToken, fetchOwnRecord, getPatientToken } from '../../../lib/patient-auth';

export default function PatientPortal() {
  const router = useRouter();
  const [record, setRecord] = useState<ApiPatient | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const token = getPatientToken();
    if (!token) {
      setFailed(true);
      return;
    }
    fetchOwnRecord(token).then((rec) => {
      if (!rec) {
        clearPatientToken();
        setFailed(true);
        return;
      }
      setRecord(rec);
    });
  }, []);

  function signOut() {
    clearPatientToken();
    router.replace('/patient/login');
  }

  if (failed) {
    return (
      <div>
        <h1>My record</h1>
        <p>
          Please <Link href="/patient/login">sign in with a one-time code</Link> to view
          your record.
        </p>
      </div>
    );
  }

  if (!record) return <p>Loading your record…</p>;

  return (
    <div>
      <h1>My record</h1>
      <p className="muted">
        {[record.full_name, record.phone, record.district].filter(Boolean).join(' · ')}
      </p>
      <section className="panel">
        <h2>Visit history</h2>
        {record.visits.length === 0 ? (
          <p className="muted">No visits recorded yet.</p>
        ) : (
          [...record.visits]
            .sort((a, b) => b.visit_date.localeCompare(a.visit_date))
            .map((v) => (
              <VisitCard key={v.id} patientId={record.id} visit={v} token={null} readOnly />
            ))
        )}
      </section>
      <button className="btn" type="button" onClick={signOut}>
        Sign out
      </button>
    </div>
  );
}
