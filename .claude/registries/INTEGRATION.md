# Integration Surface Map

> **Purpose:** machine-readable map of every cross-module integration point — API endpoints, SignalR events, DTO↔model pairings, and end-to-end data flows. The `data-architect` reads this BEFORE proposing anything that crosses a module boundary. Implementer agents consult it when their changes touch shared surfaces. The `fullstack-code-reviewer` keeps it current.
>
> **Maintained by:** `fullstack-code-reviewer` updates this file after every implementation that introduces or modifies an API endpoint, SignalR event, or DTO shape. The `validate-registries` skill checks that all file paths referenced here still exist.

---

## Module Dependency Graph

```
ScalpingMachine.API
├── ScalpingMachine.Services
├── ScalpingMachine.Persistence
├── ScalpingMachine.Domain
└── ScalpingMachine.Strategy

ScalpingMachine.Services
├── ScalpingMachine.Domain
├── ScalpingMachine.Strategy
├── ScalpingMachine.Persistence
├── ScalpingMachine.LLM
└── ScalpingMachine.IbkrApi

ScalpingMachine.Strategy
└── (no internal project references)

ScalpingMachine.Domain
└── (no dependencies — the root)

ScalpingMachine.Persistence
├── ScalpingMachine.Domain
└── ScalpingMachine.Strategy

ScalpingMachine.LLM
└── ScalpingMachine.Domain

scalping-machine (Angular) → API (REST at :5124/api + SignalR at /hubs/scalping)
admin-panel (Angular) → API (REST at :5124/api/admin + SignalR at /hubs/scalping)
scalping-mobile (Angular + Ionic) → API (GraphQL at :5124/graphql) — NO REST client, NO SignalR

--- Angular workspace libraries (ClientApp/projects/*, all four) ---

Edges below are the DECLARED peerDependencies in each projects/<lib>/package.json, which
package-manifest.spec.ts asserts in both directions against the derived imports.

@scalping/api-client         (projects/api-client)
└── (no workspace-library peer — generated NSwag REST client; the leaf)
    consumed by: scalping-machine, admin-panel

@scalping/strategy-authoring (projects/strategy-authoring)
└── @scalping/api-client   (+ @angular/{common,forms,material,router}, @syncfusion/ej2-*-querybuilder)
    consumed by: scalping-machine, admin-panel

@scalping/recording          (projects/recording)
└── @scalping/api-client   (+ @angular/material — the arm control and list are Material-based)
    consumed by: scalping-machine (REST transport, the library default)
                 scalping-mobile (GraphQL transport, host-supplied via provideRecording())
    NOT consumed by admin-panel.
    NOTE 1: apollo-angular is deliberately NOT a peer — the GraphQL adapter lives in the APP
            (scalping-mobile/core/adapters/graphql-recording-transport.ts), never in the library.
    NOTE 2: the @angular/material peer is why scalping-mobile hosts RecordingCaptureService
            headlessly with its own Ionic UI instead of CaptureArmControlComponent /
            RecordingListComponent.

@scalping/chat               (projects/chat)
└── @scalping/api-client, @scalping/strategy-authoring   (+ @angular/material, marked)
    consumed by: scalping-machine (client role), admin-panel (agent role).
    NOT consumed by scalping-mobile today, despite the multi-host design intent.

Build order (ng build): api-client → strategy-authoring → recording → chat → applications
(chat is last of the libraries because it is the only one peering on another library.)
```

### Layer Rules

- API depends on Services, Strategy, Persistence, Domain — it is the composition root
- Services depends on Domain, Strategy, Persistence, LLM, IbkrApi — business logic orchestration
- Strategy depends ONLY on itself — pure execution engine, no infrastructure
- Domain depends on NOTHING — entities, interfaces, value objects
- Persistence depends on Domain and Strategy — EF Core implementations of domain ports
- LLM depends on Domain only — LLM provider abstractions

### Operational Constraints

- **API DLL lock:** The .NET API DLL is locked while the VS debugger or `dotnet run` is active. After every backend code change, the API must be stopped and restarted.
- **EF Core migration sequence:** Stop API → `dotnet ef migrations add <Name> --project src/ScalpingMachine.Persistence --startup-project src/ScalpingMachine.API` → restart API (migration auto-applies on startup via `db.Database.Migrate()`).

---

## API Surface — Scalping Machine App

