# HookPulse — Real-Time Webhook Gateway, Inspector & Resilient Delivery Engine

## Metadatos para el Repositorio de GitHub
- **Nombre del repositorio:** `hookpulse`
- **Descripción corta (About):** Real-time webhook gateway, live payload inspector & resilient delivery engine with exponential backoff, Dead-Letter Queue (DLQ), and interactive React SPA dashboard.
- **Topics sugeridos:** `webhooks` `fastapi` `websockets` `redis` `postgresql` `react` `typescript` `event-driven-architecture` `micro-saas` `docker`

---

## 1. Visión General y Arquitectura
**HookPulse** es un Micro-SaaS para desarrolladores (inspirado en Svix y RequestBin) que actúa como pasarela de ingesta, inspector en tiempo real y motor resiliente de entrega de webhooks.

### Características Principales
1. **Ingesta de Alta Velocidad y Seguridad HMAC-SHA256:** Recibe eventos HTTP POST en rutas personalizadas (`/ingest/{slug}`), valida firmas criptográficas en tiempo constante y responde `202 Accepted` en menos de 15 ms.
2. **Streaming en Vivo (WebSockets + Redis Pub/Sub):** Cada webhook entrante y cada cambio de estado se transmite instantáneamente al navegador sin recargar la página.
3. **Motor de Entrega con Exponential Backoff + Jitter:** Un worker asíncrono reenvía el payload al servidor destino (`target_url`) y, ante caídas o errores `5xx`/timeouts, reprograma hasta 5 reintentos con espera exponencial.
4. **Dead-Letter Queue (DLQ) & Manual Replay:** Los eventos que agotan sus 5 intentos pasan a estado `DLQ`, permitiendo al desarrollador inspeccionar el fallo y disparar un **Replay** manual en un clic desde la interfaz.
5. **Simulador Integrado (Sinergia con `taxguard-api`):** Incluye un generador de tráfico que simula eventos reales de validación fiscal/facturación y un receptor mock configurable (`200 OK` vs `500 Internal Server Error`) para demostrar la tolerancia a fallos en vivo.

### Stack Tecnológico
- **Backend:** Python 3.12 + FastAPI (Async) + WebSockets nativos + `httpx.AsyncClient`.
- **Base de Datos:** PostgreSQL 16 con SQLAlchemy 2.0 (`AsyncSession` + `asyncpg`) y Alembic.
- **Tiempo Real y Mensajería:** Redis 7 (`redis.asyncio`) para canales Pub/Sub y control de colas.
- **Frontend (SPA):** React 18 + TypeScript + Vite + Tailwind CSS + `lucide-react`.
- **Infraestructura:** Docker y Docker Compose (PostgreSQL + Redis + Backend API/Worker + Frontend SPA).

---

