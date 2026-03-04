import pytest


@pytest.fixture
def simple_maze():
    """A minimal 5x5 numeric maze for path_finder_v2 (0=open, 1=wall)."""
    return [
        [1, 1, 1, 1, 1],
        [1, 0, 0, 0, 1],
        [1, 0, 1, 0, 1],
        [1, 0, 0, 0, 1],
        [1, 1, 1, 1, 1],
    ]


@pytest.fixture
def ctas_config():
    """Minimal CTAS wait config matching the real JSON schema."""
    return {
        "1": {
            "arrival_to_initial_assessment":     {"mu": 2.0, "sigma": 0.5, "low": 0, "high": 1440},
            "initial_assessment_to_disposition": {"mu": 5.0, "sigma": 0.5, "low": 0, "high": 1440},
            "disposition_to_exit":               {"mu": 4.0, "sigma": 0.5, "low": 0, "high": 1440},
        },
        "3": {
            "arrival_to_initial_assessment":     {"mu": 5.0, "sigma": 0.5, "low": 0, "high": 1440},
            "initial_assessment_to_disposition": {"mu": 5.0, "sigma": 0.5, "low": 0, "high": 1440},
            "disposition_to_exit":               {"p_zero": 0.745, "mu_pos": 5.25, "sigma_pos": 1.3, "high": 1440},
        },
    }
