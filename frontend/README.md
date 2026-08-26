# Punarvritt — Circular Economy & EPR Compliance Platform

A Next.js 15 (App Router) frontend for plastic waste recycling and EPR compliance, serving Brand Owners, Producers & Importers (PIBOs) and certified Plastic Recyclers.

## Features

- **Brand & Recycler registration wizard** — multi-step form with document uploads, capacity tier selection, and subscription plan picker
- **Authentication flows** — login/signup pages for both brand and recycler portals
- **Dashboard views** — EPR credit tracking, compliance reports, and certificate management
- **Frontend-only demo** — all data persisted to `localStorage`; no backend required

## Tech Stack

- **Next.js 15** (App Router) — file-system routing, static page generation
- **React 19** — UI library
- **Tailwind CSS v4** — styling
- **Framer Motion** (`motion`) — animations
- **Lucide React** — icons
- **TypeScript** — type safety

## Getting Started

### Prerequisites

- Node.js 18+

### Installation

```bash
npm install
```

### Environment Variables

Create a `.env.local` file from the example:

```bash
cp .env.example .env.local
```

Set the following variables:

| Variable         | Description                                      |
| ---------------- | ------------------------------------------------ |
| `GEMINI_API_KEY` | Required for Gemini AI API calls                 |
| `APP_URL`        | The URL where this app is hosted                 |

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the app.

### Build & Deploy

```bash
npm run build
npm start
```

## Project Structure

```
src/
├── app/                      # Next.js App Router routes
│   ├── layout.tsx            # Root layout + global CSS
│   ├── page.tsx              # Home (landing) route
│   ├── brand/
│   │   ├── signup/page.tsx
│   │   ├── login/page.tsx
│   │   └── dashboard/page.tsx
│   └── recycler/
│       ├── signup/page.tsx
│       ├── login/page.tsx
│       └── dashboard/page.tsx
├── components/
│   ├── auth/                 # Auth layout, inputs, success screens
│   ├── registration/         # Registration wizard components
│   └── ui/                   # Reusable UI primitives
├── data/                     # Pricing tiers, features, document lists
├── hooks/                    # Custom hooks (useRegistration)
├── views/                    # Page-level view components
├── types/                    # TypeScript interfaces
└── index.css                 # Tailwind CSS import
```

## Available Scripts

| Script       | Description                          |
| ------------ | ------------------------------------ |
| `dev`        | Start the Next.js dev server (port 3000) |
| `build`      | Create an optimized production build |
| `start`      | Start the production server          |
| `lint`       | Run ESLint and TypeScript type check |

## Routes

| Route                    | Description                          |
| ------------------------ | ------------------------------------ |
| `/`                      | Landing page with hero and features  |
| `/brand/signup`          | Brand registration wizard            |
| `/brand/login`           | Brand login form                     |
| `/brand/dashboard`       | Brand dashboard (EPR credits, certs) |
| `/recycler/signup`       | Recycler registration wizard         |
| `/recycler/login`        | Recycler login form                  |
| `/recycler/dashboard`    | Recycler dashboard (batches, buyers) |
