"""The YAS Thermostat integration."""
from __future__ import annotations
import logging
from homeassistant.components.climate.const import HVACMode
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from typing import Any, Callable, Dict, Optional
from homeassistant.core import DOMAIN as HA_DOMAIN, CoreState, callback, HomeAssistant
from homeassistant.components.climate import ClimateEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.climate import PLATFORM_SCHEMA, HVACMode

from homeassistant.const import ATTR_NAME, ATTR_TEMPERATURE, UnitOfTemperature

from homeassistant.components.climate.const import (
    ATTR_MIN_TEMP,
    ATTR_MAX_TEMP,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODES,
    ClimateEntityFeature,
)

from .const import (
    ATTR_HEATER_SWITCH,
    ATTR_COOLER_SWITCH,
    ATTR_FAN_SWITCH,
    ATTR_TEMP_SENSOR,
    ATTR_DEFAULT_PRESET,
    FanMode,
)

_LOGGER = logging.getLogger(__name__)
DEFAULT_MIN_TEMP = 7
DEFAULT_MAX_TEMP = 35

PRESET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_TARGET_TEMP_LOW): vol.Coerce(float),
        vol.Required(ATTR_TARGET_TEMP_HIGH): vol.Coerce(float),
        vol.Optional(ATTR_FAN_MODE): vol.In([FanMode.ON, FanMode.OFF, FanMode.AUTO]),
        vol.Optional(ATTR_HVAC_MODE): vol.In(
            [
                HVACMode.COOL,
                HVACMode.HEAT,
                HVACMode.OFF,
                HVACMode.HEAT_COOL,
                HVACMode.FAN_ONLY,
            ]
        ),
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_PRESET_MODES): vol.All(cv.ensure_list, [PRESET_SCHEMA]),
        vol.Optional(ATTR_TEMP_SENSOR): cv.entity_id,
        vol.Optional(ATTR_COOLER_SWITCH): cv.entity_id,
        vol.Optional(ATTR_HEATER_SWITCH): cv.entity_id,
        vol.Optional(ATTR_FAN_SWITCH): cv.entity_id,
        vol.Optional(ATTR_DEFAULT_PRESET): cv.string,
        vol.Optional(ATTR_MIN_TEMP): vol.Coerce(float),
        vol.Optional(ATTR_MAX_TEMP): vol.Coerce(float),
    }
)

