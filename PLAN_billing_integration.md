# AgenikPredict: Billing Integration Plan

**Created**: 2026-03-16
**Model**: 2-day free trial → pay-per-report (token-based)
**Billing service**: `agenikai-billing` (existing, Node.js + Postgres + Stripe)
**Status**: Plan ready, execution pending

---

## Architecture

```
AgenikPredict (Railway)          agenikai-billing (Railway)
Flask + Vue                      Node.js + Postgres + Stripe
┌──────────────────┐             ┌──────────────────────┐
│ LLM Client       │────────────>│ POST /v1/usage/pre   │
│ (token counting) │             │ Pre-authorize cost    │
│                  │             │                       │
│ Report Agent     │────────────>│ POST /v1/usage/settle │
│ (after gen done) │             │ Record actual usage   │
│                  │             │                       │
│ Auth middleware   │────────────>│ GET /v1/users/{id}    │
│ (check balance)  │             │ Balance + trial check │
│                  │             │                       │
│ Vue Frontend     │────────────>│ GET /v1/usage/summary │
│ (usage display)  │             │ Usage history         │
│                  │             │                       │
│ Vue Frontend     │────────────>│ POST /v1/stripe/...   │
│ (top-up button)  │             │ Checkout session      │
└──────────────────┘             └──────────────────────┘
```

---

## Phase A: Token Counting in LLM Client

**Goal**: Extract token usage from every LLM call

### Files to modify

**`backend/app/utils/llm_client.py`** — modify `chat()` method:

Current (discards usage):
```python
response = self.client.chat.completions.create(...)
return response.choices[0].message.content
```

New (returns content + usage):
```python
response = self.client.chat.completions.create(...)
content = response.choices[0].message.content
usage = {
    'prompt_tokens': getattr(response.usage, 'prompt_tokens', 0),
    'completion_tokens': getattr(response.usage, 'completion_tokens', 0),
    'total_tokens': getattr(response.usage, 'total_tokens', 0),
}
return content, usage
```

### Files to update (callers of llm_client.chat)

All callers need to handle the new `(content, usage)` tuple return:

1. `app/services/report_agent.py` — accumulate usage across all LLM calls per report
2. `app/services/simulation_config_generator.py` — track config generation cost
3. `app/services/oasis_profile_generator.py` — track profile generation cost
4. `app/services/ontology_generator.py` — track ontology generation cost (if uses LLM)
5. `app/utils/file_parser.py` — track vision/analysis cost

### Accumulation pattern

```python
class UsageAccumulator:
    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0

    def add(self, usage: dict):
        self.prompt_tokens += usage.get('prompt_tokens', 0)
        self.completion_tokens += usage.get('completion_tokens', 0)
        self.calls += 1

    def to_dict(self):
        return {
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.prompt_tokens + self.completion_tokens,
            'llm_calls': self.calls,
        }
```

### Verification
- [ ] Every LLM call returns (content, usage) tuple
- [ ] No caller breaks (all updated to handle tuple)
- [ ] Usage logged for each report generation
- [ ] `vite build` + backend start without errors

---

## Phase B: Billing Service Integration

**Goal**: Connect AgenikPredict to agenikai-billing API

### Pre-requisites
- Deploy agenikai-billing to Railway
- Set BILLING_API_URL env var on AgenikPredict

### Files to create

**`backend/app/services/billing_client.py`** — HTTP client for billing API:

```python
class BillingClient:
    def __init__(self):
        self.base_url = Config.BILLING_API_URL  # e.g. https://billing.railway.internal
        self.api_key = Config.BILLING_API_KEY

    def check_can_generate(self, user_id: str) -> dict:
        """Check if user can generate (has balance or in trial)"""
        # GET /v1/users/{user_id}/can-generate
        # Returns: { allowed: bool, reason: str, balance_cents: int, trial_days_left: int }

    def pre_authorize(self, user_id: str, estimated_tokens: int, model: str) -> dict:
        """Reserve estimated cost before generation"""
        # POST /v1/usage/pre-authorize
        # Body: { user_id, estimated_input_tokens, estimated_output_tokens, model }
        # Returns: { auth_id, estimated_cost_cents, balance_after }

    def settle_usage(self, auth_id: str, actual_usage: dict) -> dict:
        """Record actual usage after generation complete"""
        # POST /v1/usage/settle
        # Body: { auth_id, actual_input_tokens, actual_output_tokens, model, metadata }
        # Returns: { cost_cents, refund_cents, balance_after }

    def get_balance(self, user_id: str) -> dict:
        """Get user balance and usage summary"""
        # GET /v1/users/{user_id}/balance

    def get_usage_history(self, user_id: str, days: int = 30) -> list:
        """Get recent usage history"""
        # GET /v1/users/{user_id}/usage?days={days}
```

