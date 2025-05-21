"""Constants for the LG TV Serial integration."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "lg_tv_serial"

SERIAL_URL = "serial_url"

ATTR_COMMANDS = "commands"

SERVICE_SEND_RAW = "send_raw"

ATTR_COMMAND1 = "command1"
ATTR_COMMAND2 = "command2"
ATTR_DATA = "data"


DEFAULT_DEVICE_NAME = "LG TV"

COORDINATOR_UPDATE_INTERVAL = 10