"use client";

import Link from "next/link";
import {
  type CSSProperties,
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  BadgeCheck,
  Building2,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  CircleUserRound,
  Fingerprint,
  Gauge,
  Home,
  Info,
  LocateFixed,
  Mail,
  MapPin,
  MapPinned,
  Network,
  Phone,
  Search,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  UsersRound,
  X,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: HTMLElement,
        options: {
          sitekey: string;
          theme?: "light" | "dark" | "auto";
          size?: "normal" | "compact" | "flexible";
          callback?: (token: string) => void;
          "error-callback"?: () => void;
          "expired-callback"?: () => void;
          "timeout-callback"?: () => void;
        },
      ) => string;
      reset: (widgetId?: string) => void;
      remove: (widgetId: string) => void;
    };
  }
}

type SearchMode = "phone" | "person";
type SearchState = "ready" | "loading" | "results" | "empty" | "error";

type Nullable<T> = T | null | undefined;

type ToastState = {
  id: number;
  message: string;
  duration: number;
};

type AddressRecord = {
  street?: Nullable<string>;
  unit?: Nullable<string>;
  city?: Nullable<string>;
  state?: Nullable<string>;
  zip_code?: Nullable<string>;
  first_reported_date?: Nullable<string>;
  last_reported_date?: Nullable<string>;
  is_deliverable?: Nullable<boolean>;
  full_address?: Nullable<string>;
  house_number?: Nullable<string>;
  street_name?: Nullable<string>;
  street_type?: Nullable<string>;
  county?: Nullable<string>;
  latitude?: Nullable<number>;
  longitude?: Nullable<number>;
  neighbors?: unknown[];
};

type PhoneRecord = {
  phone_number?: Nullable<string>;
  phone_type?: Nullable<string>;
  company?: Nullable<string>;
  location_str?: Nullable<string>;
  is_connected?: Nullable<boolean>;
  first_reported_date?: Nullable<string>;
  last_reported_date?: Nullable<string>;
};

type EmailRecord = {
  email?: Nullable<string>;
  is_validated?: Nullable<boolean>;
  is_premium?: Nullable<boolean>;
  first_reported_date?: Nullable<string>;
  last_reported_date?: Nullable<string>;
};

type RelativeRecord = {
  first_name?: Nullable<string>;
  middle_name?: Nullable<string>;
  last_name?: Nullable<string>;
  relative_type?: Nullable<string>;
  spouse?: Nullable<boolean>;
  city?: Nullable<string>;
  state?: Nullable<string>;
};

type AssociateRecord = {
  full_name?: Nullable<string>;
  age?: Nullable<number>;
  is_public?: Nullable<boolean>;
};

type RawPersonRecord = {
  addresses?: AddressRecord[];
  phones?: PhoneRecord[];
  emails?: EmailRecord[];
  locations?: unknown[];
  relatives?: RelativeRecord[];
  associates?: AssociateRecord[];
  [key: string]: unknown;
};

type PaginationRecord = {
  currentPageNumber: number;
  resultsPerPage: number;
  totalPages: number;
  totalResults: number;
};

type PersonResult = {
  id: number | string;
  first_name?: Nullable<string>;
  middle_name?: Nullable<string>;
  last_name?: Nullable<string>;
  age?: Nullable<number>;

  addresses?: AddressRecord[];
  phones?: PhoneRecord[];
  emails?: EmailRecord[];
  locations?: unknown[];
  relatives?: RelativeRecord[];
  associates?: AssociateRecord[];

  raw?: RawPersonRecord;

  name?: Nullable<string>;
  confidence?: Nullable<string>;
  phone?: Nullable<string>;
  phone_type?: Nullable<string>;
  address?: Nullable<string>;
  stats?: {
    phones?: number;
    addresses?: number;
    emails?: number;
    relatives?: number;
    associates?: number;
  };
  updated?: Nullable<string>;

  [key: string]: unknown;
};

type LookupResponse = {
  status: string;
  message?: string;
  source?: "cache" | "upstream";
  query?: {
    [key: string]: string;
  };
  blacklist?: BlacklistResult;
  data?: {
    persons?: PersonResult[];
    result_count?: number;
    pagination?: PaginationRecord;
  };
};

type BlacklistResult = {
  status: string;
  message?: string;
  source?: "cache" | "upstream" | "error";
  phone_number: string;
  normalized_phone: string;
  bla_code: string;
  tcpa_status: string;
  summary_status: string;
  risk_category: string;
  status_array: string[];
  is_bad_number: boolean;
};

type ModeLookupState = {
  state: SearchState;
  validationMessage: string;
  lookupFeedback: string;
  phone: string;
  fullName: string;
  location: string;
  results: PersonResult[];
  blacklist: BlacklistResult | null;
  selected: PersonResult | null;
};

function createEmptyLookupState(): ModeLookupState {
  return {
    state: "ready",
    validationMessage: "",
    lookupFeedback: "",
    phone: "",
    fullName: "",
    location: "",
    results: [],
    blacklist: null,
    selected: null,
  };
}

