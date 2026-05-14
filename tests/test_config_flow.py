"""Test LG TV Serial config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_RECONFIGURE
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.lg_tv_serial.const import (
    DOMAIN,
    DSRDTR,
    RTSCTS,
    SERIAL_URL,
    SET_ID,
)


def _make_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="LG TV",
        data={
            SERIAL_URL: "/dev/ttyUSB0",
            SET_ID: 0,
            RTSCTS: False,
            DSRDTR: False,
        },
        entry_id="1",
    )


async def test_reconfigure_updates_entry_and_reloads(hass, mock_setup_entry) -> None:
    """Reconfigure flow updates the entry and schedules a reload."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    mock_setup_entry.assert_awaited_once()

    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )

    new_data = {
        SERIAL_URL: "/dev/ttyUSB1",
        SET_ID: 5,
        RTSCTS: True,
        DSRDTR: True,
    }

    mock_api = AsyncMock()
    mock_api.__aenter__.return_value = mock_api
    mock_api.__aexit__.return_value = False
    mock_api.connect.return_value = None
    mock_api.get_power_on.return_value = True

    with (
        patch(
            "custom_components.lg_tv_serial.config_flow.LgTv",
            return_value=mock_api,
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], user_input=new_data
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == new_data
    mock_reload.assert_called_once_with(entry.entry_id)


async def test_reconfigure_shows_connection_error(hass, mock_setup_entry) -> None:
    """Reconfigure flow shows an error when the TV cannot be reached."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    mock_setup_entry.assert_awaited_once()

    flow = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )

    mock_api = AsyncMock()
    mock_api.__aenter__.return_value = mock_api
    mock_api.__aexit__.return_value = False
    mock_api.connect.side_effect = ConnectionError("boom")

    with patch(
        "custom_components.lg_tv_serial.config_flow.LgTv",
        return_value=mock_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            user_input={
                SERIAL_URL: "/dev/ttyUSB1",
                SET_ID: 5,
                RTSCTS: True,
                DSRDTR: True,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}
