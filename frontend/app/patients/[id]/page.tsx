'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import CaptureForm from '../../../components/CaptureForm';
import MdtBriefView from '../../../components/MdtBriefView';
import VisitCard from '../../../components/VisitCard';
import { getBrief, getPatient } from '../../../lib/api';
import { useAuth } from '../../../lib/auth';
import type { ApiPatient, ApiVisit, MdtBrief } from '../../../lib/types';

export default function PatientRecord() {
  const params = useParams();
  const router = useRouter();
  const { user, token, loading: authLoading } = useAuth();
  const id = params.id;
  const [patient, setPatient] = useState<ApiPatient | null>(null);
  const [brief, setBrief] = useState<MdtBrief | null>(null);
  const [loadingBrief, setLoadingBrief] = useState(false);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/login');
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!id || Array.isArray(id) || !user || !token) return;
    getPatient(id, token).then((p) => {
      if (!p) {
        setMissing(true);
        return;
      }
      setPatient(p);
    });
  }, [id, user, token]);

  async function prepareReview() {
    if (!id || Array.isArray(id)) return;
    setLoadingBrief(true);
    setBrief(await getBrief(id));
    setLoadingBrief(false);
  }

  if (authLoading || !user || !token) {
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
      <h1>{patient.full_name}</h1>
      <p className="muted">
        {[
          patient.phone,
          patient.email,
          patient.district,
          patient.date_of_birth,
          patient.sex,
        ]
          .filter(Boolean)
          .join(' · ') || 'No contact details on record'}
      </p>

      <section className="panel">
        <h2>Visit timeline</h2>
        {patient.visits.length === 0 ? (
          <p className="muted">No visits recorded yet.</p>
        ) : (
          [...patient.visits]
            .sort((a, b) => b.visit_date.localeCompare(a.visit_date))
            .map((v: ApiVisit) => (
              <VisitCard
                key={v.id}
                patientId={patient.id}
                visit={v}
                token={token}
                onChange={(updated) =>
                  setPatient({
                    ...patient,
                    visits: patient.visits.map((old) =>
                      old.id === updated.id ? updated : old,
                    ),
                  })
                }
              />
            ))
        )}
      </section>

      <section className="panel">
        <h2>Capture today&apos;s case</h2>
        <CaptureForm
          patientId={patient.id}
          token={token}
          onAdded={(v) => setPatient({ ...patient, visits: [v, ...patient.visits] })}
        />
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