export default function HomePage() {
  const elasticOffset = useElasticScroll();
  const [mode, setMode] = useState<SearchMode>("phone");
  const activeModeRef = useRef<SearchMode>("phone");
  const turnstileSiteKey = getRealTurnstileSiteKey();
  const resetTurnstileRef = useRef<() => void>(() => {});
  const [turnstileToken, setTurnstileToken] = useState("");
  const [turnstileError, setTurnstileError] = useState("");

  const [lookupByMode, setLookupByMode] = useState<Record<SearchMode, ModeLookupState>>(() => ({
    phone: createEmptyLookupState(),
    person: createEmptyLookupState(),
  }));

  const [toast, setToast] = useState<ToastState | null>(null);

  const activeLookup = lookupByMode[mode];

  useEffect(() => {
    activeModeRef.current = mode;
  }, [mode]);

  const updateModeLookup = useCallback(
    (targetMode: SearchMode, updater: (current: ModeLookupState) => ModeLookupState) => {
      setLookupByMode((current) => ({
        ...current,
        [targetMode]: updater(current[targetMode]),
      }));
    },
    [],
  );

  const updateActiveLookup = useCallback(
    (updater: (current: ModeLookupState) => ModeLookupState) => {
      updateModeLookup(mode, updater);
    },
    [mode, updateModeLookup],
  );

  const closeToast = useCallback(() => {
    setToast(null);
  }, []);

  const showTimedToast = useCallback((message: string, duration = 4500) => {
    setToast({
      id: Date.now(),
      message,
      duration,
    });
  }, []);

  const handleModeChange = useCallback(
    (nextMode: SearchMode) => {
      if (nextMode === mode) return;

      setMode(nextMode);
      setToast(null);
    },
    [mode],
  );

  const resetTurnstile = useCallback(() => {
    setTurnstileToken("");
    resetTurnstileRef.current();
  }, []);

  const handleTurnstileVerify = useCallback(
    (token: string) => {
      setTurnstileToken(token);
      setTurnstileError("");
      updateActiveLookup((current) => ({
        ...current,
        validationMessage: current.validationMessage.includes("security check") ? "" : current.validationMessage,
        lookupFeedback: "",
      }));
    },
    [updateActiveLookup],
  );

  const handleTurnstileExpire = useCallback(() => {
    setTurnstileToken("");
    setTurnstileError("Security check expired. Please complete it again.");
  }, []);

  const handleTurnstileError = useCallback(() => {
    setTurnstileToken("");
    setTurnstileError("Security check could not load. Refresh or try again.");
  }, []);

  const registerTurnstileReset = useCallback((reset: () => void) => {
    resetTurnstileRef.current = reset;
  }, []);

  async function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const searchMode = mode;
    const currentLookup = lookupByMode[searchMode];

    const nextValidationMessage = validateSearch(
      searchMode,
      currentLookup.phone,
      currentLookup.fullName,
      currentLookup.location,
      turnstileSiteKey,
      turnstileToken,
    );

    updateModeLookup(searchMode, (current) => ({
      ...current,
      validationMessage: nextValidationMessage,
      lookupFeedback: "",
    }));

    if (nextValidationMessage) {
      updateModeLookup(searchMode, (current) => ({
        ...current,
        state: "error",
        selected: null,
        results: [],
        blacklist: null,
      }));
      setToast(null);
      return;
    }

    updateModeLookup(searchMode, (current) => ({
      ...current,
      state: "loading",
      validationMessage: "",
      lookupFeedback: "",
      selected: null,
      results: [],
      blacklist: null,
    }));
    setToast(null);

    try {
      const endpoint =
        searchMode === "phone"
          ? `${getApiBaseUrl()}/api/v1/lookups/phone/`
          : `${getApiBaseUrl()}/api/v1/lookups/name-address/`;

      const requestBody =
        searchMode === "phone"
          ? { phone_number: currentLookup.phone.trim(), turnstile_token: turnstileToken }
          : {
              full_name: currentLookup.fullName.trim(),
              address_or_zip: currentLookup.location.trim(),
              turnstile_token: turnstileToken,
            };

      const [response] = await Promise.all([
        fetch(endpoint, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(requestBody),
        }),
        sleep(1500),
      ]);

      const payload = (await response.json().catch(() => null)) as LookupResponse | null;

      if (!response.ok) {
        resetTurnstile();
        updateModeLookup(searchMode, (current) => ({
          ...current,
          state: "error",
          lookupFeedback:
            payload?.message || "Search could not complete. Please review the number and try again.",
        }));
        return;
      }

      const persons = payload?.data?.persons ?? [];
      const totalMatches =
        payload?.data?.pagination?.totalResults ?? payload?.data?.result_count ?? persons.length;

      updateModeLookup(searchMode, (current) => ({
        ...current,
        state: persons.length > 0 ? "results" : "empty",
        results: persons,
        blacklist: searchMode === "phone" ? payload?.blacklist ?? null : null,
        selected: persons[0] ?? null,
        lookupFeedback:
          persons.length > 0
            ? ""
            : payload?.message || "No records found. Try a normalized phone format or verify the number.",
      }));

      if (persons.length > 0 && activeModeRef.current === searchMode) {
        showTimedToast(`${totalMatches} potential match${totalMatches === 1 ? "" : "es"} found.`);
      }

      resetTurnstile();
    } catch {
      resetTurnstile();
      updateModeLookup(searchMode, (current) => ({
        ...current,
        state: "error",
        lookupFeedback: "The lookup service is unavailable right now. Please try again shortly.",
      }));
    }
  }

  function resetSearch() {
    updateActiveLookup(() => createEmptyLookupState());
    resetTurnstile();
    setToast(null);
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#080b10] text-foreground">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_top_left,_rgba(45,212,191,0.16),_transparent_32rem),radial-gradient(circle_at_top_right,_rgba(34,211,238,0.12),_transparent_30rem)]" />

      <TopNav />
      <TimedToast toast={toast} onClose={closeToast} />
      <LookupLoader isVisible={activeLookup.state === "loading"} />

      <div
        className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-[1480px] transform-gpu justify-center px-3 pb-10 pt-8 will-change-transform sm:px-5 lg:px-8"
        style={{ transform: `translate3d(0, ${elasticOffset}px, 0)` }}
      >
        <section className="w-full max-w-6xl space-y-6">
          <SearchPanel
            mode={mode}
            setMode={handleModeChange}
            phone={activeLookup.phone}
            setPhone={(value) => {
              updateActiveLookup((current) => ({
                ...current,
                phone: value,
                validationMessage: "",
                lookupFeedback: "",
              }));
            }}
            fullName={activeLookup.fullName}
            setFullName={(value) => {
              updateActiveLookup((current) => ({
                ...current,
                fullName: value,
                validationMessage: "",
                lookupFeedback: "",
              }));
            }}
            location={activeLookup.location}
            setLocation={(value) => {
              updateActiveLookup((current) => ({
                ...current,
                location: value,
                validationMessage: "",
                lookupFeedback: "",
              }));
            }}
            onSubmit={submitSearch}
            onReset={resetSearch}
            state={activeLookup.state}
            validationMessage={activeLookup.validationMessage}
            lookupFeedback={activeLookup.lookupFeedback}
            turnstileSiteKey={turnstileSiteKey}
            turnstileToken={turnstileToken}
            turnstileError={turnstileError}
            onTurnstileVerify={handleTurnstileVerify}
            onTurnstileExpire={handleTurnstileExpire}
            onTurnstileError={handleTurnstileError}
            registerTurnstileReset={registerTurnstileReset}
          />

          {activeLookup.state !== "results" && activeLookup.blacklist ? (
            <section className="mt-6">
              <BlacklistPanel blacklist={activeLookup.blacklist} />
            </section>
          ) : null}

          {activeLookup.state === "results" ? (
            <ResultsList
              people={activeLookup.results}
              selectedId={activeLookup.selected?.id}
              onSelect={(person) => {
                updateActiveLookup((current) => ({
                  ...current,
                  selected: person,
                }));
              }}
              blacklist={activeLookup.blacklist}
            />
          ) : null}
        </section>
      </div>
    </main>
  );
}

