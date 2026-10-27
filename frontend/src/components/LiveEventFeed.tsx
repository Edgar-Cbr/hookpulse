import React, { useState } from 'react';
import {
  AlertOctagon,
  CheckCircle2,
  Clock,
  Filter,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import type { WebhookEvent, WebhookStatus } from '../types/webhook';

interface LiveEventFeedProps {
  events: WebhookEvent[];
  selectedEvent: WebhookEvent | null;
  onSelectEvent: (event: WebhookEvent) => void;
  isLoading: boolean;
}

export const LiveEventFeed: React.FC<LiveEventFeedProps> = ({
  events,
  selectedEvent,
  onSelectEvent,
  isLoading,
}) => {
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const filteredEvents = events.filter((e) => {
    const matchesStatus =
      statusFilter === 'ALL' ? true : e.status === statusFilter;
    const matchesSearch =
      searchQuery.trim() === ''
        ? true
        : e.event_type.toLowerCase().includes(searchQuery.toLowerCase()) ||
          e.id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const renderStatusBadge = (status: WebhookStatus, retryCount: number) => {
    switch (status) {
      case 'DELIVERED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-sm shadow-emerald-500/10">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            DELIVERED
          </span>
        );
      case 'RETRYING':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 shadow-sm shadow-amber-500/10 animate-pulse">
            <RefreshCw className="w-3 h-3 text-amber-400 animate-spin" />
            RETRYING #{retryCount}/5
          </span>
        );
      case 'DLQ':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20 shadow-sm shadow-rose-500/10">
            <AlertOctagon className="w-3 h-3 text-rose-400" />
            DLQ FAILED
          </span>
        );
      case 'PENDING':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/20">
            <Clock className="w-3 h-3 text-slate-400" />
            PENDING
          </span>
        );
    }
  };

  const formatTime = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      {/* Header & Filter Controls */}
      <div className="p-3.5 border-b border-slate-800 bg-slate-900/80 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <span>Live Ingestion Feed</span>
              <span className="text-xs px-2 py-0.2 rounded-full bg-slate-800 text-slate-400 font-mono">
                {filteredEvents.length}
              </span>
            </h3>
          </div>

          {/* Search Box */}
          <div className="relative w-44 sm:w-56">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search event type..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full text-xs bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>
        </div>

        {/* Status Filter Tabs */}
        <div className="flex items-center space-x-1.5 overflow-x-auto pb-0.5 text-xs">
          {['ALL', 'DELIVERED', 'RETRYING', 'DLQ'].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                statusFilter === status
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                  : 'bg-slate-800/60 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Events List */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60 p-2 space-y-1">
        {isLoading && events.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-slate-500 text-xs">
            <RefreshCw className="w-5 h-5 animate-spin mb-2 text-indigo-400" />
            <span>Connecting to live webhook feed...</span>
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center p-6 text-slate-500 text-xs">
            <Filter className="w-8 h-8 text-slate-600 mb-2" />
            <p className="font-medium text-slate-400">No events found</p>
            <p className="text-[11px] text-slate-600 mt-1">
              {events.length === 0
                ? 'Use the Simulator above to fire a test webhook!'
                : 'Try clearing the search or status filter.'}
            </p>
          </div>
        ) : (
          filteredEvents.map((event) => {
            const isSelected = selectedEvent?.id === event.id;
            const attemptCount = event.attempts?.length || 0;

            return (
              <div
                key={event.id}
                onClick={() => onSelectEvent(event)}
                className={`group p-3 rounded-lg cursor-pointer transition-all border ${
                  isSelected
                    ? 'bg-slate-800/90 border-indigo-500/50 shadow-md shadow-indigo-500/5'
                    : 'bg-slate-900/40 border-slate-800/60 hover:bg-slate-800/50 hover:border-slate-700/80'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-xs font-semibold text-slate-200 truncate">
                        {event.event_type}
                      </span>
                      {event.signature_valid ? (
                        <span
                          title="HMAC-SHA256 signature verified"
                          className="text-[10px] inline-flex items-center gap-0.5 text-emerald-400 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20"
                        >
                          <ShieldCheck className="w-3 h-3" />
                          HMAC
                        </span>
                      ) : (
                        <span
                          title="HMAC signature invalid or missing"
                          className="text-[10px] inline-flex items-center gap-0.5 text-rose-400 bg-rose-500/10 px-1.5 py-0.2 rounded border border-rose-500/20"
                        >
                          <ShieldAlert className="w-3 h-3" />
                          NO SIG
                        </span>
                      )}
                    </div>
                    <div className="flex items-center space-x-2 text-[11px] text-slate-400 font-mono">
                      <span>{event.id.slice(0, 13)}...</span>
                      <span>•</span>
                      <span>
                        {attemptCount} {attemptCount === 1 ? 'attempt' : 'attempts'}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col items-end space-y-1 shrink-0">
                    {renderStatusBadge(event.status, event.retry_count)}
                    <span className="text-[10px] text-slate-500 font-mono">
                      {formatTime(event.created_at)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
