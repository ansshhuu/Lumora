# Lumora — Frontend

Ask anything about your codebase. Lumora traces through your code to answer with precision.

## Getting Started

1. Copy the environment file and fill in your values:

   ```bash
   cp .env.local.example .env.local
   ```

   See [`.env.local.example`](.env.local.example) for documentation on each variable.

2. Install dependencies:

   ```bash
   npm install
   ```

3. Run the development server:

   ```bash
   npm run dev
   ```

   Open [http://localhost:3000](http://localhost:3000) — you'll be greeted by the **Connect Repository** screen. Paste a public GitHub URL and hit **index repository**.

## Stack

- [Next.js](https://nextjs.org) (App Router)
- [Tailwind CSS v4](https://tailwindcss.com)
- IBM Plex Mono + Inter via `next/font/google`

## Known Limitations

- **Repo history** — switching repos discards the previous active repo from the UI (it remains indexed in the backend's Qdrant collection). A history list and multi-repo view are planned but not built in this version.
- **Multi-user auth** — there is no login or account system. The app uses a single API key configured at build time. Per-user history and authentication are planned but out of scope for this version.
- **Indexing progress** — the backend does not expose granular progress events, so the progress bar is an animation only (no real percentage).

## Deploy on Vercel

See [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for details. Make sure to set `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_API_KEY` as environment variables in your Vercel project settings.