function useElasticScroll() {
  const [offset, setOffset] = useState(0);
  const offsetRef = useRef(0);
  const velocityRef = useRef(0);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) return;

    function animate() {
      offsetRef.current += velocityRef.current;
      velocityRef.current *= 0.72;
      offsetRef.current *= 0.82;

      if (Math.abs(offsetRef.current) < 0.08 && Math.abs(velocityRef.current) < 0.08) {
        offsetRef.current = 0;
        velocityRef.current = 0;
        setOffset(0);
        frameRef.current = null;
        return;
      }

      setOffset(offsetRef.current);
      frameRef.current = window.requestAnimationFrame(animate);
    }

    function startAnimation() {
      if (frameRef.current === null) {
        frameRef.current = window.requestAnimationFrame(animate);
      }
    }

    function handleWheel(event: WheelEvent) {
      const documentElement = document.documentElement;
      const scrollTop = window.scrollY || documentElement.scrollTop;
      const maxScrollTop = Math.max(0, documentElement.scrollHeight - window.innerHeight);

      const isAtTop = scrollTop <= 0;
      const isAtBottom = scrollTop >= maxScrollTop - 1;

      const isPullingPastTop = isAtTop && event.deltaY < 0;
      const isPushingPastBottom = isAtBottom && event.deltaY > 0;

      if (!isPullingPastTop && !isPushingPastBottom) {
        return;
      }

      const nextVelocity = Math.max(-4.5, Math.min(4.5, -event.deltaY * 0.018));
      velocityRef.current += nextVelocity;
      offsetRef.current = Math.max(-18, Math.min(18, offsetRef.current));
      startAnimation();
    }

    window.addEventListener("wheel", handleWheel, { passive: true });

    return () => {
      window.removeEventListener("wheel", handleWheel);
      if (frameRef.current !== null) {
        window.cancelAnimationFrame(frameRef.current);
      }
    };
  }, []);

  return offset;
}

function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
}

