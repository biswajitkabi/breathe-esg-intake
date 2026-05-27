# Tradeoffs

Three things deliberately not built, and why.

---

## 1. Role-Based Access Control (RBAC)

**What was skipped:**
The User model has a role field (ADMIN / ANALYST / VIEWER) but
permission checks are not enforced on API endpoints. Any
authenticated user can approve, reject, or upload.

**Why:**
Implementing correct RBAC requires careful thought about the
permission matrix — can a VIEWER trigger uploads? Can an ANALYST
lock records? These rules belong in a product conversation, not
assumed in a prototype. Building fake RBAC with wrong rules would
be worse than none, because it creates a false sense of security
and would need to be torn out anyway.

**What production needs:**
Django REST Framework permission classes per endpoint, tied to
the user's role and tenant. Possibly Django Guardian for
object-level permissions if analysts should only see their
own uploaded batches.

---

## 2. Emission Factor Versioning and Custom Factors

**What was skipped:**
Emission factors are hardcoded constants in the parser files.
There is no database table for factors, no version history, and
no way for a client to supply their own supplier-specific factor.

**Why:**
Emission factor management is a domain problem that deserves its
own data model and UI. Getting it wrong — for example, applying
a 2023 factor to 2021 historical data — produces incorrect
reported emissions. Rather than build a half-baked factor system,
we use clearly labelled DEFRA 2023 constants and store the factor
string on each EmissionRecord so the computation is always
traceable.

**What production needs:**
An EmissionFactor table versioned by (category, region, year,
source), a factor selection algorithm that picks the right factor
for a given record's date and location, and a UI for clients to
upload custom supplier factors with documentation.

---

## 3. Scheduled / Automated Ingestion

**What was skipped:**
All ingestion is manual file upload. There is no scheduler,
no SFTP polling, no webhook receiver, and no Concur OAuth flow.

**Why:**
Automated ingestion requires infrastructure decisions (Celery +
Redis, or Django-Q, or a cloud scheduler) that go beyond a 4-day
prototype scope. More importantly, the trigger and delivery
mechanism varies per client — one client emails a CSV, another
drops files on an SFTP server, a third has a live Concur OAuth
token. Building one automation without knowing the client's actual
delivery mechanism would produce throwaway code.

**What production needs:**
A pluggable ingestion trigger system — SFTP poller, email
attachment parser, webhook endpoint, and OAuth-based API pull —
all feeding into the same parse → normalize → review pipeline
we have built. The pipeline itself is already decoupled from
the trigger, so adding automated triggers is additive, not a
rewrite.