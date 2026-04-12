"""Tests for WebSocket real-time analysis (v6.0-03).

Tests the streaming pipeline generator and WebSocket endpoint.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engine.pipeline_streaming import (
    StageUpdate,
    get_stage_names,
    run_pipeline_streaming,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_profile() -> dict:
    """Load the sample profile for testing."""
    path = Path(__file__).resolve().parent.parent / "config" / "sample_input.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Streaming pipeline tests
# ---------------------------------------------------------------------------

class TestStreamingPipeline:
    def test_yields_all_stages(self, sample_profile):
        """Pipeline should yield running + complete for every stage."""
        stage_names = get_stage_names()
        updates = list(run_pipeline_streaming(sample_profile))

        # Every stage should appear with both "running" and "complete"
        for name in stage_names:
            running = [u for u in updates if u.stage == name and u.status == "running"]
            complete = [u for u in updates if u.stage == name and u.status == "complete"]
            assert len(running) == 1, f"Missing 'running' for {name}"
            assert len(complete) == 1, f"Missing 'complete' for {name}"

    def test_final_result_is_report(self, sample_profile):
        """The last complete update should be the report stage with full result."""
        updates = list(run_pipeline_streaming(sample_profile))
        final = [u for u in updates if u.stage == "report" and u.status == "complete"]
        assert len(final) == 1
        assert final[0].result is not None
        assert "scoring" in final[0].result
        assert "cashflow" in final[0].result

    def test_durations_are_positive(self, sample_profile):
        """All completed stages should have positive duration."""
        updates = list(run_pipeline_streaming(sample_profile))
        for u in updates:
            if u.status == "complete":
                assert u.duration_ms >= 0, f"{u.stage} has negative duration"

    def test_stage_order(self, sample_profile):
        """Running updates should appear in pipeline order."""
        stage_names = get_stage_names()
        updates = list(run_pipeline_streaming(sample_profile))
        running_order = [u.stage for u in updates if u.status == "running"]
        assert running_order == stage_names

    def test_report_matches_sync_pipeline(self, sample_profile):
        """Streaming pipeline should produce same report as sync pipeline."""
        from engine.pipeline import run_pipeline

        sync_report, _, _ = run_pipeline(sample_profile)
        updates = list(run_pipeline_streaming(sample_profile))
        stream_report = next(
            u.result for u in updates
            if u.stage == "report" and u.status == "complete"
        )

        assert sync_report["scoring"]["overall_score"] == stream_report["scoring"]["overall_score"]
        assert sync_report["scoring"]["grade"] == stream_report["scoring"]["grade"]

    def test_stage_count(self):
        """Should have exactly 17 stages."""
        assert len(get_stage_names()) == 17


class TestStageUpdate:
    def test_defaults(self):
        u = StageUpdate(stage="test", status="running")
        assert u.duration_ms == 0.0
        assert u.result is None
        assert u.error is None


# ---------------------------------------------------------------------------
# WebSocket endpoint tests
# ---------------------------------------------------------------------------

class TestWebSocketEndpoint:
    def test_analyse_streams_progress(self, sample_profile):
        """WebSocket /ws/analyse should stream progress and result."""
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        with client.websocket_connect("/ws/analyse") as ws:
            ws.send_json({"type": "analyse", "profile": sample_profile})

            messages = []
            while True:
                msg = ws.receive_json()
                messages.append(msg)
                if msg.get("type") == "result":
                    break

            # Should have progress messages
            progress = [m for m in messages if m["type"] == "progress"]
            assert len(progress) > 0

            # Should have a final result
            results = [m for m in messages if m["type"] == "result"]
            assert len(results) == 1
            assert "report" in results[0]
            assert "scoring" in results[0]["report"]

    def test_ping_pong(self):
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        with client.websocket_connect("/ws/analyse") as ws:
            ws.send_json({"type": "ping"})
            msg = ws.receive_json()
            assert msg == {"type": "pong"}

    def test_invalid_json(self):
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        with client.websocket_connect("/ws/analyse") as ws:
            ws.send_text("not json")
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "Invalid JSON" in msg["detail"]

    def test_missing_profile(self):
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        with client.websocket_connect("/ws/analyse") as ws:
            ws.send_json({"type": "analyse"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "profile" in msg["detail"].lower()

    def test_unknown_message_type(self):
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        with client.websocket_connect("/ws/analyse") as ws:
            ws.send_json({"type": "unknown_cmd"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "Unknown" in msg["detail"]

    def test_progress_includes_index_and_total(self, sample_profile):
        from fastapi.testclient import TestClient

        from api.main import app

        client = TestClient(app)
        with client.websocket_connect("/ws/analyse") as ws:
            ws.send_json({"type": "analyse", "profile": sample_profile})

            first_progress = None
            while True:
                msg = ws.receive_json()
                if msg.get("type") == "progress" and first_progress is None:
                    first_progress = msg
                if msg.get("type") == "result":
                    break

            assert first_progress is not None
            assert "index" in first_progress
            assert "total" in first_progress
            assert first_progress["total"] == 17
