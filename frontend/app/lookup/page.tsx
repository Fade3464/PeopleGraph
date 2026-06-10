"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import {
  Activity,
  BadgeCheck,
  ChevronDown,
  CircleUserRound,
  Clock3,
  Fingerprint,
  Gauge,
  Home,
  Loader2,
  LocateFixed,
  MapPin,
  Menu,
  Phone,
  Search,
  ShieldCheck,
  Sparkles,
  UsersRound,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type SearchMode = "phone" | "person";
type SearchState = "ready" | "loading" | "results" | "empty" | "error";

const people = [
  {
    id: "evencio-pena",
    name: "Evencio Pena",
    age: "80",
    confidence: "97%",
    phone: "(617) 541-2753",
    phoneType: "Landline/Services",
    address: "35 Brannon Harris Way, Boston, MA, 02118",
    stats: { phones: 2, addresses: 5, relatives: 46 },
    aliases: ["Herencio Pena", "Euencio Pena", "Pena Evencio", "Evencio Pena", "Herencio Pena"],
    updated: "Verified 2 days ago",
  },
  {
    id: "h-pena",
    name: "H Pena",
    age: "Age not found",
    confidence: "84%",
    phone: "(617) 541-2753",
    phoneType: "LandLine/Services",
    address: "35 Brannon Harris Way, Boston, MA, 02118",
    stats: { phones: 1, addresses: 1, relatives: 0 },
    aliases: ["H Pena", "Pena H"],
    updated: "Matched by address",
  },
  {
    id: "henry-pena",
    name: "Henry Pena",
    age: "76",
    confidence: "76%",
    phone: "(617) 541-2753",
    phoneType: "Residential line",
    address: "Roxbury Crossing, MA, 02120",
    stats: { phones: 3, addresses: 4, relatives: 12 },
    aliases: ["H Pena", "Hen Pena", "Henry P"],
    updated: "Historical record",
  },
];

const activity = [
  "Phone endpoint normalized query",
  "Address confidence scored",
  "Alias graph expanded",
  "Mock data rendered",
];

export default function HomePage() {
  const [mode, setMode] = useState<SearchMode>("phone");
  const [state, setState] = useState<SearchState>("ready");
  const [phone, setPhone] = useState("");
  const [fullName, setFullName] = useState("");
  const [location, setLocation] = useState("");
  const [selected, setSelected] = useState(people[0]);

  const queryLabel = useMemo(() => {
    if (mode === "phone") return phone || "(617) 541-2753";
    return [fullName || "Evencio Pena", location || "Boston, MA"].join(" in ");
  }, [fullName, location, mode, phone]);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("loading");

    window.setTimeout(() => {
      const combined = `${phone} ${fullName} ${location}`.toLowerCase();
      if (combined.includes("error")) {
        setState("error");
        return;
      }
      if (combined.includes("empty") || combined.includes("unknown")) {
        setState("empty");
        return;
      }
      setState("results");
      setSelected(people[0]);
    }, 700);
  }

  return (
    <main className="min-h-screen overflow-hidden">
      <TopNav />
      <div className="mx-auto flex w-full max-w-[1480px] gap-0 px-3 pb-10 pt-3 sm:px-5 lg:gap-6">
        <Sidebar />
        <section className="min-w-0 flex-1">
          <Header />
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
            <div className="space-y-5">
              <SearchPanel
                mode={mode}
                setMode={setMode}
                phone={phone}
                setPhone={setPhone}
                fullName={fullName}
                setFullName={setFullName}
                location={location}
                setLocation={setLocation}
                onSubmit={submitSearch}
                state={state}
              />
              <StatusPanel state={state} queryLabel={queryLabel} />
              {state === "results" ? (
                <ResultsList selectedId={selected.id} onSelect={setSelected} />
              ) : null}
            </div>
            <InsightPanel selected={selected} state={state} />
          </div>
        </section>
      </div>
    </main>
  );
}

