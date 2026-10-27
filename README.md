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

## Tech stack

| Layer    | Technology                                  |
|----------|---------------------------------------------|
| Frontend | Next.js (React)                             |
| Backend  | FastAPI (Python)                            |
| Database | PostgreSQL (pgvector-enabled for retrieval) |
| AI       | Meta Model API: Muse Spark (multimodal + agent), Muse Voice Transcribe; self-hosted Muse Spark Open option |
| Deploy   | Docker Compose + Caddy                      |

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

## Safety and scope

- Clinician-facing only; questions and flagged concerns, not verdicts.
- Every point links to its guideline/study with a certainty level; the agent's
  self-check removes unsupported claims.
- Synthetic data only during the hackathon.
- Future deployment must follow Uganda's Data Protection and Privacy Act, 2019;
  the self-hosted open-weight option keeps data in-country.

## Roadmap

- [x] Concept note and demo scenario
- [ ] Case capture (photo + dictation → structured record + timeline)
- [ ] MDT agent (specialty selection, evidence retrieval, self-check)
- [ ] Brief screen with approve / edit / reject flow
- [ ] Referral letter generation (bonus)
- [ ] Patient follow-up in Luganda / Swahili / English (future, not in hackathon build)

## Contributing

Issues and pull requests are welcome. Please keep all test data synthetic and
never commit secrets (`.env` files) or patient-like data.

## License

MIT — see [LICENSE](LICENSE).
