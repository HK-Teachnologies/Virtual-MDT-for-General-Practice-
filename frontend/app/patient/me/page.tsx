'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import PatientQuestions from '../../../components/PatientQuestions';
import PatientSummary, { type SummaryLang } from '../../../components/PatientSummary';
import type { ApiFollowUp, ApiPatient, MySummary } from '../../../lib/types';
import {
  clearPatientToken,
  fetchMyQuestions,
  fetchMySummary,
  fetchOwnRecord,
  getPatientToken,
} from '../../../lib/patient-auth';

export default function PatientPortal() {
  const router = useRouter();
  const [record, setRecord] = useState<ApiPatient | null>(null);
  const [summary, setSummary] = useState<MySummary | undefined>(undefined);
  const [questions, setQuestions] = useState<ApiFollowUp[] | undefined>(undefined);
  const [lang, setLang] = useState<SummaryLang>('en');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const token = getPatientToken();
    if (!token) {
      setFailed(true);
      return;
    }
    Promise.all([fetchOwnRecord(token), fetchMySummary(token), fetchMyQuestions(token)])
      .then(([rec, sum, qs]) => {
        if (!rec) {
          clearPatientToken();
          setFailed(true);
          return;
        }
        setRecord(rec);
        setSummary(sum ?? undefined);
        setQuestions(qs ?? []);
      })
      .catch(() => setFailed(true));
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

  if (!record || summary === undefined || questions === undefined) {
    return <p>Loading your record…</p>;
  }

  return (
    <div>
      <h1>My record</h1>
      <p className="muted">
        {[record.full_name, record.phone, record.district].filter(Boolean).join(' · ')}
      </p>
      <PatientSummary
        summary={summary}
        visits={summary.visits ?? []}
        recordVisits={record.visits}
        lang={lang}
        onLang={setLang}
      />
      {(summary.referral_letters ?? []).length > 0 && (
        <section className="panel">
          <h2>Referral letters</h2>
          <p className="muted">
            Show this letter at the health facility you visit — even if it is
            not the one named below.
          </p>
          {(summary.referral_letters ?? []).map((l) => (
            <div key={l.id} className="brief-item">
              <div className="brief-item-head">
                <strong>To {l.destination_facility}</strong>
              </div>
              <p className="muted">{l.reason}</p>
              <pre className="letter-preview">{l.letter_text}</pre>
            </div>
          ))}
        </section>
      )}
      <PatientQuestions initial={questions} lang={lang} />
      <button className="btn" type="button" onClick={signOut}>
        Sign out
      </button>
    </div>
  );
}