## 2. Estructura del Monorepo

    hookpulse/
    ├── backend/
    │   ├── app/
    │   │   ├── api/
    │   │   │   ├── v1/
    │   │   │   │   ├── endpoints/
    │   │   │   │   │   ├── endpoints.py    (CRUD de túneles/endpoints)
    │   │   │   │   │   ├── ingest.py       (POST /ingest/{slug} público)
    │   │   │   │   │   ├── events.py       (Listado, detalle y POST replay)
    │   │   │   │   │   └── simulator.py    (Disparador de pruebas y receptor mock)
    │   │   │   │   └── router.py
    │   │   │   ├── ws.py                   (WebSocket Manager + Redis Pub/Sub listener)
    │   │   │   └── deps.py                 (Inyección de dependencias AsyncSession y Redis)
    │   │   ├── core/
    │   │   │   ├── config.py               (Pydantic Settings v2)
    │   │   │   ├── crypto.py               (Firma y verificación HMAC-SHA256)
    │   │   │   └── redis.py                (Cliente redis.asyncio y helper de publicación)
    │   │   ├── db/
    │   │   │   ├── base.py                 (DeclarativeBase de SQLAlchemy 2.0)
    │   │   │   └── session.py              (create_async_engine y async_sessionmaker)
    │   │   ├── models/
    │   │   │   ├── endpoint.py             (Modelo Endpoint)
    │   │   │   ├── webhook_event.py        (Modelo WebhookEvent)
    │   │   │   └── delivery_attempt.py     (Modelo DeliveryAttempt)
    │   │   ├── schemas/
    │   │   │   ├── endpoint.py
    │   │   │   ├── event.py
    │   │   │   └── simulator.py
    │   │   ├── services/
    │   │   │   ├── delivery_engine.py      (Envío con httpx, registro de latencia y worker)
    │   │   │   └── backoff.py              (Cálculo de Exponential Backoff + Jitter)
    │   │   └── main.py                     (Lifespan async, seed inicial y montaje de rutas)
    │   ├── tests/
    │   │   ├── conftest.py
    │   │   └── test_webhook_flow.py        (Pruebas de ingesta, HMAC, backoff y replay)
    │   ├── Dockerfile
    │   └── requirements.txt
    ├── frontend/
    │   ├── src/
    │   │   ├── components/
    │   │   │   ├── Header.tsx              (Estado del WebSocket y selector de Endpoint)
    │   │   │   ├── LiveEventFeed.tsx       (Lista en tiempo real con badges de estado)
    │   │   │   ├── PayloadInspector.tsx    (Visor JSON de Payload, Headers y firma HMAC)
    │   │   │   ├── AttemptTimeline.tsx     (Historial de reintentos, códigos HTTP y latencia)
    │   │   │   └── SimulatorBar.tsx        (Controles para simular 200 OK o 500 Fallo/DLQ)
    │   │   ├── hooks/
    │   │   │   └── useWebhookStream.ts     (Hook de conexión WebSocket auto-reconectable)
    │   │   ├── services/
    │   │   │   └── api.ts                  (Cliente HTTP hacia FastAPI)
    │   │   ├── types/
    │   │   │   └── webhook.ts              (Interfaces TypeScript)
    │   │   ├── App.tsx
    │   │   └── main.tsx
    │   ├── Dockerfile
    │   ├── package.json
    │   ├── tailwind.config.js
    │   └── vite.config.ts
    ├── .github/
    │   └── workflows/
    │       └── ci.yml                      (Pipeline con Ruff + Pytest + Build Frontend en develop y main)
    ├── docker-compose.yml
    ├── .env.example
    ├── .gitignore
    └── BLUEPRINT.md

---

## 3. Esquema de Base de Datos (PostgreSQL 16)

### Tabla 1: `endpoints`
- `id`: UUID (PK, default `uuid4`)
- `slug`: VARCHAR(40) (Unique, Index, ej. `ep_taxguard_prod`)
- `name`: VARCHAR(100) (ej. `TaxGuard Fiscal Batch Webhook`)
- `target_url`: VARCHAR(500) (URL destino donde se entregará el webhook)
- `signing_secret`: VARCHAR(128) (Secreto con prefijo `whsec_` para HMAC-SHA256)
- `is_active`: BOOLEAN (default `True`)
- `created_at`: TIMESTAMPTZ (default `now()`)

### Tabla 2: `webhook_events`
- `id`: UUID (PK, default `uuid4`)
- `endpoint_id`: UUID (FK -> `endpoints.id` ON DELETE CASCADE, Index)
- `event_type`: VARCHAR(100) (Index, ej. `tax_id.batch.completed`, `subscription.upgraded`)
- `headers`: JSONB (Encabezados HTTP originales recibidos)
- `payload`: JSONB (Cuerpo JSON recibido)
- `signature_valid`: BOOLEAN (True si el header `X-Webhook-Signature` coincide con el HMAC-SHA256)
- `status`: VARCHAR(20) (Index: `PENDING`, `DELIVERED`, `RETRYING`, `DLQ`)
- `retry_count`: INTEGER (default `0`, máximo `5`)
- `next_retry_at`: TIMESTAMPTZ (Nullable, Index para el polling del worker)
- `created_at`: TIMESTAMPTZ (default `now()`, Index)

### Tabla 3: `delivery_attempts`
- `id`: BIGSERIAL (PK)
- `event_id`: UUID (FK -> `webhook_events.id` ON DELETE CASCADE, Index)
- `attempt_number`: INTEGER (`1` a `5`, o mayor en caso de Replay manual)
- `response_status`: INTEGER (Nullable, ej. `200`, `500`, `504`)
- `response_body`: TEXT (Nullable, primeros 1000 caracteres devueltos por el destino)
- `latency_ms`: FLOAT (Duración del intento en milisegundos)
- `error_message`: VARCHAR(500) (Nullable, detalle de excepción o rechazo HTTP)
- `created_at`: TIMESTAMPTZ (default `now()`)

---

## 4. Algoritmos y Mecánicas Nucleares

### 4.1 Verificación y Firma HMAC-SHA256 (`app/core/crypto.py`)
- Función `compute_hmac_signature(secret: str, raw_body: bytes) -> str`:
  Calcula `hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()`.
