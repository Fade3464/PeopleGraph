"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  Database,
  Download,
  Eye,
  Fingerprint,
  LayoutDashboard,
  Loader2,
  LogOut,
  Mail,
  Menu,
  MessageSquareText,
  Search,
  ShieldCheck,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type AdminTab = "dashboard" | "export-logs" | "feedbacks";
type AuthState = "checking" | "authenticated" | "unauthenticated";

type AdminUser = {
  username: string;
  email?: string;
  is_staff: boolean;
  is_superuser: boolean;
};

type DashboardSummary = {
  total_lookups: number;
  unique_phone_numbers: number;
  unique_public_ips: number;
};

type LookupCountPoint = {
  timestamp: string;
  label: string;
  count: number;
};

type PublicIpCount = {
  public_ip: string;
  total_lookups: number;
  unique_phone_numbers: number;
};

type DashboardPayload = {
  status: "success";
  timezone: string;
  range: {
    from: string;
    to: string;
    bucket_minutes: number;
  };
  summary: DashboardSummary;
  lookup_counts: LookupCountPoint[];
  public_ip_counts: PublicIpCount[];
};

type FeedbackRecord = {
  id: number;
  name: string;
  email: string;
  experience: string;
  areas: string[];
  feature: string;
  device: string;
  details: string;
  suggestion: string;
  page_url: string;
  public_ip: string;
  user_agent: string;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
};

type FeedbackListPayload = {
  status: "success";
  unread_count: number;
  feedbacks: FeedbackRecord[];
};

const navItems = [
  {
    id: "dashboard",
    label: "Dashboard",
    icon: LayoutDashboard,
  },
  {
    id: "export-logs",
    label: "Export Logs",
    icon: Download,
  },
  {
    id: "feedbacks",
    label: "Feedbacks",
    icon: MessageSquareText,
  },
] satisfies Array<{ id: AdminTab; label: string; icon: LucideIcon }>;