function getRealTurnstileSiteKey() {
  const siteKey = (process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "").trim();

  if (!siteKey || siteKey === "replace-with-real-cloudflare-sitekey" || siteKey.startsWith("1x000000")) {
    return "";
  }

  return siteKey;
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function validateSearch(
  mode: SearchMode,
  phone: string,
  fullName: string,
  location: string,
  turnstileSiteKey: string,
  turnstileToken: string,
) {
  const trimmedPhone = phone.trim();
  const digits = trimmedPhone.replace(/\D/g, "");

  if (mode === "phone") {
    if (!trimmedPhone) {
      return "Enter a valid phone number to start a lookup.";
    }

    if (digits.length < 9) {
      return "Enter a valid phone number with at least 9 digits.";
    }

    if (digits.length > 15) {
      return "Phone number looks too long. Use a valid national or international format.";
    }

    if (!turnstileSiteKey) {
      return "Security check is not configured. Add the Turnstile site key before searching.";
    }

    if (!turnstileToken) {
      return "Complete the security check before searching.";
    }

    return "";
  }

  const trimmedName = fullName.trim();
  const trimmedLocation = location.trim();

  if (!trimmedName) {
    return "Enter a full name to start a lookup.";
  }
if (/\d/.test(trimmedName)) {
  return "Name cannot contain numbers.";
}
  if (trimmedName.split(/\s+/).length < 2) {
    return "Enter both first and last name.";
  }

  if (!trimmedLocation) {
    return "Enter an address or zip code.";
  }

  if (trimmedLocation.length < 3) {
    return "Enter a more specific address or zip code.";
  }

  if (!turnstileSiteKey) {
    return "Security check is not configured. Add the Turnstile site key before searching.";
  }

  if (!turnstileToken) {
    return "Complete the security check before searching.";
  }

  return "";
}

function TopNav() {
  return (
    <header className="sticky top-0 z-30 border-b border-white/10 bg-[#111316]/95 shadow-panel backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1480px] items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link
          href="/"
          aria-label="Go to PeopleGraph"
          className="flex items-center gap-3 rounded-md transition-opacity hover:opacity-85 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <div className="grid size-9 place-items-center rounded-lg bg-gradient-to-br from-cyan-400 to-emerald-400 shadow-teal">
            <Fingerprint className="size-5 text-[#07100d]" />
          </div>

          <div>
            <span className="block text-xl font-extrabold tracking-tight">PeopleGraph</span>
          </div>
        </Link>
      </div>
    </header>
  );
}

function TimedToast({ toast, onClose }: { toast: ToastState | null; onClose: () => void }) {
  const [isLeaving, setIsLeaving] = useState(false);

  useEffect(() => {
    if (!toast) return;

    setIsLeaving(false);

    const fadeTimer = setTimeout(() => {
      setIsLeaving(true);
    }, toast.duration);

    const closeTimer = setTimeout(() => {
      onClose();
    }, toast.duration + 700);

    return () => {
      clearTimeout(fadeTimer);
      clearTimeout(closeTimer);
    };
  }, [toast, onClose]);

  if (!toast) return null;

  const toastStyle = {
    "--toast-duration": `${toast.duration}ms`,
  } as CSSProperties;

  return (
    <div
      role="status"
      aria-live="polite"
      style={toastStyle}
      className={cn(
        "fixed right-4 top-20 z-50 w-[calc(100vw-2rem)] max-w-sm overflow-hidden rounded-2xl border border-white/10 bg-[#101827]/95 text-sm shadow-panel backdrop-blur-xl transition-all duration-700",
        isLeaving ? "translate-y-2 opacity-0" : "translate-y-0 opacity-100",
      )}
    >
      <div className="absolute inset-x-0 bottom-0 h-px bg-white/10">
        <div className="toast-countdown-line h-full bg-primary" />
      </div>

      <div className="flex items-start gap-3 p-4">
        <div className="grid size-10 shrink-0 place-items-center rounded-xl border border-primary/20 bg-primary/10">
          <BadgeCheck className="size-5 text-primary" />
        </div>

        <div className="min-w-0 flex-1">
          <p className="font-bold text-foreground">Lookup completed</p>
          <p className="mt-1 text-sm text-muted-foreground">{toast.message}</p>
        </div>

        <button
          type="button"
          onClick={() => {
            setIsLeaving(true);
            window.setTimeout(onClose, 250);
          }}
          className="rounded-md p-1 text-muted-foreground transition hover:bg-white/10 hover:text-foreground"
          aria-label="Close notification"
        >
          <X className="size-4" />
        </button>
      </div>

      <style>{`
        .toast-countdown-line {
          width: 100%;
          animation: toastLineCountdown var(--toast-duration) linear forwards;
        }

        @keyframes toastLineCountdown {
          from {
            width: 100%;
            opacity: 1;
          }
          to {
            width: 0%;
            opacity: 0.25;
          }
        }
      `}</style>
    </div>
  );
}

function LookupLoader({ isVisible }: { isVisible: boolean }) {
  if (!isVisible) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-0 z-40 grid place-items-center bg-[#080b10]/55 px-4 backdrop-blur-sm"
    >
      <div className="relative w-full max-w-sm animate-loader-card-in overflow-hidden rounded-3xl border border-white/10 bg-[#101827]/95 p-6 text-center shadow-panel">
        <div className="pointer-events-none absolute inset-0 rounded-3xl bg-[radial-gradient(circle_at_top,_rgba(45,212,191,0.16),_transparent_18rem)]" />

        <div className="relative mx-auto grid size-28 place-items-center">
          <div className="absolute inset-0 rounded-full border border-primary/15" />
          <div className="absolute inset-3 rounded-full border border-white/10" />

          <div className="lookup-orbit lookup-orbit-one">
            <span />
          </div>

          <div className="lookup-orbit lookup-orbit-two">
            <span />
          </div>

          <div className="lookup-orbit lookup-orbit-three">
            <span />
          </div>

          <div className="relative grid size-16 place-items-center rounded-2xl border border-primary/20 bg-primary/10 shadow-teal">
            <Fingerprint className="size-8 animate-loader-pulse text-primary" />
          </div>
        </div>

        <div className="relative mt-5">
          <p className="text-lg font-extrabold tracking-tight text-foreground">Fingerprinting</p>

          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Graphing identity signals across phone, address, and profile records.
          </p>

          <div className="mt-5 flex items-center justify-center gap-2">
            <span className="lookup-bounce-dot" />
            <span className="lookup-bounce-dot animation-delay-150" />
            <span className="lookup-bounce-dot animation-delay-300" />
          </div>
        </div>

        <style>{`
          .animate-loader-card-in {
            animation: loaderCardIn 260ms ease-out both;
          }

          .lookup-orbit {
            position: absolute;
            inset: 0;
            border-radius: 9999px;
            animation: lookupOrbit 1.8s linear infinite;
          }

          .lookup-orbit span {
            position: absolute;
            left: 50%;
            top: -0.15rem;
            width: 0.55rem;
            height: 0.55rem;
            border-radius: 9999px;
            background: hsl(var(--primary));
            box-shadow: 0 0 18px hsl(var(--primary) / 0.85);
            transform: translateX(-50%);
          }

          .lookup-orbit-one {
            animation-duration: 1.55s;
          }

          .lookup-orbit-two {
            inset: 0.65rem;
            animation-duration: 2.15s;
            animation-direction: reverse;
          }

          .lookup-orbit-two span {
            width: 0.45rem;
            height: 0.45rem;
            opacity: 0.75;
          }

          .lookup-orbit-three {
            inset: 1.35rem;
            animation-duration: 2.7s;
          }

          .lookup-orbit-three span {
            width: 0.35rem;
            height: 0.35rem;
            opacity: 0.55;
          }

          .animate-loader-pulse {
            animation: loaderPulse 1.35s ease-in-out infinite;
          }

          .lookup-bounce-dot {
            width: 0.45rem;
            height: 0.45rem;
            border-radius: 9999px;
            background: hsl(var(--primary));
            animation: lookupDotBounce 0.9s ease-in-out infinite;
          }

          .animation-delay-150 {
            animation-delay: 150ms;
          }

          .animation-delay-300 {
            animation-delay: 300ms;
          }

          @keyframes loaderCardIn {
            from {
              opacity: 0;
              transform: translateY(10px) scale(0.97);
            }
            to {
              opacity: 1;
              transform: translateY(0) scale(1);
            }
          }

          @keyframes lookupOrbit {
            from {
              transform: rotate(0deg);
            }
            to {
              transform: rotate(360deg);
            }
          }

          @keyframes loaderPulse {
            0%, 100% {
              opacity: 0.8;
              transform: scale(1);
            }
            50% {
              opacity: 1;
              transform: scale(1.08);
            }
          }

          @keyframes lookupDotBounce {
            0%, 100% {
              opacity: 0.35;
              transform: translateY(0);
            }
            50% {
              opacity: 1;
              transform: translateY(-0.35rem);
            }
          }
        `}</style>
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
  onReset: () => void;
  state: SearchState;
  validationMessage: string;
  lookupFeedback: string;
  turnstileSiteKey: string;
  turnstileToken: string;
  turnstileError: string;
  onTurnstileVerify: (token: string) => void;
  onTurnstileExpire: () => void;
  onTurnstileError: () => void;
  registerTurnstileReset: (reset: () => void) => void;
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
    onReset,
    state,
    validationMessage,
    lookupFeedback,
    turnstileSiteKey,
    turnstileToken,
    turnstileError,
    onTurnstileVerify,
    onTurnstileExpire,
    onTurnstileError,
    registerTurnstileReset,
  } = props;

  const [showPhoneHint, setShowPhoneHint] = useState(false);
  const phoneHintTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const phoneFormatHint = "Use national or international format. Spaces, dashes, and parentheses are accepted.";
  const feedbackMessage = validationMessage || lookupFeedback;
  const isErrorFeedback = Boolean(validationMessage) || state === "error";
  const lookupInputClass =
  "h-12 border-white/10 bg-[#2f343a] text-foreground placeholder:text-slate-400 shadow-none transition-colors focus-visible:border-primary/60 focus-visible:bg-[#343a42] focus-visible:ring-primary/30";

  useEffect(() => {
    return () => {
      if (phoneHintTimerRef.current) {
        clearTimeout(phoneHintTimerRef.current);
      }
    };
  }, []);

  function startPhoneHintTimer() {
    if (phoneHintTimerRef.current) {
      clearTimeout(phoneHintTimerRef.current);
    }

    phoneHintTimerRef.current = setTimeout(() => {
      setShowPhoneHint(true);
    }, 2000);
  }

  function stopPhoneHintTimer() {
    if (phoneHintTimerRef.current) {
      clearTimeout(phoneHintTimerRef.current);
    }

    setShowPhoneHint(false);
  }

  const tabs: Array<{
    value: SearchMode;
    label: string;
    helper: string;
    Icon: LucideIcon;
  }> = [
    {
      value: "phone",
      label: "Phone Number",
      helper: "Available now",
      Icon: Phone,
    },
    {
      value: "person",
      label: "Name & Address",
      helper: "Available now",
      Icon: LocateFixed,
    },
  ];

  return (
    <form onSubmit={onSubmit} className="glass-panel animate-fade-up rounded-2xl p-4 sm:p-5">
      <div className="grid gap-2 rounded-xl border border-white/10 bg-[#0d131d]/80 p-1 sm:grid-cols-2">
        {tabs.map(({ value, label, helper, Icon }) => (
          <button
            key={value}
            type="button"
            onClick={() => {
              setMode(value);
            }}
            className={cn(
              "flex items-center justify-between gap-3 rounded-lg px-4 py-3 text-left transition-all",
              mode === value
                ? "bg-white/10 text-foreground shadow-sm"
                : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
            )}
            aria-pressed={mode === value}
          >
            <span className="flex items-center gap-3">
              <span
                className={cn(
                  "grid size-9 place-items-center rounded-lg border border-white/10 bg-white/5",
                  mode === value && "border-primary/30 bg-primary/10",
                )}
              >
                <Icon className={cn("size-4", mode === value ? "text-primary" : "text-muted-foreground")} />
              </span>

              <span>
                <span className="block text-sm font-bold">{label}</span>
                <span className="block text-xs text-muted-foreground">{helper}</span>
              </span>
            </span>
          </button>
        ))}
      </div>

      <div className="mt-5">
        {mode === "phone" ? (
          <label className="block">
            <span className="mb-2 block text-sm font-semibold">Phone Number</span>

            <div
              className="relative"
              onMouseEnter={startPhoneHintTimer}
              onMouseLeave={stopPhoneHintTimer}
              onFocus={startPhoneHintTimer}
              onBlur={stopPhoneHintTimer}
            >
              <Phone className="absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />

              <Input
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                className={cn(
  lookupInputClass,
  "pl-11 text-base",
  feedbackMessage && isErrorFeedback && "border-rose-400/70",
)}
                placeholder="Enter phone number"
                inputMode="tel"
                autoComplete="tel"
                aria-invalid={Boolean(feedbackMessage && isErrorFeedback)}
                aria-describedby={showPhoneHint ? "phone-format-tooltip" : undefined}
              />

              {showPhoneHint ? (
                <div
                  id="phone-format-tooltip"
                  role="tooltip"
                  className="pointer-events-none absolute left-0 top-[calc(100%+0.75rem)] z-30 max-w-sm animate-fade-up rounded-xl border border-white/10 bg-[#101827]/95 px-3 py-2 text-xs leading-5 text-muted-foreground shadow-panel backdrop-blur-xl"
                >
                  {phoneFormatHint}
                </div>
              ) : null}
            </div>

            {feedbackMessage ? (
              <p
                className={cn(
                  "mt-2 flex items-center gap-2 text-sm",
                  isErrorFeedback ? "text-rose-300" : "text-amber-300",
                )}
              >
                {isErrorFeedback ? <XCircle className="size-4" /> : <Info className="size-4" />}
                {feedbackMessage}
              </p>
            ) : null}
          </label>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-semibold">Full Name</span>

              <div className="relative">
                <CircleUserRound className="absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />

                <Input
                  value={fullName}
                  onChange={(event) => {
  const valueWithoutDigits = event.target.value.replace(/\d/g, "");
  setFullName(valueWithoutDigits);
}}
                  className={cn(
  lookupInputClass,
  "pl-11",
  feedbackMessage && isErrorFeedback && "border-rose-400/70",
)}
                  placeholder="Enter full name"
                  autoComplete="name"
                  aria-invalid={Boolean(feedbackMessage && isErrorFeedback)}
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
                  className={cn(
  lookupInputClass,
  "pl-11",
  feedbackMessage && isErrorFeedback && "border-rose-400/70",
)}
                  placeholder="City, state, street, or zip code"
                  autoComplete="street-address"
                  aria-invalid={Boolean(feedbackMessage && isErrorFeedback)}
                />
              </div>
            </label>
          </div>
        )}
      </div>

      {mode === "person" && feedbackMessage ? (
        <p
          className={cn(
            "mt-2 flex items-center gap-2 text-sm",
            isErrorFeedback ? "text-rose-300" : "text-amber-300",
          )}
        >
          {isErrorFeedback ? <XCircle className="size-4" /> : <Info className="size-4" />}
          {feedbackMessage}
        </p>
      ) : null}

      <TurnstileBox
        siteKey={turnstileSiteKey}
        token={turnstileToken}
        errorMessage={turnstileError}
        onVerify={onTurnstileVerify}
        onExpire={onTurnstileExpire}
        onError={onTurnstileError}
        registerReset={registerTurnstileReset}
      />

      <div className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <ShieldCheck className="size-4 text-primary" />
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <Button
            type="button"
            variant="ghost"
            onClick={onReset}
            disabled={state === "loading"}
            className="sm:min-w-28"
          >
            Clear
          </Button>

          <Button type="submit" size="lg" disabled={state === "loading"} className="sm:min-w-36">
            <Search className={cn(state === "loading" && "opacity-60")} />
            {state === "loading" ? "Searching..." : "Search"}
          </Button>
        </div>
      </div>
    </form>
  );
}

function TurnstileBox({
  siteKey,
  token,
  errorMessage,
  onVerify,
  onExpire,
  onError,
  registerReset,
}: {
  siteKey: string;
  token: string;
  errorMessage: string;
  onVerify: (token: string) => void;
  onExpire: () => void;
  onError: () => void;
  registerReset: (reset: () => void) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const widgetIdRef = useRef<string | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    registerReset(() => {
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.reset(widgetIdRef.current);
      }
    });
  }, [registerReset]);

  useEffect(() => {
    if (!siteKey) return;

    const existingScript = document.getElementById("cloudflare-turnstile-script") as HTMLScriptElement | null;

    function handleReady() {
      setIsReady(true);
    }

    if (window.turnstile) {
      handleReady();
      return;
    }

    if (existingScript) {
      existingScript.addEventListener("load", handleReady, { once: true });
      return () => existingScript.removeEventListener("load", handleReady);
    }

    const script = document.createElement("script");
    script.id = "cloudflare-turnstile-script";
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.async = true;
    script.defer = true;
    script.addEventListener("load", handleReady, { once: true });
    script.addEventListener("error", onError, { once: true });
    document.head.appendChild(script);

    return () => {
      script.removeEventListener("load", handleReady);
      script.removeEventListener("error", onError);
    };
  }, [onError, siteKey]);

  useEffect(() => {
    if (!isReady || !siteKey || !containerRef.current || !window.turnstile || widgetIdRef.current) return;

    widgetIdRef.current = window.turnstile.render(containerRef.current, {
      sitekey: siteKey,
      theme: "dark",
      size: "flexible",
      callback: onVerify,
      "expired-callback": onExpire,
      "timeout-callback": onExpire,
      "error-callback": onError,
    });

    return () => {
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
        widgetIdRef.current = null;
      }
    };
  }, [isReady, onError, onExpire, onVerify, siteKey]);

  return (
    <div className="mt-5">
      {siteKey ? (
        <div ref={containerRef} className="min-h-[65px] w-full max-w-[320px] overflow-hidden rounded-lg" />
      ) : (
        <p className="text-sm text-amber-300">Turnstile site key is not configured.</p>
      )}

      {errorMessage ? (
        <p className="mt-2 flex items-center gap-2 text-sm text-amber-300">
          <Info className="size-4" />
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}

function ResultsList({
  people,
  selectedId,
  onSelect,
  blacklist,
}: {
  people: PersonResult[];
  selectedId?: PersonResult["id"];
  onSelect: (person: PersonResult) => void;
  blacklist: BlacklistResult | null;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  function toggleDetails(person: PersonResult) {
    const personKey = String(person.id);

    onSelect(person);
    setExpandedId((current) => (current === personKey ? null : personKey));
  }

  return (
    <section className="space-y-4">
      <BlacklistPanel blacklist={blacklist} />

      {people.map((person, index) => {
        const personKey = String(person.id);
        const isExpanded = expandedId === personKey;
        const counts = getCounts(person);
        const primaryPhone = getPrimaryPhone(person);
        const primaryAddress = getPrimaryAddress(person);
        const detailsId = `person-details-${index}-${getDomId(personKey)}`;

        return (
          <article
            key={`${personKey}-${index}`}
            className={cn(
              "animate-fade-up overflow-hidden rounded-2xl border bg-[#101827]/95 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-teal",
              String(selectedId) === personKey ? "border-primary/60" : "border-white/10",
            )}
            style={{ animationDelay: `${Math.min(index * 50, 250)}ms` }}
          >
            <div className="flex flex-col gap-4 border-b border-white/10 bg-white/5 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
              <button
                type="button"
                onClick={() => onSelect(person)}
                className="flex min-w-0 items-center gap-3 text-left"
              >
                <div className="grid size-12 shrink-0 place-items-center rounded-full bg-gradient-to-br from-cyan-400 to-emerald-400 shadow-teal">
                  <CircleUserRound className="size-7 text-[#07100d]" />
                </div>

                <div className="min-w-0">
                  <h3 className="truncate text-2xl font-extrabold tracking-tight">{getPersonName(person)}</h3>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span>Age: {formatValue(person.age)}</span>
                    <span className="hidden sm:inline">•</span>
                    <span>Latest report: {getLatestReportedDate(person)}</span>
                  </div>
                </div>
              </button>

              <Button
                type="button"
                onClick={() => toggleDetails(person)}
                aria-expanded={isExpanded}
                aria-controls={detailsId}
                className="sm:min-w-44"
              >
                <ChevronDown className={cn("transition-transform", isExpanded && "rotate-180")} />
                {isExpanded ? "Toggle up" : "Insights"}
              </Button>
            </div>

            <div className="grid gap-4 p-4 sm:p-5 lg:grid-cols-3">
              <InfoBox icon={Phone} title="Primary Phone">
                <p className="font-mono text-lg tracking-wide">
                  {primaryPhone?.phone_number || person.phone || "Not found"}
                </p>

                <p className="mt-1 text-sm text-muted-foreground">
                  {[primaryPhone?.phone_type || person.phone_type, primaryPhone?.company].filter(Boolean).join(" · ") ||
                    "Unknown type"}
                </p>

                {primaryPhone ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {primaryPhone.location_str || "Unknown location"} ·{" "}
                    {primaryPhone.is_connected ? "Connected" : "Connection unknown"}
                  </p>
                ) : null}
              </InfoBox>

              <InfoBox icon={MapPin} title="Primary Address" accent="text-primary">
                <p className="text-sm leading-6">
                  {primaryAddress ? formatAddress(primaryAddress) : person.address || "Not found"}
                </p>

                {primaryAddress ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {primaryAddress.county || "Unknown county"} ·{" "}
                    {primaryAddress.is_deliverable ? "Deliverable" : "Deliverability unknown"}
                  </p>
                ) : null}
              </InfoBox>

              <InfoBox icon={Gauge} title="Record Coverage" accent="text-fuchsia-300">
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                  <p>Phones: {counts.phones}</p>
                  <p>Emails: {counts.emails}</p>
                  <p>Addresses: {counts.addresses}</p>
                  <p>Relatives: {counts.relatives}</p>
                  <p>Associates: {counts.associates}</p>
                </div>
              </InfoBox>
            </div>

            {isExpanded ? <FullDetailsPanel id={detailsId} person={person} /> : null}
          </article>
        );
      })}
    </section>
  );
}

function BlacklistPanel({ blacklist }: { blacklist: BlacklistResult | null }) {
  const [shouldShake, setShouldShake] = useState(false);

  useEffect(() => {
    if (!blacklist?.is_bad_number) {
      setShouldShake(false);
      return;
    }

    function triggerShake() {
      setShouldShake(false);

      window.setTimeout(() => {
        setShouldShake(true);
      }, 20);

      window.setTimeout(() => {
        setShouldShake(false);
      }, 780);
    }

    triggerShake();

    const interval = window.setInterval(triggerShake, 5000);

    return () => window.clearInterval(interval);
  }, [blacklist?.is_bad_number, blacklist?.normalized_phone, blacklist?.tcpa_status]);

  if (!blacklist) return null;

  const isRisky = blacklist.is_bad_number || Boolean(blacklist.status_array?.length);
  const hasDisallowedBlaCode = hasUnsafeBlaCode(blacklist.bla_code);
  const cardTone = hasDisallowedBlaCode ? "danger" : isRisky ? "warning" : "safe";
  const RiskIcon = blacklist.is_bad_number ? TriangleAlert : ShieldCheck;
  const tcpAStatus = blacklist.tcpa_status || blacklist.summary_status || "No TCPA status returned";

  return (
    <section
      className={cn(
        "rounded-2xl border p-4 shadow-panel sm:p-5",
        cardTone === "danger" && "border-rose-400/30 bg-rose-400/10",
        cardTone === "warning" && "border-amber-300/25 bg-amber-300/10",
        cardTone === "safe" && "border-emerald-300/20 bg-emerald-300/8",
        shouldShake && "risk-attention-shake",
      )}
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-3">
          <div
            className={cn(
              "grid size-11 shrink-0 place-items-center rounded-xl border",
              cardTone === "danger" && "border-rose-400/35 bg-rose-400/15",
              cardTone === "warning" && "border-amber-300/30 bg-amber-300/15",
              cardTone === "safe" && "border-emerald-300/25 bg-emerald-300/12",
            )}
          >
            <RiskIcon
              className={cn(
                "size-5",
                cardTone === "danger" && "text-rose-300",
                cardTone === "warning" && "text-amber-300",
                cardTone === "safe" && "text-emerald-300",
              )}
            />
          </div>

          <div>
            <p className="text-sm font-semibold text-muted-foreground">TCPA Blacklist Check</p>
            <h2 className="mt-1 text-xl font-extrabold tracking-tight">{tcpAStatus}</h2>
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-2 md:min-w-[28rem]">
          <MiniRiskFact label="BLA results" value={blacklist.bla_code || "none"} />
          <MiniRiskFact label="Risk category" value={blacklist.risk_category || "unknown"} />
        </div>
      </div>

      {blacklist.status === "error" && blacklist.message ? (
        <p className="mt-4 rounded-xl border border-rose-300/20 bg-rose-300/10 p-3 text-sm text-rose-200">
          {blacklist.message}
        </p>
      ) : null}
    </section>
  );
}

function hasUnsafeBlaCode(blaCode: string) {
  const allowedCodes = new Set(["federal-dnc", "none"]);
  const codes = blaCode
    .split(/[,\s|]+/)
    .map((code) => code.trim().toLowerCase())
    .filter(Boolean);

  return codes.length > 0 && codes.some((code) => !allowedCodes.has(code));
}

function MiniRiskFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-bold capitalize text-foreground">{value.replace(/_/g, " ")}</p>
    </div>
  );
}