- Función `verify_hmac_signature(secret: str, raw_body: bytes, provided_sig: str | None) -> bool`:
  Si no hay firma provista, devuelve `False`. Si existe (aceptando formato `sha256=<hex>` o `<hex>`), compara con `hmac.compare_digest()` para prevenir ataques de temporización.

### 4.2 Algoritmo Exponential Backoff con Jitter (`app/services/backoff.py`)
- Cuando un intento de entrega devuelve código `>= 400` o sufre un `httpx.RequestError`:
  - Si `retry_count < 5`:
    - `retry_count += 1`
    - `status = "RETRYING"`
    - `delay = (2 ** retry_count) + random.uniform(0.1, 1.5)` segundos.
    - `next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)`
  - Si `retry_count >= 5`:
    - `status = "DLQ"`
    - `next_retry_at = None`

### 4.3 Bridge Redis Pub/Sub -> WebSockets (`app/api/ws.py`)
- Cada vez que se crea un `WebhookEvent` o se registra un nuevo `DeliveryAttempt`, el backend publica un mensaje JSON en el canal de Redis `hookpulse:events:{slug}`.
- El endpoint `WS /ws/endpoints/{slug}` se suscribe con `redis.pubsub()` a `hookpulse:events:{slug}` y retransmite cada mensaje inmediatamente al cliente React conectado.

---

## 5. Especificación de Endpoints REST y WebSocket

| Método y Ruta | Descripción | Respuesta Clave |
| :--- | :--- | :--- |
| `GET /health` | Verifica estado de PostgreSQL y Redis. | `200 OK` -> `{"status": "ok", "postgres": true, "redis": true}` |
| `GET /api/v1/endpoints` | Lista todos los endpoints configurados y contadores por estado. | `200 OK` -> Lista de `EndpointRead` |
| `POST /api/v1/endpoints` | Crea un nuevo endpoint con `slug` y `signing_secret` autogenerado. | `201 Created` -> `EndpointRead` |
| `POST /ingest/{slug}` | **Ingesta de Webhook:** recibe payload, verifica HMAC, persiste en DB, publica en WS y lanza intento #1. | `202 Accepted` -> `{"event_id": "...", "status": "PENDING"}` |
| `GET /api/v1/endpoints/{slug}/events` | Obtiene los últimos 50 eventos del endpoint incluyendo su arreglo de `attempts`. | `200 OK` -> Lista de `WebhookEventDetail` |
| `POST /api/v1/events/{event_id}/replay` | **Replay Manual:** fuerza un nuevo intento inmediato de entrega para un evento en `DLQ` o `DELIVERED`. | `200 OK` -> `WebhookEventDetail` actualizado |
| `POST /api/v1/simulator/trigger` | Dispara un webhook de prueba (`tax_id.batch.completed`) con firma HMAC y modo `success` (`200`) o `fail` (`500`). | `202 Accepted` -> Evento disparado |
| `POST /api/v1/simulator/mock-target` | Receptor interno simulado que responde `200 OK` o `500 Error` según `?behavior=success\|fail`. | `200 OK` o `500 Internal Server Error` |
| `WS /ws/endpoints/{slug}` | Stream en vivo de eventos nuevos y actualizaciones de intentos de entrega. | Mensajes JSON en tiempo real |

---

## 6. Política GitFlow con Micro-Commits Atómicos y Push en Tiempo Real

1. **Jerarquía de Ramas:**
   - `main`: Rama de **Producción**. Prohibido hacer commits directos o merges desde ramas de funcionalidad. Solo recibe merges de `develop` (`git merge --no-ff develop`).
   - `develop`: Rama de **Integración**. Todas las ramas de trabajo nacen de `develop` y se fusionan de vuelta en `develop` con `--no-ff`.
2. **Regla de Micro-Commits Atómicos (PROHIBIDO hacer 1 solo commit por fase):**
   - Cada fase debe dividirse en **4 a 6 commits granulares** (1 commit por cada módulo o componente creado).
   - Inmediatamente después de cada commit local, se debe ejecutar `git push -u origin <rama>` para que la actividad se registre en GitHub en tiempo real mientras avanza el desarrollo.
3. **Nomenclatura de Ramas:**
   - Fase 1: `chore/phase-1-core-infra`
   - Fase 2: `feat/phase-2-db-models-hmac`
   - Fase 3: `feat/phase-3-ingest-websockets`
   - Fase 4: `feat/phase-4-backoff-dlq-engine`
   - Fase 5: `feat/phase-5-react-spa-ci`