| Controller | Method | Route | Request DTO | Response `T` in `ApiResponse<T>` |
|---|---|---|---|---|
| **AuthController** | POST | `/api/auth/register` | `RegisterRequest` | `AuthResponse` |
| | POST | `/api/auth/login` | `LoginRequest` | `AuthResponse` |
| | POST | `/api/auth/forgot-password` | `ForgotPasswordRequest` | `PasswordResetResponse` |
| | POST | `/api/auth/reset-password` | `ResetPasswordRequest` | `string` |
| | GET | `/api/auth/me` | — | `CurrentUserResponse` |
| **AccountController** | POST | `/api/account/subscribe` | `AccountSubscribeRequest` | `bool` |
| | GET | `/api/account/summary` | — | `AccountSummary` |
| | GET | `/api/account/positions` | — | `Position[]` |
| **MarketDataController** | POST | `/api/marketdata/subscribe` | `MarketDataSubscription` | `MarketDataSubscription` |
| | POST | `/api/marketdata/unsubscribe` | `UnsubscribeRequest` | `bool` |
| | GET | `/api/marketdata/quotes` | — | `QuoteSnapshot[]` |
| | POST | `/api/marketdata/historical` | `HistoricalDataRequest` | `OhlcBarDto[]` |
| **StrategyController** | POST | `/api/strategies/draft` | `StrategyDefinition` | `StrategyDefinition` |
| | PATCH | `/api/strategies/{id}/draft` | `StrategyDefinition` | `StrategyDefinition` |
| | POST | `/api/strategies` | `StrategyDefinition` | `SaveStrategyResponse` |
| | PUT | `/api/strategies/{id}` | `StrategyDefinition` | `SaveStrategyResponse` |
| | GET | `/api/strategies` | — | `StrategyDefinition[]` |
| | GET | `/api/strategies/{id}` | — | `StrategyDefinition` |
| | GET | `/api/strategies/{id}/tree` | — | `StrategyDefinition` |
| | DELETE | `/api/strategies/{id}` | — | `bool` (soft-delete) |
| | POST | `/api/strategies/{id}/restore` | — | `StrategyDefinition` |
| | GET | `/api/strategies/{id}/validate` | — | `ValidationResult` |
| | GET | `/api/strategies/deleted` | — | `StrategyDefinition[]` |
| | POST | `/api/strategies/{id}/duplicate` | query: `includeChildren` | `StrategyDefinition` |
| | GET | `/api/strategies/data-elements` | query: `context` | `DataElementsResponse` — **shape changed in #32**, was `FieldDefinition[]`. Now `{ fields, templates, configurations }`. **Newly gated `[RequirePermission(strategy.read)]`** |
| | POST | `/api/strategies/data-elements/describe` | `DescribeFieldsRequest` (max 200 keys / 128 chars per key / arity 8, all enforced before parsing) | `DescribeFieldsResponse` — `{ fields, unresolved }`. `unresolved` is a first-class outcome: a key naming a retired template is returned BY NAME, never dropped, because a dropped key renders its rule blank in the builder |
| **IndicatorConfigurationController** | GET | `/api/indicator-configurations` | — | `IndicatorConfigurationListResponse` — owner-scoped; `[RequirePermission(strategy.read)]` |
| | GET | `/api/indicator-configurations/{id}` | — | `IndicatorConfigurationDto` — owner-scoped. **Another user's row returns NOT FOUND, never FORBIDDEN**, so the endpoint cannot be used as an existence oracle |
| | POST | `/api/indicator-configurations` | `CreateIndicatorConfigurationRequest` | `IndicatorConfigurationDto` — `[RequirePermission(strategy.write)]`; rejects non-`RoleAudience.User` principals |
| | PUT | `/api/indicator-configurations/{id}` | `UpdateIndicatorConfigurationRequest` | `IndicatorConfigurationDto` — `[RequirePermission(strategy.write)]` |
| | DELETE | `/api/indicator-configurations/{id}` | — | `bool` — hard delete (invariant I-7); `[RequirePermission(strategy.write)]` |
| **StrategyRunController** | POST | `/api/strategy-runs` | `StartStrategyRunRequest` + optional query `executionMode: Live \| Shadow` (default `Live`) | `StrategyRun` |
| | GET | `/api/strategy-runs` | — | `StrategyRun[]` |
| | GET | `/api/strategy-runs/{runId}` | — | `StrategyRun` |
| | POST | `/api/strategy-runs/{runId}/stop` | — | `bool` |
| | GET | `/api/strategy-runs/{runId}/flow` | — | `StrategyFlow` |
| | POST | `/api/strategy-runs/{runId}/flow/{flowId}/action` | `{ action }` | `StrategyFlow` |
| **NotificationController** | GET | `/api/notifications/unread` | — | `StrategyNotification[]` |
| | GET | `/api/notifications/runs/{runId}` | — | `StrategyNotification[]` |
| | POST | `/api/notifications/{id}/read` | — | `bool` |
| | POST | `/api/notifications/{id}/action` | `{ action }` | `StrategyNotification` |
| **BacktestController** | POST | `/api/backtests` | `{ strategyId, config }` | `BacktestResult` |
| | POST | `/api/backtests/start` | `{ strategyId, config }` | `BacktestStartResponse` |
| | GET | `/api/backtests/{id}/status` | — | `BacktestRunInfo` |
| | DELETE | `/api/backtests/{id}` | — | `bool` |
| | GET | `/api/backtests/history` | query: `strategyId` | `BacktestHistoryItem[]` |
| | GET | `/api/backtests/history/{runId}` | — | `BacktestHistoryDetail` |
| | GET | `/api/backtests/historical-data` | — | `HistoricalDataEntry[]` |
| | GET | `/api/backtests/historical-data/{symbol}` | query: `barSize` | `HistoricalDataSummary` |
| | GET | `/api/backtests/historical-data/{symbol}/bars` | query: `barSize, from, to` | `OhlcBarDto[]` |
| | POST | `/api/backtests/historical-data/import` | `ImportHistoricalDataRequest` | `bool` |
| **OrderController** | POST | `/api/orders` | `OrderRequest` | `ApiResponse<int>` (failures: broker not connected / preflight-cancelled, broker rejected, broker outcome unknown — 2026-09-01-ibkr-order-acknowledgement-and-identity) |
| | GET | `/api/orders` | — | `ScalpingOrder[]` |
| | GET | `/api/orders/{orderId}` | — | `ScalpingOrder` |
| | POST | `/api/orders/{orderId}/cancel` | — | `bool` |
| **ContractController** | POST | `/api/contracts/search` | `ContractSearchRequest` | `ContractDetails[]` |
| | GET | `/api/contracts/optionchain/{underlying}` | query: `expirationDte` | `OptionChainSnapshot` |
| **ChatController** | POST | `/api/chat/message` | `ChatRequest` | `ApiResponseOf<ChatResponse>` |
| | POST | `/api/chat/context/message` | `ChatContextRequest` | `ApiResponseOf<ChatContextResponse>` |
| | GET | `/api/chat/suggestions` | query: `contextType` | `ApiResponseOf<string[]>` |
| | GET | `/api/chat/conversations` | — | `ApiResponseOf<ChatConversationDto[]>` |
| | GET | `/api/chat/conversations/{id}/messages` | query: `skip`, `take` | `ApiResponseOf<ChatMessageDto[]>` |
| | POST | `/api/chat/conversations/{id}/archive` | — | `ApiResponseOf<bool>` |
| | DELETE | `/api/chat/conversations/{id}` | — | `ApiResponseOf<bool>` |
| **WatchlistController** | POST | `/api/watchlists` | `CreateWatchlistRequest` | `Watchlist` |
| | GET | `/api/watchlists` | — | `Watchlist[]` |
| | GET | `/api/watchlists/{id}` | — | `Watchlist` |
| | PUT | `/api/watchlists/{id}` | `UpdateWatchlistRequest` | `Watchlist` |
| | DELETE | `/api/watchlists/{id}` | — | `bool` |
| | POST | `/api/watchlists/{id}/symbols` | `{ symbols[] }` | `Watchlist` |
| **ScreenerDefinitionController** | POST | `/api/screeners` | `ScreenerDefinition` | `ScreenerDefinition` |
| | GET | `/api/screeners` | — | `ScreenerDefinition[]` |
| | GET | `/api/screeners/{id}` | — | `ScreenerDefinition` |
| | PUT | `/api/screeners/{id}` | `ScreenerDefinition` | `ScreenerDefinition` |
| | DELETE | `/api/screeners/{id}` | — | `bool` |
| | POST | `/api/screeners/{id}/run` | `ScreenerRunRequest` | `ScreenerResult` |
| **ConnectionController** | GET | `/api/connection/status` | — | `ConnectionStatus` |
| | POST | `/api/connection/connect` | — | `bool` |
| | POST | `/api/connection/disconnect` | — | `bool` |
| **ScheduleController** | *(strategy scheduling CRUD)* | `/api/schedules` | — | — |
| **PmccController** | GET | `/api/pmcc/default-account` | — | `PmccDefaultAccountResponse` |
| | GET | `/api/pmcc/accounts/{accountId:guid}` | — | `PmccSummaryDto[]` |
| | POST | `/api/pmcc/accounts/{accountId:guid}/sync` | — | `PmccSummaryDto[]` |
| | GET | `/api/pmcc/accounts/{accountId:guid}/{underlying}` | — | `PmccSummaryDto` |
| | GET | `/api/pmcc/accounts/{accountId:guid}/positions/{id:guid}` | — | `PmccLongPositionDto` |
| | PUT | `/api/pmcc/accounts/{accountId:guid}/positions/{id:guid}/notes` | `UpdatePmccNotesRequest` | `PmccLongPositionDto` |
| | POST | `/api/pmcc/accounts/{accountId:guid}/link` | `LinkPmccLongRequest` | `PmccLongPositionDto` |
| | POST | `/api/pmcc/accounts/{accountId:guid}/import` | `IFormFile (CSV, ≤10 MB)` | `FlexImportResultDto` |
| **SupportController** | POST | `/api/support/conversations` | `CreateSupportConversationRequest` | `SupportConversation` |
| | GET | `/api/support/conversations` | — | `SupportConversation[]` |
| | GET | `/api/support/conversations/{id}` | — | `SupportConversation` |
| | POST | `/api/support/conversations/{id}/messages` | `SupportMessageDto` | `SupportMessage` |
| | POST | `/api/support/conversations/{id}/mark-read` | — | `void` |
| **SymbolPriorityController** | GET | `/api/strategy/{strategyId}/pins` | — | `SymbolPriority[]` |
| | POST | `/api/strategy/{strategyId}/pins` | `SymbolPriority` | `SymbolPriority` |
| | DELETE | `/api/strategy/{strategyId}/pins/{symbol}` | — | `void` |
| **ReviewTagController** | GET | `/api/review-tags` | — | `ReviewTag[]` |
| | POST | `/api/review-tags` | `CreateReviewTagRequest` | `ReviewTag` |
| | DELETE | `/api/review-tags/{id}` | — | `bool` |
| **SymbolPerformanceController** | GET | `/api/symbol-performance/summary` | query: `lookback` | `SymbolPerfSummary` |
| | GET | `/api/symbol-performance/detail/{symbol}` | — | `SymbolPerfDetail` |
| **EarningsController** | GET | `/api/earnings/calendar` | query: `from, to` | `EarningsEvent[]` |
| | GET | `/api/earnings/{symbol}` | — | `EarningsDetail` |
| **RunPairController** *(Phase G — 2026-05-01; GET reads → `ApiResponse<T>` 2026-06-03)* | GET | `/api/run-pairs/active` | — | `ApiResponse<RunPairListItemDto[]>` (failure → HTTP 200 + `isSuccess:false`, converted 2026-06-03) |
| | GET | `/api/run-pairs/ended` | query: `offset, limit` (clamped 1-100), `strategyId?` (optional owner-scoped narrow) | `ApiResponse<PagedResponse<RunPairListItemDto>>` (failure → 200 + `isSuccess:false`, converted 2026-06-03) |
| | GET | `/api/run-pairs/{pairId}/divergence` | query: `limit` (clamped 1-5000, default 500) | `ApiResponse<RunPairDivergencePointDto[]>` (failure → 200 + `isSuccess:false`, converted 2026-06-03) |
| | GET | `/api/run-pairs/{pairId}/summary` | — | `ApiResponse<RunPairListItemDto>` (cold-start hydration; failure → 200 + `isSuccess:false`, converted 2026-06-03) |
| | POST | `/api/run-pairs/{pairId}/end` | — | `ApiResponse<…>` — **still `Task<IActionResult>` + 400-on-failure** (NOT converted; deferred — pinned `OkObjectResult`/`BadRequestObjectResult` tests) |
| | POST | `/api/run-pairs/{pairId}/force-entry` | `ForceEntryRequest` | `ApiResponse<…>` — **still `Task<IActionResult>` + 400-on-failure** (NOT converted; trading-adjacent — deferred to a `trading-safety-reviewer` cycle). Concept contract 2026-09-01-force-action-reservation-before-broker: shape unchanged, gains two new possible failure strings — `EntryAlreadyReserved` (`"A force-entry for this signal is already in flight or has already been submitted."`) alongside the existing `AlreadyPromoted` (`"Shadow order already promoted."`) |
| **StrategyRunController** *(Phase G — 2026-05-01)* | GET | `/api/strategy-runs/{runId}/pair` | — | `RunPairResolveByRunIdDto` (400 BadRequest with `Failure` envelope when unpaired or not owned — never 404, per `feedback_apiresponse_failure_status_code_must_match_nswag_throw_threshold.md`) |
| | POST | `/api/strategy-runs/{runId}/flows/{flowId}/force-close` | `ForceCloseRequest?` (optional body: quantity override for partial close; null = full close) | `ApiResponse<ForceCloseResponse>` — `Task<IActionResult>` + 400-on-failure. Concept contract 2026-09-01-force-action-reservation-before-broker: shape unchanged, gains one new possible failure string — `CloseAlreadyReserved` (`"A force-close for this position is already in flight."`). Same seam (`IForceActionService.ForceCloseAsync`) is reached from the chat tool `force_close_flow` (`ChatToolExecutor.cs:886`), so the same refusal string reaches both surfaces |
| | GET | `/api/force-actions?runId=&pairId=` | query: `runId?, pairId?` (at least one required) | `ApiResponse<List<ForceActionAuditDto>>` — `outcome` field's value set grows by two (`Pending`, `OutcomeUnknown`) per concept contract 2026-09-01-force-action-reservation-before-broker; no shape change |
| **AdminStrategyModelRegistryController** *(Phase H — 2026-05-01, admin)* | GET | `/api/admin/strategy-models` | query: `strategyId, status, promotedBy, createdAfter, createdBefore, ownerSubstring, opeScoreMin, opeScoreMax, trainingTransitionsMin, offset, limit` (7 filters + paging; limit clamped 1-100) | `PagedResponse<AdminStrategyModelListItemDto>` |
| | GET | `/api/admin/strategy-models/{modelVersionId}` | — | `AdminStrategyModelDetailDto` |
| | GET | `/api/admin/strategy-models/{modelVersionId}/transitions` | query: `limit` (default 50, max 200) | `AdminTrainingTransitionDto[]` |
| **AdminStrategyModelsController** *(Phase H — 2026-05-01, admin; Phase 3 shape 2026-05-29)* | POST | `/api/admin/strategies/{strategyId}/register-model` | `RegisterStrategyModelRequest { algoName, opeMetricsJson, modelArtifactPath }` | `ApiResponse<StrategyModelVersionDto>` — ContextJson serialised as `{ strategyId, algoName, opeMetricsJson }`; MetricsJson always `""` (Phase 3 Gap 4) |
| | POST | `/api/admin/strategies/{strategyId}/promote-model/{modelVersionId}` | — | `ApiResponse<StrategyModelVersionDto>` — best-effort GetByIdAsync follow-up after ActivateAsync; returns Success(null) if secondary fetch unavailable (Phase 3 Gap 3) |
| | POST | `/api/admin/strategies/{strategyId}/retrain-now` | `RetrainStrategyNowRequest?` (optional body with `algoName`) | `ApiResponse<IModelVersion>` (Phase 3 shape; proxied via `IModelRegistrationService.StartTrainingAsync(ModelKind.StrategyRl, …)`) |
| **SessionRecordingController** *(Slice A - 2026-08-19)* | POST | `/api/recordings` | `ArmRecordingRequest { purpose, captureMode, clientClaimedStartUtc, mediaType }` | `RecordingArmedResponse { recordingId, startedAtUtc }` - `startedAtUtc` is the SERVER stamp (I-3); the client's claim is stored for skew audit only |
| | POST | `/api/recordings/{id}/segments` | `[FromQuery]` `sequenceNumber, offsetMs, durationMs, byteLength` + streamed `multipart/form-data` body (`[DisableFormValueModelBinding]`, read via `IMultipartBlobIngestor` — metadata is NOT model-bound from the form) | `SegmentAcceptedResponse` |
| | POST | `/api/recordings/{id}/finalize` | `FinalizeRecordingRequest { totalDurationMs }` | `RecordingSummaryDto` (see the shape note below — carries `status`) |
| | GET | `/api/recordings` | query: `purpose?, offset, limit` | `PagedResponse<RecordingSummaryDto>` |
| | DELETE | `/api/recordings/{id}` | - | `bool` |
| | GET | `/api/recordings/{id}/playback` *(Playback — 2026-08-26)* | - | **Binary body, NOT `ApiResponse<T>`** — a declared, justified deviation (a byte stream cannot be enveloped). `200` declares `audio/webm` / `audio/ogg` / `application/octet-stream` via the 3-arg `[ProducesResponseType(typeof(FileResult), 200, string[])]`; the action writes straight to `Response.Body` (never `File(...)`) with an explicit `Response.ContentLength`, `Accept-Ranges: none`, `Cache-Control: no-store`, no `ETag`. **Blob-egress header controls (added 2026-08-26 by `security-auditor` F1, restoring what `BlobRangeWriter.cs:25-38` documents as mandatory for blob egress — do not weaken without re-reading that file):** `Content-Disposition: attachment` (**not** `inline` — an earlier revision of this row said `inline` and was wrong), `X-Content-Type-Options: nosniff` always, and the `Content-Type` is resolved through `ResolvePlaybackContentType`'s **allow-list** (`audio/webm` / `audio/ogg` / `video/webm` / `video/ogg`, matched on the base type with any `;codecs=…` stripped, `OrdinalIgnoreCase`) rather than echoed from the caller-controlled `MediaType` column; anything outside it is served as `application/octet-stream`. An admitted value is served **whole**, codecs parameter included, because the browser's media element reads it. **Six declared statuses:** `404` (not-found AND not-owner, deliberately indistinguishable) / `409` (not `Stored`) / `413` (over `Recording:MaxPlaybackBytes`, 512 MiB) / `500` (media unreadable) each carry `ApiResponse<object>`; `401` / `403` are refused by middleware and carry no envelope (Swashbuckle infers `ProblemDetails` for both). Gated `[RequirePermission(RecordingReadOwn)]` — no new key. |
| | GET | `/api/recordings/{id}/transcript` *(Transcription — 2026-08-29)* | - | `ApiResponse<RecordingTranscriptDto>` — `{ recordingId, status, text?, language?, providerName?, mediaDurationMs?, failureReason?, updatedAtUtc? }`. **FOUR states, not two:** `status` is `RecordingTranscriptStatus` emitted as the string union `"Pending" | "Available" | "Failed" | "NotStarted"` (the global `JsonStringEnumConverter` again). `NotStarted` is a **read-model-only** enum member, never persisted — it is the answer when the recording exists and is owned but has no transcript row, and it is deliberately distinct from `Pending` (enrolled, working) so an operator can tell "never enrolled" from "still working". `text` is `null` unless `Available` — an empty string would read as "we transcribed it and it was silent". **Two declared statuses:** `200` and `404`; not-found and not-owner are **byte-identical** (the same `ApiResponse` failure envelope), matching the playback row above, because a distinguishable 403 would turn this into a recording-existence oracle for any authenticated user. Gated `[RequirePermission(RecordingReadOwn)]` — **no new key, and no `.any` variant may ever exist**: `SystemRoleCatalog.Build` derives SuperAdmin from every Admin/Both key and Auditor from every Admin-audience `*.read(.any)` key, so an `.any` recording key would hand administrators an operator's screen-and-voice desk capture by derivation alone. |

