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

export default function PatientGuide() {
  return (
    <div>
      <h1>How to use your health portal</h1>
      <p className="muted">
        This portal shows your own record. It is read-only: you can look, but
        you cannot change anything. The clinic guide chat and Ask the doctor
        answers work in English, Kiswahili, and Luganda.
      </p>

      <Step n="1" title="Sign in">
        <p>
          Open <strong>Patient sign in</strong> and enter the email address on
          your clinic record. We email you a one-time code — enter it to see
          your record. The code expires after a few minutes; ask for a new one
          if it runs out. If the clinic has no email address for you, ask them
          to add one at your next visit.
        </p>
      </Step>

      <Step n="2" title="Read your visit summaries">
        <p>
          Each visit gets a short plain-language summary, once your doctor has
          reviewed and shared it. Until then it says{' '}
          <strong>Your doctor is preparing your summary.</strong> Use the
          language buttons to read in English, Kiswahili, or Luganda.
        </p>
      </Step>

      <Step n="3" title="Ask the clinic guide chat">
        <p>
          The <strong>clinic guide chat</strong> answers simple questions from
          your shared summaries and prescriptions: which clinic to visit for a
          concern, or what your medication note says (name, dose, timing as
          written). You can type or record a voice note in English, Kiswahili,
          or Luganda. It is not a doctor: it never diagnoses, never prescribes,
          and never changes your medicine. Anything it cannot answer from your
          record, it will send you to your doctor instead.
        </p>
      </Step>

      <Step n="4" title="In an emergency, do not wait here">
        <p>
          If you have danger signs — heavy bleeding, trouble breathing, chest
          pain, fainting, seizure, poisoning, a broken bone, labour, the worst
          headache of your life, or sudden vision loss — the chat will tell you
          to go to a health facility immediately. Do not wait for any other
          reply:
        </p>
        <ul>
          <li>
            What you describe can be an emergency. Go to the nearest health
            facility or emergency unit now — do not wait for a reply here.
          </li>
          <li>
            Dalili ulizoeleza zinaweza kuwa za dharura. Nenda kwenye kituo cha
            afya kilicho karibu nawe sasa hivi — usisubiri jibu hapa.
          </li>
          <li>
            Ebyo by&apos;ogambye biyinza okuba eby&apos;akabenje. Genda mangu ku
            ddwaliro erisinga okuba okumpi naawe — tolindirira kuddamu wano.
          </li>
        </ul>
      </Step>

      <Step n="5" title="Ask the doctor">
        <p>
          Under <strong>Ask the doctor</strong> you can send your clinic a
          question by text or voice note — for example to clarify your
          medication. A clinician reads it on your record and writes an answer,
          which appears here in the portal. If your record has an email
          address, we also email you a nudge to come and read it. Your question
          and the answer stay inside the portal; they are never emailed.
        </p>
      </Step>

      <Step n="6" title="Referral letters">
        <p>
          If your doctor refers you, the letter appears here. Open it and show
          it at the health facility you visit — even if it is not the one named
          on it.
        </p>
      </Step>

      <p>
        <Link className="back-link" href="/patient/me">
          ← Back to my record
        </Link>
      </p>
    </div>
  );
}
