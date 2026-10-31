import React from "react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught error:", error, errorInfo);
    this.setState({ errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-900 text-slate-100 p-8 flex flex-col items-center justify-center">
          <div className="max-w-3xl w-full rounded-xl border border-red-500 bg-red-950/80 p-6 shadow-2xl backdrop-blur">
            <div className="flex items-center gap-3 border-b border-red-800/80 pb-3 mb-4">
              <span className="text-2xl">⚠️</span>
              <div>
                <h1 className="text-lg font-bold text-red-200">웹 관제탑 렌더링 런타임 오류 감지</h1>
                <p className="text-xs text-red-400">컴포넌트 렌더링 중 예외가 발생했습니다.</p>
              </div>
            </div>
            <div className="space-y-3 font-mono text-xs">
              <div className="rounded bg-black/60 p-3 text-red-300 border border-red-900/50">
                <strong className="block text-white mb-1">에러 내용:</strong>
                {this.state.error?.toString()}
              </div>
              {this.state.error?.stack && (
                <div className="rounded bg-black/60 p-3 text-slate-400 border border-slate-800 overflow-auto max-h-60">
                  <strong className="block text-slate-200 mb-1">스택 트레이스:</strong>
                  <pre className="whitespace-pre-wrap">{this.state.error.stack}</pre>
                </div>
              )}
              {this.state.errorInfo?.componentStack && (
                <div className="rounded bg-black/60 p-3 text-slate-400 border border-slate-800 overflow-auto max-h-60">
                  <strong className="block text-slate-200 mb-1">컴포넌트 스택:</strong>
                  <pre className="whitespace-pre-wrap">{this.state.errorInfo.componentStack}</pre>
                </div>
              )}
            </div>
            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => window.location.reload()}
                className="rounded bg-red-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-red-500 transition-colors"
              >
                새로고침 (F5)
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
