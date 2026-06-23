import Link from "next/link";
import { ArrowLeft, Home, Search, ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="relative flex min-h-screen overflow-hidden bg-[#0c0e10] px-4 py-8 text-foreground sm:px-6 lg:px-8">
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_78%_12%,rgba(31,240,170,0.16),transparent_28rem),radial-gradient(circle_at_18%_4%,rgba(13,186,230,0.12),transparent_30rem),linear-gradient(180deg,#101316_0%,#0c0e10_62%,#08090b_100%)]" />
      <div className="absolute left-1/2 top-16 -z-10 h-64 w-[min(42rem,80vw)] -translate-x-1/2 rounded-full bg-primary/10 blur-3xl" />

      <section className="mx-auto flex w-full max-w-[1180px] flex-col">
        <header className="flex h-14 items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-white transition-opacity hover:opacity-85">
            <div className="grid size-9 place-items-center rounded-md bg-gradient-to-br from-cyan-400 to-emerald-400 shadow-teal">
              <Search className="size-5 text-[#07100d]" />
            </div>
            <span className="text-xl font-extrabold tracking-normal">PeopleGraph</span>
          </Link>
        </header>

        <div className="grid flex-1 items-center gap-10 py-14 lg:grid-cols-[1fr_0.78fr] lg:py-20">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/6 px-3 py-2 text-sm font-semibold text-primary">
              <ShieldAlert className="size-4" />
              Page not found
            </div>

            <p className="mt-8 text-sm font-bold uppercase tracking-[0.28em] text-muted-foreground">Error 404</p>
            <h1 className="mt-3 text-4xl font-black tracking-normal text-white sm:text-5xl lg:text-6xl">
              The page you requested is unavailable.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-zinc-300 sm:text-lg">
              The link may be outdated, mistyped, or no longer active. Return to PeopleGraph or open the lookup
              workspace.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button asChild size="lg" className="h-12">
                <Link href="/">
                  <Home />
                  Back to Home
                </Link>
              </Button>
              <Button asChild variant="secondary" size="lg" className="h-12">
                <Link href="/lookup">
                  <Search />
                  Open Lookup
                </Link>
              </Button>
            </div>
          </div>

          <div className="relative mx-auto aspect-square w-full max-w-sm sm:max-w-md">
            <div className="absolute inset-0 rounded-full border border-primary/25 bg-primary/5 shadow-[0_0_90px_rgba(31,240,170,0.10)]" />
            <div className="absolute inset-8 rounded-full border border-cyan-300/20 bg-white/[0.035]" />
            <div className="absolute inset-16 rounded-full border border-white/10 bg-[#11161a]/80" />
            <div className="absolute inset-0 grid place-items-center">
              <div className="text-center">
                <div className="mx-auto grid size-16 place-items-center rounded-md border border-primary/25 bg-primary/10 text-primary">
                  <ShieldAlert className="size-8" />
                </div>
                <p className="mt-6 text-7xl font-black tracking-normal text-white sm:text-8xl">404</p>
                <p className="mt-2 text-sm font-semibold text-muted-foreground">No matching route</p>
              </div>
            </div>
            <div className="absolute left-4 top-10 h-2 w-2 rounded-full bg-primary shadow-[0_0_24px_rgba(31,240,170,0.9)]" />
            <div className="absolute bottom-12 right-8 h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_24px_rgba(13,186,230,0.9)]" />
          </div>
        </div>
      </section>
    </main>
  );
}
