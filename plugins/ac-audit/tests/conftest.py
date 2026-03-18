"""Pytest configuration for ac-audit tests."""


def pytest_configure(config):  # type: ignore[no-untyped-def]
    """Suppress PytestReturnNotNoneWarning from TestResult-returning test functions."""
    config.addinivalue_line(
        "filterwarnings",
        "ignore::pytest.PytestReturnNotNoneWarning",
    )