export default function AdministrationWorkspace() {
  const [activeTab, setActiveTab] = useState<AdminTab>("dashboard");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [user, setUser] = useState<AdminUser | null>(null);
  const [unreadFeedbackCount, setUnreadFeedbackCount] = useState(0);

  const activeNavItem = useMemo(
    () => navItems.find((item) => item.id === activeTab) ?? navItems[0],
    [activeTab],
  );

  useEffect(() => {
    async function checkSession() {
      try {
        const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/me/`, {
          credentials: "include",
          cache: "no-store",
        });
        const payload = (await response.json().catch(() => null)) as
          | { authenticated?: boolean; user?: AdminUser }
          | null;

        if (!response.ok || !payload?.authenticated || !payload.user?.is_staff) {
          setAuthState("unauthenticated");
          window.location.replace("/admininstration/login");
          return;
        }

        setUser(payload.user);
        setAuthState("authenticated");
        void refreshUnreadFeedbackCount();
      } catch {
        setAuthState("unauthenticated");
        window.location.replace("/admininstration/login");
      }
    }

    void checkSession();
  }, []);

  async function handleLogout() {
    try {
      const csrfToken = await refreshCsrfToken();
      await fetch(`${getApiBaseUrl()}/api/v1/auth/logout/`, {
        method: "POST",
        credentials: "include",
        headers: {
          "X-CSRFToken": csrfToken,
        },
      });
    } finally {
      window.location.assign("/admininstration/login");
    }
  }

  function selectTab(tab: AdminTab) {
    setActiveTab(tab);
    setIsSidebarOpen(false);
  }

  async function refreshUnreadFeedbackCount() {
    try {
      const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/feedbacks/`, {
        credentials: "include",
        cache: "no-store",
      });
      const payload = (await response.json().catch(() => null)) as FeedbackListPayload | null;
      if (response.ok && payload?.status === "success") {
        setUnreadFeedbackCount(payload.unread_count);
      }
    } catch {
      setUnreadFeedbackCount(0);
    }
  }

  if (authState === "checking") {
    return (
      <main className="grid min-h-screen place-items-center bg-[#0c0e10] px-4 text-foreground">
        <div className="glass-panel rounded-2xl p-6 text-center">
          <Loader2 className="mx-auto size-7 animate-spin text-primary" />
          <p className="mt-4 text-sm font-semibold text-muted-foreground">Verifying administration session...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#0c0e10] text-foreground">
      <div className="fixed inset-0 -z-10 bg-[radial-gradient(circle_at_84%_4%,rgba(31,240,170,0.14),transparent_30rem),radial-gradient(circle_at_12%_2%,rgba(13,186,230,0.10),transparent_30rem),linear-gradient(180deg,#101316_0%,#0c0e10_54%,#08090b_100%)]" />

      <div className="flex min-h-screen">
        <AdminSidebar
          activeTab={activeTab}
          isOpen={isSidebarOpen}
          onSelect={selectTab}
          onClose={() => setIsSidebarOpen(false)}
          onLogout={handleLogout}
          unreadFeedbackCount={unreadFeedbackCount}
        />

        <section className="min-w-0 flex-1">
          <header className="sticky top-0 z-30 border-b border-white/10 bg-[#101316]/90 backdrop-blur-xl">
            <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-8">
              <Button
                type="button"
                variant="secondary"
                size="icon"
                className="lg:hidden"
                onClick={() => setIsSidebarOpen(true)}
                aria-label="Open administration menu"
              >
                <Menu />
              </Button>

              <div className="min-w-0">
                <p className="text-xs font-bold uppercase tracking-[0.22em] text-primary">Administration</p>
                <h1 className="truncate text-xl font-extrabold tracking-normal text-white sm:text-2xl">
                  {activeNavItem.label}
                </h1>
              </div>

              <div className="ml-auto hidden items-center gap-2 md:flex">
                <Button asChild variant="secondary" size="sm">
                  <Link href="/lookup">
                    <Search />
                    Lookup
                  </Link>
                </Button>
                <Button asChild variant="outline" size="sm">
                  <a href="/admin/" target="_blank" rel="noreferrer">
                    Django Admin
                    <ArrowUpRight />
                  </a>
                </Button>
              </div>
            </div>
          </header>

          <div className="border-b border-white/10 bg-[#101316]/60 px-4 py-3 sm:px-6 lg:hidden">
            <div className="grid grid-cols-3 gap-2">
              {navItems.map((item) => (
                <MobileTabButton
                  key={item.id}
                  item={item}
                  isActive={activeTab === item.id}
                  onClick={() => selectTab(item.id)}
                  unreadFeedbackCount={unreadFeedbackCount}
                />
              ))}
            </div>
          </div>

          <div className="mx-auto w-full max-w-[1240px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
            <WelcomeStrip user={user} />

            {activeTab === "dashboard" ? (
              <DashboardPanel />
            ) : activeTab === "export-logs" ? (
              <ExportLogsPanel />
            ) : (
              <FeedbacksPanel onUnreadCountChange={setUnreadFeedbackCount} />
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function AdminSidebar({
  activeTab,
  isOpen,
  onSelect,
  onClose,
  onLogout,
  unreadFeedbackCount,
}: {
  activeTab: AdminTab;
  isOpen: boolean;
  onSelect: (tab: AdminTab) => void;
  onClose: () => void;
  onLogout: () => void;
  unreadFeedbackCount: number;
}) {
  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity lg:hidden",
          isOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClose}
      />

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[18rem] flex-col border-r border-white/10 bg-[#0f1317]/96 p-4 shadow-panel transition-transform duration-300 lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:translate-x-0",
          isOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center gap-3">
          <Link href="/" className="flex min-w-0 items-center gap-2">
            <div className="grid size-10 shrink-0 place-items-center rounded-md bg-gradient-to-br from-cyan-400 to-emerald-400 shadow-teal">
              <Fingerprint className="size-5 text-[#07100d]" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-lg font-extrabold tracking-normal text-white">PeopleGraph</p>
              <p className="text-xs font-semibold text-muted-foreground">Admin Console</p>
            </div>
          </Link>

          <Button type="button" variant="ghost" size="icon" className="ml-auto lg:hidden" onClick={onClose}>
            <X />
          </Button>
        </div>

        <nav className="mt-8 space-y-2">
          {navItems.map((item) => (
            <SidebarButton
              key={item.id}
              item={item}
              isActive={activeTab === item.id}
              onClick={() => onSelect(item.id)}
              unreadFeedbackCount={unreadFeedbackCount}
            />
          ))}
        </nav>

        <div className="mt-auto space-y-3 rounded-md border border-white/10 bg-white/[0.035] p-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
            <ShieldCheck className="size-4 text-primary" />
            Staff session active
          </div>
          <Button type="button" variant="secondary" className="w-full justify-start" onClick={onLogout}>
            <LogOut />
            Sign out
          </Button>
        </div>
      </aside>
    </>
  );
}

function SidebarButton({
  item,
  isActive,
  onClick,
  unreadFeedbackCount,
}: {
  item: (typeof navItems)[number];
  isActive: boolean;
  onClick: () => void;
  unreadFeedbackCount: number;
}) {
  const Icon = item.icon;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-3 rounded-md px-3 py-3 text-left text-sm font-bold transition-all",
        isActive
          ? "bg-primary text-primary-foreground shadow-teal"
          : "text-muted-foreground hover:bg-white/8 hover:text-foreground",
      )}
    >
      <Icon className="size-4" />
      <span className="min-w-0 flex-1">{item.label}</span>
      {item.id === "feedbacks" && unreadFeedbackCount > 0 ? (
        <span
          className={cn(
            "grid min-w-6 place-items-center rounded-full px-2 py-0.5 text-xs font-black",
            isActive ? "bg-[#07100d] text-primary" : "bg-primary text-primary-foreground",
          )}
        >
          {unreadFeedbackCount}
        </span>
      ) : null}
    </button>
  );
}

function MobileTabButton({
  item,
  isActive,
  onClick,
  unreadFeedbackCount,
}: {
  item: (typeof navItems)[number];
  isActive: boolean;
  onClick: () => void;
  unreadFeedbackCount: number;
}) {
  const Icon = item.icon;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex h-11 items-center justify-center gap-2 rounded-md border px-3 text-sm font-bold transition-all",
        isActive
          ? "border-primary/40 bg-primary text-primary-foreground"
          : "border-white/10 bg-white/[0.04] text-muted-foreground",
      )}
    >
      <Icon className="size-4" />
      <span>{item.label}</span>
      {item.id === "feedbacks" && unreadFeedbackCount > 0 ? (
        <span className="grid min-w-5 place-items-center rounded-full bg-primary-foreground/90 px-1.5 text-xs font-black text-[#07100d]">
          {unreadFeedbackCount}
        </span>
      ) : null}
    </button>
  );
}

