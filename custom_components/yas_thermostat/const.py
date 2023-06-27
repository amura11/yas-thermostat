"""YetAnotherSmartThermostat Constants."""
from homeassistant.backports.enum import StrEnum

# Config attribute names
ATTR_HEATER_SWITCH = "heater_switch"
ATTR_COOLER_SWITCH = "cooler_switch"
ATTR_FAN_SWITCH = "fan_switch"
ATTR_TEMP_SENSOR = "temp_sensor"
ATTR_DEFAULT_PRESET = "default_preset"
ATTR_CYCLE_DELAY = "cycle_delay"
ATTR_OPENING_DELAY = "opening_delay"
ATTR_TEMP_TOLERANCE = "temp_tolerance"
ATTR_TEMP_STEP = "temp_step"
ATTR_OPENING_ENTITIES = "openings"
ATTR_DEFAULT_HVAC_MODE = "default_hvac_mode"
ATTR_DEFAULT_FAN_MODE = "default_fan_mode"

# State Attribute names
ATTR_MANUAL_FAN_MODE = "manual_fan_mode"
ATTR_MANUAL_HVAC_MODE = "manual_hvac_mode"
ATTR_MANUAL_TEMP_LOW = "manual_temp_low"
ATTR_MANUAL_TEMP_HIGH = "manual_temp_high"
ATTR_LAST_CYCLE = "last_cycle"


class FanMode(StrEnum):
    """Fan Mode for Climate Devices."""

    OFF = "off"
    ON = "on"
    AUTO = "auto"