# Additional validations
PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(ATTR_COOLER_SWITCH, ATTR_HEATER_SWITCH, ATTR_FAN_SWITCH),
    PLATFORM_SCHEMA,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Setup YAS Thermostat Platform"""
    name: str = config[ATTR_NAME]
    presets = dict(
        map(
            lambda p: (
                p[ATTR_NAME],
                ClimateSettings(
                    p.get(ATTR_TARGET_TEMP_LOW),
                    p.get(ATTR_TARGET_TEMP_HIGH),
                    p.get(ATTR_HVAC_MODE, HVACMode.AUTO),
                    p.get(ATTR_FAN_MODE, None),
                ),
            ),
            config[ATTR_PRESET_MODES],
        )
    )
    heater_switch_id = config.get(ATTR_HEATER_SWITCH)
    cooler_switch_id = config.get(ATTR_COOLER_SWITCH)
    fan_switch_id = config.get(ATTR_FAN_SWITCH)
    default_preset: str = config.get(ATTR_DEFAULT_PRESET, next(iter(presets)))
    temp_unit: UnitOfTemperature = hass.config.units.temperature_unit
    min_temp: float | None = config.get(ATTR_MIN_TEMP, DEFAULT_MIN_TEMP)
    max_temp: float | None = config.get(ATTR_MAX_TEMP, DEFAULT_MAX_TEMP)

    entities = [
        YetAnotherSmartThermostat(
            name,
            heater_switch_id,
            cooler_switch_id,
            fan_switch_id,
            min_temp,
            max_temp,
            temp_unit,
            presets,
            default_preset,
        )
    ]
    async_add_entities(entities, update_before_add=True)


class ClimateSettings:
    """Class to store current and preset thermostat settings"""

    _temp_high: float
    _temp_low: float
    _hvac_mode: HVACMode
    _fan_mode: FanMode

    def __init__(
        self,
        temp_low: float,
        temp_high: float,
        hvac_mode: HVACMode,
        fan_mode: FanMode | None,
    ) -> None:
        """Initializes an instance of the thermostat preset"""
        self._temp_high = temp_high
        self._temp_low = temp_low
        self._hvac_mode = hvac_mode
        self._fan_mode = fan_mode

    @property
    def temp_high(self) -> float:
        return self._temp_high

    @temp_high.setter
    def temp_high(self, value: float) -> None:
        self._temp_high = value

    @property
    def temp_low(self) -> float:
        return self._temp_low

    @temp_low.setter
    def temp_low(self, value: float) -> None:
        self._temp_low = value

    @property
    def hvac_mode(self) -> HVACMode:
        return self._hvac_mode

    @hvac_mode.setter
    def hvac_mode(self, value: HVACMode) -> None:
        self._hvac_mode = value

    @property
    def fan_mode(self) -> FanMode | None:
        return self._fan_mode

    @fan_mode.setter
    def fan_mode(self, value: FanMode | None) -> None:
        self._fan_mode = value

    def clone(self) -> ClimateSettings:
        return ClimateSettings(
            self.temp_low, self.temp_high, self.hvac_mode, self.fan_mode
        )


class YetAnotherSmartThermostat(ClimateEntity, RestoreEntity):
    """Thermostat Class"""

    _presets: dict[str, ClimateSettings]
    _heater_switch_id: str | None = None
    _cooler_switch_id: str | None = None
    _fan_switch_id: str | None = None
    _current_settings: ClimateSettings
    _current_preset: str | None = None
    _current_temp: float | None = 12.34
    _min_temp: float
    _max_temp: float
    _temp_unit: UnitOfTemperature

    _supported_features: ClimateEntityFeature = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )
    _available_hvac_modes: list[HVACMode] = [HVACMode.OFF, HVACMode.AUTO]
    _available_fan_modes: list[FanMode] | None = None

    def __init__(
        self,
        name: str,
        heater_entity_id: str | None,
        cooler_entity_id: str | None,
        fan_entity_id: str | None,
        min_temp: float | None,
        max_temp: float | None,
        temp_unit: UnitOfTemperature,
        presets: dict[str, ClimateSettings],
        initial_preset: str,
    ) -> None:
        """Initialize Thermostat"""
        self._name = name
        self._presets = presets
        self._temp_unit = temp_unit
        self._heater_switch_id = heater_entity_id
        self._cooler_switch_id = cooler_entity_id
        self._fan_switch_id = fan_entity_id
        self._min_temp = min_temp
        self._max_temp = max_temp

        # Setup modes and features
        if fan_entity_id is not None:
            self._available_hvac_modes.append(HVACMode.FAN_ONLY)
            self._available_fan_modes = [FanMode.OFF, FanMode.ON, FanMode.AUTO]
            self._supported_features |= ClimateEntityFeature.FAN_MODE
        if heater_entity_id is not None:
            self._available_hvac_modes.append(HVACMode.HEAT)
        if cooler_entity_id is not None:
            self._available_hvac_modes.append(HVACMode.COOL)
        if heater_entity_id is not None and cooler_entity_id is not None:
            self._available_hvac_modes.append(HVACMode.HEAT_COOL)

        # Initialize the default preset
        self.set_preset_mode(initial_preset)

    @property
    def name(self) -> str:
        """Returns the name of the entity"""
        return self._name

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        _LOGGER.debug("Getting supported features %s", self._supported_features)
        return self._supported_features

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        _LOGGER.debug("Getting low temp: %d", self._current_settings.temp_low)
        return self._current_settings.temp_low

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        _LOGGER.debug("Getting high temp: %d", self._current_settings.temp_high)
        return self._current_settings.temp_high

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temp

    def set_temperature(self, **kwargs) -> None:
        """Sets the new temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        if temp is not None:
            raise ValueError("Target temperature mode not supported")

        if temp_low is not None:
            self._current_settings.temp_low = temp_low
        if temp_high is not None:
            self._current_settings.temp_high = temp_high

        self._current_preset = None

        _LOGGER.debug(
            "Temperature set to range (%d,%d), preset value reset", temp_low, temp_high
        )

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """List of available operation modes."""
        return self._available_hvac_modes

    @property
    def hvac_mode(self) -> HVACMode:
        """Returns the current HVAC mode."""
        return self._current_settings.hvac_mode

    def set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        self._current_settings.hvac_mode = hvac_mode
        self._current_preset = None

        _LOGGER.debug("HVAC Mode set to %s, preset value reset", hvac_mode)

    @property
    def preset_modes(self) -> list[str] | None:
        return list(self._presets.keys())

    @property
    def preset_mode(self) -> str | None:
        """Returns the current preset mode or none."""
        return self._current_preset

    def set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in self._presets:
            raise KeyError("Preset does not exist")

        self._current_preset = preset_mode
        self._current_settings = self._presets[preset_mode].clone()

        _LOGGER.debug("Preset set to %s", preset_mode)

    @property
    def temperature_unit(self) -> UnitOfTemperature:
        return self._temp_unit

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return 1

    @property
    def min_temp(self) -> float:
        return self._min_temp

    @property
    def max_temp(self) -> float:
        return self._max_temp

    def update(self) -> None:
        _LOGGER.info("Thermostat test! Name is %s", self._name)
