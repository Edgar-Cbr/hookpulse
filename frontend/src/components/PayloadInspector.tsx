import React, { useState } from 'react';
import {
  Check,
  Code2,
  Copy,
  FileJson,
  Layers,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import type { WebhookEvent } from '../types/webhook';

interface PayloadInspectorProps {
  event: WebhookEvent | null;
}

export const PayloadInspector: React.FC<PayloadInspectorProps> = ({ event }) => {
  const [activeTab, setActiveTab] = useState<'payload' | 'headers'>('payload');
  const [copied, setCopied] = useState<boolean>(false);

  if (!event) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[300px] p-8 text-center bg-slate-900/50 border border-slate-800 rounded-xl text-slate-500">
        <FileJson className="w-10 h-10 text-slate-700 mb-3" />
        <h3 className="text-sm font-semibold text-slate-400">No Event Selected</h3>
        <p className="text-xs text-slate-600 mt-1 max-w-xs">
          Select any event from the live feed to inspect its raw JSON payload and HTTP headers.
        </p>
      </div>
    );
  }

  const payloadString = JSON.stringify(event.payload || {}, null, 2);
  const headersString = JSON.stringify(event.headers || {}, null, 2);

  const handleCopy = () => {
    const textToCopy = activeTab === 'payload' ? payloadString : headersString;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col h-full bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
      {/* Header & Tabs */}
      <div className="p-3.5 border-b border-slate-800 bg-slate-900/80 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setActiveTab('payload')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-colors ${
                activeTab === 'payload'
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Code2 className="w-3.5 h-3.5" />
              <span>Payload</span>
            </button>
            <button
              onClick={() => setActiveTab('headers')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium transition-colors ${
                activeTab === 'headers'
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Headers</span>
            </button>
          </div>

          {/* HMAC Signature pill */}
          {event.signature_valid ? (
            <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
              <ShieldCheck className="w-3 h-3" />
              HMAC Verified
            </span>
          ) : (
            <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-medium text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2 py-0.5 rounded-full">
              <ShieldAlert className="w-3 h-3" />
              Unverified Signature
            </span>
          )}
        </div>

        {/* Copy Button */}
        <button
          onClick={handleCopy}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700/60 rounded-md transition-colors"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span>Copy JSON</span>
            </>
          )}
        </button>
      </div>

      {/* Code Viewer Body */}
      <div className="flex-1 overflow-auto p-4 bg-slate-950 font-mono text-xs text-slate-200 leading-relaxed selection:bg-indigo-600 selection:text-white">
        <pre className="whitespace-pre-wrap break-words">
          <code>{activeTab === 'payload' ? payloadString : headersString}</code>
        </pre>
      </div>
    </div>
  );
};
