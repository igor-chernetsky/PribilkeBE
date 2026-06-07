# Capital Scanner Backend Product Requirements Document (PRD) v1.0

## 1. Project Overview

### Purpose

Build a backend platform that continuously collects, normalizes, stores, analyzes, and distributes financial market data to help users identify capital allocation opportunities.

The platform is not an investment advisor and does not provide financial recommendations.

The platform provides:

* Market data aggregation
* Opportunity discovery
* Historical tracking
* Market comparison
* User-defined alerts
* Financial instrument monitoring

---

# 2. Business Goals

### Primary Goals

* Aggregate financial products from multiple sources
* Track changes in yields, rates, and prices
* Notify users when better opportunities become available
* Create a scalable data infrastructure that can expand into multiple countries

### Future Goals

* AI-assisted market analysis
* Personalized opportunity ranking
* Portfolio tracking
* Open Banking integrations
* Real estate investment analytics

---

# 3. Supported Asset Classes (MVP)

## 3.1 Bank Deposits

Collected fields:

* Institution name
* Product name
* Country
* Currency
* Annual interest rate
* Deposit term
* Interest capitalization
* Minimum deposit amount
* Maximum deposit amount
* Early withdrawal conditions
* Requirements for promotional rates
* Last updated timestamp
* Source URL

---

## 3.2 Government Bonds

Collected fields:

* Issuer
* Bond series
* ISIN
* Issue date
* Maturity date
* Coupon rate
* Yield to maturity (YTM)
* Currency
* Market price
* Face value
* Minimum investment
* Last updated timestamp

---

## 3.3 Corporate Bonds

Collected fields:

* Issuer
* Industry sector
* Credit rating
* ISIN
* Coupon rate
* Yield to maturity
* Maturity date
* Market price
* Currency
* Trading volume
* Liquidity indicators
* Last updated timestamp

---

## 3.4 Gold

Collected fields:

* Spot price
* Buy price
* Sell price
* Currency
* Daily change
* Weekly change
* Monthly change
* Annual change
* Last updated timestamp

---

## 3.5 Foreign Exchange Rates

Collected fields:

* Currency pair
* Bid price
* Ask price
* Mid-market rate
* Daily change
* Weekly change
* Monthly change
* Source
* Last updated timestamp

Supported currencies:

* USD
* EUR
* GBP
* CHF
* PLN
* Local market currencies

---

# 4. Phase 2 Asset Classes

## Residential Real Estate

Collected fields:

* Property type
* Location
* Purchase price
* Rental price
* Rental yield
* Price per square meter
* Listing age
* Historical trends

---

## Commercial Real Estate

Collected fields:

* Property category
* Location
* Purchase price
* Rental income
* Estimated yield
* Occupancy indicators
* Historical trends

---

## ETFs

Collected fields:

* Ticker
* Fund name
* Expense ratio
* Dividend yield
* AUM
* Current price
* Historical performance

---

## Stocks

Collected fields:

* Ticker
* Company
* Sector
* Market capitalization
* Dividend yield
* Current price
* Historical performance

---

# 5. Data Collection Architecture

The system must use independent collectors for each asset class.

Examples:

* deposit_collector
* government_bond_collector
* corporate_bond_collector
* gold_collector
* fx_collector
* real_estate_collector

Collectors must operate independently and be horizontally scalable.

---

# 6. Data Refresh Schedule

| Asset Class   | Refresh Interval |
| ------------- | ---------------- |
| Bank Deposits | Every 4 hours    |
| Bonds         | Every 1 hour     |
| FX Rates      | Every 15 minutes |
| Gold Prices   | Every 15 minutes |
| Real Estate   | Every 24 hours   |

---

# 7. Data Normalization

All collected data must be transformed into a unified internal format.

Examples:

Input:

* "up to 6.5%"
* "6.5 percent annually"
* "annual yield 6.5%"

Output:

rate = 6.5

Normalization must include:

* Currency conversion support
* Unified date formats
* Standardized yield calculations
* Duplicate detection

---

# 8. Historical Data Storage

The system must store every meaningful change.

Examples:

Deposit Rate History:

2026-01-01 → 5.2%

2026-01-10 → 5.8%

2026-01-20 → 6.3%

Historical records must support:

* Daily comparisons
* Weekly comparisons
* Monthly comparisons
* Trend analysis

---

# 9. Event Engine

The platform must generate events whenever significant changes occur.

Supported events:

* NEW_INSTRUMENT
* RATE_INCREASED
* RATE_DECREASED
* YIELD_INCREASED
* YIELD_DECREASED
* PRICE_CHANGED
* MATURITY_APPROACHING
* INSTRUMENT_REMOVED

---

