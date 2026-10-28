'use client';

import Link from 'next/link';
import { useAuth } from '../../lib/auth';

export default function About() {
  const { token } = useAuth();
  return (
    <div>
      <h1>About Virtual MDT</h1>
      <p>
        Virtual MDT for General Practice lets a medical officer at a district hospital or
        Health Centre IV get a multidisciplinary review of a complex patient in minutes —
        without a specialist on site.
      </p>

      <section className="panel">
        <h2>How it works</h2>
        <ol>
          <li>
            <strong>Capture</strong> — the doctor photographs today&apos;s notes and dictates
            the consultation.
          </li>
          <li>
            <strong>Timeline</strong> — the case is structured alongside previous visits, which
            the doctor corrects.
          </li>
          <li>
            <strong>MDT review</strong> — the agent selects relevant specialties, gathers
            cited evidence for each, and self-checks its draft for unsupported claims.
          </li>
          <li>
            <strong>Decision</strong> — the doctor accepts, edits, or rejects each point, then
            manages the patient or refers with the brief attached.
          </li>
        </ol>
      </section>

      <section className="panel">
        <h2>Safety</h2>
        <p>
          Clinician-facing decision support only. The tool does not diagnose, prescribe, or
          advise patients — every AI suggestion must be reviewed and signed off by a
          qualified clinician, and each item is marked AI-suggested or clinician-approved.
        </p>
        <p className="muted">Demo data is synthetic. No real patient data is used.</p>
      </section>

      <p>
        {token ? (
          <Link className="btn btn-primary" href="/">
            Go to patients
          </Link>
        ) : (
          <Link className="btn btn-primary" href="/login">
            Sign in
          </Link>
        )}
      </p>
    </div>
  );
}
