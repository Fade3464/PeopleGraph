"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { PointerEvent, ReactNode } from "react";
import {
  ArrowRight,
  BadgeCheck,
  Check,
  CircleUserRound,
  Fingerprint,
  Gauge,
  LockKeyhole,
  MapPin,
  Phone,
  Search,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const capabilities = [
  {
    title: "Search with flexible inputs",
    body: "Look up records by phone number, full name, city, state, street, or zip code.",
    icon: Search,
  },
  {
    title: "Review clean match summaries",
    body: "See primary phone, current address, aliases, relatives, and confidence signals at a glance.",
    icon: BadgeCheck,
  },
  {
    title: "Move from summary to detail",
    body: "Open a focused record view when an operator needs deeper context before taking action.",
    icon: UsersRound,
  },
];

const values = [
  "Responsive interface for desktop and mobile workflows",
  "Search states designed for loading, empty, error, and matched results",
  "Frontend structure ready for a Django API integration",
  "Dark teal visual system with clear hierarchy and restrained motion",
];

export default function LandingPage() {
  const [spotlight, setSpotlight] = useState({ x: 50, y: 20 });

  function handlePointerMove(event: PointerEvent<HTMLElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    setSpotlight({
      x: ((event.clientX - rect.left) / rect.width) * 100,
      y: ((event.clientY - rect.top) / rect.height) * 100,
    });
  }

  return (
    <main className="min-h-screen overflow-hidden bg-[#0c0e10] text-foreground">
      <LandingNav />

      <section
        className="relative px-4 pb-10 pt-14 sm:px-6 lg:px-8"
        onPointerMove={handlePointerMove}
        style={{
          background: `radial-gradient(circle at ${spotlight.x}% ${spotlight.y}%, rgba(31, 240, 170, 0.14), transparent 24rem)`,
        }}
      >
        <div className="absolute inset-0 -z-10 bg-[linear-gradient(180deg,rgba(20,24,28,0.96)_0%,rgba(12,14,16,1)_78%)]" />
        <div className="absolute inset-x-0 top-16 -z-10 mx-auto h-64 max-w-5xl rounded-full bg-primary/10 blur-3xl" />

        <Reveal className="mx-auto max-w-[1180px] text-center">
          <div className="mx-auto inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/6 px-3 py-2 text-sm font-semibold text-primary shadow-panel transition-transform duration-300 hover:-translate-y-0.5">
            <ShieldCheck className="size-4" />
            Professional people lookup portal
          </div>

          <h1 className="mx-auto mt-6 max-w-4xl text-5xl font-black tracking-normal text-white sm:text-6xl lg:text-7xl">
            PeopleGraph
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-zinc-300 sm:text-lg">
            Search phone numbers, names, and addresses through a polished workspace built for fast review and clear
            record intelligence.
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild size="lg" className="h-12 min-w-48">
              <Link href="/lookup">
                Open Lookup Portal
                <ArrowRight />
              </Link>
            </Button>
            <Button asChild variant="secondary" size="lg" className="h-12 min-w-40">
              <a href="#overview">View Overview</a>
            </Button>
          </div>
        </Reveal>

        <Reveal className="mx-auto mt-12 max-w-[1180px]" delay={120}>
          <ProductScene />
        </Reveal>
      </section>

      <section id="overview" className="border-y border-white/10 bg-[#101316] px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-[1180px] gap-4 md:grid-cols-3">
          {capabilities.map((item, index) => (
            <Reveal key={item.title} delay={index * 90}>
              <FeatureCard {...item} />
            </Reveal>
          ))}
        </div>
      </section>

      <section className="px-4 py-16 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-[1180px] gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div>
            <p className="text-sm font-semibold text-primary">Built for a production-grade portal</p>
            <h2 className="mt-3 text-3xl font-extrabold tracking-normal text-white sm:text-4xl">
              A front end that is ready for real search operations.
            </h2>
            <p className="mt-4 max-w-xl text-sm leading-7 text-muted-foreground">
              PeopleGraph keeps the public landing experience refined while giving operators a dedicated lookup
              workspace for structured search and result review.
            </p>
            <div className="mt-6 grid max-w-md grid-cols-3 gap-3">
              <Metric value={2} suffix="" label="Search modes" />
              <Metric value={4} suffix="" label="UI states" />
              <Metric value={53} suffix="" label="Graph links" />
            </div>
          </div>

          <div className="rounded-md border border-white/10 bg-[#12171a] p-4 shadow-panel">
            <div className="grid gap-3 sm:grid-cols-2">
              {values.map((value, index) => (
                <Reveal key={value} delay={index * 70}>
                  <div className="group flex gap-3 rounded-md border border-white/10 bg-white/[0.04] p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/35 hover:bg-white/[0.065]">
                  <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-primary text-[#07100d]">
                    <Check className="size-3.5 transition-transform duration-200 group-hover:scale-110" />
                  </span>
                  <p className="text-sm leading-6 text-zinc-300">{value}</p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 pb-16 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-5 rounded-md border border-primary/20 bg-primary/8 p-6 transition-all duration-300 hover:border-primary/40 hover:bg-primary/10 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-2xl font-extrabold tracking-normal text-white">Start with the lookup workspace.</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              The prototype is ready for endpoint wiring when the API and search logic are finalized.
            </p>
          </div>
          <Button asChild size="lg" className="h-12 sm:min-w-44">
            <Link href="/lookup">
              Launch Portal
              <ArrowRight />
            </Link>
          </Button>
        </div>
      </section>
    </main>
  );
}

function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.18 },
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={cn(
        "transition-all duration-700 ease-out",
        visible ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0",
        className,
      )}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}

function FeatureCard({
  title,
  body,
  icon: Icon,
}: {
  title: string;
  body: string;
  icon: LucideIcon;
}) {
  return (
    <article className="group h-full rounded-md border border-white/10 bg-white/[0.045] p-5 transition-all duration-300 hover:-translate-y-1 hover:border-primary/45 hover:bg-white/[0.065]">
      <div className="mb-4 grid size-11 place-items-center rounded-md bg-primary/12 text-primary transition-all duration-300 group-hover:scale-105 group-hover:bg-primary group-hover:text-[#07100d]">
        <Icon className="size-5" />
      </div>
      <h2 className="text-lg font-bold">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{body}</p>
    </article>
  );
}

function Metric({ value, suffix, label }: { value: number; suffix: string; label: string }) {
  const [display, setDisplay] = useState(0);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;

      let frame = 0;
      const totalFrames = 34;
      const timer = window.setInterval(() => {
        frame += 1;
        const progress = 1 - Math.pow(1 - frame / totalFrames, 3);
        setDisplay(Math.round(value * progress));
        if (frame >= totalFrames) {
          setDisplay(value);
          window.clearInterval(timer);
        }
      }, 24);

      observer.disconnect();
    });

    observer.observe(element);
    return () => observer.disconnect();
  }, [value]);

  return (
    <div ref={ref} className="rounded-md border border-white/10 bg-white/[0.04] p-4 text-center">
      <p className="text-2xl font-extrabold text-primary">
        {display}
        {suffix}
      </p>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">{label}</p>
    </div>
  );
}

