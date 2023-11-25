"""Common fixtures for the LG TV Serial tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield

@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.lg_tv_serial.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
