import React, { useState } from 'react';
import {
  Activity,
  Check,
  Copy,
  Radio,
} from 'lucide-react';
import type { Endpoint, WebhookEvent } from '../types/webhook';

interface HeaderProps {
  endpoint: Endpoint | null;
  events: WebhookEvent[];
  isConnected: boolean;
  isReconnecting: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  endpoint,
  events,
  isConnected,
  isReconnecting,
}) => {
  const [copied, setCopied] = useState(false);

  const slug = endpoint?.slug || 'ep_taxguard_prod';
  const ingestUrl = `${window.location.origin}/ingest/${slug}`;

  const copyIngestUrl = () => {
    navigator.clipboard.writeText(ingestUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Compute live stats
  const totalCount = events.length;
  const deliveredCount = events.filter((e) => e.status === 'DELIVERED').length;
  const retryingCount = events.filter((e) => e.status === 'RETRYING').length;
  const dlqCount = events.filter((e) => e.status === 'DLQ').length;

  return (
    <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur-md sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          {/* Brand & Connection Badge */}
          <div className="flex items-center space-x-3.5">
            <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-500 shadow-lg shadow-indigo-500/20 ring-1 ring-white/20">
              <Activity className="w-5 h-5 text-white animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2.5">
                <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-1.5">
                  Hook<span className="text-indigo-400">Pulse</span>
                </h1>
                <span className="text-[11px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  v1.0.0
                </span>
                {/* Live WebSocket Status Pill */}
                <div className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border transition-colors">
                  {isConnected ? (
                    <span className="flex items-center gap-1.5 text-emerald-400 bg-emerald-500/10 border-emerald-500/30 px-2 py-0.5 rounded-full">
                      <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                      </span>
                      LIVE STREAM
                    </span>
                  ) : isReconnecting ? (
                    <span className="flex items-center gap-1.5 text-amber-400 bg-amber-500/10 border-amber-500/30 px-2 py-0.5 rounded-full">
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500 animate-pulse"></span>
                      RECONNECTING...
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 text-rose-400 bg-rose-500/10 border-rose-500/30 px-2 py-0.5 rounded-full">
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
                      OFFLINE
                    </span>
                  )}
                </div>
              </div>
              <p className="text-xs text-slate-400">
                Real-Time Webhook Gateway & Resilient Delivery Engine
              </p>
            </div>
          </div>

          {/* Quick Metrics Bar */}
          <div className="flex items-center space-x-2 sm:space-x-3 text-xs">
            <div className="bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-1.5">
              <span className="text-slate-400 block text-[10px] uppercase font-semibold">Total</span>
              <span className="font-mono text-sm font-bold text-slate-100">{totalCount}</span>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-1.5">
              <span className="text-emerald-400 block text-[10px] uppercase font-semibold">Delivered</span>
              <span className="font-mono text-sm font-bold text-emerald-400">{deliveredCount}</span>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-1.5">
              <span className="text-amber-400 block text-[10px] uppercase font-semibold">Retrying</span>
              <span className="font-mono text-sm font-bold text-amber-400">{retryingCount}</span>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-1.5">
              <span className="text-rose-400 block text-[10px] uppercase font-semibold">DLQ</span>
              <span className="font-mono text-sm font-bold text-rose-400">{dlqCount}</span>
            </div>
          </div>

          {/* Ingest Webhook URL with One-Click Copy */}
          <div className="flex items-center space-x-2 bg-slate-950/80 border border-slate-800/80 rounded-lg px-3 py-1.5 max-w-md">
            <Radio className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            <div className="truncate text-xs font-mono text-slate-300">
              <span className="text-slate-500">POST </span>
              {ingestUrl}
            </div>
            <button
              onClick={copyIngestUrl}
              title="Copy Ingest URL"
              className="ml-auto inline-flex items-center gap-1 text-slate-400 hover:text-white px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 transition-colors text-[11px] font-sans"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400" />
                  <span className="text-emerald-400">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
