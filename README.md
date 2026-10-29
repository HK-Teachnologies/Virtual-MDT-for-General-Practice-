# Virtual MDT for General Practice

A virtual multidisciplinary team (MDT) for general practice: a medical officer at a
district hospital or Health Centre IV photographs or dictates a complex case, and an
AI agent prepares a structured, evidence-cited MDT brief — per-specialty concerns,
drug-interaction flags, overdue screening checks, and questions for referral —
which the clinician reviews, edits, and approves.

> **Clinician-facing decision support only.** This tool does not diagnose,
> prescribe, or advise patients. Every AI suggestion must be reviewed and signed
> off by a qualified clinician. Hackathon development uses **synthetic data only**
> — no real patient data.

Built for the **Build for Your World** track of the Meta Global AI Developer
Hackathon (26 Oct – 4 Nov 2026).

## How it works

1. **Capture** — Doctor photographs today's notes / patient-held books and dictates
   the consultation.
2. **Timeline** — AI structures the case and shows a short timeline of previous
   visits; the doctor corrects it.
3. **MDT review** — Doctor taps "Prepare MDT review". The agent selects relevant
   specialties (e.g. HIV care, TB, cardiology, endocrinology, pharmacy, mental
   health, nutrition), gathers cited evidence per specialty, and self-checks its
   draft for unsupported claims.
4. **Decision** — Doctor accepts, edits, or rejects each point, then manages the
   patient or refers with the brief attached.
5. Every item is marked **AI-suggested** or **clinician-approved** (audit trail).

Demo scenario: a 52-year-old on ART for HIV, with hypertension and diabetes,
presenting with a two-week cough. The agent flags TB screening, a possible
interaction to check if TB treatment starts, and an overdue kidney function test —
each with citation and certainty level.

## Specialist review workflow

After the brief is ready, the case can be sent to specialists for input:

1. **Prepare MDT review** — On the patient record, tap "Prepare MDT review".
   The agent plans, retrieves guideline evidence, drafts, and self-checks in a
   background job; the page polls until the brief lands. Reopening the record
   resumes the latest finished brief, so sign-off survives a reload.
2. **Sign off** — Approve, edit, or reject each point. Every change is saved
   server-side and badged `AI-suggested` → `clinician-approved` / `edited` /
   `rejected` (audit trail).
3. **Send for specialist review** — Tap "Send for specialist review". The
   specialties the brief is about come pre-ticked: everyone in a ticked
   specialty is notified, anyone can be unticked, and specific people can be
   hand-picked instead. Each recipient gets an email with a link that opens
   the review directly once signed in.
4. **Sent, not duplicated** — While a review is open (`pending`/`responded`),
   the patient page shows "Sent — waiting for review" with a link, and no new
   brief can be prepared. Close the review to start another round.
5. **Respond** — Specialists open it from Reviews → Assigned to me and reply
   in text, by voice recording (transcribed so it stays readable, and kept
   listenable), or with a photo attached. The requester is emailed on each
   response. Reviews the user sent live under Requested by me.
6. **Close** — The requester (or an admin) closes the review when the loop is
   complete. Reviews are never approved/rejected — they are responded to.

Admins manage the routing under Admin → Specialties (e.g. HIV care,
Cardiology, Pharmacy) and can delete a patient record in full (visits, files,
vectors, briefs, reviews, login codes) from the record page.

## Tech stack

| Layer    | Technology                                  |
|----------|---------------------------------------------|
| Frontend | Next.js (React)                             |
| Backend  | FastAPI (Python)                            |
| Database | PostgreSQL (pgvector-enabled for retrieval) |
| AI       | Meta Model API: Muse Spark (multimodal + agent), Muse Voice Transcribe; self-hosted Muse Spark Open option |
| Deploy   | Docker Compose + Caddy                      |

## Running on Muse Spark Open

The default agent model is Meta's hosted Muse Spark (`LLM_MODEL=openai/muse-spark-1.3`
via `LLM_API_BASE=https://api.meta.ai/v1`). To run the open-weight sibling instead,
point LiteLLM at an OpenAI-compatible endpoint serving `meta-models/muse-spark-open-1026`
(Baseten or Modal), keeping everything else identical:

```env
LLM_PROVIDER=litellm
LLM_API_BASE=<your Baseten or Modal OpenAI-compatible base URL>
LLM_API_KEY=<your Baseten or Modal API key>
LLM_MODEL=openai/meta-models/muse-spark-open-1026
LLM_TRANSCRIBE_MODEL=muse-voice-transcribe-1.0
```

Status: configured but **not yet verified end to end** — the hosted Muse Spark path is
the verified one. After one brief runs cleanly on the open model, confirm here.

## Repo layout

```text
frontend/                  Next.js app
backend/                   FastAPI app
deployment/docker-compose/ docker-compose.yaml, Caddyfile, .env (local only, never committed)
Virtual MDT for General Practice - Concept Note.docx  Original concept note
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
```

## Backend API

Users and auth (FastAPI, served same-origin under `/api` in compose):

- `POST /api/auth/register` — `{email, password, full_name?}` → 201 + user
- `POST /api/auth/login` — form `username` (= email) + `password` → `{access_token}`
- `GET /api/auth/me` — Bearer token → current user
- `GET /api/health` — liveness check

Backend settings come from `deployment/docker-compose/.env` (see `.env.example`):
`SECRET_KEY` signs the login tokens — set a long random value, never commit it.

## Safety and scope

- Clinician-facing only; questions and flagged concerns, not verdicts.
- Every point carries an evidence-source badge (MoH guideline / patient record /
  clinical reasoning) and links to its cited guideline page; the agent's
  self-check removes unsupported claims and keeps an audit of what it removed.
- Synthetic data only during the hackathon.
- Future deployment must follow Uganda's Data Protection and Privacy Act, 2019;
  the self-hosted open-weight option keeps data in-country.

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
- [ ] Referral letter generation (bonus)
- [ ] Patient follow-up in Luganda / Swahili / English (future, not in hackathon build)

## Contributing

Issues and pull requests are welcome. Please keep all test data synthetic and
never commit secrets (`.env` files) or patient-like data.

## License

MIT — see [LICENSE](LICENSE).
