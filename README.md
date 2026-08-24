# WealthGuard — AI-Powered Personal Finance Platform

WealthGuard is a personal finance app I built on AWS. It handles budgeting, tax planning, investments, goal tracking, and has an AI chat assistant you can actually ask real questions to.

**Live demo:** http://wealthguard-frontend-703890345539.s3-website.ap-south-1.amazonaws.com

## What it is

Instead of one big backend, I split everything into 23+ small AWS Lambda functions, each doing one job — auth, budgeting, tax calculations, investments, chat, and so on. The frontend is a 13-page React + TypeScript app with a custom dark theme built on shadcn/ui.

## How it's built

- **Compute:** AWS Lambda, API Gateway
- **Database:** RDS PostgreSQL for the main data (users, transactions, budgets, goals, investments, tax records), DynamoDB for high-write audit logs
- **AI:** Amazon Bedrock (Nova Lite) powers the chat assistant, with OpenSearch doing vector search so answers are grounded in real financial knowledge instead of generic advice — a RAG setup
- **Networking:** Custom VPC, private subnets for the database, security groups locked down to only what needs access, least-privilege IAM
- **Automation:** EventBridge runs scheduled jobs like daily NAV refreshes
- **Frontend:** React, TypeScript, Tailwind, shadcn/ui, hosted on S3

## What it does

- Login with optional 2FA and login history
- Daily budget/spend tracking with category breakdowns
- Goals — preset types plus custom ones
- Tax planning — compares old vs new regime and tells you which saves more
- Investment tracking, including CAS (mutual fund statement) PDF import
- An AI chat assistant that answers using your actual financial data
- A financial health score that combines budget, goals, and tax status into one number
- Monthly reports
- A fraud detection pipeline I tested against a real labeled dataset

## Tech stack

**Backend:** Python, AWS Lambda, API Gateway, RDS (PostgreSQL), DynamoDB, Amazon Bedrock, OpenSearch, EventBridge, SNS/SQS, S3

**Frontend:** React, TypeScript, Tailwind CSS, shadcn/ui, Vite

## Project structure
wealthguard-repo/
├── backend/
│ └── lambda-functions/ # each Lambda function in its own folder
├── frontend/
│ └── src/
│ ├── pages/ # 13 pages
│ └── components/ # shared UI components
└── docs/
└── PROJECT_STATUS.md # what's actually tested vs what isn't yet

## A note on security

Database credentials are pulled from environment variables, not hardcoded — you won't find any real passwords or AWS keys in this repo. Anything that was hardcoded during development has since been rotated.

## Where things stand

This is still a work in progress. I've kept `docs/PROJECT_STATUS.md` honest about what I've actually tested versus what's built but unverified — didn't want to just claim everything works without backing it up.