### Files to modify

**`backend/app/api/report.py`** — wrap report generation with billing:

```python
# Before generation:
billing = BillingClient()
check = billing.check_can_generate(g.user_id)
if not check['allowed']:
    return jsonify({"success": False, "error": check['reason']}), 402

auth = billing.pre_authorize(g.user_id, estimated_tokens=50000, model=Config.LLM_MODEL_NAME)

# After generation:
billing.settle_usage(auth['auth_id'], {
    'input_tokens': accumulated_usage.prompt_tokens,
    'output_tokens': accumulated_usage.completion_tokens,
    'model': Config.LLM_MODEL_NAME,
    'metadata': {'report_id': report_id, 'simulation_id': simulation_id}
})
```

**`backend/app/api/auth.py`** — add billing endpoints proxy:

```python
@auth_bp.route('/billing/balance', methods=['GET'])
@require_auth
def get_balance():
    billing = BillingClient()
    return jsonify(billing.get_balance(g.user_id))

@auth_bp.route('/billing/usage', methods=['GET'])
@require_auth
def get_usage():
    billing = BillingClient()
    return jsonify(billing.get_usage_history(g.user_id))

@auth_bp.route('/billing/topup', methods=['POST'])
@require_auth
def create_topup():
    billing = BillingClient()
    # Create Stripe checkout session via billing service
    return jsonify(billing.create_checkout(g.user_id, amount_cents))
```

### Verification
- [ ] `check_can_generate()` returns allowed=true for trial users
- [ ] `check_can_generate()` returns allowed=false for expired trial with $0 balance
- [ ] Pre-auth reserves correct amount
- [ ] Settle records actual usage and adjusts balance
- [ ] Report generation blocked when no balance (402 response)

---

## Phase C: Trial Logic

**Goal**: 2-day free trial from registration date

### Where to implement

**Option 1 — In billing service** (recommended):
Add trial logic to agenikai-billing's user model:
```sql
ALTER TABLE users ADD COLUMN trial_ends_at TIMESTAMP;
-- Set to created_at + 2 days on user creation
```

`check_can_generate()` logic:
```
if now < user.trial_ends_at:
    return { allowed: true, reason: "trial", trial_days_left: ... }
elif user.balance_cents > 0:
    return { allowed: true, reason: "balance", balance_cents: ... }
else:
    return { allowed: false, reason: "trial_expired_no_balance" }
```

**Option 2 — In AgenikPredict** (simpler, no billing service changes):
Check `user.created_at` in auth middleware:
```python
from datetime import datetime, timedelta

def is_in_trial(user):
    created = datetime.fromisoformat(user['created_at'])
    return datetime.utcnow() < created + timedelta(days=2)
```

### Recommendation
Start with Option 2 (simple, no billing dependency), migrate to Option 1 when billing is fully integrated.

### Files to modify

**`backend/app/api/report.py`** — add trial check before generation:
```python
user = get_user(g.user_id)
if not is_in_trial(user) and not has_balance(g.user_id):
    return jsonify({"success": False, "error": "trial_expired", "message": "..."}), 402
```

**`backend/app/api/auth.py`** — return trial info in user data:
```python
# In JWT payload and /me endpoint:
"trial_ends_at": user['trial_ends_at'],
"is_trial": is_in_trial(user),
```

### Verification
- [ ] New user gets 2-day trial (can generate without balance)
- [ ] After 2 days, generation blocked without balance
- [ ] Trial status visible in frontend
- [ ] Demo user exempt from trial (unlimited)

---

## Phase D: Frontend Usage Display

**Goal**: Show balance, usage, trial status, top-up button

### Components to create

**`frontend/src/components/UsageBadge.vue`** — header badge showing:
```
Trial: 1 day left  |  or  |  Balance: $4.23  |  or  |  ⚠️ Top up
```