function FullDetailsPanel({ id, person }: { id: string; person: PersonResult }) {
  const addresses = getPersonAddresses(person);
  const phones = getPersonPhones(person);
  const emails = getPersonEmails(person);
  const locations = getPersonLocations(person);
  const relatives = getPersonRelatives(person);
  const associates = getPersonAssociates(person);
  const counts = getCounts(person);

  return (
    <div id={id} className="border-t border-white/10 p-4 sm:p-5">
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="rounded-xl border border-white/10 bg-[#0f1724]/80 p-4">
          <div className="mb-3 flex items-center gap-2 font-bold">
            <Info className="size-4 text-cyan-300" />
            Profile Summary
          </div>

          <p className="text-sm leading-7 text-muted-foreground">{buildBiography(person)}</p>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#0f1724]/80 p-4">
          <div className="mb-3 flex items-center gap-2 font-bold">
            <Gauge className="size-4 text-fuchsia-300" />
            Coverage
          </div>

          <CoverageGrid counts={counts} locationCount={locations.length} />
        </div>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <DetailsSection icon={Phone} title={`Phone Numbers (${phones.length})`} accent="text-cyan-300">
          <div className="space-y-2">
            {phones.length ? (
              phones.map((item, index) => <PhoneCard key={`${person.id}-phone-${index}`} phone={item} />)
            ) : (
              <EmptyDetail message="No phone records returned." />
            )}
          </div>
        </DetailsSection>

        <DetailsSection icon={Mail} title={`Email Addresses (${emails.length})`} accent="text-emerald-400">
          <div className="space-y-2">
            {emails.length ? (
              emails.map((item, index) => <EmailCard key={`${person.id}-email-${index}`} email={item} />)
            ) : (
              <EmptyDetail message="No email records returned." />
            )}
          </div>
        </DetailsSection>
      </div>

      <DetailsSection
        icon={Home}
        title={`Known Addresses (${addresses.length})`}
        accent="text-violet-300"
        className="mt-5"
      >
        {addresses.length ? (
          <div className="grid gap-4 md:grid-cols-2">
            {addresses.map((item, index) => (
              <AddressCard key={`${person.id}-address-${index}`} address={item} />
            ))}
          </div>
        ) : (
          <EmptyDetail message="No address records returned." />
        )}
      </DetailsSection>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <DetailsSection icon={UsersRound} title={`Relatives (${relatives.length})`} accent="text-amber-300">
          <PeopleList
            emptyMessage="No relative records returned."
            people={relatives.map((relative) => ({
              title: getRelativeName(relative),
              subtitle: [
                relative.relative_type,
                relative.spouse ? "Spouse" : "",
                formatCityState(relative.city, relative.state),
              ]
                .filter(Boolean)
                .join(" · "),
            }))}
          />
        </DetailsSection>

        <DetailsSection icon={Network} title={`Associates (${associates.length})`} accent="text-fuchsia-300">
          <PeopleList
            emptyMessage="No associate records returned."
            people={associates.map((associate) => ({
              title: associate.full_name || "Unknown associate",
              subtitle: [`Age: ${formatValue(associate.age)}`, associate.is_public ? "Public" : "Private/Unknown"]
                .filter(Boolean)
                .join(" · "),
            }))}
          />
        </DetailsSection>
      </div>
    </div>
  );
}