function TopNav() {
  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-[#111316]/92 shadow-panel backdrop-blur-xl">
      <div className="flex h-14 items-center gap-3 px-4">
        <Button variant="ghost" size="icon" aria-label="Open navigation" className="lg:hidden">
          <Menu />
        </Button>
        <Link
          href="/"
          aria-label="Go to PeopleGraph landing page"
          className="flex items-center gap-2 rounded-md transition-opacity hover:opacity-85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <div className="grid size-8 place-items-center rounded-md bg-gradient-to-br from-cyan-400 to-emerald-400 shadow-teal">
            <Fingerprint className="size-5 text-[#07100d]" />
          </div>
          <span className="text-xl font-extrabold tracking-normal">PeopleGraph</span>
        </Link>
        <div className="ml-auto hidden items-center gap-2 rounded-md border border-white/10 bg-white/8 px-3 py-2 text-sm text-muted-foreground md:flex">
          <Search className="size-4" />
          Search people, phones, addresses
        </div>
      </div>
    </header>
  );
}

function Sidebar() {
  const links = [
    ["Lookup", Search],
    ["Records", UsersRound],
    ["Verification", ShieldCheck],
    ["Activity", Activity],
  ] as const;

  return (
    <aside className="sticky top-17 hidden h-[calc(100vh-4.5rem)] w-60 shrink-0 rounded-md border border-white/10 bg-[#121417]/90 p-3 shadow-panel lg:block">
      <div className="mb-4 rounded-md border border-white/10 bg-white/5 p-3">
        <p className="text-xs uppercase text-muted-foreground">Workspace</p>
        <p className="mt-1 font-semibold">Production Search</p>
      </div>
      <nav className="space-y-1">
        {links.map(([label, Icon], index) => (
          <button
            key={label}
            className={cn(
              "flex h-11 w-full items-center gap-3 rounded-md px-3 text-left text-sm font-semibold transition-all hover:bg-white/8",
              index === 0 ? "bg-white/10 text-primary" : "text-muted-foreground",
            )}
          >
            <Icon className="size-4" />
            {label}
          </button>
        ))}
      </nav>
      <div className="absolute bottom-3 left-3 right-3 rounded-md border border-primary/30 bg-primary/10 p-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-primary">
          <Sparkles className="size-4" />
          API Ready
        </div>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          Search logic can plug into this interface when the endpoint is ready.
        </p>
      </div>
    </aside>
  );
}

