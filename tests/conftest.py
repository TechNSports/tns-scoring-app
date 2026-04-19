"""
tests/conftest.py
-----------------
Session-scoped pytest configuration for the TNS PCA Pipeline test suite.

Purpose
~~~~~~~
All tests run with the TNS_ALLOW_DEV_RENDER=1 environment variable set so
that functions guarded by assert_client_facing_allowed() do not raise
ClientFacingBlockedError during testing.

In CI / production this env var must NOT be set — the guard is intended to
block client-facing output until the v1.1.0 clinical review cycle is
complete and CLIENT_FACING is flipped to True.
"""

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _allow_dev_render_in_tests():
    """Enable dev-render bypass for the entire test session.

    Scoped to session (not function) so the env var is set once at startup
    and torn down after the last test, minimising fixture overhead across the
    ~60-test suite.
    """
    os.environ["TNS_ALLOW_DEV_RENDER"] = "1"
    yield
    os.environ.pop("TNS_ALLOW_DEV_RENDER", None)