function CoverageGrid({ counts, locationCount }: { counts: ReturnType<typeof getCounts>; locationCount: number }) {
  const coverage = [
    ["Addresses", counts.addresses],
    ["Phones", counts.phones],
    ["Emails", counts.emails],
    ["Relatives", counts.relatives],
    ["Associates", counts.associates],
    ["Locations", locationCount],
  ];

  return (
    <div className="grid grid-cols-2 gap-2">
      {coverage.map(([label, value]) => (
        <div key={label} className="rounded-lg border border-white/10 bg-white/5 p-3">
          <p className="text-lg font-extrabold text-primary">{value}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">{label}</p>
        </div>
      ))}
    </div>
  );
}

function PhoneCard({ phone }: { phone: PhoneRecord }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-sm tracking-wide">{phone.phone_number || "Unknown phone"}</p>
          <p className="mt-1 text-xs text-muted-foreground">{phone.phone_type || "Unknown type"}</p>
        </div>

        <BooleanBadge value={phone.is_connected} trueLabel="Connected" falseLabel="Disconnected" />
      </div>

      <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
        <MiniFact icon={Building2} label="Company" value={phone.company} />
        <MiniFact icon={MapPin} label="Location" value={phone.location_str} />
        <MiniFact icon={CalendarDays} label="First Reported" value={phone.first_reported_date} />
        <MiniFact icon={CalendarDays} label="Last Reported" value={phone.last_reported_date} />
      </div>
    </div>
  );
}

