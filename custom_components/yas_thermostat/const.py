"""YetAnotherSmartThermostat Constants"""
from homeassistant.backports.enum import StrEnum

# Config attribute names
ATTR_HEATER_SWITCH = "heater_switch"
ATTR_COOLER_SWITCH = "cooler_switch"
ATTR_FAN_SWITCH = "fan_switch"
ATTR_TEMP_SENSOR = "temp_sensor"
ATTR_DEFAULT_PRESET = "default_preset"
ATTR_MIN_CYCLE_DURATION = "min_cycle"
ATTR_TEMP_TOLERANCE = "temp_tolerance"
ATTR_TEMP_STEP = "temp_step"
# State Attribute names
ATTR_MANUAL_FAN_MODE = "manual_fan_mode"
ATTR_MANUAL_HVAC_MODE = "manual_hvac_mode"
ATTR_MANUAL_TEMP_LOW = "manual_temp_low"
ATTR_MANUAL_TEMP_HIGH = "manual_temp_high"
ATTR_LAST_CYCLE = "last_cycle"


class FanMode(StrEnum):
    """Fan Mode for Climate Devices"""

    OFF = "off"
    ON = "on"
    AUTO = "auto"
