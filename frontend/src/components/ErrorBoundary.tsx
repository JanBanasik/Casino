import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: "3rem", textAlign: "center" }}>
          <h2>Coś poszło nie tak</h2>
          <p style={{ color: "#888" }}>{this.state.error.message}</p>
          <button onClick={() => window.location.reload()}>Odśwież stronę</button>
        </div>
      );
    }
    return this.props.children;
  }
}