function EmailCard({ email }: { email: EmailRecord }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="break-all text-sm">{email.email || "Unknown email"}</p>
          <p className="mt-1 text-xs text-muted-foreground">{email.is_premium ? "Premium email" : "Standard email"}</p>
        </div>

        <BooleanBadge value={email.is_validated} trueLabel="Validated" falseLabel="Unvalidated" />
      </div>

      <div className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
        <MiniFact icon={Sparkles} label="Premium" value={email.is_premium ? "Yes" : "No"} />
        <MiniFact icon={ShieldCheck} label="Validated" value={email.is_validated ? "Yes" : "No"} />
        <MiniFact icon={CalendarDays} label="First Reported" value={email.first_reported_date} />
        <MiniFact icon={CalendarDays} label="Last Reported" value={email.last_reported_date} />
      </div>
    </div>
  );
}

function AddressCard({ address }: { address: AddressRecord }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold leading-6">{formatAddress(address)}</p>
          <p className="mt-1 text-xs text-muted-foreground">{address.county || "Unknown county"}</p>
        </div>

        <BooleanBadge value={address.is_deliverable} trueLabel="Deliverable" falseLabel="Not deliverable" />
      </div>

      <div className="mt-4 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
        <MiniFact icon={MapPin} label="Street" value={address.street} />
        <MiniFact icon={Home} label="Unit" value={address.unit} />
        <MiniFact icon={MapPinned} label="City/State" value={formatCityState(address.city, address.state)} />
        <MiniFact icon={MapPin} label="Zip" value={address.zip_code} />
        <MiniFact icon={Home} label="House Number" value={address.house_number} />
        <MiniFact icon={Home} label="Street Name" value={address.street_name} />
        <MiniFact icon={Home} label="Street Type" value={address.street_type} />
        <MiniFact icon={CalendarDays} label="First Reported" value={address.first_reported_date} />
        <MiniFact icon={CalendarDays} label="Last Reported" value={address.last_reported_date} />
        <MiniFact icon={MapPinned} label="Coordinates" value={formatCoordinates(address.latitude, address.longitude)} />
        <MiniFact icon={UsersRound} label="Neighbors" value={String(address.neighbors?.length ?? 0)} />
      </div>
    </div>
  );
}

function PeopleList({
  people,
  emptyMessage,
}: {
  people: Array<{ title: string; subtitle: string }>;
  emptyMessage: string;
}) {
  if (!people.length) return <EmptyDetail message={emptyMessage} />;

  return (
    <div className="max-h-96 space-y-2 overflow-auto pr-1">
      {people.map((person, index) => (
        <div key={`${person.title}-${index}`} className="rounded-xl border border-white/10 bg-white/5 p-3">
          <p className="text-sm font-semibold">{person.title}</p>
          <p className="mt-1 text-xs text-muted-foreground">{person.subtitle || "No additional details"}</p>
        </div>
      ))}
    </div>
  );
}

