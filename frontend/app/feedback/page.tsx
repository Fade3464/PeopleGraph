"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { FormEvent, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  Fingerprint,
  Lightbulb,
  Loader2,
  MessageSquareText,
  Send,
  Sparkles,
  Star,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

const experienceOptions = ["Excellent", "Good", "Average", "Difficult"];
const feedbackAreas = ["Search flow", "Results layout", "Visual design", "Speed", "Mobile experience", "Other"];
const feedbackFieldClass =
  "border-white/10 bg-[#30363c] text-white placeholder:text-zinc-400 shadow-inner focus:border-primary focus:bg-[#343b42] focus:ring-2 focus:ring-primary/25";

export default function FeedbackPage() {
  const [selectedExperience, setSelectedExperience] = useState("Good");
  const [selectedAreas, setSelectedAreas] = useState<string[]>(["Results layout"]);
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  function toggleArea(area: string) {
    setSelectedAreas((current) =>
      current.includes(area) ? current.filter((item) => item !== area) : [...current, area],
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage("");

    const formData = new FormData(event.currentTarget);

    try {
      const response = await fetch(`${getApiBaseUrl()}/api/v1/auth/feedback/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: formData.get("name"),
          email: formData.get("email"),
          experience: selectedExperience,
          areas: selectedAreas,
          feature: formData.get("feature"),
          device: formData.get("device"),
          details: formData.get("details"),
          suggestion: formData.get("suggestion"),
          page_url: typeof window !== "undefined" ? window.location.href : "",
        }),
      });
      const payload = (await response.json().catch(() => null)) as { message?: string } | null;

      if (!response.ok) {
        setErrorMessage(payload?.message || "Feedback could not be submitted. Please try again.");
        return;
      }

      setSubmitted(true);
    } catch {
      setErrorMessage("Feedback service is unavailable. Please try again shortly.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#0c0e10] px-4 py-8 text-foreground sm:px-6 lg:px-8">
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

          <Button asChild variant="secondary" size="sm">
            <Link href="/lookup">
              <ArrowLeft />
              Lookup
            </Link>
          </Button>
        </header>

        <div className="grid flex-1 items-start gap-8 py-12 lg:grid-cols-[0.82fr_1fr] lg:py-16">
          <aside className="lg:sticky lg:top-8">
            <div className="inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/6 px-3 py-2 text-sm font-semibold text-primary">
              <MessageSquareText className="size-4" />
              Help us improve
            </div>

            <h1 className="mt-7 max-w-2xl text-4xl font-black tracking-normal text-white sm:text-5xl">
              Share feedback on the lookup experience.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-zinc-300">
              Tell us what felt clear, what slowed you down, and what would make PeopleGraph easier to use.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
              <InsightCard icon={Sparkles} title="Interface" body="Clarity, layout, spacing, and visual hierarchy." />
              <InsightCard icon={Lightbulb} title="Workflow" body="Search flow, result review, and next actions." />
              <InsightCard icon={Star} title="Quality" body="Anything that would make the portal feel more polished." />
            </div>
          </aside>

          <form onSubmit={handleSubmit} className="glass-panel rounded-2xl p-5 sm:p-6">
            {submitted ? (
              <div className="grid min-h-[34rem] place-items-center text-center">
                <div>
                  <div className="mx-auto grid size-14 place-items-center rounded-xl border border-primary/25 bg-primary/10 text-primary">
                    <CheckCircle2 className="size-7" />
                  </div>
                  <h2 className="mt-5 text-2xl font-extrabold tracking-normal text-white">Feedback noted</h2>
                  <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                    Thanks. Your feedback has been sent to the PeopleGraph administration queue.
                  </p>
                  <Button asChild className="mt-6">
                    <Link href="/lookup">
                      <ArrowLeft />
                      Back to lookup
                    </Link>
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-extrabold tracking-normal text-white">Feedback details</h2>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Focus on the parts of the interface that affected speed, confidence, or ease of use.
                  </p>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Name">
                    <Input name="name" placeholder="Optional" autoComplete="name" className={feedbackFieldClass} />
                  </Field>
                  <Field label="Email">
                    <Input
                      name="email"
                      type="email"
                      placeholder="Optional"
                      autoComplete="email"
                      className={feedbackFieldClass}
                    />
                  </Field>
                </div>

                <Field label="Overall experience">
                  <div className="grid gap-2 sm:grid-cols-4">
                    {experienceOptions.map((option) => (
                      <button
                        key={option}
                        type="button"
                        onClick={() => setSelectedExperience(option)}
                        className={cn(
                          "h-11 rounded-md border px-3 text-sm font-bold transition-all",
                          selectedExperience === option
                            ? "border-primary/40 bg-primary text-primary-foreground shadow-teal"
                            : "border-white/10 bg-white/[0.04] text-muted-foreground hover:bg-white/[0.08] hover:text-foreground",
                        )}
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                  <input type="hidden" name="experience" value={selectedExperience} />
                </Field>

                <Field label="What area should we improve?">
                  <div className="flex flex-wrap gap-2">
                    {feedbackAreas.map((area) => (
                      <button
                        key={area}
                        type="button"
                        onClick={() => toggleArea(area)}
                        className={cn(
                          "rounded-md border px-3 py-2 text-sm font-semibold transition-all",
                          selectedAreas.includes(area)
                            ? "border-primary/40 bg-primary/15 text-primary"
                            : "border-white/10 bg-white/[0.04] text-muted-foreground hover:bg-white/[0.08] hover:text-foreground",
                        )}
                      >
                        {area}
                      </button>
                    ))}
                  </div>
                  <input type="hidden" name="areas" value={selectedAreas.join(", ")} />
                </Field>

                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Page or feature">
                    <Input name="feature" placeholder="e.g. phone search results" className={feedbackFieldClass} />
                  </Field>
                  <Field label="Device">
                    <select
                      name="device"
                      className={cn(
                        "flex h-12 w-full rounded-md px-4 py-2 text-sm outline-none transition-all",
                        feedbackFieldClass,
                      )}
                      defaultValue="Desktop"
                    >
                      <option className="bg-[#101316]">Desktop</option>
                      <option className="bg-[#101316]">Mobile</option>
                      <option className="bg-[#101316]">Tablet</option>
                    </select>
                  </Field>
                </div>

                <Field label="What happened?">
                  <textarea
                    name="details"
                    required
                    rows={5}
                    placeholder="Describe the issue, confusion, or improvement idea."
                    className={cn(
                      "w-full resize-y rounded-md px-4 py-3 text-sm leading-6 outline-none transition-all",
                      feedbackFieldClass,
                    )}
                  />
                </Field>

                <Field label="What would make it better?">
                  <textarea
                    name="suggestion"
                    rows={4}
                    placeholder="Optional: share the change you would prefer."
                    className={cn(
                      "w-full resize-y rounded-md px-4 py-3 text-sm leading-6 outline-none transition-all",
                      feedbackFieldClass,
                    )}
                  />
                </Field>

                {errorMessage ? (
                  <p className="rounded-md border border-rose-300/25 bg-rose-300/10 p-3 text-sm text-rose-200">
                    {errorMessage}
                  </p>
                ) : null}

                <Button type="submit" size="lg" className="h-12 w-full sm:w-auto" disabled={isSubmitting}>
                  {isSubmitting ? <Loader2 className="animate-spin" /> : <Send />}
                  Submit feedback
                </Button>
              </div>
            )}
          </form>
        </div>
      </section>
    </main>
  );
}

function getApiBaseUrl() {
  return process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="block">
      <span className="mb-2 block text-sm font-semibold text-white">{label}</span>
      {children}
    </div>
  );
}

function InsightCard({
  icon: Icon,
  title,
  body,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
}) {
  return (
    <article className="rounded-md border border-white/10 bg-white/[0.045] p-4">
      <div className="mb-3 grid size-10 place-items-center rounded-md bg-primary/10 text-primary">
        <Icon className="size-5" />
      </div>
      <h2 className="font-bold text-white">{title}</h2>
      <p className="mt-1 text-sm leading-6 text-muted-foreground">{body}</p>
    </article>
  );
}
