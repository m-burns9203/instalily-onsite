"""Test configuration.

Set environment BEFORE any ``app`` import so the module-level engine binds to an
isolated test database in deterministic mock mode.
"""
import os
import tempfile

os.environ["MOCK_MODE"] = "true"
os.environ["DATABASE_URL"] = (
    f"sqlite:///{os.path.join(tempfile.gettempdir(), 'cosailor_test.db')}"
)
