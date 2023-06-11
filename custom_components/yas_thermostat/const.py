from homeassistant.backports.enum import StrEnum

ATTR_HEATER_SWITCH = "heater_switch"
ATTR_COOLER_SWITCH = "cooler_switch"
ATTR_FAN_SWITCH = "fan_switch"
ATTR_TEMP_SENSOR = "temp_sensor"
ATTR_DEFAULT_PRESET = "default_preset"


class FanMode(StrEnum):
    """Fan Mode for Climate Devices"""

    OFF = "off"
    ON = "on"
    AUTO = "auto"
