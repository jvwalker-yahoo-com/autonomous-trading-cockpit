import pytest
from pathlib import Path
from backend.engine.ai_committee import AICommitteeEngine, AICommitteeDossier
from backend.engine.federation import FederationModule
from fastapi.testclient import TestClient
from backend.server import app

def test_ai_committee_deliberation_and_report_tree(tmp_path):
    engine = AICommitteeEngine(reports_dir=str(tmp_path))
    dossier = engine.evaluate(
        symbol="NVDA",
        price=218.5,
        indicators={"rsi_14": 52.0, "adx": 28.5, "supertrend_dir": 1.0, "volume_surge": 1.35, "wyckoff_phase_code": "D"},
        fundamentals={"pe_ratio": 38.5, "market_cap_b": 2800.0, "revenue_growth_pct": 55.0},
        sentiment_score=0.45,
        headlines=["NVIDIA expands enterprise AI data center compute contracts"],
        smart_money_conviction=0.35
    )

    assert isinstance(dossier, AICommitteeDossier)
    assert dossier.symbol == "NVDA"
    assert dossier.conviction_score > 0
    assert dossier.verdict in ("BUY", "STRONG_BUY")
    assert "technical" in dossier.analyst_reports
    assert "fundamental" in dossier.analyst_reports
    assert len(dossier.debate_transcript) >= 5
    assert "aggressive" in dossier.risk_evaluation
    assert "portfolio" in dossier.pm_rationale.lower()

    # Check TradingAgents report tree on disk
    sym_dir = tmp_path / "NVDA"
    assert (sym_dir / "1_analysts" / "technical.md").exists()
    assert (sym_dir / "1_analysts" / "fundamental.md").exists()
    assert (sym_dir / "2_research" / "research_debate.md").exists()
    assert (sym_dir / "4_risk" / "risk_evaluation.md").exists()
    assert (sym_dir / "5_portfolio" / "final_decision.md").exists()
    assert (sym_dir / "complete_report.md").exists()
    assert (sym_dir / "dossier.json").exists()

def test_federation_incorporates_ai_committee():
    fed = FederationModule()
    out_without = fed.model_federation(
        indicators={"rsi_14": 50.0, "adx": 22.0},
        price=100.0,
        sentiment_val=0.0,
        current_weights={},
        trend="BULL_TREND"
    )
    assert "ai_committee" not in out_without.outputs

    out_with = fed.model_federation(
        indicators={"rsi_14": 50.0, "adx": 22.0},
        price=100.0,
        sentiment_val=0.0,
        current_weights={},
        trend="BULL_TREND",
        ai_committee_score=0.85,
        ai_committee_rationale="Strong Bullish AI Committee Consensus"
    )
    assert "ai_committee" in out_with.outputs
    assert out_with.outputs["ai_committee"] == 0.85
    assert any("AI Committee" in m.name for m in out_with.model_details)

def test_research_api_endpoints():
    client = TestClient(app)
    res = client.get("/api/research/MSFT")
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "MSFT"
    assert "conviction_score" in data
    assert "debate_transcript" in data
    assert "complete_report_md" in data
