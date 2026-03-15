# AgenikPredict — Product Roadmap

## Vision
From document-based simulation to **live-data prediction platform** with real-world API integrations and personal use cases.

---

## Phase 1: Foundation (DONE)
- [x] Fork MiroFish → AgenikPredict
- [x] Full rebrand (0 Chinese, 0 MiroFish references)
- [x] i18n: 5 languages (EN, HE, RU, ES, DE) — 318 keys
- [x] Language Switcher + RTL support
- [x] LLM default: Claude via OpenRouter
- [x] Multilingual LLM prompts (Accept-Language header)
- [x] Dark theme + Magic UI animations
- [x] AGENIKAI logo integration
- [x] Next.js landing page (startup-template)

---

## Phase 2: API Tool Framework
**Goal**: Extensible tool system so agents can call external APIs during simulation and reporting.

### 2.1 Tool Registry Architecture
- [ ] Create `backend/app/tools/` module with base `Tool` class
- [ ] Tool interface: `name`, `description`, `parameters`, `execute()`
- [ ] Tool registry: auto-discovers tools, exposes to ReportAgent
- [ ] Config: enable/disable tools per simulation via UI

### 2.2 Tool UI in Step 2 (Environment Setup)
- [ ] Checkbox list of available tools in simulation config
- [ ] API key management per tool (stored encrypted)
- [ ] Tool usage preview (which agents can use which tools)

---

## Phase 3: Financial APIs
**Goal**: Agents can access real market data for investment/business simulations.

### 3.1 Alpha Vantage Integration (free tier)
- [ ] Tool: `MarketData` — get stock price, volume, fundamentals
- [ ] Tool: `ForexRates` — currency exchange rates
- [ ] Auto-enrich graph with market context before simulation

### 3.2 CoinGecko Integration (free)
- [ ] Tool: `CryptoMarket` — price, market cap, sentiment
- [ ] Historical data for trend context

### 3.3 SEC EDGAR (free)
- [ ] Tool: `CompanyFilings` — 10-K, 10-Q, 8-K filings
- [ ] Auto-extract financial metrics from filings

### 3.4 TradingView Webhooks (later)
- [ ] Real-time alerts integration
- [ ] Technical indicator data for agents

---

## Phase 4: News & Trends APIs
**Goal**: Ground simulations in current real-world events.

### 4.1 NewsAPI Integration
- [ ] Tool: `LatestNews` — search news by topic, date, source
- [ ] Pre-simulation: inject recent news as initial graph facts
- [ ] During simulation: agents can "check news"

### 4.2 Google Trends
- [ ] Tool: `TrendCheck` — what people are searching now
- [ ] Calibration: compare simulation interest vs real interest

### 4.3 Twitter/X API (if available)
- [ ] Tool: `RealTweets` — fetch real tweets on topic
- [ ] Post-simulation: compare simulated vs real sentiment

### 4.4 Reddit API
- [ ] Tool: `RedditPosts` — fetch real subreddit discussions
- [ ] Validation: are simulated discussions realistic?

---

## Phase 5: Personal Use Case — Trip Planner
**Goal**: First consumer-facing vertical. Upload preferences → get optimized travel plan.

### 5.1 Travel APIs
- [ ] Skyscanner/Kiwi API — real flight prices
- [ ] Booking.com API — hotel availability and prices
- [ ] OpenWeather API — weather forecasts and historical data
- [ ] Google Maps API — routes, distances, POIs

### 5.2 Trip Planner Template
- [ ] Pre-built persona set: Budget Traveler, Luxury Seeker, Adventure Fan, Family Expert, Local Guide
- [ ] Simplified UI: skip graph construction, go straight to "plan my trip"
- [ ] Custom report template: itinerary format instead of analysis report

### 5.3 Trip-specific Tools
- [ ] Tool: `FlightSearch` — search flights by date/destination
- [ ] Tool: `HotelSearch` — search hotels with filters
- [ ] Tool: `WeatherForecast` — 16-day forecast for destination
- [ ] Tool: `PlacesNearby` — restaurants, attractions, activities

---

## Phase 6: Business Intelligence APIs
**Goal**: Deep business analysis capabilities.

### 6.1 Company Data
- [ ] Crunchbase API — startup funding, investors, team
- [ ] LinkedIn API — company profiles, employee count
- [ ] SimilarWeb API — website traffic, competitors

### 6.2 HR / Talent
- [ ] Glassdoor API — reviews, salaries, interview experience
- [ ] LinkedIn API — job postings, skill demand trends

### 6.3 Real Estate (future)
- [ ] Zillow/Redfin API — property listings, price history
- [ ] Census data — demographics, income, growth
- [ ] Crime statistics API

---

## Phase 7: Platform & Scale
**Goal**: From single-user tool to multi-tenant platform.

### 7.1 Authentication
- [ ] User accounts (Clerk/Auth0)
- [ ] API key management per user
- [ ] Usage tracking and billing

### 7.2 Templates Marketplace
- [ ] Pre-built simulation templates (Trip Planner, Investment Analysis, PR Crisis, Product Launch)
- [ ] Community-contributed templates
- [ ] One-click start from template

### 7.3 Deployment
- [ ] Docker production build
- [ ] Vercel/Railway deployment for landing
- [ ] Cloud hosting for backend (Fly.io / Railway)
- [ ] Separate worker for simulations (long-running)

### 7.4 Graph Visualization Upgrade
- [ ] Replace D3.js with G6 (AntV) or Cosmograph
- [ ] 3D graph mode
- [ ] Timeline view
- [ ] Community clusters
- [ ] Sentiment heatmap

---

## Priority Matrix

| Phase | Impact | Effort | Priority |
|-------|--------|--------|----------|
| 2. Tool Framework | HIGH | MEDIUM | P0 — enables everything else |
| 3. Financial APIs | HIGH | LOW | P1 — high-value use case |
| 4. News & Trends | HIGH | LOW | P1 — grounds simulations in reality |
| 5. Trip Planner | MEDIUM | MEDIUM | P2 — first consumer vertical |
| 6. Business Intel | MEDIUM | MEDIUM | P2 — enterprise value |
| 7. Platform | HIGH | HIGH | P3 — after product-market fit |

---

## Tech Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| API keys storage | `.env` per tool, encrypted at rest | Simple, secure |
| Tool framework | Python base class + registry | Extensible, type-safe |
| Rate limiting | Per-tool configurable | Different APIs, different limits |
| Caching | Redis or in-memory with TTL | Avoid redundant API calls |
| Graph viz upgrade | G6 5.0 (AntV) | Best Vue compat, WebGL, animations |
| Auth | Clerk | Fast integration, social login |
| Deployment | Railway (backend) + Vercel (landing) | Easy, auto-deploy |
