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
        you cannot change anything. Ask the doctor answers arrive in English,
        Kiswahili, or Luganda.
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

      <Step n="3" title="Ask the doctor">
        <p>
          Under <strong>Ask the doctor</strong> you can send your clinic a
          question by text or voice note in English, Kiswahili, or Luganda —
          for example to clarify your medication. No computer answers you: a
          clinician reads every question and writes an answer, which appears
          here in the portal, in your language. If your record has an email
          address, we also email you a nudge to come and read it. Your
          question and the answer stay inside the portal; they are never
          emailed.
        </p>
        <p>
          In an emergency, do not wait for an answer. If you feel very unwell,
          have bleeding, chest pain, difficulty breathing, a seizure, or
          thoughts of harming yourself, go to the nearest health facility now:
        </p>
        <ul>
          <li>
            Your doctor will reply here, usually within a few days. If you feel
            very unwell, have bleeding, chest pain, difficulty breathing, a
            seizure, or thoughts of harming yourself, go to the nearest health
            facility now.
          </li>
          <li>
            Daktari wako atajibu hapa, kwa kawaida ndani ya siku chache. Ikiwa
            unajisikia vibaya sana, unavuja damu, una maumivu ya kifua,
            unapumua kwa shida, una kifafa, au una mawazo ya kujidhuru, nenda
            kwenye kituo cha afya kilicho karibu naawe sasa hivi.
          </li>
          <li>
            Musawo wo ajja kuddamu wano, ebiseera ebisinga mu nnaku ntono.
            Bw&apos;owulira obulwadde obw&apos;amaanyi, olugulu
            olw&apos;omusaayi, obulumi mu kifuba, obuzibu mu kussa, ekikolo, oba
            endowooza ez&apos;okwetta, genda ku ddwaliro erisinga okuba okumpi
            naawe kati.
          </li>
        </ul>
      </Step>

      <Step n="4" title="Referral letters">
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