function Header() {
  return (
    <div className="mb-5 flex flex-col gap-4 rounded-md border border-white/10 bg-[#14161a]/80 px-4 py-5 shadow-panel sm:px-6 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <p className="text-sm font-semibold text-primary">People intelligence portal</p>
        <h1 className="mt-1 text-3xl font-extrabold tracking-normal sm:text-4xl">PeopleGraph Lookup</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
          Search by phone number, full name, or address and review identity signals in a clean operational workspace.
        </p>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        {[
          ["3", "Mock matches"],
          ["97%", "Top confidence"],
          ["53", "Graph links"],
        ].map(([value, label]) => (
          <div key={label} className="rounded-md border border-white/10 bg-white/6 px-4 py-3">
            <p className="text-lg font-bold text-primary">{value}</p>
            <p className="text-xs text-muted-foreground">{label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

type SearchPanelProps = {
  mode: SearchMode;
  setMode: (mode: SearchMode) => void;
  phone: string;
  setPhone: (value: string) => void;
  fullName: string;
  setFullName: (value: string) => void;
  location: string;
  setLocation: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  state: SearchState;
};

function SearchPanel(props: SearchPanelProps) {
  const {
    mode,
    setMode,
    phone,
    setPhone,
    fullName,
    setFullName,
    location,
    setLocation,
    onSubmit,
    state,
  } = props;

  return (
    <form onSubmit={onSubmit} className="glass-panel animate-fade-up rounded-md p-4 sm:p-5">
      <div className="grid grid-cols-2 border-b border-white/10">
        {[
          ["phone", "Phone Number", Phone],
          ["person", "Name & Address", LocateFixed],
        ].map(([value, label, Icon]) => (
          <button
            key={value as string}
            type="button"
            onClick={() => setMode(value as SearchMode)}
            className={cn(
              "relative flex h-12 items-center justify-center gap-2 text-sm font-bold transition-colors",
              mode === value ? "text-primary" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="size-4" />
            {label as string}
            {mode === value ? <span className="teal-line absolute bottom-[-1px] h-0.5 w-full" /> : null}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {mode === "phone" ? (
          <label className="block">
            <span className="mb-2 block text-sm font-semibold">Phone Number</span>
            <div className="relative">
              <Phone className="absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                className="pl-11"
                placeholder="Enter phone number, e.g. 617-541-2753"
              />
            </div>
          </label>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-semibold">Full Name</span>
              <div className="relative">
                <CircleUserRound className="absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  className="pl-11"
                  placeholder="Enter full name, e.g. Evencio Pena"
                />
              </div>
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold">Address or Zip Code</span>
              <div className="relative">
                <MapPin className="absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={location}
                  onChange={(event) => setLocation(event.target.value)}
                  className="pl-11"
                  placeholder="City, state, street, or zip code"
                />
              </div>
            </label>
          </div>
        )}
      </div>

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock3 className="size-4 text-primary" />
          Prototype uses mock results until the Django endpoint is connected.
        </div>
        <Button type="submit" size="lg" disabled={state === "loading"} className="sm:min-w-36">
          {state === "loading" ? <Loader2 className="animate-spin" /> : <Search />}
          Search
        </Button>
      </div>
    </form>
  );
}

function StatusPanel({ state, queryLabel }: { state: SearchState; queryLabel: string }) {
  const content = {
    ready: {
      icon: Phone,
      title: "Ready to Search",
      body: "Enter a phone number, name, or address to preview the PeopleGraph result workspace.",
    },
    loading: {
      icon: Loader2,
      title: "Searching PeopleGraph",
      body: `Resolving identity signals for ${queryLabel}.`,
    },
    results: {
      icon: BadgeCheck,
      title: "3 Potential Matches",
      body: `Showing mock people records for ${queryLabel}.`,
    },
    empty: {
      icon: X,
      title: "No Records Found",
      body: "Try a broader location, alternate name spelling, or a normalized phone format.",
    },
    error: {
      icon: Gauge,
      title: "Search Could Not Complete",
      body: "The future API error state is ready for endpoint validation and retry handling.",
    },
  }[state];
  const Icon = content.icon;

  return (
    <section className="glass-panel animate-fade-up rounded-md p-6 text-center">
      <div className="mx-auto grid size-14 place-items-center rounded-full border border-white/10 bg-white/8">
        <Icon className={cn("size-7 text-primary", state === "loading" && "animate-spin")} />
      </div>
      <h2 className="mt-4 text-xl font-bold">{content.title}</h2>
      <p className="mx-auto mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">{content.body}</p>
    </section>
  );
}

function ResultsList({
  selectedId,
  onSelect,
}: {
  selectedId: string;
  onSelect: (person: (typeof people)[number]) => void;
}) {
  return (
    <section className="space-y-4">
      {people.map((person, index) => (
        <article
          key={person.id}
          className={cn(
            "animate-fade-up overflow-hidden rounded-md border bg-[#17202f]/92 transition-all duration-200 hover:-translate-y-1 hover:border-primary/55 hover:shadow-teal",
            selectedId === person.id ? "border-primary/60" : "border-white/12",
          )}
          style={{ animationDelay: `${index * 80}ms` }}
        >
          <div className="flex flex-col gap-4 border-b border-white/10 bg-white/5 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
            <button onClick={() => onSelect(person)} className="flex min-w-0 items-center gap-3 text-left">
              <div className="grid size-11 shrink-0 place-items-center rounded-full bg-gradient-to-br from-cyan-400 to-emerald-400">
                <CircleUserRound className="size-6 text-[#07100d]" />
              </div>
              <div className="min-w-0">
                <h3 className="truncate text-2xl font-extrabold tracking-normal">{person.name}</h3>
                <p className="text-sm text-muted-foreground">Age: {person.age}</p>
              </div>
            </button>
            <Button onClick={() => onSelect(person)}>
              <ChevronDown />
              View Full Details
            </Button>
          </div>

          <div className="grid gap-4 p-4 sm:p-5 lg:grid-cols-3">
            <InfoBox icon={Phone} title="Primary Phone">
              <p className="text-lg tracking-wide">{person.phone}</p>
              <p className="mt-1 text-sm text-muted-foreground">{person.phoneType}</p>
            </InfoBox>
            <InfoBox icon={MapPin} title="Primary Address" accent="text-primary">
              <p className="text-sm leading-6">{person.address}</p>
            </InfoBox>
            <InfoBox icon={Gauge} title="Quick Stats" accent="text-fuchsia-300">
              <div className="space-y-1 text-sm">
                <p>Phones: {person.stats.phones}</p>
                <p>Addresses: {person.stats.addresses}</p>
                <p>Relatives: {person.stats.relatives}</p>
              </div>
            </InfoBox>
          </div>

          <div className="mx-4 mb-4 rounded-md border border-white/12 bg-white/4 p-4 sm:mx-5 sm:mb-5">
            <div className="flex items-center gap-2 font-bold">
              <Sparkles className="size-4 text-yellow-300" />
              Also Known As
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {person.aliases.map((alias, aliasIndex) => (
                <span
                  key={`${person.id}-${alias}-${aliasIndex}`}
                  className={cn(
                    "rounded px-2.5 py-1 text-xs font-medium",
                    aliasIndex > 2 ? "bg-fuchsia-500/70" : "bg-amber-500/55",
                  )}
                >
                  {alias}
                </span>
              ))}
            </div>
          </div>
        </article>
      ))}
    </section>
  );
}

function InfoBox({
  icon: Icon,
  title,
  accent = "text-cyan-300",
  children,
}: {
  icon: typeof Phone;
  title: string;
  accent?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-28 rounded-md border border-white/12 bg-[#111b2d]/80 p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-bold">
        <Icon className={cn("size-4", accent)} />
        {title}
      </div>
      {children}
    </div>
  );
}

function InsightPanel({
  selected,
  state,
}: {
  selected: (typeof people)[number];
  state: SearchState;
}) {
  return (
    <aside className="glass-panel top-20 h-fit rounded-md p-5 xl:sticky">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-primary">Selected Record</p>
          <h2 className="mt-1 text-2xl font-extrabold tracking-normal">{selected.name}</h2>
        </div>
        <div className="grid size-12 place-items-center rounded-md bg-primary/15 text-primary">
          <CircleUserRound />
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3">
        <Metric value={selected.confidence} label="Confidence" />
        <Metric value={String(selected.stats.relatives)} label="Relatives" />
      </div>

      <div className="mt-5 rounded-md border border-white/10 bg-white/5 p-4">
        <div className="mb-3 flex items-center gap-2 font-bold">
          <Home className="size-4 text-primary" />
          Record Snapshot
        </div>
        <dl className="space-y-3 text-sm">
          <div>
            <dt className="text-muted-foreground">Phone</dt>
            <dd className="mt-1 font-medium">{selected.phone}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Address</dt>
            <dd className="mt-1 font-medium leading-6">{selected.address}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Status</dt>
            <dd className="mt-1 font-medium">{selected.updated}</dd>
          </div>
        </dl>
      </div>

      <div className="mt-5 rounded-md border border-white/10 bg-[#101820] p-4">
        <div className="mb-3 flex items-center gap-2 font-bold">
          <Activity className="size-4 text-cyan-300" />
          Search Pipeline
        </div>
        <div className="space-y-3">
          {activity.map((item, index) => (
            <div key={item} className="flex items-center gap-3 text-sm">
              <span
                className={cn(
                  "grid size-6 place-items-center rounded-full text-xs font-bold",
                  state === "loading" && index === 3
                    ? "bg-cyan-400 text-black"
                    : "bg-primary/18 text-primary",
                )}
              >
                {index + 1}
              </span>
              <span className="text-muted-foreground">{item}</span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-white/6 p-4 text-center">
      <p className="text-2xl font-extrabold text-primary">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{label}</p>
    </div>
  );
}