> **`RecordingSummaryDto` shape (2026-08-19, fifth-pass review):** `{ id, purpose, captureMode, startedAtUtc, durationMs?, segmentCount, totalBytes, title?, status }`. `Status` is a **required** positional parameter on the C# record (`Domain/Recording/SessionRecordingDtos.cs`) and is projected from the aggregate by BOTH `SessionRecordingRepository.ListByOwnerAsync` and `SessionRecordingService.FinalizeAsync`. NSwag nonetheless emits it as `status?: RecordingStatus` (optional) — the generator makes every reference-shaped field optional. `RecordingStatus` is emitted as the string union `"Arming" | "Capturing" | "Finalizing" | "Stored" | "Failed" | "Deleted"`, which holds only because `Program.cs` registers a global `JsonStringEnumConverter` on `AddControllers()`. The library mirror `RecordingSummary.status?` matches the generated optional shape deliberately; `RecordingListComponent.statusMarker` currently treats `undefined` as "no marker" (i.e. as healthy) — see the open finding below.

> **Playback consumers (2026-08-26).** DESKTOP: `RestRecordingTransport.playback()` — `SessionRecordingClient.sessionRecordingPlayback(id): Observable<FileResponse>`, narrowed to `Blob`. MOBILE: `GraphQlRecordingTransport.playback()` — GraphQL carries recording METADATA only; the audio is fetched over this SAME REST route with `HttpClient` and an EXPLICIT `Authorization: Bearer` header, because `scalping-mobile` registers no HTTP interceptor. Both feed the shared `RecordingPlaybackService` in `@scalping/recording`. **Known asymmetry (do not read this row as symmetric) — RESTATED 2026-08-26 after measurement; the previous wording was wrong in BOTH directions.** Mobile *does* mint `PermanentRecordingRejection` (`classifyHttpError`, `graphql-recording-transport.ts:220-227`); desktop does not, and surfaces NSwag's `ApiException` whose `message` is the bare HTTP reason phrase (`"Conflict"`, `"Payload Too Large"`). But **neither host reaches the server's operator-facing sentence.** Mobile's fetch is `responseType: 'blob'`, so Angular delivers `HttpErrorResponse.error` as a **`Blob`**, never a parsed object — `readHttpEnvelopeErrorMessage` tests `'error' in body` against that Blob, misses, and returns the generic fallback every time. Measured: a `413` carrying `{"error":{"message":"This recording is too large to play back in the browser."}}` reaches the trader as `"The recording could not be loaded."`. Reading the envelope on this route requires `await (error.error as Blob).text()` before parsing. See `JOURNAL.md` 2026-08-26 — *A contract cannot both forbid `catchError` and require a named rejection class on a non-enveloped route*.

> **Transcription flow (2026-08-29, `blob-arrival-and-artifact-flows`).** Two boundaries this contract crosses are deliberately listed even though NEITHER is a .NET-to-TypeScript surface and neither generates a client: (1) `GoogleTranscriptionProvider` -> **Google Speech-to-Text v2 `BatchRecognize`**, a NEW EGRESS carrying an assembled copy of an operator's screen-and-voice capture to a third party, per audio-minute; (2) the **Speech service account -> the recordings bucket**, `roles/storage.objectViewer`, a NEW INBOUND READ making a second principal able to read that media. Both are granted by `docs/deployment/gcs-blob-arrival-notifications.md` and are recorded here so they are reviewable rather than discoverable at deployment. Their absence from the generator diff is a decision, not an omission. **No SignalR event and no GraphQL field is added** — a `transcriptReady` receiver would break every hand-written `IScalpingHubReceiver` implementer for zero consumers, and a GraphQL `transcript` field is a client-facing change with no consumer in this scope; both belong to the viewing-surface follow-up.

> **Consumer:** `@scalping/recording` -> `RestRecordingTransport` (`ClientApp/projects/recording/src/lib/transport/rest-recording-transport.ts`) over the generated `SessionRecordingClient` in `@scalping/api-client`. TS mirrors live in `projects/recording/src/lib/models/recording.model.ts` (`RecordingSummary`, `RecordingSegmentDescriptor`, `RecordingPurpose`, `CaptureMode` - all string unions, never numeric enums, per I-13). `scalping-mobile` reaches the SAME service over GraphQL in Slice C; a transport may not introduce a sibling entity, container or purpose value (I-13).
> **Client-half drift as of the 2026-08-19 FIFTH-pass review (SUPERSEDES the second-pass note above it, which is now factually wrong on two of its three items):** the `isSuccess` half is FIXED - `RestRecordingTransport` routes every call through an `unwrap()` that throws a typed `PermanentRecordingRejection` on `!isSuccess`. **CLOSED:** (1) segment time semantics now agree - `offsetMs` anchors the interval START (the previous flush, or the Capture Clock origin for segment 0) and `durationMs` is MEASURED, so `offset[n+1] == offset[n] + duration[n]` and I-7/I-9 both hold; (2) `RecordingSummary.durationMs` is now declared `number | null | undefined` and `formatDuration` uses `== null`, so an unfinalized row renders `—` rather than `NaN:NaN`. **STILL OPEN:** (3) `.list()` accepts `offset`/`limit` and `RestRecordingTransport` defaults them to `0`/`100`, but `RecordingListComponent.load()` calls `list()` with no arguments and `PagedResponseOfRecordingSummaryDto.totalCount` is still discarded - the Recordings screen is a fixed first-100 page with no pager. (4) **NEW:** `RestRecordingTransport` itself has ZERO test coverage - every green spec in `projects/recording` substitutes a hand-rolled fake transport, so the production claim "a C3 status rejection reaches the capture service as a `PermanentRecordingRejection`" is pinned by reading only, not by any test.

---

## API Surface — Admin Panel App