function DetailsSection({
  icon: Icon,
  title,
  accent = "text-cyan-300",
  className,
  children,
}: {
  icon: LucideIcon;
  title: string;
  accent?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={cn("rounded-2xl border border-white/10 bg-[#0f1724]/80 p-4", className)}>
      <div className="mb-4 flex items-center gap-2 font-bold">
        <Icon className={cn("size-4", accent)} />
        {title}
      </div>

      {children}
    </section>
  );
}

function EmptyDetail({ message }: { message: string }) {
  return <p className="rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-muted-foreground">{message}</p>;
}

function InfoBox({
  icon: Icon,
  title,
  accent = "text-cyan-300",
  children,
}: {
  icon: LucideIcon;
  title: string;
  accent?: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-28 rounded-xl border border-white/10 bg-[#0f1724]/80 p-4">
      <div className="mb-3 flex items-center gap-2 text-sm font-bold">
        <Icon className={cn("size-4", accent)} />
        {title}
      </div>

      {children}
    </div>
  );
}

function MiniFact({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: Nullable<string | number | boolean>;
}) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-white/10 bg-black/20 p-2">
      <Icon className="mt-0.5 size-3.5 shrink-0 text-primary" />

      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="break-words text-xs text-foreground">{formatValue(value)}</p>
      </div>
    </div>
  );
}

function BooleanBadge({
  value,
  trueLabel,
  falseLabel,
}: {
  value: Nullable<boolean>;
  trueLabel: string;
  falseLabel: string;
}) {
  const isTrue = value === true;
  const isUnknown = value === null || value === undefined;

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-1 text-[11px] font-semibold",
        isTrue && "border-emerald-400/20 bg-emerald-400/10 text-emerald-300",
        !isTrue && !isUnknown && "border-rose-400/20 bg-rose-400/10 text-rose-300",
        isUnknown && "border-white/10 bg-white/5 text-muted-foreground",
      )}
    >
      {isTrue ? <CheckCircle2 className="size-3" /> : <XCircle className="size-3" />}
      {isTrue ? trueLabel : isUnknown ? "Unknown" : falseLabel}
    </span>
  );
}

function getRawPerson(person: PersonResult): RawPersonRecord {
  return person.raw && typeof person.raw === "object" ? person.raw : {};
}

function getPersonAddresses(person: PersonResult): AddressRecord[] {
  const raw = getRawPerson(person);
  return person.addresses?.length ? person.addresses : raw.addresses ?? [];
}

function getPersonPhones(person: PersonResult): PhoneRecord[] {
  const raw = getRawPerson(person);
  return person.phones?.length ? person.phones : raw.phones ?? [];
}

function getPersonEmails(person: PersonResult): EmailRecord[] {
  const raw = getRawPerson(person);
  return person.emails?.length ? person.emails : raw.emails ?? [];
}

function getPersonLocations(person: PersonResult): unknown[] {
  const raw = getRawPerson(person);
  return person.locations?.length ? person.locations : raw.locations ?? [];
}

function getPersonRelatives(person: PersonResult): RelativeRecord[] {
  const raw = getRawPerson(person);
  return person.relatives?.length ? person.relatives : raw.relatives ?? [];
}

function getPersonAssociates(person: PersonResult): AssociateRecord[] {
  const raw = getRawPerson(person);
  return person.associates?.length ? person.associates : raw.associates ?? [];
}

function getPersonName(person: PersonResult) {
  if (person.name) return person.name;

  return [person.first_name, person.middle_name, person.last_name].filter(Boolean).join(" ") || `Person ${person.id}`;
}

function getRelativeName(relative: RelativeRecord) {
  return [relative.first_name, relative.middle_name, relative.last_name].filter(Boolean).join(" ") || "Unknown relative";
}

function getPrimaryPhone(person: PersonResult) {
  return getPersonPhones(person)[0] ?? null;
}

function getPrimaryAddress(person: PersonResult) {
  return getPersonAddresses(person)[0] ?? null;
}

function getCounts(person: PersonResult) {
  const phones = getPersonPhones(person);
  const emails = getPersonEmails(person);
  const addresses = getPersonAddresses(person);
  const relatives = getPersonRelatives(person);
  const associates = getPersonAssociates(person);
  const locations = getPersonLocations(person);

  return {
    phones: person.stats?.phones ?? phones.length,
    emails: person.stats?.emails ?? emails.length,
    addresses: person.stats?.addresses ?? addresses.length,
    relatives: person.stats?.relatives ?? relatives.length,
    associates: person.stats?.associates ?? associates.length,
    locations: locations.length,
  };
}

function formatAddress(address: Nullable<AddressRecord>) {
  if (!address) return "Not found";

  if (address.full_address) return address.full_address;

  const formattedAddress = [
    address.street,
    address.unit ? `Unit ${address.unit}` : "",
    formatCityState(address.city, address.state),
    address.zip_code,
  ]
    .filter(Boolean)
    .join(", ");

  return formattedAddress || "Not found";
}

function formatCityState(city: Nullable<string>, state: Nullable<string>) {
  return [city, state].filter(Boolean).join(", ");
}

function formatCoordinates(latitude: Nullable<number>, longitude: Nullable<number>) {
  if (latitude === null || latitude === undefined || longitude === null || longitude === undefined) {
    return "Not reported";
  }

  return `${latitude}, ${longitude}`;
}

function formatValue(value: Nullable<string | number | boolean>) {
  if (value === null || value === undefined || value === "") return "N/A";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function buildBiography(person: PersonResult) {
  const name = getPersonName(person);
  const age =
    typeof person.age === "number" ? `${name} is ${person.age} years old.` : `${name}'s age was not returned.`;

  const address = getPrimaryAddress(person);
  const phone = getPrimaryPhone(person);

  const addressText = address
    ? ` Their most recent address was ${formatAddress(address)}${
        address.first_reported_date ? `, first reported ${address.first_reported_date}` : ""
      }${address.last_reported_date ? ` and last reported ${address.last_reported_date}` : ""}.`
    : "";

  const phoneText = phone
    ? ` Their primary phone is ${phone.phone_number || "unknown"}${phone.phone_type ? ` which is ${phone.phone_type}` : ""}${
        phone.company ? ` through ${phone.company}` : ""
      }${phone.location_str ? `, ${phone.location_str}` : ""}.`
    : "";

  return `${age}${addressText}${phoneText}`;
}

function getLatestReportedDate(person: PersonResult) {
  const dates = [
    ...getPersonAddresses(person).map((item) => item.last_reported_date),
    ...getPersonPhones(person).map((item) => item.last_reported_date),
    ...getPersonEmails(person).map((item) => item.last_reported_date),
  ]
    .filter((value): value is string => Boolean(value))
    .sort();

  return dates.at(-1) ?? person.updated ?? "Not reported";
}

function getDomId(value: string) {
  return value.replace(/[^a-zA-Z0-9_-]/g, "-") || "record";
}