function WelcomeStrip({ user }: { user: AdminUser | null }) {
  return (
    <section className="mb-6 rounded-2xl border border-white/10 bg-white/[0.045] p-4 shadow-panel sm:p-5">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-semibold text-primary">Welcome back</p>
          <h2 className="mt-1 text-2xl font-extrabold tracking-normal text-white">
            {user?.email || user?.username || "Administration user"}
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Manage PeopleGraph operations from a focused workspace. Dashboard and export tools will be wired next.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:min-w-72">
          <StatusBadge icon={ShieldCheck} label="Access" value={user?.is_superuser ? "Superuser" : "Staff"} />
          <StatusBadge icon={Activity} label="State" value="Online" />
        </div>
      </div>
    </section>
  );
}

function DashboardPanel() {
  const initialRange = getQuickRange(24);
  const [from, setFrom] = useState(initialRange.from);
  const [to, setTo] = useState(initialRange.to);
  const [activeQuickFilter, setActiveQuickFilter] = useState("24h");
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    void loadDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadDashboard(nextFrom = from, nextTo = to) {
    setState("loading");
    setMessage("");

    try {
      const params = new URLSearchParams({
        from: nextFrom,
        to: nextTo,
      });
      const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/dashboard/phone-lookups/?${params}`, {
        credentials: "include",
        cache: "no-store",
      });
      const payload = (await response.json().catch(() => null)) as
        | DashboardPayload
        | { message?: string; status?: string }
        | null;
      const isSuccessPayload =
        payload?.status === "success" &&
        "summary" in payload &&
        "lookup_counts" in payload &&
        "public_ip_counts" in payload;

      if (!response.ok || !isSuccessPayload) {
        setState("error");
        setMessage(getDashboardErrorMessage(payload));
        return;
      }

      setData(payload);
      setState("ready");
    } catch {
      setState("error");
      setMessage("Dashboard service is unavailable.");
    }
  }

  function applyQuickFilter(hours: number, key: string) {
    const range = getQuickRange(hours);
    setFrom(range.from);
    setTo(range.to);
    setActiveQuickFilter(key);
    void loadDashboard(range.from, range.to);
  }

  function handleRangeSubmit() {
    setActiveQuickFilter("custom");
    void loadDashboard();
  }

  const summary = data?.summary ?? {
    total_lookups: 0,
    unique_phone_numbers: 0,
    unique_public_ips: 0,
  };

  return (
    <section className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <AdminMetric icon={Search} label="Phone Lookups" value={formatNumber(summary.total_lookups)} />
        <AdminMetric icon={Database} label="Unique Numbers" value={formatNumber(summary.unique_phone_numbers)} />
        <AdminMetric icon={BarChart3} label="Public IPs" value={formatNumber(summary.unique_public_ips)} />
      </div>

      <section className="rounded-2xl border border-white/10 bg-[#101827]/90 p-4 shadow-panel sm:p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-primary">
              <CalendarClock className="size-4" />
              New York timezone
            </div>
            <h3 className="mt-2 text-xl font-extrabold tracking-normal text-white">Lookup volume</h3>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              Counts are based on `PhoneLookupAudit.timestamp` converted to America/New_York.
            </p>
          </div>

          <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto] xl:min-w-[42rem]">
            <DateTimeField label="From" value={from} onChange={setFrom} />
            <DateTimeField label="To" value={to} onChange={setTo} />
            <Button type="button" className="h-12 self-end" onClick={handleRangeSubmit} disabled={state === "loading"}>
              {state === "loading" ? <Loader2 className="animate-spin" /> : <Activity />}
              Apply
            </Button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {[
            ["6h", 6, "Last 6 hours"],
            ["24h", 24, "Last 24 hours"],
            ["7d", 24 * 7, "Last 7 days"],
            ["30d", 24 * 30, "Last 30 days"],
          ].map(([key, hours, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => applyQuickFilter(Number(hours), String(key))}
              className={cn(
                "rounded-md border px-3 py-2 text-sm font-bold transition-all",
                activeQuickFilter === key
                  ? "border-primary/40 bg-primary text-primary-foreground"
                  : "border-white/10 bg-white/[0.04] text-muted-foreground hover:bg-white/[0.08] hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {state === "error" ? (
          <p className="mt-4 rounded-md border border-rose-300/25 bg-rose-300/10 p-3 text-sm text-rose-200">
            {message}
          </p>
        ) : null}

        <div className="mt-5 h-[19rem] rounded-xl border border-white/10 bg-black/15 p-3">
          {state === "loading" && !data ? (
            <div className="grid h-full place-items-center text-sm font-semibold text-muted-foreground">
              <span className="inline-flex items-center gap-2">
                <Loader2 className="size-4 animate-spin text-primary" />
                Loading chart
              </span>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data?.lookup_counts ?? []} margin={{ left: -18, right: 8, top: 12, bottom: 0 }}>
                <defs>
                  <linearGradient id="lookupCountFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(153 88% 50%)" stopOpacity={0.34} />
                    <stop offset="95%" stopColor="hsl(153 88% 50%)" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
                <XAxis
                  dataKey="label"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: "rgba(255,255,255,0.58)", fontSize: 12 }}
                  minTickGap={28}
                />
                <YAxis
                  allowDecimals={false}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: "rgba(255,255,255,0.58)", fontSize: 12 }}
                />
                <Tooltip
                  cursor={{ stroke: "rgba(31,240,170,0.36)", strokeWidth: 1 }}
                  contentStyle={{
                    background: "#101827",
                    border: "1px solid rgba(255,255,255,0.12)",
                    borderRadius: "8px",
                    color: "#fff",
                  }}
                  labelStyle={{ color: "rgba(255,255,255,0.7)" }}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  name="Phone lookups"
                  stroke="hsl(153 88% 50%)"
                  strokeWidth={2}
                  fill="url(#lookupCountFill)"
                  activeDot={{ r: 5, fill: "hsl(153 88% 50%)", stroke: "#07100d", strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-white/10 bg-[#101827]/90 p-4 shadow-panel sm:p-5">
        <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="text-xl font-extrabold tracking-normal text-white">Phone numbers by public IP</h3>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              Ranked by total lookup requests in the selected New York time range.
            </p>
          </div>
          <p className="text-sm font-semibold text-primary">{data?.public_ip_counts.length ?? 0} IPs shown</p>
        </div>

        <div className="mt-4 overflow-hidden rounded-xl border border-white/10">
          <div className="grid grid-cols-[1fr_auto_auto] gap-3 bg-white/[0.045] px-4 py-3 text-xs font-bold uppercase tracking-[0.14em] text-muted-foreground">
            <span>Public IP</span>
            <span className="text-right">Lookups</span>
            <span className="text-right">Numbers</span>
          </div>

          {(data?.public_ip_counts ?? []).length ? (
            data?.public_ip_counts.map((row) => (
              <div
                key={row.public_ip}
                className="grid grid-cols-[1fr_auto_auto] gap-3 border-t border-white/10 px-4 py-3 text-sm"
              >
                <span className="min-w-0 truncate font-semibold text-white">{row.public_ip}</span>
                <span className="text-right font-mono text-muted-foreground">{row.total_lookups}</span>
                <span className="text-right font-mono text-primary">{row.unique_phone_numbers}</span>
              </div>
            ))
          ) : (
            <div className="border-t border-white/10 px-4 py-8 text-center text-sm font-semibold text-muted-foreground">
              No phone lookup audit records in this range.
            </div>
          )}
        </div>
      </section>
    </section>
  );
}

function ExportLogsPanel() {
  const initialRange = getQuickRange(24);
  const [from, setFrom] = useState(initialRange.from);
  const [to, setTo] = useState(initialRange.to);
  const [activeQuickFilter, setActiveQuickFilter] = useState("24h");
  const [message, setMessage] = useState("");

  function applyQuickFilter(hours: number, key: string) {
    const range = getQuickRange(hours);
    setFrom(range.from);
    setTo(range.to);
    setActiveQuickFilter(key);
    setMessage("");
  }

  function exportLookupResults() {
    setMessage("");
    if (!from || !to) {
      setMessage("Select both From and To before exporting.");
      return;
    }

    const params = new URLSearchParams({ from, to });
    window.location.assign(`${getApiBaseUrl()}/api/v1/auth/exports/lookup-results/?${params}`);
  }

  return (
    <section className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <AdminMetric icon={Download} label="Export Type" value="Lookup Results" />
        <AdminMetric icon={CalendarClock} label="Timezone" value="New York" />
        <AdminMetric icon={Database} label="Source" value="Audit + Cache" />
      </div>

      <section className="rounded-2xl border border-white/10 bg-[#101827]/90 p-4 shadow-panel sm:p-5">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="flex items-start gap-3">
            <div className="grid size-11 shrink-0 place-items-center rounded-xl border border-primary/25 bg-primary/10 text-primary">
              <Download className="size-5" />
            </div>
            <div>
              <h3 className="text-xl font-extrabold tracking-normal text-white">Export Lookup Results</h3>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                Export phone lookup results from audited searches in the selected New York time range. Each row includes
                the searched number, matched name, age, and primary phone from the cached lookup response.
              </p>
            </div>
          </div>

          <div className="w-full max-w-2xl">
            <div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
              <DateTimeField label="From" value={from} onChange={setFrom} />
              <DateTimeField label="To" value={to} onChange={setTo} />
              <Button type="button" className="h-12 self-end" onClick={exportLookupResults}>
                <Download />
                Export CSV
              </Button>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              {[
                ["6h", 6, "Last 6 hours"],
                ["24h", 24, "Last 24 hours"],
                ["7d", 24 * 7, "Last 7 days"],
                ["30d", 24 * 30, "Last 30 days"],
              ].map(([key, hours, label]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => applyQuickFilter(Number(hours), String(key))}
                  className={cn(
                    "rounded-md border px-3 py-2 text-sm font-bold transition-all",
                    activeQuickFilter === key
                      ? "border-primary/40 bg-primary text-primary-foreground"
                      : "border-white/10 bg-white/[0.04] text-muted-foreground hover:bg-white/[0.08] hover:text-foreground",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>

            {message ? (
              <p className="mt-4 rounded-md border border-amber-300/25 bg-amber-300/10 p-3 text-sm text-amber-100">
                {message}
              </p>
            ) : null}
          </div>
        </div>
      </section>
    </section>
  );
}

function FeedbacksPanel({ onUnreadCountChange }: { onUnreadCountChange: (count: number) => void }) {
  const [feedbacks, setFeedbacks] = useState<FeedbackRecord[]>([]);
  const [selectedFeedback, setSelectedFeedback] = useState<FeedbackRecord | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");
  const unreadCount = feedbacks.filter((feedback) => !feedback.is_read).length;

  useEffect(() => {
    void loadFeedbacks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadFeedbacks() {
    setState("loading");
    setMessage("");

    try {
      const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/feedbacks/`, {
        credentials: "include",
        cache: "no-store",
      });
      const payload = (await response.json().catch(() => null)) as
        | FeedbackListPayload
        | { message?: string; status?: string }
        | null;

      if (!response.ok || payload?.status !== "success" || !("feedbacks" in payload)) {
        setState("error");
        setMessage(getApiErrorMessage(payload, "Feedbacks could not be loaded."));
        return;
      }

      setFeedbacks(payload.feedbacks);
      onUnreadCountChange(payload.unread_count);
      setState("ready");
    } catch {
      setState("error");
      setMessage("Feedback service is unavailable.");
    }
  }

  async function markAsRead(feedback: FeedbackRecord) {
    if (feedback.is_read) return;

    try {
      const csrfToken = await refreshCsrfToken();
      const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/feedbacks/${feedback.id}/read/`, {
        method: "POST",
        credentials: "include",
        headers: {
          "X-CSRFToken": csrfToken,
        },
      });
      const payload = (await response.json().catch(() => null)) as
        | { status?: string; unread_count?: number; feedback?: FeedbackRecord; message?: string }
        | null;

      if (!response.ok || payload?.status !== "success" || !payload.feedback) {
        setMessage(payload?.message || "Feedback could not be marked as read.");
        return;
      }

      setFeedbacks((current) => current.map((item) => (item.id === payload.feedback?.id ? payload.feedback : item)));
      setSelectedFeedback(payload.feedback);
      onUnreadCountChange(payload.unread_count ?? Math.max(0, unreadCount - 1));
    } catch {
      setMessage("Feedback service is unavailable.");
    }
  }

  return (
    <section className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <AdminMetric icon={MessageSquareText} label="Total Feedbacks" value={formatNumber(feedbacks.length)} />
        <AdminMetric icon={Mail} label="Unread" value={formatNumber(unreadCount)} />
        <AdminMetric icon={CheckCircle2} label="Reviewed" value={formatNumber(feedbacks.length - unreadCount)} />
      </div>

      <section className="rounded-2xl border border-white/10 bg-[#101827]/90 p-4 shadow-panel sm:p-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 className="text-xl font-extrabold tracking-normal text-white">Feedbacks</h3>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              Review user interface and user experience feedback submitted from the lookup page.
            </p>
          </div>
          <Button type="button" variant="secondary" onClick={() => void loadFeedbacks()} disabled={state === "loading"}>
            {state === "loading" ? <Loader2 className="animate-spin" /> : <Activity />}
            Refresh
          </Button>
        </div>

        {message ? (
          <p className="mt-4 rounded-md border border-amber-300/25 bg-amber-300/10 p-3 text-sm text-amber-100">
            {message}
          </p>
        ) : null}

        <div className="mt-5 overflow-hidden rounded-xl border border-white/10">
          <div className="hidden grid-cols-[auto_1.1fr_1fr_0.8fr_0.8fr_auto] gap-3 bg-white/[0.045] px-4 py-3 text-xs font-bold uppercase tracking-[0.14em] text-muted-foreground lg:grid">
            <span>Status</span>
            <span>Submitted by</span>
            <span>Area</span>
            <span>Experience</span>
            <span>Created</span>
            <span className="text-right">Action</span>
          </div>

          {state === "loading" && !feedbacks.length ? (
            <div className="grid min-h-44 place-items-center text-sm font-semibold text-muted-foreground">
              <span className="inline-flex items-center gap-2">
                <Loader2 className="size-4 animate-spin text-primary" />
                Loading feedbacks
              </span>
            </div>
          ) : feedbacks.length ? (
            feedbacks.map((feedback) => (
              <article
                key={feedback.id}
                className={cn(
                  "grid gap-3 border-t border-white/10 px-4 py-4 first:border-t-0 lg:grid-cols-[auto_1.1fr_1fr_0.8fr_0.8fr_auto] lg:items-center",
                  !feedback.is_read && "bg-primary/[0.045]",
                )}
              >
                <div>
                  <span
                    className={cn(
                      "inline-flex rounded-full px-2.5 py-1 text-xs font-black",
                      feedback.is_read
                        ? "bg-white/8 text-muted-foreground"
                        : "bg-primary text-primary-foreground",
                    )}
                  >
                    {feedback.is_read ? "Read" : "New"}
                  </span>
                </div>

                <div className="min-w-0">
                  <p className="truncate font-semibold text-white">
                    {feedback.email || feedback.name || "Anonymous user"}
                  </p>
                  <p className="mt-1 truncate text-xs text-muted-foreground">{feedback.device || "Unknown device"}</p>
                </div>

                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">{feedback.feature || "General feedback"}</p>
                  <p className="mt-1 truncate text-xs text-muted-foreground">{feedback.areas.join(", ") || "No area"}</p>
                </div>

                <p className="text-sm font-bold text-primary">{feedback.experience}</p>
                <p className="text-sm text-muted-foreground">{formatDateTime(feedback.created_at)}</p>

                <div className="flex justify-end">
                  <Button type="button" size="sm" variant="secondary" onClick={() => setSelectedFeedback(feedback)}>
                    <Eye />
                    Explore
                  </Button>
                </div>
              </article>
            ))
          ) : (
            <div className="grid min-h-44 place-items-center px-4 py-8 text-center text-sm font-semibold text-muted-foreground">
              No feedback has been submitted yet.
            </div>
          )}
        </div>
      </section>

      {selectedFeedback ? (
        <FeedbackModal
          feedback={selectedFeedback}
          onClose={() => setSelectedFeedback(null)}
          onMarkAsRead={() => void markAsRead(selectedFeedback)}
        />
      ) : null}
    </section>
  );
}

function FeedbackModal({
  feedback,
  onClose,
  onMarkAsRead,
}: {
  feedback: FeedbackRecord;
  onClose: () => void;
  onMarkAsRead: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/70 px-4 py-6 backdrop-blur-sm">
      <section className="max-h-[88vh] w-full max-w-3xl overflow-hidden rounded-2xl border border-white/10 bg-[#101827] shadow-panel">
        <header className="flex items-start justify-between gap-4 border-b border-white/10 p-5">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={cn(
                  "rounded-full px-2.5 py-1 text-xs font-black",
                  feedback.is_read ? "bg-white/8 text-muted-foreground" : "bg-primary text-primary-foreground",
                )}
              >
                {feedback.is_read ? "Read" : "Unread"}
              </span>
              <span className="rounded-full border border-white/10 px-2.5 py-1 text-xs font-bold text-muted-foreground">
                {feedback.experience}
              </span>
            </div>
            <h3 className="mt-3 text-2xl font-extrabold tracking-normal text-white">
              {feedback.feature || "General feedback"}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {feedback.email || feedback.name || "Anonymous user"} · {formatDateTime(feedback.created_at)}
            </p>
          </div>
          <Button type="button" variant="ghost" size="icon" onClick={onClose} aria-label="Close feedback details">
            <X />
          </Button>
        </header>

        <div className="max-h-[calc(88vh-9rem)] overflow-y-auto p-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <FeedbackFact label="Device" value={feedback.device || "Unknown"} />
            <FeedbackFact label="Public IP" value={feedback.public_ip || "Unknown"} />
            <FeedbackFact label="Areas" value={feedback.areas.join(", ") || "None"} />
            <FeedbackFact label="Page URL" value={feedback.page_url || "Not provided"} />
          </div>

          <div className="mt-5 space-y-4">
            <FeedbackTextBlock title="What happened?" value={feedback.details} />
            <FeedbackTextBlock title="What would make it better?" value={feedback.suggestion || "No suggestion provided."} />
            <FeedbackTextBlock title="User agent" value={feedback.user_agent || "Not captured."} />
          </div>
        </div>

        <footer className="flex flex-col-reverse gap-3 border-t border-white/10 p-5 sm:flex-row sm:justify-end">
          <Button type="button" variant="secondary" onClick={onClose}>
            Close
          </Button>
          <Button type="button" onClick={onMarkAsRead} disabled={feedback.is_read}>
            <CheckCircle2 />
            Mark as read
          </Button>
        </footer>
      </section>
    </div>
  );
}

function FeedbackFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-md border border-white/10 bg-black/15 p-3">
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
      <p className="mt-2 break-words text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

function FeedbackTextBlock({ title, value }: { title: string; value: string }) {
  return (
    <section className="rounded-md border border-white/10 bg-black/15 p-4">
      <h4 className="text-sm font-bold text-primary">{title}</h4>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-zinc-200">{value}</p>
    </section>
  );
}

function DateTimeField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-semibold text-white">{label}</span>
      <div className="relative">
        <CalendarClock className="absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="datetime-local"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="h-12 min-w-0 pl-11 text-sm [color-scheme:dark]"
        />
      </div>
    </label>
  );
}

function AdminMetric({ icon: Icon, label, value }: { icon: typeof Search; label: string; value: string }) {
  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.045] p-5 shadow-panel">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-muted-foreground">{label}</p>
          <p className="mt-2 text-2xl font-extrabold tracking-normal text-white">{value}</p>
        </div>
        <div className="grid size-11 place-items-center rounded-xl border border-primary/20 bg-primary/10 text-primary">
          <Icon className="size-5" />
        </div>
      </div>
    </article>
  );
}

function StatusBadge({ icon: Icon, label, value }: { icon: typeof ShieldCheck; label: string; value?: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-black/15 p-3">
      <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-muted-foreground">
        <Icon className="size-3.5 text-primary" />
        {label}
      </div>
      <p className="mt-2 text-sm font-bold text-white">{value || "Unknown"}</p>
    </div>
  );
}

function getQuickRange(hours: number) {
  const to = new Date();
  const from = new Date(to.getTime() - hours * 60 * 60 * 1000);

  return {
    from: formatDateTimeLocalInNewYork(from),
    to: formatDateTimeLocalInNewYork(to),
  };
}

function formatDateTimeLocalInNewYork(date: Date) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
    .formatToParts(date)
    .reduce<Record<string, string>>((acc, part) => {
      if (part.type !== "literal") {
        acc[part.type] = part.value;
      }
      return acc;
    }, {});

  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function getDashboardErrorMessage(payload: DashboardPayload | { message?: string; status?: string } | null) {
  return getApiErrorMessage(payload, "Dashboard data could not be loaded.");
}

function getApiErrorMessage(
  payload: DashboardPayload | FeedbackListPayload | { message?: string; status?: string } | null,
  fallback: string,
) {
  if (payload && "message" in payload && payload.message) {
    return payload.message;
  }

  return fallback;
}

async function refreshCsrfToken() {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/csrf/`, {
    method: "GET",
    credentials: "include",
    cache: "no-store",
  });

  const payload = (await response.json().catch(() => null)) as { csrfToken?: string } | null;
  return payload?.csrfToken || getCookie("csrftoken") || "";
}

function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
}

function getCookie(name: string) {
  const cookie = document.cookie
    .split("; ")
    .find((item) => item.startsWith(`${encodeURIComponent(name)}=`));

  if (!cookie) return "";
  return decodeURIComponent(cookie.split("=").slice(1).join("="));
}