# 10. Alert Engine

Users can define custom monitoring rules.

Example:

Currency: PLN

Minimum Yield: 6%

Maximum Term: 12 Months

Risk Level: Low

When matching instruments appear, the system generates alerts.

---

# 11. Public API

## Market Data

GET /api/v1/deposits

GET /api/v1/bonds

GET /api/v1/gold

GET /api/v1/fx

GET /api/v1/market-summary

---

## Instrument Details

GET /api/v1/deposits/{id}

GET /api/v1/bonds/{id}

GET /api/v1/gold/history

GET /api/v1/fx/history

---

## Analytics

GET /api/v1/best-deposits

GET /api/v1/best-bonds

GET /api/v1/top-yields

GET /api/v1/trends

GET /api/v1/market-opportunities

---

## User Alerts

POST /api/v1/alerts

GET /api/v1/alerts

PUT /api/v1/alerts/{id}

DELETE /api/v1/alerts/{id}

---

## Notifications

GET /api/v1/notifications

POST /api/v1/notifications/read

---

# 12. Opportunity Scoring Engine

The platform must calculate an Opportunity Score for every instrument.

Example formula:

Opportunity Score =

40% Yield

25% Liquidity

20% Issuer Reliability

15% Investment Term

The scoring algorithm must be configurable and market-specific.

Purpose:

* Ranking opportunities
* Personalized recommendations
* Market summaries

---

# 13. AI Services (Phase 2)

AI is not responsible for investment decisions.

AI may be used for:

### Product Condition Extraction

Convert unstructured financial product descriptions into structured data.

### Instrument Classification

Classify products by category and risk level.

### Market Summaries

Generate short descriptions and insights.

### Anomaly Detection

Identify unusually attractive or unusual market offers.

Example:

"Current deposit rate is 45% above market average."

---

# 14. Non-Functional Requirements

### Availability

99.9% uptime

### API Response Time

< 300 ms

### Data Accuracy

> 95%

### Scalability

Support:

* Multiple countries
* Multiple currencies
* Millions of instruments
* Millions of historical records

### Security

* JWT Authentication
* Role-based access control
* Rate limiting
* Audit logging

---

# 15. Technology Stack

## Backend

| Layer | Technology | Purpose |
| ----- | ---------- | ------- |
| Language | Python 3.12 | Data collection, normalization, API |
| API Framework | FastAPI | REST API, OpenAPI docs, validation |
| ORM | SQLAlchemy 2.0 | Database models and queries |
| Migrations | Alembic | Schema versioning |
| Validation | Pydantic v2 | Request/response schemas |
| HTTP Client | httpx | Collector requests to external sources |
| Scraping | Playwright | Dynamic pages (bank websites) |
| Task Queue | Celery | Scheduled collectors, alert processing |
| Auth (Phase 2) | python-jose + passlib | JWT authentication |

## Data Storage

| Layer | Technology | Purpose |
| ----- | ---------- | ------- |
| Primary DB | PostgreSQL 16 | Instruments, history, alerts |
| Cache / Broker | Redis 7 | API cache, Celery broker |

## Infrastructure

| Layer | Technology | Purpose |
| ----- | ---------- | ------- |
| Containers | Docker + Docker Compose | Local dev and deployment |
| API Hosting | Render / Railway | Free tier for MVP, ~$7/mo for always-on |
| Worker Hosting | Hetzner VPS (CX22) | Always-on collectors (~€4/mo) |
| Database Hosting | Neon / Supabase | Free PostgreSQL tier |
| Redis Hosting | Upstash | Free serverless Redis tier |
| Monitoring | Sentry (free tier) | Error tracking |
| Future | Kubernetes, Prometheus, Grafana | Scale beyond MVP |

## Architecture

Two independent processes:

* **api** — FastAPI server, serves public REST endpoints
* **worker** — Celery worker, runs collectors on schedule

Collectors are independent modules (`deposit_collector`, `bond_collector`, etc.) registered in the worker scheduler.

## Initial Market

* Country: Poland (`PL`)
* Primary currency: PLN
* Architecture supports multi-country expansion via `CountryCode` enum and per-country collector configs

---

# 16. MVP Success Metrics

* 20+ active data sources
* 100+ deposit products
* 500+ bond instruments
* Historical data retention enabled
* Average refresh interval below target
* API response time below 300ms
* Data accuracy above 95%

---

# 17. Future Roadmap

Phase 1

* Deposits
* Bonds
* Gold
* FX Rates
* Alerts

Phase 2

* Real Estate
* ETFs
* Stocks
* AI Analysis

Phase 3

* Open Banking
* Portfolio Tracking
* Cross-country Expansion
* Premium Subscription Features
