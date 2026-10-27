import React, { useState } from 'react';
import {
  AlertCircle,
  AlertOctagon,
  CheckCircle2,
  Clock,
  Loader2,
  RotateCcw,
  Timer,
  Zap,
} from 'lucide-react';
import type { DeliveryAttempt, WebhookEvent } from '../types/webhook';

interface AttemptTimelineProps {
  event: WebhookEvent | null;
  onReplay: (eventId: string) => Promise<void>;
}

export const AttemptTimeline: React.FC<AttemptTimelineProps> = ({
  event,
  onReplay,
}) => {
  const [isReplaying, setIsReplaying] = useState<boolean>(false);
  const [replayError, setReplayError] = useState<string | null>(null);

  if (!event) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[250px] p-8 text-center bg-slate-900/50 border border-slate-800 rounded-xl text-slate-500">
        <Clock className="w-10 h-10 text-slate-700 mb-3" />
        <h3 className="text-sm font-semibold text-slate-400">No Attempts Available</h3>
        <p className="text-xs text-slate-600 mt-1 max-w-xs">
          Select an event to view its delivery dispatch history and exponential backoff retry timeline.
        </p>
      </div>
    );
  }

  const handleReplayClick = async () => {
    try {
      setIsReplaying(true);
      setReplayError(null);
      await onReplay(event.id);
    } catch (err: any) {
      setReplayError(err.message || 'Replay failed');
    } finally {
      setIsReplaying(false);
    }
  };

  const attempts: DeliveryAttempt[] = event.attempts || [];

  return (
    <div className="flex flex-col h-full bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      {/* Header with Replay Action */}
      <div className="p-3.5 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Zap className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-slate-100">
            Delivery Attempts Timeline
          </h3>
          <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">
            {attempts.length} {attempts.length === 1 ? 'attempt' : 'attempts'}
          </span>
        </div>

        {/* Replay Event Button */}
        <button
          onClick={handleReplayClick}
          disabled={isReplaying}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold shadow-sm transition-all ${
            event.status === 'DLQ'
              ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-600/20 hover:scale-[1.02]'
              : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/20 hover:scale-[1.02]'
          } active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none`}
        >
          {isReplaying ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <RotateCcw className="w-3.5 h-3.5" />
          )}
          <span>{event.status === 'DLQ' ? 'Recover & Replay DLQ' : 'Replay Event'}</span>
        </button>
      </div>

      {replayError && (
        <div className="px-4 py-2 bg-rose-950/60 border-b border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{replayError}</span>
        </div>
      )}

      {/* Next Retry Countdown Banner */}
      {event.status === 'RETRYING' && event.next_retry_at && (
        <div className="px-4 py-2.5 bg-amber-950/40 border-b border-amber-500/30 flex items-center justify-between text-xs text-amber-300">
          <div className="flex items-center gap-2">
            <Timer className="w-4 h-4 animate-pulse text-amber-400" />
            <span>
              <strong>Exponential Backoff Active:</strong> Next attempt scheduled for{' '}
              <span className="font-mono">{new Date(event.next_retry_at).toLocaleTimeString()}</span>
            </span>
          </div>
          <span className="text-[11px] font-mono bg-amber-500/20 px-2 py-0.5 rounded border border-amber-500/30">
            Retry #{event.retry_count + 1}
          </span>
        </div>
      )}

      {/* Attempts Timeline List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {attempts.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center text-slate-500 text-xs">
            <Clock className="w-6 h-6 text-slate-600 mb-2 animate-spin" />
            <p>Initial dispatch in flight...</p>
          </div>
        ) : (
          <div className="relative border-l-2 border-slate-800 ml-4 pl-5 space-y-5">
            {attempts.map((attempt) => {
              const isSuccess =
                attempt.response_status &&
                attempt.response_status >= 200 &&
                attempt.response_status < 300;

              return (
                <div key={attempt.id} className="relative group">
                  {/* Timeline Node Dot */}
                  <div
                    className={`absolute -left-[29px] top-1 w-4 h-4 rounded-full border-2 border-slate-900 flex items-center justify-center ${
                      isSuccess ? 'bg-emerald-500 ring-2 ring-emerald-500/20' : 'bg-rose-500 ring-2 ring-rose-500/20'
                    }`}
                  >
                    {isSuccess ? (
                      <CheckCircle2 className="w-2.5 h-2.5 text-slate-950" />
                    ) : (
                      <AlertOctagon className="w-2.5 h-2.5 text-slate-950" />
                    )}
                  </div>

                  {/* Card Content */}
                  <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-3 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-slate-200">
                          Attempt #{attempt.attempt_number}
                        </span>
                        {attempt.response_status ? (
                          <span
                            className={`font-mono font-bold px-2 py-0.5 rounded text-[11px] ${
                              isSuccess
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                                : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                            }`}
                          >
                            HTTP {attempt.response_status}
                          </span>
                        ) : (
                          <span className="font-mono text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded text-[11px] border border-rose-500/30">
                            Connection Error
                          </span>
                        )}
                      </div>

                      <div className="flex items-center space-x-3 text-slate-400 text-[11px] font-mono">
                        <span>{attempt.latency_ms.toFixed(1)}ms</span>
                        <span>{new Date(attempt.created_at).toLocaleTimeString()}</span>
                      </div>
                    </div>

                    {/* Error message or snippet */}
                    {attempt.error_message && (
                      <div className="text-xs text-rose-300 bg-rose-950/40 border border-rose-500/20 rounded p-2 font-mono">
                        {attempt.error_message}
                      </div>
                    )}

                    {attempt.response_body && (
                      <div className="text-[11px] text-slate-400 bg-slate-950 border border-slate-800/80 rounded p-2 font-mono break-all max-h-24 overflow-y-auto">
                        <span className="text-slate-600 block text-[10px] uppercase font-sans">
                          Response Body Snippet:
                        </span>
                        {attempt.response_body}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
