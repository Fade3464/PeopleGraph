# PeopleGraph

PeopleGraph is a production-focused people lookup portal. The current project includes a polished Next.js frontend with a public landing page and an interactive lookup workspace. A Django backend will be added later for the API endpoint and search logic.

## Current Scope

- Public landing page at `/`
- Lookup workspace at `/lookup`
- Search modes for phone number and name/address
- Mocked loading, empty, error, and results states
- Mock result cards based on the previous portal data shape
- Dark teal responsive UI using Tailwind CSS and shadcn-style components
- JavaScript interactions on the landing page, including scroll reveals, counters, and an interactive product preview

## Tech Stack

- Next.js App Router
- React
- TypeScript
- Tailwind CSS
- shadcn/ui-style local primitives
- lucide-react icons

Planned backend:

- Django
- API endpoint for lookup/search logic

## Project Structure

```text
PeopleGraph/
  frontend/
    app/
      page.tsx          # Landing page
      lookup/page.tsx   # Lookup portal prototype
      globals.css       # Global theme and utilities
    components/ui/      # Local UI primitives
    lib/                # Shared frontend utilities
```

## Getting Started

Install frontend dependencies:

```bash
cd frontend
npm install
```

Run the development server:

```bash
npm run dev
```

Open:

```text
http://localhost:3000
```

Build for production:

```bash
npm run build
```

## Routes

- `/` - Public PeopleGraph landing page
- `/lookup` - Interactive people lookup workspace

## Notes

The lookup page currently uses mock data. The real endpoint, request payloads, response parsing, and search behavior will be connected once the Django backend and API contract are finalized.
