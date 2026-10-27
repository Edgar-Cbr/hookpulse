import React, { useEffect, useState } from 'react';
import { AttemptTimeline } from './components/AttemptTimeline';
import { Header } from './components/Header';
import { LiveEventFeed } from './components/LiveEventFeed';
import { PayloadInspector } from './components/PayloadInspector';
import { SimulatorBar } from './components/SimulatorBar';
import { useWebhookStream } from './hooks/useWebhookStream';
import { api } from './services/api';
import type { Endpoint } from './types/webhook';

export const App: React.FC = () => {
  const [endpoint, setEndpoint] = useState<Endpoint | null>(null);
  const activeSlug = endpoint?.slug || 'ep_taxguard_prod';

  // Load active endpoint info
  useEffect(() => {
    let isMounted = true;
    api
      .getEndpoints()
      .then((endpoints) => {
        if (!isMounted) return;
        const defaultEp =
          endpoints.find((e) => e.slug === 'ep_taxguard_prod') || endpoints[0] || null;
        setEndpoint(defaultEp);
      })
      .catch(() => {
        // Fallback to static representation if API temporarily unavailable
        if (!isMounted) return;
        setEndpoint({
          id: '00000000-0000-0000-0000-000000000000',
          slug: 'ep_taxguard_prod',
          name: 'TaxGuard Fiscal Batch Webhook',
          target_url: 'http://backend:8000/api/v1/simulator/mock-target?behavior=success',
          signing_secret: 'whsec_taxguard_secure_token_secret_123',
          is_active: true,
          created_at: new Date().toISOString(),
        });
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const {
    events,
    selectedEvent,
    setSelectedEvent,
    isConnected,
    isReconnecting,
    isLoading,
    replayEvent,
  } = useWebhookStream({ slug: activeSlug });

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      {/* 1. Header with Live Status & Counters */}
      <Header
        endpoint={endpoint}
        events={events}
        isConnected={isConnected}
        isReconnecting={isReconnecting}
      />

      {/* 2. Simulator Controls Bar */}
      <SimulatorBar
        endpointSlug={activeSlug}
        onTriggered={() => {
          // New event will arrive automatically through WebSocket
        }}
      />

      {/* 3. Main Dashboard Workspace */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-full min-h-[calc(100vh-210px)]">
          {/* Left Column: Live Event Ingestion Feed (5 cols) */}
          <div className="lg:col-span-5 h-[650px] lg:h-[calc(100vh-240px)] sticky top-28">
            <LiveEventFeed
              events={events}
              selectedEvent={selectedEvent}
              onSelectEvent={setSelectedEvent}
              isLoading={isLoading}
            />
          </div>

          {/* Right Column: Timeline & Payload Inspector (7 cols) */}
          <div className="lg:col-span-7 flex flex-col gap-6">
            {/* Upper: Attempt Timeline & Replay Controls */}
            <div className="min-h-[300px] flex-1">
              <AttemptTimeline
                event={selectedEvent}
                onReplay={replayEvent}
              />
            </div>

            {/* Lower: Payload & Headers Inspector */}
            <div className="min-h-[340px] flex-1">
              <PayloadInspector event={selectedEvent} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default App;