**`frontend/src/components/UsagePanel.vue`** — detailed usage panel:
```
This Month
├── Reports generated: 12
├── Tokens used: 523,400
├── Cost: $6.82
└── [View History]

Recent Reports
├── Report #1 — $0.85 (34K tokens) — Mar 15
├── Report #2 — $1.23 (52K tokens) — Mar 14
└── ...

[Add Credits →]  ← Opens Stripe checkout
```

**`frontend/src/components/ReportCostPreview.vue`** — before generation:
```
Estimated cost: ~$0.80 - $1.50
Your balance: $4.23
[Generate Report]
```

**`frontend/src/components/ReportCostSummary.vue`** — after generation:
```
Report generated successfully!
Cost: $1.12 (47,230 tokens)
Remaining balance: $3.11
```

### Files to modify

**`frontend/src/store/auth.js`** — add billing state:
```javascript
const balance = ref(0)
const isTrialActive = ref(false)
const trialDaysLeft = ref(0)

async function fetchBalance() {
    const res = await api.get('/api/auth/billing/balance')
    balance.value = res.data.balance_cents / 100
    isTrialActive.value = res.data.is_trial
    trialDaysLeft.value = res.data.trial_days_left
}
```

**`frontend/src/components/Step3Simulation.vue`** — show cost before "Generate Report":
- If trial: "Free (trial)" badge
- If paid: show estimated cost + balance

### i18n keys to add (all 12 locales)
```json
"billing.balance": "Balance",
"billing.trialDaysLeft": "{days} days left in trial",
"billing.trialExpired": "Trial expired",
"billing.topUp": "Add Credits",
"billing.estimatedCost": "Estimated cost",
"billing.reportCost": "Report cost",
"billing.tokens": "tokens",
"billing.generateFree": "Generate (Free Trial)",
"billing.insufficientBalance": "Insufficient balance. Please add credits.",
"billing.usageHistory": "Usage History",
"billing.thisMonth": "This Month",
"billing.reportsGenerated": "Reports generated",
"billing.tokensUsed": "Tokens used"
```

### Verification
- [ ] Balance badge visible in header
- [ ] Trial countdown shows correct days
- [ ] Cost preview shows before generation
- [ ] Cost summary shows after generation
- [ ] Top-up button opens Stripe checkout
- [ ] All 12 languages have billing translations

---

## Phase E: Deploy Billing Service

**Goal**: Deploy agenikai-billing to Railway alongside AgenikPredict

### Steps

1. Create new Railway service in same project
2. Add Postgres database on Railway
3. Set environment variables:
   ```
   DATABASE_URL=postgresql://...
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   BILLING_API_KEY=<internal_secret>
   MARKUP_PERCENT=20
   DEFAULT_TRIAL_DAYS=2
   ```
4. Run database migrations
5. Seed model pricing (Claude Sonnet rates)
6. Set `BILLING_API_URL` on AgenikPredict service
7. Configure Railway internal networking (private domain)

### Model Pricing to Seed

| Model | Input $/1M | Output $/1M | Cached $/1M |
|-------|-----------|------------|-------------|
| anthropic/claude-sonnet-4.6 | $3.00 | $15.00 | $0.30 |
| anthropic/claude-haiku-3.5 | $0.25 | $1.25 | $0.03 |

With 20% markup:
- Sonnet report (~50K tokens): ~$0.80-$1.50 per report
- User-facing cost: transparent in UI

### Verification
- [ ] Billing service health check passes
- [ ] Database migrations run
- [ ] Model pricing seeded
- [ ] AgenikPredict can reach billing via private network
- [ ] Stripe webhook endpoint accessible
- [ ] End-to-end: register → trial → generate → see cost → trial expires → top up → generate

---

## Execution Order

```
Phase A (token counting)     ← Can do independently, no external deps
    ↓
Phase E (deploy billing)     ← Need Stripe keys + Postgres
    ↓
Phase B (integration)        ← Needs billing service running
    ↓
Phase C (trial logic)        ← Can start with simple version (no billing)
    ↓
Phase D (frontend UI)        ← Needs B+C working
    ↓
End-to-end testing
```

**Parallel track**: Phase C (simple trial) can start alongside Phase A.

---

## Cost Transparency for Users

Every report shows:
1. **Before**: "This report will cost approximately $X.XX"
2. **During**: Progress bar with running token count
3. **After**: "Report cost: $X.XX (Y tokens input + Z tokens output)"
4. **Dashboard**: Monthly summary, per-report breakdown, CSV export

This matches the user's requirement: "прозрачность в обсуждении — transparency in billing discussion."
