'use client';

import Link from 'next/link';

function Step({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <h2>
        {n}. {title}
      </h2>
      {children}
    </section>
  );
}

export default function Guide() {
  return (
    <div>
      <h1>User guide</h1>
      <p className="muted">
        How to use Virtual MDT, from registering a patient to closing a specialist review.
      </p>

      <Step n="1" title="Register a patient">
        <p>
          Open <strong>Patients</strong> and tap <strong>Register a new patient</strong>. Fill
          in at least the full name; phone or email is needed if the patient should sign
          in to the portal later. Sex, district, area of residence, and date of birth help
          the AI brief. Open the patient card to start their record.
        </p>
      </Step>

      <Step n="2" title="Capture a visit">
        <p>
          In <strong>Capture today&apos;s case</strong>, set the visit date (change it for
          past records) and pick the clinic that classifies the record. Then capture any
          combination:
        </p>
        <ul>
          <li>
            <strong>Record dictation</strong> — press to record, press Stop to attach. The
            AI transcribes it for your verification after saving.
          </li>
          <li>
            <strong>Take a photo</strong> — opens the camera on a phone for handwritten
            notes, lab slips, or patient-held books.
          </li>
          <li>
            <strong>Upload files</strong> — PDFs, documents, or audio from storage.
          </li>
          <li>
            <strong>Notes</strong> — type directly, with or without attachments.
          </li>
        </ul>
        <p>
          After saving, every machine read (transcription or extracted text) appears under
          the visit with a <strong>Verify</strong> action — confirm or correct it so the
          record stays trustworthy. Use <strong>+ Add lab / imaging / note</strong> on any
          visit card to append standard sections later.
        </p>
      </Step>

      <Step n="3" title="Prepare the MDT review">
        <p>
          Tap <strong>Prepare MDT review</strong>. The agent plans specialties, retrieves
          past history and guideline evidence, drafts the brief, and self-checks it. This
          runs in the background — the page polls until the brief lands.
        </p>
      </Step>

      <Step n="4" title="Sign off the brief">
        <p>
          Each point shows its citation and certainty. <strong>Approve</strong>,
          <strong> Edit</strong>, or <strong>Reject</strong> every point; each decision is
          saved and badged (an approved button locks to avoid double sign-off).{' '}
          <strong>Copy referral summary</strong> copies a handover note.
        </p>
      </Step>

      <Step n="5" title="Send for specialist review">
        <p>
          Tap <strong>Send for specialist review</strong>. Specialties from the brief come
          pre-ticked: everyone in a ticked specialty is emailed a link; untick anyone to
          exclude them, or pick specific people instead. While a review is open the record
          shows <strong>Sent — waiting for review</strong> and no new brief can be
          prepared.
        </p>
      </Step>

      <Step n="6" title="Respond and close">
        <p>
          Specialists open assigned reviews from <strong>Reviews → Assigned to me</strong>{' '}
          and reply in text, by voice (transcribed and kept listenable), or with a photo.
          Reviews you sent live under <strong>Requested by me</strong>. The requester or
          an admin <strong>closes</strong> the review when done — reviews are responded
          to, never approved or rejected.
        </p>
      </Step>

      <Step n="7" title="Admin tasks">
        <ul>
          <li>
            <strong>Users</strong> — only admins create accounts and edit email, role, or
            password.
          </li>
          <li>
            <strong>Specialties</strong> — create routing groups (e.g. HIV care,
            Cardiology, Pharmacy) and assign members; these drive review notifications.
          </li>
          <li>
            <strong>Clinics</strong> — the classification list for visit records.
          </li>
          <li>
            <strong>Guidelines</strong> — upload PDF clinical guidelines; watch indexing
            to <strong>ready</strong> and use <strong>Retry indexing</strong> if one
            fails. Only ready, active editions feed the brief.
          </li>
          <li>
            <strong>Patients</strong> — admins can delete a record in full (visits,
            files, briefs, reviews, login codes) from the record page after confirmation.
          </li>
        </ul>
      </Step>

      <Step n="8" title="Patient portal">
        <p>
          Patients sign in separately at <strong>Patient sign in</strong> with their email
          or phone number plus a one-time code. The portal is read-only: they can view
          their record but not change it.
        </p>
        <p>
          Each visit automatically gets a draft plain-language summary in English,
          Kiswahili, and Luganda — no review needs to run first. Patients only ever
          see text a clinician has reviewed and released; anything still in draft
          shows <strong>Your doctor is preparing your summary.</strong>
        </p>
      </Step>

      <Step n="9" title="Release summaries to the patient">
        <p>
          On the patient record, every visit card carries a <strong>Patient
          summary</strong> panel: read the draft in English, open the Kiswahili and
          Luganda versions, edit any language, then tap <strong>Release to
          patient</strong>. The portal labels it <strong>Reviewed and shared by Dr.
          [your name] on [date]</strong>. Editing or regenerating a released summary
          returns it to draft.
        </p>
        <p>
          After signing off the brief, tap <strong>Prepare patient summary</strong>
          below it: the overall message is drafted from approved and edited points
          only — suggested and rejected points, interactions, and overdue checks are
          never included — for the same edit-and-release.
        </p>
        <p>
          Doctors can also send follow-up questions from the patient record,
          which the patient answers by text or voice note in the portal.
        </p>
      </Step>

      <p>
        <Link className="back-link" href="/">
          ← Back to patients
        </Link>
      </p>
    </div>
  );
}