function LandingNav() {
  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-[#111316]/92 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1180px] items-center gap-4 px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-2">
          <div className="grid size-9 place-items-center rounded-md bg-gradient-to-br from-cyan-400 to-emerald-400 shadow-teal">
            <Fingerprint className="size-5 text-[#07100d]" />
          </div>
          <span className="text-xl font-extrabold">PeopleGraph</span>
        </Link>
        <nav className="ml-auto hidden items-center gap-6 text-sm font-semibold text-muted-foreground md:flex">
          <a className="transition-colors hover:text-foreground" href="#overview">
            Overview
          </a>
        </nav>
        <Button asChild size="sm" className="ml-auto md:ml-0">
          <Link href="/lookup">
            Launch
            <ArrowRight />
          </Link>
        </Button>
      </div>
    </header>
  );
}

function ProductScene() {
  const modes = [
    { key: "phone", label: "Phone", icon: Phone, query: "(617) 541-2753" },
    { key: "name", label: "Name", icon: CircleUserRound, query: "Evencio Pena" },
    { key: "address", label: "Address", icon: MapPin, query: "Boston, MA 02118" },
  ] as const;
  const [activeMode, setActiveMode] = useState<(typeof modes)[number]["key"]>("phone");
  const active = modes.find((mode) => mode.key === activeMode) ?? modes[0];

  return (
    <div className="group relative overflow-hidden rounded-md border border-white/12 bg-[#11161a] p-3 shadow-panel transition-transform duration-500 hover:-translate-y-1">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,rgba(31,240,170,0.08),transparent_38%,rgba(13,186,230,0.08))] transition-opacity duration-500 group-hover:opacity-80" />
      <div className="relative rounded-md border border-white/10 bg-[#0f151b]">
        <div className="flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="size-2.5 rounded-full bg-primary" />
            <span className="size-2.5 rounded-full bg-cyan-400" />
            <span className="size-2.5 rounded-full bg-zinc-500" />
          </div>
          <div className="hidden items-center gap-2 rounded-md border border-white/10 bg-white/6 px-3 py-1.5 text-xs text-muted-foreground sm:flex">
            <LockKeyhole className="size-3.5" />
            Secure search workspace
          </div>
        </div>

        <div className="grid gap-4 p-4 lg:grid-cols-[330px_minmax(0,1fr)]">
          <div className="rounded-md border border-white/10 bg-[#151b20] p-4">
            <p className="text-xs font-semibold uppercase text-primary">Lookup</p>
            <h2 className="mt-1 text-xl font-extrabold text-white">Search records</h2>
            <div className="mt-4 grid grid-cols-3 gap-2">
              {modes.map((mode) => (
                <button
                  key={mode.key}
                  type="button"
                  onClick={() => setActiveMode(mode.key)}
                  className={cn(
                    "flex h-10 items-center justify-center gap-1.5 rounded-md border text-xs font-bold transition-all duration-200",
                    activeMode === mode.key
                      ? "border-primary bg-primary text-[#07100d]"
                      : "border-white/10 bg-white/[0.045] text-muted-foreground hover:border-primary/35 hover:text-white",
                  )}
                >
                  <mode.icon className="size-3.5" />
                  {mode.label}
                </button>
              ))}
            </div>
            <div className="mt-3 space-y-3">
              <PreviewField icon={active.icon} label={`${active.label} query`} value={active.query} active />
              <PreviewField icon={CircleUserRound} label="Best match" value="Evencio Pena" />
              <PreviewField icon={MapPin} label="Location signal" value="Boston, MA" />
            </div>
            <div className="mt-4 flex h-11 items-center justify-center gap-2 rounded-md bg-primary text-sm font-bold text-[#07100d] transition-transform duration-200 hover:scale-[1.01]">
              <Search className="size-4" />
              Search
            </div>
          </div>

          <div className="rounded-md border border-white/10 bg-[#17202f]/90 transition-all duration-300">
            <div className="flex flex-col gap-3 border-b border-white/10 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <div className="grid size-11 place-items-center rounded-full bg-gradient-to-br from-cyan-400 to-emerald-400">
                  <CircleUserRound className="size-6 text-[#07100d]" />
                </div>
                <div>
                  <h3 className="text-2xl font-extrabold text-white">Evencio Pena</h3>
                  <p className="text-sm text-muted-foreground">Age: 80 · Verified match</p>
                </div>
              </div>
              <div className="rounded-md border border-primary/35 bg-primary/10 px-3 py-2 text-sm font-bold text-primary animate-glow">
                <AnimatedNumber value={activeMode === "address" ? 91 : activeMode === "name" ? 94 : 97} />% confidence
              </div>
            </div>

            <div className="grid gap-3 p-4 md:grid-cols-3">
              <RecordSignal icon={Phone} title="Primary phone" value="(617) 541-2753" />
              <RecordSignal icon={MapPin} title="Primary address" value="Boston, MA 02118" />
              <RecordSignal icon={Gauge} title="Related records" value="53 graph links" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PreviewField({
  icon: Icon,
  label,
  value,
  active = false,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  active?: boolean;
}) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.045] p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className={active ? "size-3.5 text-primary" : "size-3.5"} />
        {label}
      </div>
      <p className="mt-1 text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

function RecordSignal({
  icon: Icon,
  title,
  value,
}: {
  icon: LucideIcon;
  title: string;
  value: string;
}) {
  return (
    <div className="min-h-28 rounded-md border border-white/10 bg-[#111b2d] p-4">
      <div className="mb-3 flex items-center gap-2 text-xs font-bold text-muted-foreground">
        <Icon className="size-4 text-primary" />
        {title}
      </div>
      <p className="text-sm font-semibold leading-6 text-white">{value}</p>
    </div>
  );
}

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(value);

  useEffect(() => {
    const start = display;
    const difference = value - start;
    let frame = 0;
    const totalFrames = 18;

    const timer = window.setInterval(() => {
      frame += 1;
      const progress = frame / totalFrames;
      setDisplay(Math.round(start + difference * progress));
      if (frame >= totalFrames) window.clearInterval(timer);
    }, 18);

    return () => window.clearInterval(timer);
  }, [value]);

  return <span>{display}</span>;
}
