'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import CaptureForm from '../../../components/CaptureForm';
import MdtBriefView from '../../../components/MdtBriefView';
import ReviewSendDialog from '../../../components/ReviewSendDialog';
import VisitCard from '../../../components/VisitCard';
import {
  deletePatient,
  getBriefRun,
  getOpenReviews,
  getPatient,
  listBriefRuns,
  requestBriefRun,
  signOffBriefItem,
} from '../../../lib/api';
import { useAuth } from '../../../lib/auth';
import type {
  ApiBriefItem,
  ApiBriefRun,
  ApiPatient,
  ApiReview,
  ApiVisit,
  BriefItem,
  Certainty,
  ItemStatus,
  MdtBrief,
} from '../../../lib/types';

function toCertainty(value: string): Certainty {
  return value === 'high' || value === 'moderate' || value === 'low' ? value : 'low';
}

function toStatus(value: string): ItemStatus {
  return value === 'approved' || value === 'rejected' || value === 'edited' ? value : 'suggested';
}

function runToBrief(patientId: string, run: ApiBriefRun): MdtBrief {
  return {
    patientId,
    specialties: run.specialties,
    items: run.items.map((i: ApiBriefItem) => ({
      id: i.id,
      specialty: i.specialty,
      concern: i.status === 'edited' && i.edited_text ? i.edited_text : i.concern,
      citation: i.citation,
      certainty: toCertainty(i.certainty),
      status: toStatus(i.status),
    })),
    interactions: [],
    overdueChecks: [],
    generatedAt: new Date().toISOString(),
  };
}

export default function PatientRecord() {
  const params = useParams();
  const router = useRouter();
  const { user, token, loading: authLoading } = useAuth();
  const id = params.id;
  const [patient, setPatient] = useState<ApiPatient | null>(null);
  const [brief, setBrief] = useState<MdtBrief | null>(null);
  const [briefRunId, setBriefRunId] = useState<string | null>(null);
  const [briefStep, setBriefStep] = useState('');
  const [briefError, setBriefError] = useState<string | null>(null);
  const [loadingBrief, setLoadingBrief] = useState(false);
  const [missing, setMissing] = useState(false);
  const [sending, setSending] = useState<BriefItem[] | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [openReviews, setOpenReviews] = useState<ApiReview[] | null>(null);

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
    getOpenReviews(token, Array.isArray(id) ? id[0] : id)
      .then(setOpenReviews)
      .catch(() => setOpenReviews([]));
    // Resume the latest finished brief so sign-off survives a reload.
    listBriefRuns(token, Array.isArray(id) ? id[0] : id)
      .then((runs) => {
        const ready = runs.find((r) => r.status === 'ready');
        if (ready) {
          setBriefRunId(ready.id);
          setBrief(runToBrief(Array.isArray(id) ? id[0] : (id as string), ready));
        }
      })
      .catch(() => {});
  }, [id, user, token]);

  function refreshOpenReviews() {
    if (!id || Array.isArray(id) || !token) return;
    getOpenReviews(token, id)
      .then(setOpenReviews)
      .catch(() => {});
  }

  async function pollRun(runId: string, auth: string, pid: string) {
    // The agent plans, retrieves, drafts, and self-checks in the worker —
    // usually under a minute. Poll until it lands or fails.
    for (let i = 0; i < 100; i++) {
      await new Promise((r) => setTimeout(r, 3000));
      let run: ApiBriefRun;
      try {
        run = await getBriefRun(auth, runId);
      } catch {
        continue;
      }
      if (run.status === 'ready') {
        setBriefRunId(run.id);
        setBrief(runToBrief(pid, run));
        setLoadingBrief(false);
        return;
      }
      if (run.status === 'failed') {
        setBriefError(run.error || 'The agent could not prepare a review.');
        setLoadingBrief(false);
        return;
      }
      setBriefStep(run.current_step || 'Working…');
    }
    setBriefError('The agent is taking too long — try again.');
    setLoadingBrief(false);
  }

  async function prepareReview() {
    if (!id || Array.isArray(id) || !token) return;
    setLoadingBrief(true);
    setBriefError(null);
    setBriefStep('Queued…');
    setBrief(null);
    setBriefRunId(null);
    try {
      const run = await requestBriefRun(token, id);
      if (run.status === 'ready') {
        setBriefRunId(run.id);
        setBrief(runToBrief(id, run));
        setLoadingBrief(false);
        return;
      }
      setBriefStep(run.current_step || 'Queued…');
      await pollRun(run.id, token, id);
    } catch (e) {
      setBriefError(e instanceof Error ? e.message : 'Could not prepare a review.');
      setLoadingBrief(false);
    }
  }

  async function persistSignOff(itemId: string, status: BriefItem['status'], editedText?: string) {
    if (!token) throw new Error('Not signed in.');
    await signOffBriefItem(token, itemId, { status, edited_text: editedText });
  }

  async function removePatient() {
    if (!patient || !token) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deletePatient(token, patient.id);
      router.replace('/');
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : 'Could not delete this patient.');
      setDeleting(false);
      setConfirmingDelete(false);
    }
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
      {user.role === 'admin' && (
        <div className="row">
          {!confirmingDelete ? (
            <button className="btn" type="button" onClick={() => setConfirmingDelete(true)}>
              Delete patient
            </button>
          ) : (
            <>
              <span>
                Delete {patient.full_name} and every visit, file, brief, and review? This
                cannot be undone.
              </span>
              <button
                className="btn btn-danger"
                type="button"
                onClick={removePatient}
                disabled={deleting}
              >
                {deleting ? 'Deleting…' : 'Yes, delete everything'}
              </button>
              <button
                className="btn"
                type="button"
                onClick={() => setConfirmingDelete(false)}
                disabled={deleting}
              >
                Keep
              </button>
            </>
          )}
        </div>
      )}
      {deleteError && <p className="error">{deleteError}</p>}

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
        {openReviews === null ? (
          <p className="muted">Checking for open reviews…</p>
        ) : openReviews.length > 0 ? (
          <div>
            {openReviews.map((r) => (
              <div key={r.id} className="row review-card-head">
                <span>
                  <span className={`badge badge-${r.status}`}>
                    {r.status === 'pending' ? 'Sent — waiting for review' : r.status}
                  </span>{' '}
                  {r.message || 'Review sent to specialists'}{' '}
                  <span className="muted">
                    ({r.response_count} response{r.response_count === 1 ? '' : 's'})
                  </span>
                </span>
                <Link className="btn" href={`/reviews/${r.id}`}>
                  Open review
                </Link>
              </div>
            ))}
            <p className="muted">
              Close the open review before preparing a new one.
            </p>
          </div>
        ) : !brief ? (
          <div>
            <p className="muted">
              The agent reviews the case and past visits, selects relevant specialties, and drafts
              an evidence-cited brief for your sign-off.
            </p>
            {briefError && <p className="error">{briefError}</p>}
            <button className="btn btn-primary" type="button" onClick={prepareReview} disabled={loadingBrief}>
              {loadingBrief ? (briefStep || 'Preparing review…') : 'Prepare MDT review'}
            </button>
          </div>
        ) : sending ? (
          <ReviewSendDialog
            patientId={patient.id}
            brief={brief}
            items={sending}
            token={token}
            onClose={() => {
              setSending(null);
              refreshOpenReviews();
            }}
          />
        ) : (
          <MdtBriefView
            key={briefRunId ?? 'brief'}
            brief={brief}
            onSend={(items) => setSending(items)}
            persistItem={persistSignOff}
          />
        )}
      </section>
    </div>
  );
}
