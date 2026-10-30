'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import PatientAskDoctor from '../../../components/PatientAskDoctor';
import PatientQuestions from '../../../components/PatientQuestions';
import PatientSummary, { type SummaryLang } from '../../../components/PatientSummary';
import type {
  ApiFollowUp,
  ApiPatient,
  ApiPatientQuestion,
  MySummary,
} from '../../../lib/types';
import {
  clearPatientToken,
  fetchMyAskedQuestions,
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
  const [asked, setAsked] = useState<ApiPatientQuestion[] | undefined>(undefined);
  const [lang, setLang] = useState<SummaryLang>('en');
  const [failed, setFailed] = useState(false);
  const [hasToken, setHasToken] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const token = getPatientToken();
    if (!token) {
      setHasToken(false);
      setFailed(true);
      return;
    }
    // Keep the token: a failed load may be a blip, an expired code, or the
    // server being unreachable — only an explicit sign-out clears it, so a
    // valid sign-in is never destroyed by a bad connection.
    setHasToken(true);
    Promise.all([
      fetchOwnRecord(token),
      fetchMySummary(token),
      fetchMyQuestions(token),
      fetchMyAskedQuestions(token),
    ])
      .then(([rec, sum, qs, mine]) => {
        if (!rec) {
          setFailed(true);
          return;
        }
        setRecord(rec);
        setSummary(sum ?? undefined);
        setQuestions(qs ?? []);
        setAsked(mine ?? []);
      })
      .catch(() => setFailed(true));
  }, [attempt]);

  function signOut() {
    clearPatientToken();
    router.replace('/patient/login');
  }

  if (failed) {
    return (
      <div>
        <h1>My record</h1>
        {hasToken ? (
          <>
            <p>
              We couldn&apos;t open your record. Check your connection and try
              again — or sign out and sign in with a fresh code.
            </p>
            <div className="row">
              <button
                className="btn btn-primary"
                type="button"
                onClick={() => {
                  setFailed(false);
                  setAttempt((a) => a + 1);
                }}
              >
                Try again
              </button>
              <button className="btn" type="button" onClick={signOut}>
                Sign out
              </button>
            </div>
          </>
        ) : (
          <>
            <p>
              Please <Link href="/patient/login">sign in with a one-time code</Link> to
              view your record.
            </p>
            <p>
              <Link href="/patient/guide">How to use this portal</Link>
            </p>
          </>
        )}
      </div>
    );
  }

  if (!record || summary === undefined || questions === undefined || asked === undefined) {
    return <p>Loading your record…</p>;
  }

  return (
    <div>
      <h1>My record</h1>
      <p className="muted">
        {[record.full_name, record.phone, record.district].filter(Boolean).join(' · ')}
      </p>
      <p>
        <Link href="/patient/guide">How to use this portal</Link>
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
      <PatientAskDoctor initial={asked} lang={lang} />
      <button className="btn" type="button" onClick={signOut}>
        Sign out
      </button>
    </div>
  );
}
