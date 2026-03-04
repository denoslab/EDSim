import random
import statistics
import pytest
from wait_time_utils import _load_ctas_wait_config, _sample_wait_minutes


class TestLoadCtasWaitConfig:
    def test_returns_dict(self):
        config = _load_ctas_wait_config()
        assert isinstance(config, dict)

    def test_has_all_ctas_keys(self):
        config = _load_ctas_wait_config()
        for score in range(1, 6):
            assert str(score) in config

    def test_each_entry_has_three_stages(self):
        config = _load_ctas_wait_config()
        expected_stages = {
            "arrival_to_initial_assessment",
            "initial_assessment_to_disposition",
            "disposition_to_exit",
        }
        for score_key, stages in config.items():
            assert expected_stages == set(stages.keys()), f"CTAS {score_key} missing stages"


class TestSampleWaitMinutes:
    def test_empty_config_returns_zero(self):
        assert _sample_wait_minutes({}, 1, "arrival_to_initial_assessment") == 0

    def test_missing_stage_returns_zero(self, ctas_config):
        assert _sample_wait_minutes(ctas_config, 1, "nonexistent_stage") == 0

    def test_truncated_lognormal_within_bounds(self, ctas_config):
        results = [
            _sample_wait_minutes(ctas_config, 1, "arrival_to_initial_assessment")
            for _ in range(100)
        ]
        assert all(0 <= x <= 1440 for x in results)

    def test_hurdle_zero_path(self, ctas_config):
        # Force p_zero branch: seed so random() is always 0.0 (< any p_zero > 0)
        random.seed(0)
        # Keep drawing until we hit a zero return (p_zero=0.745 means ~74.5% chance)
        zeros = [
            _sample_wait_minutes(ctas_config, 3, "disposition_to_exit")
            for _ in range(200)
        ]
        assert 0.0 in zeros

    def test_hurdle_positive_path(self, ctas_config):
        # There should also be positive values (p_zero < 1.0)
        results = [
            _sample_wait_minutes(ctas_config, 3, "disposition_to_exit")
            for _ in range(200)
        ]
        assert any(x > 0 for x in results)

    def test_hurdle_positive_within_bounds(self, ctas_config):
        results = [
            _sample_wait_minutes(ctas_config, 3, "disposition_to_exit")
            for _ in range(200)
        ]
        assert all(0 <= x <= 1440 for x in results)

    def test_surge_multiplier_increases_median(self, ctas_config):
        random.seed(42)
        baseline = [
            _sample_wait_minutes(ctas_config, 1, "arrival_to_initial_assessment", surge_multiplier=1.0)
            for _ in range(500)
        ]
        random.seed(42)
        surge = [
            _sample_wait_minutes(ctas_config, 1, "arrival_to_initial_assessment", surge_multiplier=2.0)
            for _ in range(500)
        ]
        assert statistics.median(surge) > statistics.median(baseline)
