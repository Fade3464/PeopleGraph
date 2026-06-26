"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, Fingerprint, Loader2, LockKeyhole, ShieldCheck, UserRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type LoginState = "idle" | "loading" | "success" | "error";

export default function AdministrationLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [state, setState] = useState<LoginState>("idle");
  const [message, setMessage] = useState("");

  useEffect(() => {
    void refreshCsrfToken();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("loading");
    setMessage("");

    try {
      let csrfToken = getCookie("csrftoken");
      if (!csrfToken) {
        csrfToken = await refreshCsrfToken();
      }

      const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/login/`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken || "",
        },
        body: JSON.stringify({
          username: email.trim().toLowerCase(),
          password,
        }),
      });

      const payload = (await response.json().catch(() => null)) as { message?: string } | null;

      if (!response.ok) {
        setState("error");
        setMessage(payload?.message || "Login failed. Check your credentials and try again.");
        return;
      }

      setState("success");
      setMessage("Login successful. Opening administration console...");
      window.location.assign("/admininstration");
    } catch {
      setState("error");
      setMessage("Administration login is unavailable. Please try again shortly.");
    }
  }

  return (
    <main className="relative flex min-h-screen overflow-hidden bg-[#0c0e10] px-4 py-8 text-foreground sm:px-6 lg:px-8">
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_78%_12%,rgba(31,240,170,0.16),transparent_28rem),radial-gradient(circle_at_18%_4%,rgba(13,186,230,0.12),transparent_30rem),linear-gradient(180deg,#101316_0%,#0c0e10_62%,#08090b_100%)]" />
      <div className="absolute left-1/2 top-16 -z-10 h-64 w-[min(42rem,80vw)] -translate-x-1/2 rounded-full bg-primary/10 blur-3xl" />

      <section className="mx-auto flex w-full max-w-[1180px] flex-col">
        <header className="flex h-14 items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-white transition-opacity hover:opacity-85">
            <div className="grid size-9 place-items-center rounded-md bg-gradient-to-br from-cyan-400 to-emerald-400 shadow-teal">
              <Fingerprint className="size-5 text-[#07100d]" />
            </div>
            <span className="text-xl font-extrabold tracking-normal">PeopleGraph</span>
          </Link>
        </header>

        <div className="grid flex-1 items-center gap-10 py-14 lg:grid-cols-[0.92fr_1fr] lg:py-20">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/6 px-3 py-2 text-sm font-semibold text-primary">
              <ShieldCheck className="size-4" />
              Staff access
            </div>

            <h1 className="mt-8 text-4xl font-black tracking-normal text-white sm:text-5xl lg:text-6xl">
              Administration login
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-zinc-300 sm:text-lg">
              Sign in with a Django staff account to manage PeopleGraph users and administrative records.
            </p>
          </div>

          <form
            onSubmit={handleSubmit}
            className="glass-panel mx-auto w-full max-w-md rounded-2xl p-5 sm:p-6"
          >
            <div className="mb-6">
              <div className="grid size-12 place-items-center rounded-xl border border-primary/25 bg-primary/10 text-primary">
                <LockKeyhole className="size-6" />
              </div>
              <h2 className="mt-4 text-2xl font-extrabold tracking-normal text-white">Secure sign in</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Access is limited to active Django staff users.
              </p>
            </div>

            <div className="space-y-4">
              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-white">Email address</span>
                <div className="relative">
                  <UserRound className="absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className="pl-11"
                    type="email"
                    autoComplete="username"
                    placeholder="Enter admin email"
                    required
                  />
                </div>
              </label>

              <label className="block">
                <span className="mb-2 block text-sm font-semibold text-white">Password</span>
                <div className="relative">
                  <LockKeyhole className="absolute left-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="pl-11"
                    type="password"
                    autoComplete="current-password"
                    placeholder="Enter password"
                    required
                  />
                </div>
              </label>
            </div>

            {message ? (
              <p
                className={
                  state === "error"
                    ? "mt-4 rounded-md border border-rose-300/25 bg-rose-300/10 p-3 text-sm text-rose-200"
                    : "mt-4 rounded-md border border-primary/25 bg-primary/10 p-3 text-sm text-primary"
                }
              >
                {message}
              </p>
            ) : null}

            <Button type="submit" size="lg" className="mt-6 h-12 w-full" disabled={state === "loading"}>
              {state === "loading" ? <Loader2 className="animate-spin" /> : <ArrowRight />}
              Sign in
            </Button>
          </form>
        </div>
      </section>
    </main>
  );
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
