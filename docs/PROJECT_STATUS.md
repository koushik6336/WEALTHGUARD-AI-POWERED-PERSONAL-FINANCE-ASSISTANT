# Project Status

Keeping this honest — here's what I've actually verified working versus what's built but untested.

## Confirmed working (tested live)

- Dashboard — real computed financial health score, live data
- AI chat assistant — the Bedrock + OpenSearch RAG pipeline gives grounded, personalized answers, confirmed
- Report generator — confirmed working after fixing a schema issue
- Budget spend logging — confirmed writing directly to the database
- NAV refresh — confirmed running on schedule via EventBridge
- Frontend — 13 pages built with a consistent design system (Notifications page was never built)

## Built but currently switched off

- Budget Intelligence, Goal Tracker, monthly Report Generator, and Tax monthly jobs exist as scheduled rules but are currently disabled

## Built but not independently verified yet

- Tax Optimizer's regime comparison logic
- Investment Advisor's AMFI fund data integration
- CAS PDF import parsing
- OTP-based human approval flow for fraud review
- SNS alerts (the topics exist, but nothing's subscribed to them yet)

## What's still missing

- No CI/CD — deploys are manual right now
- No automated test suite
- Demo video not recorded yet
- Notifications page not built

## One thing worth explaining

I tested the fraud detection pipeline against 2,000 real labeled transactions. Recall came out to 17.6% against an 85% target — not great. Digging into why, I found two real causes: an AWS Lambda concurrency limit was causing timeouts and fallback to a cruder scoring method, and a genuine data limitation — a single transaction alone often can't tell a new legitimate customer apart from a fraudster testing a stolen card. I documented this as a real structural limit rather than trying to prompt-tune my way around it.
