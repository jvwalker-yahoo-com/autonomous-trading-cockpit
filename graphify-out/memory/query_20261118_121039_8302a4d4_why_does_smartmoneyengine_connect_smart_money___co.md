---
type: "query"
date: "2026-11-18T12:10:39.030530+00:00"
question: "Why does SmartMoneyEngine connect Smart Money & Congress Radar to Cockpit Diagnostics & Telemetry API, Live Data Feed Manager, Engine Package Architecture Docs, Watchlist & Optimization Tests?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["SmartMoneyEngine", "server.py", "smart_money.py", "test_screener_congress_buy_does_not_amplify_short_conviction()", "test_optimizations.py", "MarketScreener", "DataFeedManager"]
---

# Q: Why does SmartMoneyEngine connect Smart Money & Congress Radar to Cockpit Diagnostics & Telemetry API, Live Data Feed Manager, Engine Package Architecture Docs, Watchlist & Optimization Tests?

## Answer

Expanded from original query via vocab: [smart, money, engine, congress, radar, telemetry, screener, feed, watchlist, optimizations, flow, conviction]. SmartMoneyEngine (backend/engine/smart_money.py L43, Community 5: Smart Money & Congress Radar, degree 28) bridges four external communities: (1) Community 1 (Cockpit Diagnostics & Telemetry API) via server.py (backend/server.py L56), which imports SmartMoneyEngine and wires smart_money into collect_pre_trade_intelligence, autonomous_background_worker_loop, and the /api/smart_money/* & /api/flow/* telemetry endpoints; (2) Community 2 (Live Data Feed Manager) via test_screener_congress_buy_does_not_amplify_short_conviction() (tests/test_optimizations.py L181, L204), which pairs SmartMoneyEngine with DataFeedManager, MarketDataPoint, and MarketScreener.get_symbol_screen() (backend/engine/screener.py L522); (3) Community 20 (Engine Package Architecture Docs) via smart_money.py (backend/engine/smart_money.py L1, L43) module containment and stdlib/requests runtime dependencies; and (4) Community 30 (Watchlist & Optimization Tests) via test_optimizations.py (tests/test_optimizations.py L1, L36) importing SmartMoneyEngine and containing test_smart_money_congress_buy_survives_cached_flow() (L465).

## Outcome

- Signal: useful

## Source Nodes

- SmartMoneyEngine
- server.py
- smart_money.py
- test_screener_congress_buy_does_not_amplify_short_conviction()
- test_optimizations.py
- MarketScreener
- DataFeedManager