'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import CaptureForm from '../../../components/CaptureForm';
import MdtBriefView from '../../../components/MdtBriefView';
import VisitTimeline from '../../../components/VisitTimeline';
import { getBrief, getPatient } from '../../../lib/api';
import { useAuth } from '../../../lib/auth';
import type { MdtBrief, Patient, Visit } from '../../../lib/types';

export default function PatientRecord() {
  const params = useParams();
  const router = useRouter();
  const { user, token, loading: authLoading } = useAuth();
  const id = params.id;
  const [patient, setPatient] = useState<Patient | null>(null);
  const [visits, setVisits] = useState<Visit[]>([]);
  const [brief, setBrief] = useState<MdtBrief | null>(null);
  const [loadingBrief, setLoadingBrief] = useState(false);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!id || Array.isArray(id) || !user) return;
    getPatient(id, token ?? undefined).then((p) => {
      if (!p) {
        setMissing(true);
        return;
      }
      setPatient(p);
      setVisits(p.visits);
    });
  }, [id, user, token]);

  async function prepareReview() {
    if (!id || Array.isArray(id)) return;
    setLoadingBrief(true);
    setBrief(await getBrief(id, token ?? undefined));
    setLoadingBrief(false);
  }

  if (authLoading || !user) {
    return <p>Checking sign-in…</p>;
  }

  if (missing) {
    return (
      <div>
        <p>Patient not found.</p>
        <Link className="back-link" href="/">
          ← Back to patients
        </Link>
      </div>
    );
  }

  if (!patient) return <p>Loading patient…</p>;

  return (
    <div>
      <Link className="back-link" href="/">
        ← Back to patients
      </Link>
      <h1>{patient.name}</h1>
      <p className="muted">
        {patient.age} years · {patient.sex}
      </p>

      <section className="panel">
        <h2>Known conditions</h2>
        <p>{patient.conditions.join(' · ')}</p>
        <h2>Current medications</h2>
        <ul>
          {patient.medications.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <h2>Visit timeline</h2>
        <VisitTimeline visits={visits} />
      </section>

      <section className="panel">
        <h2>Capture today&apos;s case</h2>
        <CaptureForm onAdd={(v) => setVisits((prev) => [...prev, v])} />
      </section>

      <section className="panel">
        <h2>MDT review</h2>
        {!brief ? (
          <div>
            <p className="muted">
              The agent reviews the case and past visits, selects relevant specialties, and drafts
              an evidence-cited brief for your sign-off.
            </p>
            <button className="btn btn-primary" type="button" onClick={prepareReview} disabled={loadingBrief}>
              {loadingBrief ? 'Preparing review…' : 'Prepare MDT review'}
            </button>
          </div>
        ) : (
          <MdtBriefView brief={brief} />
        )}
      </section>
    </div>
  );
}
