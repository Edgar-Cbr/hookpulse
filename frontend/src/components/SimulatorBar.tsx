import React, { useState } from 'react';
import {
  CheckCircle2,
  Flame,
  Loader2,
  ShieldCheck,
  Sparkles,
  Zap,
} from 'lucide-react';
import { api } from '../services/api';
import type { SimulatorTriggerResponse } from '../types/webhook';

interface SimulatorBarProps {
  endpointSlug: string;
  onTriggered?: (res: SimulatorTriggerResponse) => void;
}

export const SimulatorBar: React.FC<SimulatorBarProps> = ({
  endpointSlug,
  onTriggered,
}) => {
  const [signHmac, setSignHmac] = useState<boolean>(true);
  const [isTriggering, setIsTriggering] = useState<boolean>(false);
  const [lastFeedback, setLastFeedback] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const handleTrigger = async (behavior: 'success' | 'fail') => {
    try {
      setIsTriggering(true);
      setLastFeedback(null);
      const res = await api.triggerSimulator({
        endpoint_slug: endpointSlug,
        behavior,
        event_type: 'tax_id.batch.completed',
        sign_hmac: signHmac,
      });

      setLastFeedback({
        type: behavior === 'success' ? 'success' : 'error',
        text:
          behavior === 'success'
            ? `Dispatched TaxGuard batch event (${res.event_id.slice(0, 8)}...) -> 200 OK Delivered!`
            : `Dispatched failure scenario (${res.event_id.slice(0, 8)}...) -> 500 downstream error, retrying with Backoff!`,
      });

      if (onTriggered) {
        onTriggered(res);
      }
    } catch (err: any) {
      setLastFeedback({
        type: 'error',
        text: `Simulation error: ${err.message || 'Failed to dispatch'}`,
      });
    } finally {
      setIsTriggering(false);
    }
  };

  return (
    <div className="bg-slate-900/60 border-b border-slate-800 px-4 sm:px-6 lg:px-8 py-3">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Left: Simulation Title & Info */}
        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
            <Zap className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              TaxGuard Traffic Simulator
            </h2>
            <p className="text-[11px] text-slate-500">
              Generate synthetic fiscal webhook events to test HMAC verification, exponential backoff and DLQ routing.
            </p>
          </div>
        </div>

        {/* Center: Feedback Alert */}
        {lastFeedback && (
          <div
            className={`text-xs px-3 py-1.5 rounded-lg border flex items-center gap-1.5 transition-all ${
              lastFeedback.type === 'success'
                ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-950/40 border-rose-500/30 text-rose-300'
            }`}
          >
            {lastFeedback.type === 'success' ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            ) : (
              <Flame className="w-3.5 h-3.5 text-rose-400 shrink-0" />
            )}
            <span className="truncate max-w-sm sm:max-w-md">{lastFeedback.text}</span>
          </div>
        )}

        {/* Right: Controls & Action Buttons */}
        <div className="flex items-center space-x-3 w-full md:w-auto justify-end">
          {/* HMAC Toggle */}
          <label className="flex items-center space-x-1.5 text-xs text-slate-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={signHmac}
              onChange={(e) => setSignHmac(e.target.checked)}
              className="rounded border-slate-700 bg-slate-800 text-indigo-600 focus:ring-0 focus:ring-offset-0"
            />
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-[11px]">HMAC-SHA256</span>
          </label>

          {/* Trigger Success (200 OK) */}
          <button
            onClick={() => handleTrigger('success')}
            disabled={isTriggering}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none"
          >
            {isTriggering ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            )}
            <span>Send 200 OK</span>
          </button>

          {/* Simulate Failure & Retries (500 Error) */}
          <button
            onClick={() => handleTrigger('fail')}
            disabled={isTriggering}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 transition-all hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none"
          >
            {isTriggering ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Flame className="w-3.5 h-3.5 text-rose-400" />
            )}
            <span>Simulate 500 (Backoff & DLQ)</span>
          </button>
        </div>
      </div>
    </div>
  );
};
