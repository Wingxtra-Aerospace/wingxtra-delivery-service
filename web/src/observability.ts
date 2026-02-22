export type ApiErrorEventDetail = {
  requestId: string;
  message: string;
  status?: number;
  retryable: boolean;
};

const API_ERROR_EVENT = "wingxtra-api-error";

function toFriendlyMessage(status?: number): string {
  if (status === 429) {
    return "Too many requests right now. Please retry shortly.";
  }
  if (status != null && status >= 500) {
    return "Service is temporarily unavailable. Please retry.";
  }
  if (status != null && status >= 400) {
    return "Unable to process your request. Please check input and retry.";
  }
  return "Network issue detected. Please check your connection and retry.";
}

export function createRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function emitApiError(detail: { requestId: string; status?: number; message?: string }) {
  const normalized: ApiErrorEventDetail = {
    requestId: detail.requestId,
    status: detail.status,
    message: detail.message ?? toFriendlyMessage(detail.status),
    retryable: detail.status == null || detail.status >= 500 || detail.status === 429
  };

  window.dispatchEvent(new CustomEvent<ApiErrorEventDetail>(API_ERROR_EVENT, { detail: normalized }));
}

export function subscribeToApiErrors(handler: (detail: ApiErrorEventDetail) => void): () => void {
  const listener = (event: Event) => {
    const customEvent = event as CustomEvent<ApiErrorEventDetail>;
    if (customEvent.detail) {
      handler(customEvent.detail);
    }
  };

  window.addEventListener(API_ERROR_EVENT, listener);
  return () => window.removeEventListener(API_ERROR_EVENT, listener);
}

export function initSentry() {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return;

  const sentry = (window as Window & {
    Sentry?: { init: (options: { dsn: string; environment?: string }) => void };
  }).Sentry;

  if (!sentry) return;

  sentry.init({
    dsn,
    environment: import.meta.env.MODE
  });
}
