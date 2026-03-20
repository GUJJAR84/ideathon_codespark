import React from "react";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", padding: "60px 20px", color: "#94a3b8",
        }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>⚠️</div>
          <h3 style={{ color: "#f1f5f9", marginBottom: 8 }}>Something went wrong</h3>
          <p style={{ fontSize: 14, marginBottom: 20 }}>
            {this.state.error?.message || "An unexpected error occurred"}
          </p>
          <button
            onClick={() => { this.setState({ hasError: false }); window.location.reload(); }}
            style={{
              padding: "8px 20px", borderRadius: 8, border: "1px solid #6366f1",
              background: "rgba(99,102,241,0.15)", color: "#818cf8",
              cursor: "pointer", fontSize: 13, fontWeight: 600,
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
