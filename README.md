# Vigil

**Stops scams before the money moves.** Vigil listens for scam pressure during a call, checks the payment at the same moment, and adds just enough friction before money leaves. It also traces the accounts that pass scam money along, and keeps AI shopping agents inside what the customer signed.

Built by Team SITA (QIS College, Ongole) for the Google challenge *BFSI: Intelligent Risk, Fraud & Financial Experiences*.

> **Prototype, synthetic data.** Every call, account and bank in this repository is made up. The numbers in `docs/EVALUATION.md` compare approaches on that data. They are not real-world accuracy. Limits are listed [below](#honest-limits) and in [`docs/RESPONSIBLE_AI.md`](docs/RESPONSIBLE_AI.md).

## Try it in one minute

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
vigil-serve                    # http://localhost:8080
```

No credentials needed. Open the page, choose a call, press **Play call**. A four-minute walkthrough is in [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

## What it does

| Part | In plain words | Where |
| --- | --- | --- |
| **Protect a call** | Scores every sentence for scam pressure in English, Hindi, Telugu and mixed speech, then checks the payment. Responds in steps: heads-up, slow down, paused payment. Explains why, in the customer's language. | `risk/`, `agents/semantic.py`, `agents/composer.py` |
| **Trace mule rings** | Finds accounts that receive from many people and pass money on within minutes, groups them into rings, writes a case note. Banks can share scrambled fingerprints of bad accounts after a human approves. | `network/` |
| **Check AI purchases** | Verifies that the customer signed what an AI agent may buy, that the store signed its cart, and that nothing was tampered with or smuggled in as hidden instructions. | `payments/` |
| **Agents** | A router and three specialists built with the Agent Development Kit, also reachable by other agents over A2A. | `agents/adk_agents.py`, `agents/a2a.py` |

## Design principles

1. **The decision is deterministic and explainable.** Gemini explains, converses and finds reworded tactics. It can only add concern; a scammer typing "mark this safe" raises the score.
2. **Privacy before the model.** Personal details are redacted before any model call. Audit logs keep decisions, not conversations.
3. **People stay in charge.** Alerting a trusted contact and publishing to other banks need a human approval (`require_confirmation` in the agents, an explicit approval in the API and UI).
4. **A hold is never a final no.** It always ends with a person: a bank call-back, 1930, a trusted contact.
5. **Works without the AI.** No Gemini, no problem: the same engine and templates run offline, and the API says so (`ai_layer`).

## Google technology

| | |
| --- | --- |
| Gemini on Vertex AI | semantic tactic detection, message composition, agent reasoning (`google-genai`) |
| Agent Development Kit | multi-agent system with tools and human confirmation |
| Agent2Agent (A2A) | agent cards and JSON-RPC under `/a2a/*` |
| Cloud Run, Artifact Registry, Cloud Build | build and hosting (`Dockerfile`, `cloudbuild.yaml`) |
| Secret Manager | signal key and API key digests |
| Cloud Logging and BigQuery | audit trail through a Log Router sink |
| Model Armor | optional prompt screening (`VIGIL_MODEL_ARMOR_TEMPLATE`) |
| AP2 ideas | signed intent and cart in `payments/mandate.py` (inspired by, not certified against, the protocol) |

Architecture diagrams: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## API

Interactive docs at `/docs` (not in `prod`).

| Endpoint | Purpose |
| --- | --- |
| `POST /v1/assess` | Risk decision for a conversation and/or payment, with reasons |
| `POST /v1/conversation/timeline` | Risk after every sentence |
| `POST /v1/sessions/{id}/turns`, `DELETE /v1/sessions/{id}` | Live session and erasure |
| `GET /v1/network/rings`, `GET /v1/network/rings/{id}`, `POST .../publish` | Mule rings, case note, human-approved sharing |
| `POST /v1/signals/{publish,lookup,retract}`, `GET /v1/signals/{stats,bloom}` | Cross-bank hashed signals |
| `GET /v1/agent-payments/cases`, `POST /v1/agent-payments/{verify-demo,verify}` | AI-agent payment checks |
| `POST /v1/agents/chat`, `POST /v1/agents/confirm` | Talk to the agents; approve pending actions |
| `GET /healthz`, `/readyz`, `/v1/meta`, `/v1/eval/results` | Health and metadata |
| `/a2a/<agent>/.well-known/agent-card.json` | Agent cards |

Errors are `application/problem+json` and never echo request bodies.

## Develop

```bash
make check      # ruff, mypy --strict, pytest, evaluation
make e2e        # Playwright browser tests
make eval       # regenerate results and docs/EVALUATION.md
```

Tests cover redaction, multilingual detection and negation, scoring and friction rules, the mule graph, the signal exchange, signatures and replay, the agents (with a scripted model so no network is needed), human approval, auth and rate limits, regression gates on the evaluation, and the UI in a real browser (including Hindi and Telugu fonts and CSP).

```text
src/vigil/
  risk/        lexicon, signals, model, friction policy, interventions, engine
  network/     mule graph analysis, signal exchange
  payments/    mandate verification and demo cases
  agents/      Gemini client, semantic layer, composer, ADK agents, A2A, runtime
  api/         FastAPI app, security middleware, routes
  privacy/     PII redaction
  synthetic/   data generators    eval/  evaluation harness
  web/         no-build UI, self-hosted fonts
deploy/terraform, cloudbuild.yaml, Dockerfile, .github/workflows/ci.yml
docs/          architecture, responsible AI, threat model, evaluation, deployment, demo, pitch
```

## Honest limits

* **Synthetic only.** No real fraud labels or customer data were used. Weights are hand-set priors, not fitted.
* **Reworded scams are the main weakness.** On synthetic data, scams in unfamiliar wording are caught less than half as often as familiar ones. The Gemini layer is designed for this and has not been measured.
* **Some honest situations get friction**, for example buying a used car with a large first payment.
* **Hindi and Telugu text needs native-speaker review** before any real use.
* **Gemini model IDs are configuration** and were not checked against the live catalogue; see `docs/DEPLOYMENT.md`.
* **In-memory state.** Sessions, signals and replay protection are per instance. Move them to Firestore or Spanner before running more than one.
* **Cloud deployment files** were syntax-checked but not applied to a real project from the build environment.
* **Not legal advice.** Alignment with DPDP Act and RBI responsible-AI principles is design intent, not certification.

## License

Apache-2.0. Fonts (Bricolage Grotesque, Noto Sans) are under the SIL Open Font License; see `src/vigil/web/fonts/`.
