# Virtual Multidisciplinary Team (MDT) for General Practice

A specialist team for every doctor, in every patient's language.

🎬 Demo video: [YouTube link]
🌍 Live app: https://virtualmdt.hk-technologies.net

> **Clinician-facing decision support only.** This tool does not diagnose,
> prescribe, or advise patients. Every AI suggestion must be reviewed and signed
> off by a qualified clinician. Hackathon development uses **synthetic data only**
> — no real patient data.

## Why this matters

Uganda has about one licensed doctor for every 6,400 people, concentrated in
urban areas ([UMDPC figures via Nile Post, Aug
2026](https://allafrica.com/stories/202608180128.html)).
Medical officers at district hospitals and HC IVs — and interns on night
duty — manage patients with HIV, diabetes and hypertension alone. Records are
on paper, and many patients speak Luganda or Kiswahili.

## Team

- Dr. Rugogoma Jesse  clinical lead, Makerere University College of Health Sciences (MakCHS)
- Kawesi Hakim  product and build lead

## What makes it different

- It reads handwritten notes: slips and patient-held books are photographed
  and transcribed, and every machine read waits for staff verification.
- A self-checking agent cites Ministry of Health guideline pages, with page
  numbers verified in code — unsupported points are removed with reasons kept
  visible.
- A full Luganda/Kiswahili voice loop: patients dictate, doctors answer, and
  the doctor checks every translation before sending.
- There is no AI chat answering patients: patients see only what a doctor has
  released, and a clinician answers every question.

## How it works

1. **Capture** — The medical officer (or intern on night duty) photographs
   today's handwritten notes / patient-held books, dictates, uploads files, or
   types — including lab, imaging, and vitals sections on any visit.
2. **Verify the reads** — Every photo and recording gets an AI read shown as
   *AI read — verify*; staff confirm or correct each one, and the visit
   auto-refreshes as reads and summaries land.
3. **MDT review** — "Prepare MDT review": the agent selects relevant
   specialties, gathers cited guideline evidence per specialty, and self-checks
   its draft for unsupported claims.
4. **Sign off** — The doctor approves, edits, or rejects each point. Every
   item is marked **AI-suggested** or **clinician-approved** (audit trail).
5. **Specialist or supervisor review** — The case is sent for review by email
   link (text/voice/photo replies); interns reach their supervising doctor
   through a Supervisor specialty.
6. **Referral letter** — A deterministic letter drafted from signed-off points
   only, released for the patient to present at any facility.
7. **Patient portal** — Released visit summaries and the overall message in
   English, Kiswahili, and Luganda, plus Ask the doctor: patients ask in
   their own language and a clinician answers every one.

## Demo case: Teopista Namubiru

Teopista Namubiru, 61, from Mukono, lives with HIV (on TDF/3TC/DTG), diabetes
and hypertension, and speaks Luganda only. Her brief flags dolutegravir
raising metformin levels, and tenofovir alongside a creatinine that has
nearly doubled.

![MDT brief for a synthetic patient: sourced points, safety panels, and the self-check audit](docs/brief-hero.png)

## Built during the hackathon

- Everything in this repository was built during the hackathon; first commit
  27 Oct 2026.
- Built for the **Build for Your World** track of the Meta Global AI Developer
  Hackathon (26 Oct – 4 Nov 2026).
- One repository: Next.js frontend, FastAPI backend, self-hosted
  embedding/rerank server, Docker Compose + Caddy deploy.

## Clinical guidelines

Guideline PDFs are uploaded by an admin (Admin → Guidelines) and are **not**
shipped in this repo. Editions used for the demo:

- Uganda Clinical Guidelines 2023
- Consolidated Guidelines for the Prevention and Treatment of HIV and AIDS in
  Uganda 2022
- Practical Guideline for Dispensing at Lower Level Health Centres 2014

Guidelines uploaded before page-aware indexing need one **Reindex** (Admin →
Guidelines → Reindex) so brief citations carry verified page numbers.

## Testing

87 backend tests, all passing. Backend runs on the echo provider — no keys, no
network, tasks run inline:

```bash
cd backend
python -m pytest tests -q
```

Frontend has no test harness; type-check with `npx tsc --noEmit` from `frontend/`.

## Where the AI models are used

Every AI call in this app goes to Meta's models or to the self-hosted
retrieval server — Muse Spark (briefs, summaries, vision reads, translations),
Muse Voice Transcribe (all dictation and voice notes), and the local
embedding/rerank server. No third-party AI vendor ever sees patient content:
there is no browser or phone-vendor speech recognition anywhere in the app
(the old live-dictation path was removed for exactly this reason), and no
OpenAI/Google endpoints. All model access goes through one OpenAI-compatible
client (`backend/app/llm/client.py`, LiteLLM), so endpoints stay swappable
without touching features. `LLM_PROVIDER=echo` returns deterministic canned
output for the test suite — no keys, no network.

| Capability | Model | Notes |
|---|---|---|
| Brief plan, draft, self-check | Muse Spark (`LLM_MODEL`, default `openai/muse-spark-1.3`) | JSON-mode calls in `mdt.run_brief`; prompts in `backend/app/llm/prompts.py` |
| Photo reads | Muse Spark vision (`LLM_VISION_MODEL`, falls back to `LLM_MODEL`) | Transcribes slips and books; every read needs staff verification |
| Dictation and voice notes | Muse Voice Transcribe (`LLM_TRANSCRIBE_MODEL`, default `muse-voice-transcribe-1.0`) | Consults in English as-is; patient answers in Luganda/Kiswahili/English become English text with the original kept |
| Visit and patient summaries, question/answer translation | Muse Spark | Trilingual summaries; overall message from signed-off points only; answer drafts machine-translated for the doctor to check and edit |
| Embeddings | bge-base-en-v1.5 on the self-hosted `model_server/` (or `LLM_EMBED_MODEL` via API) | Patient and guideline vectors; `LLM_EMBED_DIM` must match (768) |
| Guideline reranking | ms-marco-MiniLM-L-6-v2 cross-encoder on `model_server/` | Top 4 of 20 candidates per query; falls back to vector order if down |
| Deterministic, no model | — | Referral letters, PDF/text extraction, PII redaction |

## How information flows

1. **Capture** — typed notes, visit sections, and files land on a visit
   (`POST /api/patients/{id}/visits`, sections, `…/visits/{visit_id}/attachments`).
2. **Machine reads** — `mdt.transcribe_attachment` reads each file (vision for
   photos, speech-to-text for audio — the audio is then deleted and never
   served, deterministic parse for PDF/TXT/MD) into a transcription shown as
   *AI read — verify* until staff confirm or correct it.
3. **Index and summarize** — `mdt.embed_patient_chunks` embeds notes, sections,
   and reads into per-patient vectors; `mdt.summarize_visit` drafts the
   trilingual visit summary. Any later content resets it to draft.
4. **Review** — `mdt.run_brief`: plan (specialties chosen only from the Admin
   list) → retrieve (patient vectors plus guideline vectors, cross-encoder
   rerank) → draft → self-check (unsupported points removed with reasons kept
   visible). Prompts carry de-identified text only: age, never date of birth;
   names, phones, and emails redacted — photograph clinical content, not name
   labels, since redaction cannot clean image pixels.
5. **Sign-off** — approve / edit / reject is persisted per item; only
   approved/edited wording flows downstream.
6. **Send, refer, release** — specialist reviews by email link; deterministic
   referral letters whose history includes photo and dictation reads; and the
   release gates that publish summaries and letters to the patient portal.

Steps 2–4 run as Celery tasks (Redis queue, `worker` service in compose).
Without a running worker nothing after capture processes — run one locally
(see below) or set `CELERY_TASK_ALWAYS_EAGER=1` for inline execution.

## Specialist review workflow

After the brief is ready, the case can be sent to specialists for input:

1. **Prepare MDT review** — On the patient record, tap "Prepare MDT review".
   The agent plans (choosing only from the specialties configured under
   Admin → Specialties, so the brief's specialties match review routing),
   retrieves patient history plus guideline evidence (wide vector net re-ranked
   by the cross-encoder), drafts, and self-checks in a background job; the page
   polls until the brief lands. Reopening the record resumes the latest finished
   brief, so sign-off survives a reload.
2. **Sign off** — Approve, edit, or reject each point. Every change is saved
   server-side and badged `AI-suggested` → `clinician-approved` / `edited` /
   `rejected` (audit trail). Points carry the specialty's question for the
   doctor, an `Urgent` flag when same-day action is needed, and a footer naming
   the model and prompt (`Prepared by Muse Spark 1.3 · prompt v2`). Points the
   self-check dropped are kept visible under a collapsed
   `Removed by self-check (n)` audit list with the reason for each — they can
   never be signed off or sent to specialists.
3. **Send for specialist review** — Tap "Send for specialist review". The
   specialties the brief is about come pre-ticked: everyone in a ticked
   specialty is notified, anyone can be unticked, and specific people can be
   hand-picked instead. Each recipient gets an email with a link that opens
   the review directly once signed in. Interns can send a case to their
   supervising doctor by adding a Supervisor specialty in Admin → Specialties.
4. **Sent, not duplicated** — While a review is open (`pending`/`responded`),
   the patient page shows "Sent - waiting for review" with a link, and no new
   brief can be prepared. Close the review to start another round.
5. **Respond** — Specialists open it from Reviews → Assigned to me and reply
   in text, by voice recording (transcribed; the audio itself is never kept
   or served), or with a photo attached. The requester is emailed on each
   response. Reviews the user sent live under Requested by me.
6. **Close** — The requester (or an admin) closes the review when the loop is
   complete. Reviews are never approved/rejected — they are responded to.

Admins manage the routing under Admin → Specialties (e.g. HIV care,
Cardiology, Pharmacy) and can delete a patient record in full (visits, files,
vectors, briefs, reviews, login codes) from the record page.

## Patient portal and clinician release

AI-written text reaches patients only through a clinician release gate —
every summary starts as `draft` and the portal serves `released` ones:

1. **Visit summaries** — Recording a visit drafts a plain-language line in
   English, Kiswahili, and Luganda (decided items only: tests ordered,
   medicines continued, return date — never suspected or ruled-out
   conditions). Regenerating a released summary returns it to draft.
2. **Review and release** — On the patient record, each visit card shows its
   draft summary in English with the Kiswahili and Luganda versions one tap
   away. The doctor edits any language, then taps **Release to patient**; the
   portal labels it `Reviewed and shared by Dr. [name] on [date]`.
3. **Overall message** — After signing off the brief, the doctor taps
   **Prepare patient summary**: the worker drafts the overall message from
   approved/edited points only (suggested and rejected points, interactions,
   and overdue checks are never included), for the same edit-and-release.
4. **Portal** — Patients sign in with a one-time code and see only released
   text. Anything still in draft shows `Your doctor is preparing your
   summary.` Reading the portal never generates or publishes anything.
   Visits recorded before the gate existed are queued with
   `docker compose exec backend python backfill_visit_summaries.py` —
   they land as drafts for review, never published directly.
5. **Referral letters** — After sign-off, the doctor drafts a referral letter
   from the approved/edited points only (deterministic text, no model call):
   demographics, recent history (including photo and dictation machine reads,
   tagged verified or unverified), agreed findings, flagged interactions,
   overdue checks, and the reason. Each letter is released like a summary and
   appears in the portal, so the patient can present it at any facility they
   end up attending — even a different hospital than intended.

## Tech stack

| Layer    | Technology                                  |
|----------|---------------------------------------------|
| Frontend | Next.js (React)                             |
| Backend  | FastAPI (Python)                            |
| Database | PostgreSQL (pgvector-enabled for retrieval) |
| AI       | Meta Model API: Muse Spark (multimodal + agent), Muse Voice Transcribe |
| Retrieval| Self-hosted model server: bge-base embeddings + MiniLM cross-encoder rerank |
| Queue    | Redis + Celery (transcription, indexing, summaries, briefs) |
| Deploy   | Docker Compose + Caddy (same-origin: `/api/*` → backend, rest → frontend) |

## Repo layout

```text
frontend/                  Next.js app
backend/                   FastAPI app
deployment/docker-compose/ docker-compose.yaml, Caddyfile, .env (local only, never committed)
model_server/              local embedding + rerank server (sentence-transformers)
docs/demo-cases.md         synthetic demo cases (Teopista Namubiru is the hero case)
```

## Getting started

### Prerequisites

- Node.js 20+, Python 3.11+, Docker + Docker Compose
- A Meta Model API key (`META_API_KEY`)

### 1. Configure environment

```bash
cp deployment/docker-compose/.env.example deployment/docker-compose/.env
# then edit .env and set your real META_API_KEY (never commit this file)
```

### 2. Run with Docker Compose

```bash
cd deployment/docker-compose
docker compose up --build
```

### 3. Run services individually (dev)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev

# Background worker (new terminal — needs Redis running; transcriptions,
# summaries, and briefs only process with this running, otherwise set
# CELERY_TASK_ALWAYS_EAGER=1 on the API process for inline execution)
cd backend
celery -A app.mdt.tasks.celery_app worker --loglevel=info
```

> Frontend dev runs on another port than the API, so set
> `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` (or your backend origin) before
> `npm run dev` — otherwise the browser cannot reach the backend. Compose does
> not need this (same-origin under Caddy).

## Backend API

Users and auth (FastAPI, served same-origin under `/api` in compose):

- `POST /api/auth/register` — `{email, password, full_name?}` → 201 + user
- `POST /api/auth/login` — form `username` (= email) + `password` → `{access_token}`
- `GET /api/auth/me` — Bearer token → current user
- `GET /api/health` — liveness check

Backend settings come from `deployment/docker-compose/.env` (see `.env.example`):
`SECRET_KEY` signs the login tokens — set a long random value, never commit it.

Patient records and result sections:

- `POST /api/patients/{patient_id}/visits/{visit_id}/sections` — `{section, content}` → typed lab/imaging/vitals/note entry
- `POST /api/patients/visits/{visit_id}/attachments` — multipart `files` → photo/dictation/document attached to an existing visit (same AI read as capture)
- `DELETE /api/patients/visits/{visit_id}` — removes a visit with its sections, files, and reads
- `GET /api/patients` and `GET /api/patients/{id}` — carry `open_review_count` and `unverified_read_count` triage signals

## Safety and scope

- Clinician-facing only; questions and flagged concerns, not verdicts.
- Patients only ever see text a clinician has reviewed and released.
- Every point carries an evidence-source badge (MoH guideline / patient record /
  clinical reasoning) and links to its cited guideline page; the agent's
  self-check removes unsupported claims and keeps an audit of what it removed.
- Synthetic data only during the hackathon.

### Data protection

- **De-identified by design.** Names, dates of birth, phone numbers and email
  addresses never leave the database towards the AI model: the case summary
  carries age (not date of birth), and every staff-typed note, visit section
  and machine-read transcript is stripped of the patient's own identifiers
  plus any other email or phone-like number before it is sent. Clinical
  content (dates, BP readings, lab values) is preserved.
- **Known limit — labelled photos.** A photograph of a labelled lab slip or
  patient-held book can expose a name to the vision model in the image pixels,
  which text redaction cannot remove. Photograph the clinical content, not the
  name label, wherever possible.
- **Local first.** Embeddings and reranking run on the self-hosted model
  server, so patient text stays inside the deployment for retrieval; only the
  de-identified case text and evidence excerpts go to the Meta Model API for
  planning, drafting, self-check, vision reads and transcription.
- **Meta models only — no third-party AI vendors.** Every model call lands on
  Meta's API or the self-hosted retrieval server. Patient audio is never sent
  to a browser or phone-vendor speech API: the Add Result Dictate button
  records locally and posts the clip to Meta's transcription model, which
  returns text for editing.
- **Voice is transcription fuel only.** Clinicians dictate in English and are
  transcribed as-is; patient voice notes (English, Luganda, or Kiswahili) are
  transcribed to English text. The audio file is deleted once transcription
  succeeds and is never served to any user — text is what travels on slow
  connections. The original-language transcript is kept next to the English
  so bilingual staff can check the translation.
- **Access control.** Staff sign in with passwords (admin-managed accounts);
  patients use a separate OTP login that sees only their own record. Review
  links require sign-in.
- Future deployment must follow Uganda's Data Protection and Privacy Act, 2019.

## Roadmap

- [x] Concept note and demo scenario
- [x] Case capture (photo + dictation → structured record + timeline)
- [x] MDT agent (specialty selection, evidence retrieval, self-check)
- [x] Brief screen with approve / edit / reject flow (persisted server-side)
- [x] Specialist reviews (specialty routing, email links, text/voice/photo
      responses, pending → responded → closed, no-duplicate gate)
- [x] Guideline library (PDF upload, async indexing with retry, RAG citations)
  - Guidelines uploaded before page-aware indexing need one **Reindex** (Admin →
    Guidelines → Reindex) so brief citations carry verified page numbers.
- [x] Referral letter generation (bonus) — drafted from signed-off points,
      released like a summary, carried by the patient to any facility
- [x] Patient follow-up in Luganda / Swahili / English — staff questions
      auto-translated for the portal; answers by text or voice note

## Contributing

Issues and pull requests are welcome. Please keep all test data synthetic and
never commit secrets (`.env` files) or patient-like data.

## License

MIT — see [LICENSE](LICENSE).
