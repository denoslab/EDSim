import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from compute_metrics import (
    resolve_sim_code,
    ensure_compressed,
    find_pia_step,
    find_disposition_step,
)


class TestResolveSimCode:
    def test_explicit_name_passthrough(self):
        assert resolve_sim_code("my-run") == "my-run"

    def test_explicit_name_not_auto(self):
        assert resolve_sim_code("48hr-test") == "48hr-test"

    def test_auto_reads_from_file(self, tmp_path):
        temp_storage = tmp_path / "temp_storage"
        temp_storage.mkdir()
        (temp_storage / "curr_sim_code.json").write_text(
            json.dumps({"sim_code": "test-sim-42"})
        )

        with patch("compute_metrics.FRONTEND_ROOT", tmp_path):
            result = resolve_sim_code("auto")

        assert result == "test-sim-42"

    def test_auto_falls_back_to_default_when_file_missing(self, tmp_path):
        with patch("compute_metrics.FRONTEND_ROOT", tmp_path):
            result = resolve_sim_code("auto")
        assert result == "12hrs"

    def test_latest_alias_same_as_auto(self, tmp_path):
        with patch("compute_metrics.FRONTEND_ROOT", tmp_path):
            result = resolve_sim_code("latest")
        assert result == "12hrs"


class TestEnsureCompressed:
    def test_skips_subprocess_when_already_compressed(self, tmp_path):
        sim_code = "my-sim"
        compressed = tmp_path / "compressed_storage" / sim_code
        compressed.mkdir(parents=True)
        (compressed / "master_movement.json").write_text("{}")

        with patch("compute_metrics.FRONTEND_ROOT", tmp_path), \
             patch("compute_metrics.subprocess") as mock_sub:
            ensure_compressed(sim_code)
            mock_sub.run.assert_not_called()

    def test_raises_when_storage_dir_missing(self, tmp_path):
        with patch("compute_metrics.FRONTEND_ROOT", tmp_path):
            with pytest.raises(FileNotFoundError):
                ensure_compressed("nonexistent-sim")


class TestFindPiaStep:
    def test_returns_step_when_doctor_in_chat(self):
        entries = [
            (10, {"chat": [("Nurse A", "Hello"), ("Doctor Smith", "Hi there")]}),
            (20, {"chat": [("Patient 1", "Thanks")]}),
        ]
        assert find_pia_step(entries) == 10

    def test_returns_none_when_no_doctor_in_chat(self):
        entries = [
            (5, {"chat": [("Triage Nurse", "What brings you in?")]}),
            (15, {}),
        ]
        assert find_pia_step(entries) is None

    def test_returns_none_when_no_chat_at_all(self):
        entries = [(1, {}), (2, {"description": "waiting"})]
        assert find_pia_step(entries) is None

    def test_returns_first_doctor_step(self):
        entries = [
            (5, {"chat": [("Doctor Jones", "Hello")]}),
            (10, {"chat": [("Doctor Lee", "Follow-up")]}),
        ]
        assert find_pia_step(entries) == 5


class TestFindDispositionStep:
    def test_returns_step_on_exit_description(self):
        entries = [
            (30, {"description": "Patient is waiting"}),
            (50, {"description": "Patient exit confirmed"}),
        ]
        assert find_disposition_step(entries) == 50

    def test_returns_step_on_leaving_description(self):
        entries = [
            (10, {"description": "Patient is leaving the department"}),
        ]
        assert find_disposition_step(entries) == 10

    def test_returns_none_when_no_match(self):
        entries = [
            (1, {"description": "Triage in progress"}),
            (2, {"description": "Waiting for doctor"}),
        ]
        assert find_disposition_step(entries) is None

    def test_handles_missing_description_key(self):
        entries = [(1, {}), (2, {"description": None})]
        assert find_disposition_step(entries) is None