| Controller | Method | Route | Request DTO | Response `T` in `ApiResponse<T>` |
|---|---|---|---|---|
| **AdminConnectionController** | GET | `/api/admin/connection/accounts` | — | `AdminAccountDto[]` |
| | GET | `/api/admin/connection/pool` | — | `GatewayInstanceDto[]` |
| | POST | `/api/admin/connection/connect/{userAccountId}` | — | `void` |
| | POST | `/api/admin/connection/disconnect/{userAccountId}` | — | `void` |
| **AdminSystemAccountsController** | GET | `/api/admin/system-accounts` | — | `SystemAccountDto[]` |
| | GET | `/api/admin/system-accounts/{id}` | — | `SystemAccountDto` |
| | GET | `/api/admin/system-accounts/{id}/status` | — | `SystemAccountStatusDto` |
| | POST | `/api/admin/system-accounts` | `CreateSystemAccountRequest` | `SystemAccountDto` |
| | PUT | `/api/admin/system-accounts/{id}` | `UpdateSystemAccountRequest` | `SystemAccountDto` |
| | DELETE | `/api/admin/system-accounts/{id}` | — | `bool` |
| | POST | `/api/admin/system-accounts/{id}/connect` | — | `SystemAccountStatusDto` |
| | POST | `/api/admin/system-accounts/{id}/disconnect` | — | `bool` |
| | POST | `/api/admin/system-accounts/{id}/set-default` | — | `SystemAccountDto` |
| | PUT | `/api/admin/system-accounts/{id}/capabilities` | `SessionCapability[]` | `SystemAccountDto` |
| **LlmController** | GET | `/api/llm/providers` | — | `LlmProviderStatus[]` |
| | GET | `/api/llm/models` | — | `ModelVersionInfo[]` |
| | GET | `/api/llm/models/active` | — | `ModelVersionInfo?` |
| | POST | `/api/llm/models/{id}/deploy` | — | `string` |
| | POST | `/api/llm/models/{id}/archive` | — | `string` |
| | POST | `/api/llm/models/upload` | `IFormFile, name, baseModel` | `ModelVersionInfo` |
| | GET | `/api/llm/gpu-status` | — | `GpuStatus` |
| | GET | `/api/llm/data-stats` | — | `DataCollectionStats` |
| | GET | `/api/llm/sidecar-health` | — | `SidecarHealth` |
| **AdminSymbolDataController** | GET | `/api/admin/symbol-data/filter-options` | — | `SymbolFilterOptions` |
| | GET | `/api/admin/symbol-data` | query: `page, pageSize, sortBy, filters` | `SymbolBrowseResult` |
| | GET | `/api/admin/symbol-data/{symbol}` | — | `SymbolDetailDto` |
| | POST | `/api/admin/symbol-data/enrich` | `{ symbols[], missingField }` | `bool` |
| | POST | `/api/admin/symbol-data/upsert-earnings` | `{ symbol, earningsDate, timeOfDay }` | `bool` |
| **IngestionController** | GET | `/api/ingestion/status` | — | `IngestionStatus` |
| | POST | `/api/ingestion/jobs/{jobName}/trigger` | — | `void` |
| | POST | `/api/ingestion/jobs/{jobName}/cancel` | — | `void` |
| | GET | `/api/ingestion/priorities` | — | `CapabilityPriorityMap` |
| | POST | `/api/ingestion/priorities` | `CapabilityPriorityMap` | `CapabilityPriorityMap` |
| | GET | `/api/ingestion/call-log` | query: `page, pageSize, provider?, success?` | `ProviderCallLogPage` |
| **AdminSupportController** | GET | `/api/admin/support/conversations` | — | `SupportConversationDto[]` |
| | GET | `/api/admin/support/conversations/{id}/messages` | — | `SupportMessageDto[]` |
| | POST | `/api/admin/support/conversations/{id}/replies` | `{ content }` | `SupportMessageDto` |
| | POST | `/api/admin/support/conversations/{id}/mark-read` | — | `void` |
| | POST | `/api/admin/support/conversations/{id}/close` | — | `void` |
| **TrainingController** | POST | `/api/Training/start` | `TrainingRequest` | `ApiResponse<TrainingJobInfo>` — proxied via `IModelRegistrationService.StartTrainingAsync(ChatLlm, …)` *(Phase 2 active, amendment A)* |
| | GET | `/api/Training/{jobId}/status` | — | `ApiResponse<TrainingStatus>` |
| | POST | `/api/Training/{jobId}/cancel` | — | `ApiResponse<string>` |
| | POST | `/api/Training/upload-dataset` | multipart/form-data | `ApiResponse<DatasetUploadResult>` |
| | GET | `/api/Training/dataset-info` | — | `ApiResponse<DatasetDirectoryInfo>` |
| | DELETE | `/api/Training/datasets/{fileName}` | — | `ApiResponse<string>` |
| | POST | `/api/Training/{jobId}/register` | — | `ApiResponse<ModelVersionInfo>` — to be proxied to /api/model-training/chat-llm/register in Phase 2 |
| | POST | `/api/Training/{jobId}/convert` | — | `ApiResponse<ConversionJobInfo>` |
| | GET | `/api/Training/{jobId}/convert/status` | — | `ApiResponse<ConversionStatus>` |
| | POST | `/api/Training/{id:guid}/promote` | — | `ApiResponse<bool>` — to be proxied to /api/model-training/chat-llm/versions/{id}/promote in Phase 2 |
| | GET | `/api/Training/{id:guid}/evaluation` | — | `ApiResponse<EvaluationResult>` |
| | GET | `/api/Training/setup-status` | — | `ApiResponse<SetupStatus>` |
| **TrainingBacklogController** | GET | `/api/training-backlog` | — | `ApiResponse<List<TrainingBacklogItemDto>>` |
| | GET | `/api/training-backlog/{id:guid}` | — | `ApiResponse<TrainingBacklogItemDto>` |
| | POST | `/api/training-backlog` | `CreateBacklogItemRequest` | `ApiResponse<TrainingBacklogItemDto>` |
| | PUT | `/api/training-backlog/{id:guid}` | `UpdateBacklogItemRequest` | `ApiResponse<TrainingBacklogItemDto>` |
| | DELETE | `/api/training-backlog/{id:guid}` | — | `ApiResponse<bool>` |
| | POST | `/api/training-backlog/generate` | `GenerateBacklogRequest` | `ApiResponse<List<GenerationResultDto>>` |
| | POST | `/api/training-backlog/train` | `TrainBacklogRequest` | `ApiResponse<string>` — proxied via `IModelRegistrationService.StartTrainingAsync(ChatLlm, …)` *(Phase 2 active, amendment A)* |
| | GET | `/api/training-backlog/sentinel-files` | — | `ApiResponse<List<string>>` |
| **ModelTrainingController** | POST | `/api/model-training/{kind}/register` | `ModelRegistrationRequest { kind, name, externalJobId, artifacts[], initialStatus, metricsJson?, contextJson? }` | `ApiResponse<IModelVersion>` |
| | GET | `/api/model-training/{kind}/versions` | query: `status?, take?, skip?` | `ApiResponse<List<IModelVersion>>` |
| | GET | `/api/model-training/{kind}/versions/{id}` | — | `ApiResponse<IModelVersion>` |
| | POST | `/api/model-training/{kind}/versions/{id}/evaluate` | `EvalRunRequest` *(handler-defined)* | `ApiResponse<EvalRunResult>` *(amendment B — was `EvalRunHandle`, deleted 2026-05-26)* |
| | POST | `/api/model-training/{kind}/versions/{id}/promote` | — | `ApiResponse<PromotionDecision>` |
| | POST | `/api/model-training/{kind}/versions/{id}/activate` | — | `ApiResponse<bool>` |
| | GET | `/api/model-training/{kind}/data-plan` | — | `ApiResponse<DataPlan>` |
| | POST | `/api/model-training/{kind}/data-plan/preview` | — | `ApiResponse<DataPlanResolution>` |
| | POST | `/api/model-training/{kind}/start-training` | `ModelTrainingRequest { datasetPath, triggerSource, baseModelOverride?, hyperParameters? }` | `ApiResponse<IModelVersion>` *(amendment A — 10th endpoint; proxies to `IModelRegistrationService.StartTrainingAsync`)* |
| | GET | `/api/model-training/kinds` | — | `ApiResponse<IReadOnlyList<string>>` — alphabetically-ordered list of registered kind strings; absolute path to bypass class-level `{kind}` prefix; safe for inclusion in error messages (no user-input echo) |
| **AdminUserManagementController** | GET | `/api/admin/users?page&pageSize` | gate `users.read` | `ApiResponse<AdminUserPagedResult>` — `AdminUserListItem` carries `roleCount` (red "No roles" pill) + `isReserved`/`reservedReason` |
| | GET | `/api/admin/users/{id}` | gate `users.read` | `ApiResponse<AdminUserDetail>` |
| | POST | `/api/admin/users` | `AdminCreateUserRequest { username, email, password, isActive, audience, initialRoleId }` — gate `users.manage`, plus `admin.users.assignRoles` enforced in-service for EVERY role grant regardless of audience | `ApiResponse<AccessMemberDto>` *(changed 2026-08-16 from `ApiResponse<AdminUserDetail>`; delegates to `IRbacManagementService.CreateMemberAsync`, which writes principal + mirror + initial role in ONE transaction. The `Status400BadRequest` ProducesResponseType was dropped — failures are 200 + `isSuccess:false`, so the NSwag client lost its `status === 400` throw branch)* |
| | PATCH | `/api/admin/users/{id}` | gate `users.manage` | `ApiResponse<AdminUserDetail>` |
| | PATCH | `/api/admin/users/{id}/active` | gate `users.manage` | `ApiResponse<AdminUserDetail>` |
| | POST | `/api/admin/users/{id}/reset-password` | gate `users.manage` | `ApiResponse<string>` |
| | DELETE | `/api/admin/users/{id}/broker-accounts/{accountId}` | gate `users.manage` (legacy alias: `/ibkr-accounts/`) | `ApiResponse<bool>` |
| | POST | `/api/admin/users/{id}/broker-accounts/{accountId}/test-connection` | gate `users.manage` | `BrokerAccountTestResult` |
| **AdminAccessController** | GET | `/api/admin/access/permissions` | gate `admin.access.read` | `ApiResponse<PermissionCatalogResponse>` *(re-gated 2026-08-16 from `admin.roles.manage` — a WIDENING; Operator and Auditor gain it, nobody loses it)* |
| | GET | `/api/admin/access/roles` | gate `admin.access.read` | `ApiResponse<RoleSummaryListResponse>` — `RoleSummaryDto` gained `memberIds` + `memberVersionHash` (2026-08-16). `memberIds` is audience-homogeneous and EXCLUDES reserved `Users` rows |
| | GET | `/api/admin/access/members?audience=` | gate `admin.access.read`, default `Admin` | `ApiResponse<AccessMemberListResponse>` — unified projection over `AdminUsers` / `Users`; User-audience branch excludes `ReservedUser.Classify != None` |
| | PUT | `/api/admin/access/roles/{id}/permissions` | `SetRolePermissionsBody` — gate `admin.roles.manage` | `ApiResponse` |
| | PUT | `/api/admin/access/operators/{id}/roles` | `SetOperatorRolesBody` — gate `admin.users.assignRoles` | `ApiResponse` — carries I-5 (SuperAdmin membership immutable), evaluated AFTER the last-SuperAdmin guard so that guard keeps its break-glass wording |
| | PUT | `/api/admin/access/users/{id}/roles` | `SetUserRolesBody` — gate `admin.users.assignRoles` | `ApiResponse` *(new 2026-08-16 — the previously missing half; before this, a trading user's roles could only be changed by SQL)* |
| | PUT | `/api/admin/access/roles/{id}/members` | `SetRoleMembersBody` — gate `admin.users.assignRoles` | `ApiResponse` *(new 2026-08-16 — role-centric bulk membership; rejects SuperAdmin outright, refuses reserved member ids on input, and PRESERVES reserved rows it filtered out of the read)* |
| | ~~GET~~ | ~~`/api/admin/access/operators`~~ | **DELETED 2026-08-16** along with `AdminOperatorDto` / `AdminOperatorListResponse` — superseded by `GET members?audience=Admin` | — |
| **AdminStrategyController** | GET | `/api/admin/strategies/roots` | query: `userId?, sortBy?, sortDir?` | `AdminStrategyListItemDto[]` |
| **AuditController** | *(audit log reads)* | `/api/audit` | — | — |
| **AdminModelShadowController** | POST | `/api/admin/model-testing/shadow/enter` | `ShadowEnterRequest` | `bool` — flips candidate to ShadowEval, starts llama-server on assigned port |
| | POST | `/api/admin/model-testing/shadow/exit/{candidateModelVersionId}` | — | `bool` — flips candidate back to EvaluatedPass, stops llama-server |
| | GET | `/api/admin/model-testing/shadow/comparisons` | query: `candidateModelVersionId?, verdict?, hasSafetyConcern?, wasSkipped?, isArchived?, offset, limit` | `PagedResponse<ShadowComparisonListItem>` |
| | GET | `/api/admin/model-testing/shadow/comparisons/{id}` | — | `ShadowComparisonDetail` (full active+candidate response JSON + DiffSummary) |
| | PATCH | `/api/admin/model-testing/shadow/comparisons/{id}/verdict` | `{verdict, note?, confirmOverwrite?}` | `ShadowComparisonDetail` |
| | GET | `/api/admin/model-testing/shadow/snapshot/{candidateModelVersionId}` | — | `ShadowSnapshot` (gate-readiness counters) |
| | POST | `/api/admin/model-testing/shadow/comparisons/{id}/archive` | — | `bool` |
| **AdminModelTestRunsController** | GET | `/api/admin/model-testing/runs` | query: `modelVersionId?, take=20, skip=0` | `ApiResponse<List<ModelTestRunDto>>` — paginated eval-run history, optionally filtered by model version |
| | GET | `/api/admin/model-testing/runs/by-model/{modelVersionId}` | query: `take=20` | `ApiResponse<List<ModelTestRunDto>>` — deprecated; prefer `GET /runs?modelVersionId=…` |
| | GET | `/api/admin/model-testing/runs/{id}` | — | `ApiResponse<ModelTestRunDetailDto>` — single run + per-scenario results |
| | POST | `/api/admin/model-testing/runs/trigger/{modelVersionId}` | — | `ApiResponse<ModelEvalRunSummary>` — synchronous manual eval run against authoritative scenarios. **Structured failure codes (2026-05-18 + 2026-05-22):** when no authoritative scenario exists, `error.code = "NoAuthoritativeScenarios"`; when the exported corpus has zero assistant turns (precondition failure), `error.code = "precondition_no_assistant_turn"` (status `FrameworkFailure`) — the run is created but immediately terminal and `error.data = TriggerEvalPrerequisiteError { Code, Title, Explanation, TotalScenarios, AuthoritativeScenarios, ArchivedScenarios, Remediation: RemediationStep[] }` where each `RemediationStep` carries `Label`, `Target: RemediationTarget` (semantic enum — `ScenariosNonAuthoritative`, `ScenariosCreate`, or **`StrategyManualPromote`** (added 2026-06-04 — routes to `/strategy-models/:id` for manual promotion of a not-auto-eligible strategy-RL candidate)), `Hint?`. Frontend renders the payload as an inline rich panel via `AdminModelTestRunsState._triggerPrerequisiteError` + `RemediationStepButtonComponent`. **Note (2026-06-04):** `RemediationTarget` is NOT a typed wire schema — it rides inside the loosely-typed `ApiResponse.error.data`, so it has 0 refs in the generated `api.generated.ts`; the frontend `remediation-target.model.ts` is a hand-written mirror kept in sync with the C# enum manually. The strategy-RL renderer's "Promote this model manually" CTA (`2026-06-04-remediation-target-strategy-manual-promote.md`) translates the separate kebab string `PromotionDecision.RemediationTarget = "strategy-manual-promote"` to the typed `StrategyManualPromote` at the component boundary (Q1=a). |
| | POST | `/api/admin/model-testing/runs/{id}/cancel` | — | `ApiResponse<bool>` — best-effort cancel; no-op on terminal status |
| **AdminModelTestScenariosController** | GET | `/api/admin/model-testing/scenarios` | query: `includeArchived=false` | `ApiResponse<List<ModelTestScenarioDto>>` — all scenarios (active by default) |
| | GET | `/api/admin/model-testing/scenarios/{id}` | — | `ApiResponse<ModelTestScenarioDetailDto>` — single scenario with full prompt + args |
| | POST | `/api/admin/model-testing/scenarios` | `SaveScenarioRequest` | `ApiResponse<ModelTestScenarioDetailDto>` — create |
| | PUT | `/api/admin/model-testing/scenarios/{id}` | `SaveScenarioRequest` | `ApiResponse<ModelTestScenarioDetailDto>` — update |
| | DELETE | `/api/admin/model-testing/scenarios/{id}` | — | `ApiResponse<bool>` — soft-delete (archive) |
| | POST | `/api/admin/model-testing/scenarios/{id}/restore` | — | `ApiResponse<ModelTestScenarioDetailDto>` — unarchive |
| | POST | `/api/admin/model-testing/scenarios/{id}/mark-authoritative` | — | `ApiResponse<ModelTestScenarioDetailDto>` — mark as authoritative corpus member |
| | POST | `/api/admin/model-testing/scenarios/{id}/unmark-authoritative` | — | `ApiResponse<ModelTestScenarioDetailDto>` — remove authoritative status |
| | POST | `/api/admin/model-testing/scenarios/draft-from-prompt` *(Feature A — 2026-05-19)* | `DraftScenarioFromPromptRequest { prompt: string, preferredCategory: ModelTestScenarioCategory? }` | `ApiResponse<ScenarioDraftDto>` — LLM-generated scenario draft. `ScenarioDraftDto` shape: `{ name, category, userPromptJson, expectedToolName?, expectedArgsShapeJson?, expectedRefusal, forbiddenSubstrings?, notes? }`. Wire-type: `userPromptJson` and `expectedArgsShapeJson` are raw JSON strings; `forbiddenSubstrings` is a CSV string. Angular: `AdminModelTestScenariosService.draftFromPrompt()` uses direct `HttpClient` POST (NSwag client not yet regenerated — regen hook will replace once backend lands). |
| **AdminSystemConfigController** | GET | `/api/admin/system-config/{key}` | — | `SystemConfigDto` |
| | PATCH | `/api/admin/system-config/{key}` | `{value: string}` | `SystemConfigDto` |
| **ReadinessController** *(Phase B3 — 2026-06-01, admin)* | GET | `/api/readiness/current` | query: `mode=executive\|engineer` (default `executive`) | `ApiResponse<ReadinessScoreDto>` — fans out to all four probes in parallel, SignalR-pushes `ReadinessScoreChanged` after every call |
| | GET | `/api/readiness/history` | query: `days` (default 30, max 365) | `ApiResponse<IReadOnlyList<ReadinessSnapshotSummaryDto>>` — daily snapshot history for trend sparkline |
| | POST | `/api/readiness/scan/patterns` | — | `ApiResponse<PatternScanReportDto>` — cache-busting pattern scan; writes audit entry (`AuditAction.Update`, `ResourceType = "ReadinessPatternScan"`) |
| **Authorization:** `ReadinessRead` policy | Requires claim `Readiness.Read = "true"` | All three endpoints above | Claim seeded on every admin JWT by `AdminAuthService.IssueToken` via `ClaimNames.ReadinessRead` | Exposed in `AdminAuthResponse.Claims[]` (policy-gating claims only — no identity claims leaked) |

---

## GraphQL Surface — Scalping Mobile App

Single endpoint: `POST /graphql`, mapped `AllowAnonymous()` under the global
`RequireAuthenticatedUser()` fallback (`Program.cs:408-422`) — authorization is per-field.
Frontend consumer for every row: `ClientApp/projects/scalping-mobile/src/app/core/graphql/`
(`operations/*.graphql` authored, `generated/graphql.ts` generated from `tools/graphql/schema.graphql`).

| Root | Field | Authorization | Returns | Backend source |
|---|---|---|---|---|
| **Query** | `me` | viewer only (no policy) | `Viewer` | `Queries/Query.cs:47` |
| | `watchlists` | `perm:watchlist.read` | `[Watchlist]` (IQueryable) | `Query.cs:83-89` |
| | `watchlist` | `perm:watchlist.read` | `Watchlist` | `Query.cs:119-121` |
| | `notifications` | `perm:notification.read` | `[Notification]` (IQueryable) | `Query.cs:164-170` |
| | `strategies` | `perm:strategy.read` | `[StrategySummary]` | `Query.cs:205-207` |
| | `strategy` | `perm:strategy.read` | `StrategySummary` | `Query.cs:234-236` |
| | `dashboardPreferences` **(NEW)** | `perm:preference.read` | `DashboardPreferences` | `Query.cs` (work item #14) |
| **Mutation** | `createWatchlist` | `perm:watchlist.write` | `Watchlist` | `Mutations/Mutation.cs:61-63` |
| | `renameWatchlist` | `perm:watchlist.write` | `Watchlist` | `Mutation.cs:89-91` |
| | `deleteWatchlist` | `perm:watchlist.write` | `UUID` | `Mutation.cs:119-121` |
| | `addWatchlistItem` | `perm:watchlist.write` | `Watchlist` | `Mutation.cs:149-151` |
| | `removeWatchlistItem` | `perm:watchlist.write` | `Watchlist` | `Mutation.cs:179-181` |
| | `markNotificationRead` | viewer only (no policy) | `Notification` | `Mutation.cs:212-213` |
| | `login` | anonymous by design | `AuthResponse` | `Mutation.cs:263-264` |
| | `register` | anonymous by design | `AuthResponse` | `Mutation.cs:283-284` |
| | `forgotPassword` | anonymous by design | `PasswordResetResponse` | `Mutation.cs:306-308` |
| | `resetPassword` | anonymous by design | `Boolean` | `Mutation.cs:335-336` |
| | `setDashboardFeatures` **(NEW)** | `perm:preference.write` | `DashboardPreferences` | `Mutation.cs` (work item #14) |
| **Query** | `recordings` **(NEW — Slice C, 2026-08-25)** | `perm:recording.read.own` | `PagedResponseOfRecordingSummaryDto` | `Queries/RecordingQueries.cs` |
| **Mutation** | `armRecording` **(NEW)** | `perm:recording.write.own` | `RecordingArmedResponse` | `Mutations/RecordingMutations.cs` |
| | `appendRecordingSegment` **(NEW)** | `perm:recording.write.own` | `SegmentAcceptedResponse` | `RecordingMutations.cs` |
| | `finalizeRecording` **(NEW)** | `perm:recording.write.own` | `RecordingSummaryDto` | `RecordingMutations.cs` |
| | `deleteRecording` **(NEW)** | `perm:recording.delete.own` | `UUID` | `RecordingMutations.cs` |

Recording DTO ↔ model pairs (Slice C — the SECOND transport over the SAME vault, invariant I-13):

| GraphQL type | TypeScript model | Adapter |
|---|---|---|
| `RecordingSummaryDto` | `RecordingSummary` (`@scalping/recording`) | `GraphQlRecordingTransport.toRecordingSummary` |
| `PagedResponseOfRecordingSummaryDto` | flattened to `readonly RecordingSummary[]` | `GraphQlRecordingTransport.list` |
| `RecordingArmedResponse` | `RecordingArmedResult` | `GraphQlRecordingTransport.arm` |
| `ArmRecordingRequestInput` | `(purpose, captureMode, mediaType)` port args | `GraphQlRecordingTransport.arm` |
| `AppendRecordingSegmentInput` | `RecordingSegmentDescriptor` + base64 `Blob` | `GraphQlRecordingTransport.appendSegment` |
| `FinalizeRecordingRequestInput` | `totalDurationMs: number` | `GraphQlRecordingTransport.finalize` |
| `SegmentAcceptedResponse` | discarded (`Observable<void>`) | `GraphQlRecordingTransport.appendSegment` |

Recording transport asymmetries — DELIBERATE, do not "fix" without reading this:
- **No `byteLength` on `AppendRecordingSegmentInput`.** The resolver derives it from the decoded
  payload, so the REST path's declared-vs-actual mismatch (and its orphaned-blob consequence) is
  structurally impossible on GraphQL. Adding the field back re-opens that failure mode.
- **Enum casing.** The schema renders SCREAMING_SNAKE (`TRADING_JOURNAL`); the library's domain
  unions are PascalCase (`TradingJournal`). `GraphQlRecordingTransport` derives both directions from
  the string; there is no lookup table to keep in step.
- **Paging arguments.** REST defaults `offset=0, limit=20`; the GraphQL field declares
  `offset: Int!, limit: Int!` with no default and the adapter supplies `0 / 100`. Same clamp
  inside `ISessionRecordingService`, different defaults at the edge.
- **Effective segment size cap — SYMMETRIC as of 2026-08-25.** `Recording:MaxSegmentBytes` is 5 MiB
  and both transports enforce it against the DECODED payload. This entry previously recorded a live
  I-13 defect: the `/graphql` request body was clamped to a hardcoded 256 KiB, which after base64
  inflation (4:3) capped segments at ~192 KiB decoded — a 26.7x asymmetry that made the resolver's
  own check unreachable. **That defect is closed.** `src/ScalpingMachine.API/Startup/GraphQLRequestBodyLimit.cs`
  now derives the clamp from `Recording:MaxSegmentBytes` (5 MiB → ~6.99 MiB clamp → 5,292,033 bytes
  decoded, comfortably under `CeilingBytes` ≈ 66.7 MiB, which is itself derived from the REST
  backstop). `Program.cs` warns at startup if configuration ever makes the two contradict — including
  the ABSENT-key case, where the resolvers fall back to `long.MaxValue` while the clamp falls back to
  its 256 KiB floor. Pinned by `tests/ScalpingMachine.Services.Tests/Storage/GraphQLRequestBodyLimitParityTests.cs`,
  which asserts the PARITY relationship rather than a literal byte count, over all three configuration
  states (absent, non-positive, configured). Still open one layer up: HotChocolate's own
  `maxAllowedRequestSize` is unset and unguarded — see
  `.claude/concepts/followups/2026-08-25-hotchocolate-request-size-second-cap.followup.md`.

Notes:
- `markNotificationRead` is the last un-gated data field; `Query.cs:158-163` records the read-side
  equivalent as a repaired defect. Treat it as a known gap, not as a pattern to copy.
- The committed SDL at `tools/graphql/schema.graphql` is snapshot-asserted by
  `tests/ScalpingMachine.GraphQL.Tests/SchemaTests.cs` and is the input to `ClientApp/codegen.ts`.
  A field added here without regenerating both artifacts fails the schema test and then the client build.
- The sixteen non-NEW rows are pre-existing surfaces this file had never registered. They were
  enumerated from source and added on 2026-08-22 as the drift repair JOURNAL 2026-05-17 asks for —
  register every field in the root type, not only the one being added.

---

## SignalR Event Surface

**Hub:** `ScalpingHub` at `/hubs/scalping`
**Base class:** `LoggingHubBase<IScalpingHubReceiver>` (structured lifecycle logging, `TrySubscribeAsync`/`TryUnsubscribeAsync` helpers)
**Typed contract since 2026-04-12:** server→client events defined by `IScalpingHubReceiver` (composite of 5 sub-interfaces under `src/ScalpingMachine.Services/SignalR/Receivers/*.cs`); client→server invocations defined by `IScalpingHubInvoker` under `src/ScalpingMachine.Services/SignalR/IScalpingHubInvoker.cs`. TypeScript clients generated by `tools/generate-typed-hub-clients.cmd` into `ClientApp/projects/*/src/app/core/hub/generated/` (committed per contract Q4). Both Angular apps implement `IScalpingHubReceiver` directly on their SignalR service class (no `HubRouter` — class names `SignalRService` / `AdminSignalrService` preserved per contract Q5).

### Client → Server (Subscription Methods)

| Method | Parameter | Group |
|---|---|---|
| `SubscribeToTicker(symbol)` | `string` | `ticker:{symbol}` |
| `UnsubscribeFromTicker(symbol)` | `string` | `ticker:{symbol}` |
| `SubscribeToOrders()` | — | `orders` |
| `SubscribeToAccount()` | — | `account` |
| `SubscribeToOptionChain(symbol)` | `string` | `optionchain:{symbol}` |
| `UnsubscribeFromOptionChain(symbol)` | `string` | `optionchain:{symbol}` |
| `SubscribeToStrategyNotifications()` | — | `StrategyNotifications` |
| `UnsubscribeFromStrategyNotifications()` | — | `StrategyNotifications` |
| `SubscribeToStrategyRun(runId)` | `string` | `StrategyRun_{runId}` |
| `UnsubscribeFromStrategyRun(runId)` | `string` | `StrategyRun_{runId}` |
| `SubscribeToBacktest(backtestId)` | `string` | `Backtest_{backtestId}` |
| `UnsubscribeFromBacktest(backtestId)` | `string` | `Backtest_{backtestId}` |
| `SubscribeToIngestion()` | — | `Ingestion` |
| `UnsubscribeFromIngestion()` | — | `Ingestion` |
| `SubscribeToTraining()` | — | `Training` |
| `UnsubscribeFromTraining()` | — | `Training` |
| `SubscribeToSupportInbox()` | — | `Support` |
| `UnsubscribeFromSupportInbox()` | — | `Support` |
| `SubscribeToSupportConversation(id)` | `string` | `SupportConversation_{id}` |
| `SubscribeToReadiness()` | — | `admin-readiness` |
| `UnsubscribeFromReadiness()` | — | `admin-readiness` |
| `UnsubscribeFromSupportConversation(id)` | `string` | `SupportConversation_{id}` |

### Server → Client Events

| Event Name | C# Payload | Group(s) | Frontend Consumer | State Service |
|---|---|---|---|---|
| `MarketDataUpdate` | `QuoteSnapshot` | `ticker:{symbol}` | scalping-machine `signalr.service.ts` | `MarketDataState` |
| `CandleUpdate` | `OhlcBar` | `ticker:{symbol}` | scalping-machine `signalr.service.ts` | — (direct component) |
| `IndicatorUpdate` | `IndicatorSnapshot` | `ticker:{symbol}` | scalping-machine `signalr.service.ts` | — (direct component) |
| `OptionChainUpdate` | `OptionGreeksSnapshot` | `optionchain:{underlying}` | scalping-machine `signalr.service.ts` | — |
| `OrderStatusUpdate` | `ScalpingOrder` | `orders` | scalping-machine `signalr.service.ts` | `OrderState` |
| `PositionUpdate` | `Position` | `account` | scalping-machine `signalr.service.ts` | — |
| `AccountUpdate` | `AccountSummary` | `account` | scalping-machine `signalr.service.ts` | — |
| `ConnectionStatusChanged` | `ConnectionStatus` | all clients | both apps | `ConnectionState` / `AdminConnectionState` |
| `StrategyNotification` | `StrategyNotification` | `StrategyNotifications` | scalping-machine `signalr.service.ts` | `NotificationState` |
| `RunStatusUpdate` | `RunStatusUpdatePayload` | `StrategyRun_{runId}` | scalping-machine `signalr.service.ts` | `StrategyRunState` |
| `FlowUpdate` | `StrategyFlow` | `StrategyRun_{runId}` | scalping-machine `signalr.service.ts` | `StrategyRunState` |
| `BacktestProgress` | `BacktestProgress` | `Backtest_{id}` | scalping-machine `signalr.service.ts` | — (direct component) |
| `BacktestCompleted` | `BacktestCompletedPayload` | `Backtest_{id}` | scalping-machine `signalr.service.ts` | — |
| `BacktestFailed` | `BacktestFailedPayload` | `Backtest_{id}` | scalping-machine `signalr.service.ts` | — |
| `ImportLog` | `ImportLogEntry` | all clients | scalping-machine `signalr.service.ts` | — |
| `IngestionLog` | `IngestionLogEntry` | `Ingestion` | admin-panel `signalr.service.ts` | `IngestionState` |
| `TrainingProgress` | `TrainingJobStatusPayload` | `Training` | admin-panel `signalr.service.ts` | — (component-consumed via `trainingProgress$`) |
| `SupportMessageReceived` | `SupportMessagePayload` | `Support` + `SupportConversation_{id}` | both apps | `SupportChatState` / `AdminSupportChatState` |
| `NewSupportConversation` | `SupportConversationDto` | `Support` | admin-panel `signalr.service.ts` | `AdminSupportChatState` |
| `SupportConversationClosed` | `SupportConversationClosedPayload` | `Support` + `SupportConversation_{id}` | both apps | `SupportChatState` / `AdminSupportChatState` |
| `ModelShadowComparisonCreated` | `ModelShadowComparisonCreatedPayload` | `AdminModelTesting` | admin-panel `AdminSignalrService` | `ModelShadowState` |
| `ModelShadowComparisonVerdicted` | `ModelShadowComparisonVerdictedPayload` | `AdminModelTesting` | admin-panel `AdminSignalrService` | `ModelShadowState` |
| `ReadinessScoreChanged` | `ReadinessScoreChangedPayload { overallScore, mode, capturedAtUtc, pillarSummaries[] }` | `admin-readiness` | admin-panel `readiness.state.ts` *(PENDING F1)* | `ReadinessState` *(PENDING F1)* |
| `ReadinessSnapshotCaptured` | `ReadinessSnapshotCapturedPayload { snapshotId, capturedAtUtc, overallScore }` | `admin-readiness` | admin-panel `readiness.state.ts` *(PENDING F1)* | `ReadinessState` *(PENDING F1)* |
| `ModelEvalRunCompleted` | `ModelEvalRunCompletedPayload` (with `errorCode`, `warnings[]`) | `AdminModelTesting` | admin-panel `AdminSignalrService` | `AdminModelTestRunsState` |
| `TrainingProgressUpdated` | `TrainingProgressPayload { kind, modelVersionId, status, kindSpecificStatus?, progress?, metrics?, failureReason? }` | `Training` | admin-panel `RegressionWorkbenchState.mergeProgressUpdate` (Phase 4 active — consumed by `regression-workbench.component`, `training-monitor.component`, `admin-dashboard.component` via a single root-scoped state's `computed()` slice per JOURNAL 2026-05-22) | `RegressionWorkbenchState` *(Phase 2 emit + Phase 3 emit + Phase 4 deferral-A per-strategy fresh-dirty emit; payload Status + KindSpecificStatus mandatory per amendment E-1; other fields advisory)* |
| `RetrainJobTickCompleted` | `RetrainJobTickPayload { jobRunId, tickStartedAtUtc, tickCompletedAtUtc, strategiesEvaluated, strategiesDirty, strategiesTrained, strategiesPromoted, strategiesFailed, durationSeconds, errorMessage?, tickSucceeded, crashedTickError? }` | `Training` | admin-panel `signalr.service.ts → _retrainJobTickCompleted$` → `StrategyModelState` (existing) + `AdminDashboardComponent` tick-counter tile (Phase 4 legacy-fallback consumer per `## Data Shapes → Events`) | `StrategyModelState`, `AdminDashboardComponent` *(Phase 3 emit + Phase 4 deferral-B crashed-tick finally + Phase 4 amendment E-1 mandatory Status; consumer-side hand-written `RetrainJobTickPayload` at `core/models/strategy-model.model.ts:164-179` DELETED per deferral D; consumers use generated TypedSignalR shape)* |
| `ForceActionExecuted` | `ForceActionExecutedPayload { auditId, kind, outcome, runId, pairId?, flowId?, sourceSide?, realOrderHandleId, brokerOrderId, brokerOrderSource, symbol, quantity, occurredAtUtc }` — fires only on a terminal `Submitted`; a reservation (`Pending`) never fires this event | `StrategyRun_{runId}` always; `StrategyRunPair_{pairId}` also, when the action is pair-scoped (force-entry) | **Two consumers.** scalping-machine `signalr.service.ts` → `ForceActionState` (real consumer — drives the force-action audit panel). admin-panel `signalr.service.ts` (typed `IScalpingHubReceiver.forceActionExecuted`, migrated off the raw `registerRawHandlers()` bridge once the Tapper `[TranspilationSource]` blocker cleared) is a **deliberate no-op** — force actions are a scalping-machine concern only; the admin-panel handler exists solely so the typed hub receiver contract is complete | `ForceActionState` (scalping-machine only) |

---

## DTO ↔ Model Naming Convention

- **C# DTOs** use PascalCase properties, serialized to camelCase via `System.Text.Json` with `JsonNamingPolicy.CamelCase`
- **TypeScript interfaces** must match the camelCase shape exactly
- **Enums** serialized as strings via `JsonStringEnumConverter` — TypeScript side uses `type Foo = 'ValueA' | 'ValueB'` string unions, NOT numeric enums

### Phase A1 — Shadow execution additions (2026-04-22)

- **`StrategyDefinition` DTO** gained `learnerEnabled: boolean` (default `false`) — per-strategy opt-in gate for the Shadow execution branch.
- **`StrategyRun` DTO** gained `executionMode: 'Live' | 'Shadow'` (default `'Live'`) — immutable after insert. Propagated from `StrategyRunEntity.ExecutionMode`.
- **`StrategyFlow.EntryReference` / `.CloseReference`** wire shapes changed from `{ orderId: number }` to `{ handle: { id: string, brokerOrderId: number | null, source: 'Ibkr' | 'Alpaca' | 'Shadow' | 'BacktestSimulated' }, orderId: number | null, ... }`. Legacy `orderId` retained for back-compat; new consumers MUST read `handle.id` (canonical identity) instead. Legacy JSON rows persisted before this migration are synthesized into `handle = { Id: <fresh Guid>, BrokerOrderId: <legacy int>, Source: 'Ibkr' }` at deserialization time via `OrderReferenceJsonHelper`.
- **`UserShadowAccountConfig` DTO** (future admin API surface — entity exists, no endpoint yet): `{ userId: string, startingCash: number, updatedAtUtc: string }`. Centralized per-user Shadow bankroll — shared across every Shadow run of every strategy owned by that user.

---


### Recording transcript (2026-08-30, `blob-arrival-and-artifact-flows`) — REST-only, and currently unconsumed

- **`RecordingTranscriptDto`** ↔ `ClientApp/projects/api-client/src/lib/generated/api.generated.ts:19719` — `{ recordingId, status, text?, language?, providerName?, failureReason?, … }`. NSwag emits **every** property optional, including the non-nullable `recordingId` (`Guid`) and `status`, because Swashbuckle writes no `required` array. That is uniform across all ~200 DTOs in this client, not specific to this one — a strict-template consumer must guard the discriminant rather than assume it is present.
- **`RecordingTranscriptStatus`** ↔ `api.generated.ts:19730` — `"Pending" | "Available" | "Failed" | "NotStarted"`. Serialization form verified: `JsonStringEnumConverter` is registered on the MVC pipeline (`Program.cs:221-224`), so the enum crosses as a **string**, matching the generated union. `NotStarted = 3` is **read-model-only** — the only persisted values are 0/1/2, and the sole construction site is the no-row DTO at `SessionRecordingService.cs:1408`. A stored `3` is unreachable.
- **Endpoint:** `GET /api/recordings/{id}/transcript` → `ApiResponse<RecordingTranscriptDto>`.

**Two asymmetries recorded deliberately, because both are cheap to settle now and expensive once the viewing surface subscribes** (`.claude/concepts/followups/2026-08-29-transcript-viewing-surface.followup.md`):

1. **This is the only recordings action whose failures arrive on the generated client's ERROR channel.** `GetTranscriptAsync` is declared `Task<ActionResult<ApiResponse<T>>>` and answers `NotFound(result)`; its five siblings (arm, append-segment, finalize, delete, list) return a bare `Task<ApiResponse<T>>` and therefore always answer 200. NSwag turns the declared 404 into `throwException(...)`, so the envelope survives on `ApiException.result` but never reaches `next`. A consumer written to this repo's rule — *always check `res.isSuccess` before `res.value`* — will **never see not-found**. The blast radius is unusual here because the endpoint answers five things: four success states on `next` (`NotStarted` / `Pending` / `Failed` / `Available`) and "not yours or absent" on `error`. Mapping "any error → no transcript" collapses five answers into two and destroys the `NotStarted`-vs-`Pending` distinction the enum exists for.
2. **The transcript read is REST-only.** `RecordingTransport` (`ClientApp/projects/recording/src/lib/transport/recording-transport.ts:40`) is a dual-implementation port — a REST adapter and a GraphQL adapter serving scalping-mobile, which is GraphQL-for-everything. `ScalpingMachine.GraphQL` has **zero** diff in this change set, so a future `transcript()` on the port has nothing to call on the mobile side. If it stays REST-only, say so in the port's docblock and have the GraphQL adapter throw a named unsupported error; if it is added, note that HotChocolate will serialize the enum as `NOT_STARTED`, not `NotStarted`.

**No wire surface at all** for `ArtifactFlowRunStatus`, `ArtifactFlowFailureCodes`, `ArtifactKinds` or `BlobStoreReachability`. Consequence worth naming: an operator has **no API path to see that a transcription flow dead-lettered** — the transcript row's `failureReason` is the only externally visible trace, and only for a recording that got as far as a row. Tracked by `.claude/concepts/followups/2026-08-29-artifact-flow-dead-letter-replay.followup.md`.

**Currently unconsumed:** `sessionRecordingGetTranscript`, `RecordingTranscriptDto` and `RecordingTranscriptStatus` are referenced only by the generated client — no service, state or component in any of the five Angular projects. This is by design (the work item is backend + API only); recorded so a future reader does not mistake it for dead code.

## Named Integration Flows

These document end-to-end data flows through multiple modules — the composition of individual mechanisms at runtime.

### Flow 1: Strategy Execution

```
User clicks "Start"
  → StrategyRunController.POST /api/strategy-runs
  → StrategyExecutionEngine.StartRunAsync
  → FlowManager.ExecuteAsync
    → ContextResolver → each IFieldResolver → EvaluationContext
    → ConditionEvaluator (entry conditions)
    → EntryExecutor → IOrderExecutionProvider
      Live: LiveOrderExecutionProvider → ITwsOrderService → IBKR TWS
      Backtest: BacktestOrderExecutionProvider → SimulatedBroker
    → Order fill callback → CloseEvaluator (continuous loop)
    → ConditionEvaluator (close conditions) → close triggered
    → LoopDecisionEngine (escalation: FullAuto → Suggest → Manual → Stop)
    → SuggestionEngine (if escalated to Suggest mode)
  → SignalR: FlowUpdate, RunStatusUpdate → StrategyRun_{runId} group
  → scalping-machine signalr.service.ts → StrategyRunState signals
  → Angular component re-renders via OnPush
```

### Flow 2: Condition Evaluation

```
ContextResolver.ResolveAsync(conditionContext, symbol, FieldRequest, ct)
  ⚠ FieldRequest is REQUIRED and non-nullable as of #32 — never defaulted. Callers build it from
    the exact condition trees about to be evaluated (ConditionFieldCollector), so only the
    configured indicators a strategy actually references get computed. FieldRequest.None is a
    first-class value meaning "built-ins only", distinct from absent. The two Scheduling call
    sites pass None; the three Entry/Close sites pass a real request. NOTE: the Close request
    must include PassiveClose.EarlyManagement.Condition — a third tree nested two levels down.
  → PriceFieldResolver (price.*, from IBKR live or local cache)
  → IndicatorFieldResolver (indicator.*, from IndicatorService using Skender.Stock.Indicators)
    ↳ also implements IRequestAwareFieldResolver: delegates to IConfiguredIndicatorContextWriter,
      the SINGLE owner of collect → parse → de-duplicate → invoke → write for parameterized keys
      like indicator.ema(20). Backtest calls the SAME writer — one component, two call sites,
      zero copies (MECHANISMS.md:76 IScreenerCriteriaExecutor precedent).
  → FinancialFieldResolver (financial.*, from local StockFundamentals table)
  → EarningsFieldResolver (earnings.*, from local EarningsCalendar table)
  → OptionsFieldResolver (options.*, from IBKR option chain)
  → VolumeFieldResolver (volume.*, from IBKR live data)
  → PositionFieldResolver (position.*, from open position state)
  → LoopFieldResolver (loop.*, from StrategyRun loop history)
  → SchedulingFieldResolver (scheduling.*, from SchedulingElements)
  → ... (11 total resolvers)
  → EvaluationContext fully populated
  → ConditionEvaluator.Evaluate(conditionGroup, evaluationContext)
  → boolean result (all conditions AND/OR tree)
```

### Flow 3: Data Ingestion

```
Quartz cron fires (e.g., FundamentalsRefreshJob at 2 AM)
  → CancellableQuartzJobBase ceremony (start log, cancellation, error handling)
  → IExternalDataDispatcher.DispatchAsync(DataCapability.Fundamentals, symbols)
    → QuotaManager check (sliding window + daily limit)
    → Provider selected by priority (FMP > Finnhub > AlphaVantage > Polygon)
    → Provider HTTP call → external API
    → ProviderCallLog persisted (success/failure, latency, data size)
  → StockFundamentals table bulk-upserted
  → SignalR: IngestionLog → Ingestion group
  → admin-panel admin-signalr.service.ts → IngestionState signals
  → Admin dashboard live log updates
```

### Flow 4: IBKR Connection

```
User clicks "Connect"
  → ConnectionController.POST /api/connection/connect
  → GatewayPool.AcquireAsync (Docker.DotNet)
    → IbGatewayContainerService.StartContainerAsync
    → PortAllocator.AllocateAsync (API: 4010+, VNC: 5910+)
    → Docker container starts (IB Gateway image)
    → Health check poll until ready
  → IbkrSessionManager.CreateSessionAsync
  → TwsConnectionService.ConnectAsync (TWS API handshake on allocated port)
  → SignalR: ConnectionStatusChanged → all clients
  → scalping-machine signalr.service.ts → ConnectionState
  → admin-panel admin-signalr.service.ts → AdminConnectionState
```

### Flow 5: Screener Resolution

```
SymbolResolver.ResolveAsync (runs every ~1 second during strategy execution)
  → StockScreenerService.ExecuteScreenerAsync(screenerId)
    → LOCAL StockFundamentals table query ONLY (EF Core, AsNoTracking)
    → DynamicExpresso evaluates filter expressions against local data
    → NEVER calls external APIs — all data pre-populated by ingestion jobs
  → List<string> candidateSymbols returned to strategy engine
```

### Flow 6: LLM Chat

```
User sends message in chat widget
  → ChatController.POST /api/chat/message        (legacy, stateless)
     or POST /api/chat/context/message           (context-scoped, persisted)
  → ChatService.ProcessAsync
    → SystemPromptBuilder builds context (available tools, indicators, strategies)
    → ILlmDispatcher.CompleteAsync (priority routing)
      → DataCollectingLlmDispatcher wraps call (captures for training)
      → Provider: AnthropicLlmProvider (cloud) or OpenAiCompatibleLlmProvider (local llama.cpp :8080)
    → Response may include tool calls
    → ChatToolExecutor.ExecuteAsync (lookup strategies, run screener, get market data, etc.)
    → Tool results fed back to LLM for final response
  → SignalR: chat response pushed to client (if streaming)
  → scalping-machine chat component updates
```

### Flow 7: Browser error reporting — third-party egress (2026-09-03, `sentry-error-monitoring-three-apps`)

**This is an EGRESS row, not a .NET↔TypeScript surface.** It generates no client, adds no endpoint and adds no hub event, and it is listed here for the same reason the Google Speech-to-Text row above is: a new outbound boundary to a third party should be reviewable rather than discoverable at deployment. Its absence from any generator diff is a decision, not an omission.

```
Entry file (main.ts, all three apps)
  → startMonitoring(environment.sentry)          @scalping/observability, BEFORE bootstrapApplication
    → recognised real address AND enabled === true ?
        yes → Sentry.init(...)  → HTTPS POST  →  https://o4512023789830144.ingest.us.sentry.io/api/<project>/envelope/
        no  → no client, no socket, no egress at all
  → app.config.ts → provideObservability()      ErrorHandler resolved LAZILY at injection time
        outcome 'initialised'   → Sentry.createErrorHandler()   (reports)
        any skipped-* or 'not-started' → new ErrorHandler()     (console, framework default)
```

| Source | Destination | Payload | Live today? |
|---|---|---|---|
| `scalping-machine` browser bundle | Sentry project `4512023800774656` (org `o4512023789830144`, US region) | unhandled error events — message, stack, breadcrumbs, HTTP context, culture, browser session — **plus** pageload and navigation performance spans on one production session in ten (`tracesSampleRate: 0.1`, user decision Q2). **No** session replay (both replay rates are `0` in all six settings files, by user decision Q1). **No** signed-in identity. | **Yes**, in a production build only — `enabled` is `false` in every development settings file |
| `admin-panel` browser bundle | none | none | **No** — carries `PLACEHOLDER-NO-SENTRY-PROJECT-YET-admin-panel`, refused by the recognition rule |
| `scalping-mobile` browser bundle | none | none | **No** — carries `PLACEHOLDER-NO-SENTRY-PROJECT-YET-scalping-mobile`, refused by the recognition rule |
| `ScalpingMachine.API` (.NET) | Sentry project `4512023898488832`, SAME org | server-side exceptions | Owned by the SIBLING contract `2026-09-03-sentry-error-monitoring-dotnet-api.md`. **Different project on purpose** — one project per application. Do not merge the two rows. |

**Three things a future change must not break.** (1) The three browser addresses are **pairwise distinct across applications and identical within an application** — pinned by `ClientApp/projects/admin-panel/src/distinct-monitoring-addresses.spec.ts`, which reads all six settings files as text. Pasting one real address into a second application merges two applications into one project, and the guard is the only thing that catches it. (2) Silence from `admin-panel` or `scalping-mobile` means **not yet connected**, never healthy. (3) Performance tracing is configured (`tracesSampleRate: 0.1` in production) **and live**. `@sentry/angular` does not include `browserTracingIntegration` in its ten defaults, so `startMonitoring` installs it explicitly whenever `tracesSampleRate > 0` and passes it through the `integrations` array; a build shipping the rate at `0` never installs it. Do not remove that gate and do not switch the `integrations` array to a `defaultIntegrations` array — an `integrations` array is MERGED with the defaults by `getIntegrationsToSetup` in `@sentry/core`, while replacing `defaultIntegrations` would drop `dedupeIntegration` and falsify point (2) of the double-reporting proof below.

---

---

## Frontend State Service → Backend Source Mapping

### Scalping Machine App

| State Service | Key Signals | HTTP Source | SignalR Source |
|---|---|---|---|
| `StrategyState` | `items`, `selected`, `loading` | `StrategyService` → `/api/strategies` | — |
| `StrategyRunState` | `runs`, `activeRun`, `flow` | `StrategyRunService` → `/api/strategy-runs` | `FlowUpdate`, `RunStatusUpdate` |
| `ConnectionState` | `status`, `connected` | `ConnectionService` → `/api/connection/status` | `ConnectionStatusChanged` |
| `MarketDataState` | `quotes`, `loading` | `MarketDataService` → `/api/marketdata` | `MarketDataUpdate` |
| `OrderState` | `orders`, `loading`, `selectedOrder` | `OrderService` → `/api/orders` | `OrderStatusUpdate` |
| `NotificationState` | `unread`, `items` | `NotificationService` → `/api/notifications` | `StrategyNotification` |
| `SupportChatState` | `mode`, `conversation`, `messages` | `SupportChatService` → `/api/support` | `SupportMessageReceived`, `ConversationClosed` |
| `ChatState` *(`@scalping/chat`)* | `isOpen`, `messages`, `sending` | `ChatService` → `/api/chat` (via the generated `ChatClient`) | — |
| `ChatContextState` *(`@scalping/chat`)* | `activeContext`, `conversations`, `conversationsByType`, `messages` | `ChatService` → `/api/chat/conversations` | — |
| `SymbolPriorityState` | `pins`, `loading` | `SymbolPriorityService` → `/api/strategy/{id}/pins` | — |

### Shared Libraries

| State Service | Key Signals | HTTP Source | SignalR Source |
|---|---|---|---|
| `RecordingState` (`@scalping/recording`) | `snapshot` (`CaptureSnapshot`: `phase`, `purpose`, `captureMode`, `elapsedMs`, `inputLevel`, `pendingSegmentCount`, `lastError`) | `RECORDING_TRANSPORT` -> REST `/api/recordings` (scalping-machine) / GraphQL (scalping-mobile, Slice C) | - (capture is deliberately decoupled; no hub surface) |

### Admin Panel App

| State Service | Key Signals | HTTP Source | SignalR Source |
|---|---|---|---|
| `AdminConnectionState` | `accounts`, `instances`, `loading` | `AdminConnectionService` → `/api/admin/connection` | `ConnectionStatusChanged` |
| `LlmState` | `providers`, `models`, `gpuStatus`, `sidecarHealth` | `LlmService` → `/api/llm` | — (30s polling) |
| `IngestionState` | `jobs`, `quotas`, `freshness`, `logs`, `progress` | `IngestionService` → `/api/ingestion` | `IngestionLog`, `IngestionProgressUpdated` |
| `AdminSupportChatState` | `conversations`, `messages`, `selectedConversation` | `AdminSupportChatService` → `/api/admin/support` | `NewSupportConversation`, `MessageReceived`, `ConversationClosed` |
| `SymbolDataState` | `result`, `filterOptions`, `detail` | `SymbolDataService` → `/api/admin/symbol-data` | — |
| `TrainingBacklogState` | `items`, `loading` | `TrainingBacklogService` → `/api/training-backlog` | — |

---

## Auto-Refresh Strategies

| State Service | Strategy | Interval |
|---|---|---|
| `AdminConnectionState` | SignalR-driven + 5s poll when containers transitioning | 5s (conditional) |
| `LlmState` | Interval-based polling | 30s |
| `IngestionState` | Interval-based + SignalR log streaming | 15s |

---

## Appending to this file

When a new API endpoint, SignalR event, or frontend state service is introduced:

1. Add the endpoint to the correct API Surface table (Scalping Machine or Admin Panel)
2. Add any new SignalR events to the SignalR Event Surface table with the frontend consumer
3. Update the State Service → Backend Source mapping if a new state service was created
4. If the change affects a Named Integration Flow, update the relevant flow diagram
5. Run `/validate-registries` to check all file paths still resolve
