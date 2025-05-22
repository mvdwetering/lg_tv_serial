"""Constants for the LG TV Serial integration."""

import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "lg_tv_serial"

SERIAL_URL = "serial_url"

ATTR_COMMANDS = "commands"

SERVICE_SEND_RAW = "send_raw"

ATTR_COMMAND_1 = "command1"
ATTR_COMMAND_2 = "command2"
ATTR_DATA_0 = "data0"
ATTR_DATA_1 = "data1"
ATTR_DATA_2 = "data2"
ATTR_DATA_3 = "data3"
ATTR_DATA_4 = "data4"
ATTR_DATA_5 = "data5"


DEFAULT_DEVICE_NAME = "LG TV"

COORDINATOR_UPDATE_INTERVAL = 10