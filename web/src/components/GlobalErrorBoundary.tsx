import { Component, ReactNode } from "react";

type Props = { children: ReactNode };
type State = { hasError: boolean };

export class GlobalErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch() {
    // Prevent leaking potentially sensitive user payloads from thrown objects.
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="app-content">
          <section className="error" role="alert">
            <h2>Something went wrong</h2>
            <p>We hit an unexpected UI issue. Please reload and try again.</p>
            <button type="button" onClick={() => window.location.reload()}>
              Reload
            </button>
          </section>
        </main>
      );
    }

    return this.props.children;
  }
}
