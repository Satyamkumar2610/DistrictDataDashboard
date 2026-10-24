import { useQueryClient } from "@tanstack/react-query";
import { Component, useEffect, useState, type ReactNode } from "react";
import { ApiError } from "../api";

/** One line that says what went wrong and one way out. */
export function ErrorState({ title, detail, onRetry, retryLabel = "Try again" }:
  { title: string; detail?: string; onRetry?: () => void; retryLabel?: string }) {
  return (
    <div className="error-state" role="alert">
      <div>
        <p className="strong">{title}</p>
        {detail && <p className="small muted">{detail}</p>}
      </div>
      {onRetry && <button type="button" className="btn" onClick={onRetry}>{retryLabel}</button>}
    </div>
  );
}

/** Catches a page that fails to render or to load its code. After a new release the old page chunks are gone,
 *  so a failed dynamic import means "reload", not "broken". Reset by changing `resetKey` (the route). */
export class PageErrorBoundary extends Component<{ resetKey: string; children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidUpdate(prev: { resetKey: string }) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }
  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    const stale = /dynamically imported module|Importing a module script failed|Loading chunk/i.test(error.message);
    return (
      <main className="page">
        <ErrorState
          title={stale ? "A newer version of this site is available." : "This page could not be shown."}
          detail={stale ? "Reload to get it." : error.message}
          onRetry={() => (stale ? window.location.reload() : this.setState({ error: null }))}
          retryLabel={stale ? "Reload" : "Try again"} />
      </main>
    );
  }
}

/** A banner while the data service is unreachable or failing, with one retry for every failed request.
 *  A 404 is an answer (no such district), not an outage, so it never raises the banner. */
export function ConnectionBanner() {
  const client = useQueryClient();
  const [down, setDown] = useState(false);
  useEffect(() => {
    const cache = client.getQueryCache();
    const check = () => setDown(cache.getAll().some((q) => q.state.status === "error"
      && q.state.error instanceof ApiError && q.state.error.transient));
    check();
    return cache.subscribe(check);
  }, [client]);
  if (!down) return null;
  return (
    <div className="conn-banner">
      <ErrorState title="The data service is not responding."
        detail="Parts of this page could not load. Nothing you entered is lost."
        onRetry={() => client.refetchQueries({ predicate: (q) => q.state.status === "error" })} />
    </div>
  );
}
