# Deployment

Two ways to run Vigil: on your laptop (nothing external needed), or on Google Cloud Run.

> **Status of this guide.** The local path and the container's start-up were tested. The Terraform and Cloud Build files were written and syntax-checked but **not applied to a real project** from the authoring environment (no Terraform binary or Docker daemon was available). Run `terraform validate` and a first deploy in a scratch project before relying on them.

## 1. Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make serve            # http://localhost:8080  (reload on)
# or: vigil-serve
```

No credentials are needed. Without Gemini the guardian uses the rule engine and templates, and the UI says so at the top of the page.

Useful checks:

```bash
make check            # lint, types, tests, evaluation
make e2e              # browser tests (needs: python -m playwright install chromium)
```

## 2. Turn on Gemini (optional)

Vigil calls Gemini through `google-genai` and ADK. On Vertex AI with Application Default Credentials:

```bash
export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT=<project>
export GOOGLE_CLOUD_LOCATION=global
export VIGIL_LLM_ENABLED=true
```

Or with a Gemini API key: `export GOOGLE_API_KEY=<key>` and leave `GOOGLE_GENAI_USE_VERTEXAI` unset.

**Check the model IDs first.** Defaults are in `config.py` and can be overridden without code changes:

| Variable | Used for | Default |
| --- | --- | --- |
| `VIGIL_MODEL_REASONING` | guardian and investigator agents | `gemini-3.5-flash` |
| `VIGIL_MODEL_FAST` | router, payment guard, semantic layer, composer | `gemini-3.1-flash-lite` |
| `VIGIL_MODEL_LIVE` | reserved for streaming voice | `gemini-3.1-flash-live-preview` |

These IDs came from the installed SDKs at build time and were not verified against the live model catalogue. List the models available to your project and set the variables to IDs you can actually call.

Optional prompt screening with Model Armor: create a template in your project following the Model Armor documentation, then set `VIGIL_MODEL_ARMOR_TEMPLATE` to its full resource name.

## 3. Deploy to Cloud Run

Prerequisites: a project with billing, `gcloud` and `terraform` installed, and `gcloud auth application-default login`.

```bash
cd deploy/terraform
cp terraform.tfvars.example terraform.tfvars   # edit project_id, env, public_access
terraform init
terraform apply
```

This creates the Artifact Registry repository, a least-privilege runtime service account, Secret Manager secrets (a generated signal key and your API key digests), a Cloud Run service with health probes, and a BigQuery dataset plus Log Router sink for the audit trail. Then build and deploy the image:

```bash
cd ../..
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_REGION=asia-south1,_ENV=demo,_LLM_ENABLED=false
```

### Environments

| `VIGIL_ENV` | Meant for | Behaviour |
| --- | --- | --- |
| `dev` | laptops | Open routes, API docs on. |
| `demo` | a public showcase | Open routes, synthetic data only, rate limits on. Set `public_access = true` in Terraform to allow unauthenticated calls. |
| `prod` | real institutions | **Refuses to start** without `VIGIL_AUTH_MODE=apikey`, `VIGIL_API_KEYS`, and a non-default `VIGIL_SIGNAL_KEY`. API docs are off. |

### API keys

Store only digests. Generate a key and its digest:

```bash
python -c "import secrets,hashlib; k=secrets.token_urlsafe(32); print('key   ', k); print('digest', hashlib.sha256(k.encode()).hexdigest())"
```

Give the key to the institution; put the digest in `api_key_digests` (comma-separated for several). Each key identifies one institution, and that identity is what the signal exchange records as the reporter. Rotate by adding a new digest, switching the client, then removing the old one.

### Settings reference

| Variable | Default | Meaning |
| --- | --- | --- |
| `VIGIL_ENV` | `dev` | `dev`, `demo` or `prod` |
| `VIGIL_AUTH_MODE` | `demo` | `demo` or `apikey` (required in prod) |
| `VIGIL_API_KEYS` | empty | SHA-256 digests, comma-separated |
| `VIGIL_RATE_LIMIT_PER_MIN` | 120 | Per caller and IP, per instance |
| `VIGIL_MAX_BODY_BYTES` | 256000 | Request size limit |
| `VIGIL_TRUSTED_PROXY_HOPS` | 0 | Set 1 on Cloud Run so the client IP is read correctly |
| `VIGIL_SIGNAL_KEY` | dev key | Base64 consortium HMAC key (32+ bytes) |
| `VIGIL_SIGNAL_MIN_REPORTERS` | 2 | Banks needed to confirm a payee |
| `VIGIL_SIGNAL_TTL_DAYS` | 30 | Signal lifetime |
| `VIGIL_LLM_ENABLED` | false | Use Gemini for the semantic layer, composer and agents |
| `VIGIL_LLM_TIMEOUT_S` | 8 | Per-call model timeout |
| `VIGIL_PUBLIC_BASE_URL` | `http://localhost:8080` | Written into A2A agent cards |
| `VIGIL_A2A_ENABLED` | true | Serve `/a2a/*` |
| `VIGIL_CORS_ORIGINS` | empty | Comma-separated allowed origins |

## 4. Operate

**Health.** `/healthz` (liveness) and `/readyz` (readiness) are public. Cloud Run uses them as probes.

**Audit trail.** Decisions are logged on the `vigil.audit` logger with caller, tier, score, scam type, phase, and whether the AI layer was used. Never the transcript, payee or amount. The Log Router sink writes them to `vigil_audit` in BigQuery. Inspect the table schema first, then adapt a query such as:

```sql
-- Example only: confirm column names in your table before running.
SELECT jsonPayload.tier AS tier, COUNT(*) AS decisions
FROM `PROJECT.vigil_audit.run_googleapis_com_stdout_*`
WHERE jsonPayload.logger = 'vigil.audit' AND jsonPayload.message = 'assess'
GROUP BY tier;
```

**Scaling.** Sessions, the signal store, replay state and the demo graph are per instance and in memory. For more than one instance, move them to Firestore or Spanner first (see `ARCHITECTURE.md`). Until then keep `max-instances` low and treat the deployment as a demo.

**Rollback.** Redeploy a previous image tag: `gcloud run deploy vigil --image <repo>/vigil:<sha>`.

## 5. Calling the API

```bash
curl -s https://<service>/v1/assess -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d '{
  "profile": {"user_id": "u1", "preferred_language": "hi"},
  "transcript": [{"speaker": "caller", "text": "Aapka KYC expire ho gaya, OTP bataiye", "t": 0}]
}'
```

Interactive API docs are at `/docs` in `dev` and `demo`. Agent cards for other agents are at `/a2a/<guardian|investigator|payment_guard|vigil>/.well-known/agent-card.json` (they require the API key in `prod`).
