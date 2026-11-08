// API client. In mock mode (VITE_MOCK=1, default in dev) it serves ../fixtures/*.json, so the UI works without a backend.
import type { AgentEvent, CorrelationReport, Health, Mandate, Mode, Notification, Portfolio, ProfileResult, Question, RunSummary } from "./types";

const fixtureMode = import.meta.env.VITE_MOCK;
export const MOCK = fixtureMode === "1" || (fixtureMode === undefined && import.meta.env.DEV);

const errorCopy: Record<string, string> = {
  rate_limited: "Too many requests. Please wait a minute and try again.",
  budget_exceeded: "Today's AI budget is used up. You can still explore the portfolio and past reviews.",
};

export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string, readonly details?: unknown) {
    super(errorCopy[code] ?? message);
    this.name = "ApiError";
  }
}

interface ApiFeedback {
  showError: (error: ApiError) => void;
  requestPasscode: (previousRejected: boolean) => Promise<string | null>;
}

let feedback: ApiFeedback | undefined;
let passcode: string | undefined;
let passcodeRequest: Promise<string | null> | undefined;

export function attachApiFeedback(next: ApiFeedback): () => void {
  feedback = next;
  return () => {
    if (feedback === next) feedback = undefined;
  };
}

const fixtures = import.meta.glob("../../../fixtures/*.json", { eager: true, import: "default" }) as Record<string, unknown>;
const fx = <T,>(name: string): T => {
  const hit = Object.entries(fixtures).find(([k]) => k.endsWith(`/${name}.json`));
  if (!hit) throw new Error(`fixture ${name} missing: run \`make fixtures\``);
  return hit[1] as T;
};

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, init);
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new ApiError(0, "network_error", "Could not reach the app. Check your connection and try again.");
  }
  if (response.ok) {
    try {
      return await response.json();
    } catch (error) {
      if (init.signal?.aborted) throw error;
      throw new ApiError(response.status, "invalid_response", "The app returned a response that could not be read.");
    }
  }
  const body = await response.json().catch(() => null);
  const error = body?.error;
  throw new ApiError(
    response.status,
    typeof error?.code === "string" ? error.code : "http_error",
    typeof error?.message === "string" ? error.message : response.statusText || `Request failed (${response.status}).`,
    error?.details,
  );
}

export async function get<T>(path: string, mock: string, signal?: AbortSignal): Promise<T> {
  signal?.throwIfAborted();
  if (MOCK) return fx<T>(mock);
  try {
    return await request<T>(path, { signal });
  } catch (error) {
    if (!signal?.aborted && error instanceof ApiError) feedback?.showError(error);
    throw error;
  }
}

function canAskForPasscode(path: string, body: unknown): boolean {
  return path === "/chat" || path === "/portfolio/build" || path === "/portfolio/review" || (
    path === "/sim/start" && !!body && typeof body === "object" && "run_agents" in body && body.run_agents === true
  );
}

function passcodeRejected(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401 && error.code === "unauthorized";
}

function askForPasscode(previousRejected: boolean): Promise<string | null> {
  if (!passcodeRequest && feedback) {
    passcodeRequest = feedback.requestPasscode(previousRejected).finally(() => { passcodeRequest = undefined; });
  }
  return passcodeRequest ?? Promise.resolve(null);
}

async function retryWithPasscode<T>(send: (credential: string) => Promise<T>, previousPasscode?: string): Promise<T> {
  if (passcode === previousPasscode) passcode = undefined;
  const supplied = passcode ?? await askForPasscode(!!previousPasscode);
  if (!supplied) throw new Error("Action cancelled.");
  try {
    const result = await send(supplied);
    passcode = supplied;
    return result;
  } catch (error) {
    if (!passcodeRejected(error)) throw error;
    if (passcode === supplied) passcode = undefined;
    throw new ApiError(401, "unauthorized", "That demo passcode was rejected. Please try again.");
  }
}

export async function put<T>(path: string, body: T, mock: string): Promise<T> {
  if (MOCK) return body ?? fx<T>(mock);
  return request<T>(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

export async function post<T>(path: string, body: unknown, mock: string): Promise<T> {
  if (MOCK) return fx<T>(mock);
  const protectedAction = canAskForPasscode(path, body);
  const previousPasscode = protectedAction ? passcode : undefined;
  const send = (credential?: string) => {
    const headers = new Headers({ "Content-Type": "application/json" });
    if (credential) headers.set("X-Demo-Passcode", credential);
    return request<T>(path, { method: "POST", headers, body: JSON.stringify(body) });
  };
  try {
    return await send(previousPasscode).catch((error) => {
      if (protectedAction && passcodeRejected(error)) return retryWithPasscode(send, previousPasscode);
      throw error;
    });
  } catch (error) {
    if (error instanceof ApiError) feedback?.showError(error);
    throw error;
  }
}

export const api = {
  health: (signal?: AbortSignal) => get<Health>("/health", "health", signal),
  setMode: (mode: Mode) => post<Pick<Health, "mode" | "as_of">>("/mode", { mode }, "health"),
  questions: () => get<{ questions: Question[] }>("/profile/questions", "questions"),
  quiz: (answers: Record<string, string>, followUpAnswer?: "yes" | "no") => post<{ profile: ProfileResult; mandate: Mandate }>("/profile/quiz", { answers, follow_up_answer: followUpAnswer }, "quiz_result"),
  mandate: () => get<Mandate>("/mandate", "mandate"),
  portfolio: () => get<Portfolio>("/portfolio", "portfolio"),
  notifications: () => get<{ items: Notification[] }>("/notifications", "notifications"),
  markNotificationRead: (id: string) => MOCK ? Promise.resolve({ ok: true })
    : post<{ ok: true }>(`/notifications/${encodeURIComponent(id)}/read`, {}, "notifications"),
  correlation: () => get<CorrelationReport>("/risk/correlation", "correlation"),
  runs: () => get<{ items: Omit<RunSummary, "agents">[] }>("/runs", "runs"),
  runDetail: (runId: string) => get<RunSummary>(`/runs/${encodeURIComponent(runId)}`, "run_detail"),
  build: () => post<{ run_id: string }>("/portfolio/build", {}, "runs").then((r) => ("run_id" in r ? r : { run_id: "mock" })),
  review: () => post<{ run_id: string }>("/portfolio/review", {}, ""),
  // TODO(#fe-*): pnl, rebalances, benchmarks, proposals, approve/decline, evidence, chat, sim controls
};

export const mockEvents = (): AgentEvent[] => fx<AgentEvent[]>("events_construction");
