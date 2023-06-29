"""The YAS Thermostat integration."""
from __future__ import annotations
import asyncio
import logging
import voluptuous as vol

from datetime import datetime, timedelta, timezone
from homeassistant.core import (
    HomeAssistant,
    Event,
    State,
    CoreState,
    callback,
    DOMAIN as HA_DOMAIN,
)
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.components.climate import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_NAME,
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_OPEN,
    EVENT_HOMEASSISTANT_START,
    UnitOfTemperature,
)

from homeassistant.components.climate.const import (
    ATTR_MIN_TEMP,
    ATTR_MAX_TEMP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ClimateEntityFeature,
)

from .const import (
    ATTR_HEATER_SWITCH,
    ATTR_COOLER_SWITCH,
    ATTR_FAN_SWITCH,
    ATTR_TEMP_SENSOR,
    ATTR_DEFAULT_PRESET,
    ATTR_TEMP_TOLERANCE,
    ATTR_TEMP_STEP,
    ATTR_OPENING_ENTITIES,
    ATTR_OPENING_DELAY,
    ATTR_CYCLE_DELAY,
    ATTR_DEFAULT_HVAC_MODE,
    ATTR_DEFAULT_FAN_MODE,
    ATTR_MANUAL_FAN_MODE,
    ATTR_MANUAL_HVAC_MODE,
    ATTR_MANUAL_TEMP_LOW,
    ATTR_MANUAL_TEMP_HIGH,
    FanMode,
)

_LOGGER = logging.getLogger(__name__)
DEFAULT_TEMP_MIN = 7
DEFAULT_TEMP_MAX = 35
DEFAULT_CYCLE_DELAY = timedelta(minutes=5)
DEFAULT_OPENING_DELAY = timedelta(seconds=30)
DEFAULT_TEMP_TOLERANCE = 0.75
DEFAULT_FAN_MODE = FanMode.OFF
DEFAULT_HVAC_MODE = HVACMode.OFF

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
        vol.Required(ATTR_TEMP_SENSOR): cv.entity_id,
        vol.Required(ATTR_PRESET_MODES): vol.All(cv.ensure_list, [PRESET_SCHEMA]),
        # Optional Values
        vol.Optional(ATTR_COOLER_SWITCH): cv.entity_id,
        vol.Optional(ATTR_HEATER_SWITCH): cv.entity_id,
        vol.Optional(ATTR_FAN_SWITCH): cv.entity_id,
        vol.Optional(ATTR_OPENING_ENTITIES): cv.entity_ids,
        vol.Optional(ATTR_MIN_TEMP): vol.Coerce(float),
        vol.Optional(ATTR_MAX_TEMP): vol.Coerce(float),
        vol.Optional(ATTR_TEMP_STEP): vol.Coerce(float),
        vol.Optional(ATTR_OPENING_DELAY): vol.All(
            cv.time_period, cv.positive_timedelta
        ),
        vol.Optional(ATTR_CYCLE_DELAY): vol.All(cv.time_period, cv.positive_timedelta),
        vol.Optional(ATTR_TEMP_TOLERANCE): vol.Coerce(float),
        vol.Optional(ATTR_DEFAULT_PRESET): cv.string,
        vol.Optional(ATTR_DEFAULT_HVAC_MODE): vol.In(
            [
                HVACMode.COOL,
                HVACMode.HEAT,
                HVACMode.OFF,
                HVACMode.HEAT_COOL,
                HVACMode.FAN_ONLY,
            ]
        ),
        vol.Optional(ATTR_DEFAULT_FAN_MODE): vol.In(
            [FanMode.ON, FanMode.OFF, FanMode.AUTO]
        ),
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
    """Initialize the YAS Thermostat Platform."""

    name: str = config[ATTR_NAME]
    default_hvac_mode = config.get(ATTR_DEFAULT_HVAC_MODE, DEFAULT_HVAC_MODE)
    default_fan_mode = config.get(ATTR_DEFAULT_FAN_MODE, DEFAULT_FAN_MODE)

    def createPreset(c) -> ClimateSettings:
        return ClimateSettings(
            c.get(ATTR_TARGET_TEMP_LOW),
            c.get(ATTR_TARGET_TEMP_HIGH),
            c.get(ATTR_HVAC_MODE, default_hvac_mode),
            c.get(ATTR_FAN_MODE, default_fan_mode),
        )

    presets = {p[ATTR_NAME]: createPreset(p) for p in config[ATTR_PRESET_MODES]}
    heater_switch_id = config.get(ATTR_HEATER_SWITCH)
    cooler_switch_id = config.get(ATTR_COOLER_SWITCH)
    fan_switch_id = config.get(ATTR_FAN_SWITCH)
    opening_entity_ids = config.get(ATTR_OPENING_ENTITIES)
    default_preset: str = config.get(ATTR_DEFAULT_PRESET, next(iter(presets)))
    temp_sensor_id = config.get(ATTR_TEMP_SENSOR)
    temp_unit: UnitOfTemperature = hass.config.units.temperature_unit
    temp_min: float = config.get(ATTR_MIN_TEMP, DEFAULT_TEMP_MIN)
    temp_max: float = config.get(ATTR_MAX_TEMP, DEFAULT_TEMP_MAX)
    temp_tolerance: float = config.get(ATTR_TEMP_TOLERANCE, DEFAULT_TEMP_TOLERANCE)
    temp_step: float = config.get(ATTR_TEMP_STEP, 1.0)
    cycle_delay: timedelta = config.get(ATTR_CYCLE_DELAY, DEFAULT_CYCLE_DELAY)
    opening_delay: timedelta = config.get(ATTR_OPENING_DELAY, DEFAULT_OPENING_DELAY)

    entities = [
        YetAnotherSmartThermostat(
            name,
            temp_sensor_id,
            heater_switch_id,
            cooler_switch_id,
            fan_switch_id,
            opening_entity_ids,
            temp_min,
            temp_max,
            temp_unit,
            temp_tolerance,
            temp_step,
            cycle_delay,
            opening_delay,
            presets,
            default_preset,
            default_fan_mode,
            default_hvac_mode,
        )
    ]
    async_add_entities(entities, update_before_add=True)


class YetAnotherSmartThermostat(ClimateEntity, RestoreEntity):
    """Thermostat Class."""

    # Settings
    _heater_switch_id: str | None = None
    _cooler_switch_id: str | None = None
    _temp_sensor_id: str
    _fan_switch_id: str | None = None
    _opening_entity_ids: list[str] | None = None
    _presets: dict[str, ClimateSettings]
    _temp_min: float
    _temp_max: float
    _temp_unit: UnitOfTemperature
    _temp_tolerance: float
    _temp_step: float
    _cycle_delay: timedelta
    _opening_delay: timedelta = timedelta(seconds=30)

    # Current values
    _current_settings: ClimateSettings
    _current_preset: str | None = None
    _current_temp: float | None = None
    _current_opening_states: dict[str, bool] = {}
    _is_heater_active: bool = False
    _is_cooler_active: bool = False
    _is_fan_active: bool = False
    _is_initialized: bool = False
    _openings_locked_value: bool | None = None
    _openings_lock_expiry: datetime | None = None
    _cycle_lock_expiry: datetime | None = None

    _supported_features: ClimateEntityFeature = (
        ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )
    _available_hvac_modes: list[HVACMode] = [HVACMode.OFF]
    _available_fan_modes: list[FanMode] | None = None
    _valid_heat_hvac_modes: list[HVACMode] = [
        HVACMode.HEAT_COOL,
        HVACMode.HEAT,
    ]
    _valid_cool_hvac_modes: list[HVACMode] = [
        HVACMode.HEAT_COOL,
        HVACMode.COOL,
    ]

    def __init__(
        self,
        name: str,
        temp_sensor_id: str,
        heater_entity_id: str | None,
        cooler_entity_id: str | None,
        fan_entity_id: str | None,
        opening_entity_ids: list[str] | None,
        temp_min: float | None,
        temp_max: float | None,
        temp_unit: UnitOfTemperature,
        temp_tolerance: float,
        temp_step: float,
        cycle_delay: timedelta,
        opening_delay: timedelta,
        presets: dict[str, ClimateSettings],
        default_preset: str,
        default_hvac_mode: HVACMode,
        default_fan_mode: FanMode,
    ) -> None:
        """Initialize a new instance of the YetAnotherSmartThermostat class."""
        self._name = name
        self._presets = presets
        self._temp_sensor_id = temp_sensor_id
        self._heater_switch_id = heater_entity_id
        self._cooler_switch_id = cooler_entity_id
        self._fan_switch_id = fan_entity_id
        self._opening_entity_ids = opening_entity_ids
        self._temp_min = temp_min
        self._temp_max = temp_max
        self._temp_unit = temp_unit
        self._temp_tolerance = temp_tolerance
        self._temp_step = temp_step
        self._cycle_delay = cycle_delay
        self._opening_delay = opening_delay
        self._default_hvac_mode = default_hvac_mode
        self._default_fan_mode = default_fan_mode

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
        self._current_preset = default_preset
        self._current_settings = self._presets[default_preset].clone()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""

        await super().async_added_to_hass()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._temp_sensor_id], self._async_on_temperature_changed
            )
        )

        if self._heater_switch_id is not None:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._heater_switch_id], self._on_heater_switch_changed
                )
            )

        if self._cooler_switch_id is not None:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._cooler_switch_id], self._on_cooler_switch_changed
                )
            )

        # Setup the listener for the openings if they are set
        if self._opening_entity_ids:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    self._opening_entity_ids,
                    self._on_opening_entity_changed,
                )
            )

        # Load the previous state if it's present
        previous_state: State | None = await self.async_get_last_state()
        if previous_state is not None:
            _LOGGER.debug("Previous state found, loading data")
            # Set the previous preset
            if (
                previous_preset := previous_state.attributes.get(ATTR_PRESET_MODE)
            ) is not None and previous_preset in self._presets:
                _LOGGER.debug("Previous state had preset %s", previous_preset)
                self._current_preset = previous_preset
                self._current_settings = self._presets[previous_preset].clone()
            elif (
                previous_settings := self._read_manual_settings(previous_state)
            ) is not None:
                _LOGGER.debug(
                    "Previous state had manual settings %s", previous_settings
                )
                self._current_preset = None
                self._current_settings = previous_settings
            # Otherwise something is weird or we have no state so use the default which is set already

        # Startup function to run at HA startup or on creation, loads current values and old state
        @callback
        def _async_startup(*_) -> None:
            sensor_state = self.hass.states.get(self._temp_sensor_id)
            self._current_temp = (
                float(sensor_state.state) if sensor_state is not None else None
            )

            # Set the current cooler siwtch state
            if self._cooler_switch_id is not None:
                cooler_state: State | None = self.hass.states.get(
                    self._cooler_switch_id
                )
                self._is_cooler_active = (
                    cooler_state.state == STATE_ON
                    if cooler_state is not None
                    else False
                )

            # Set the current heater siwtch state
            if self._heater_switch_id is not None:
                heater_state: State | None = self.hass.states.get(
                    self._heater_switch_id
                )
                self._is_heater_active = (
                    heater_state.state == STATE_ON
                    if heater_state is not None
                    else False
                )

            # Set the current fan state
            if self._fan_switch_id is not None:
                fan_state: State | None = self.hass.states.get(self._fan_switch_id)
                self._is_fan_active = (
                    fan_state.state == STATE_ON if fan_state is not None else False
                )

            # Build the dictionary of opening states
            if self._opening_entity_ids:
                _LOGGER.debug("Initializing openings %s", self._opening_entity_ids)
                for entity_id in self._opening_entity_ids:
                    opening_state: State | None = self.hass.states.get(entity_id)
                    self._current_opening_states[entity_id] = (
                        opening_state in [STATE_OPEN, STATE_ON]
                        if opening_state is not None
                        else False
                    )

            self._is_initialized = True

            # Call update to get things going
            asyncio.run_coroutine_threadsafe(self.async_update(), self.hass.loop)

        # Call the startup function immediately if HA is running or wait until it is to run it
        if self.hass.state == CoreState.running:
            _async_startup()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes to be saved."""
        data = {
            ATTR_MANUAL_HVAC_MODE: None,
            ATTR_MANUAL_FAN_MODE: None,
            ATTR_MANUAL_TEMP_LOW: None,
            ATTR_MANUAL_TEMP_HIGH: None,
        }

        if self._current_preset is None:
            data[ATTR_MANUAL_HVAC_MODE] = self._current_settings.hvac_mode
            data[ATTR_MANUAL_FAN_MODE] = self._current_settings.fan_mode
            data[ATTR_MANUAL_TEMP_LOW] = self._current_settings.temp_low
            data[ATTR_MANUAL_TEMP_HIGH] = self._current_settings.temp_high

        return data

    @property
    def name(self) -> str:
        """Returns the name of the entity."""
        return self._name

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        return self._supported_features

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        return self._current_settings.temp_low

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        return self._current_settings.temp_high

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._current_temp

    async def async_set_temperature(self, **kwargs) -> None:
        """Set the new temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        if temp is not None:
            raise ValueError("Target temperature mode not supported")

        if temp_low is None and temp_high is None:
            raise ValueError("At least one temperature value is required")

        self._current_preset = None
        self._current_settings.temp_low = (
            temp_low if temp_low is not None else self._current_settings.temp_low
        )
        self._current_settings.temp_high = (
            temp_high if temp_high is not None else self._current_settings.temp_high
        )

        _LOGGER.debug("Temperate range changed to %s - %s", temp_low, temp_high)

        await self.async_update()
        self.async_write_ha_state()

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """List of available operation modes."""
        return self._available_hvac_modes

    @property
    def hvac_mode(self) -> HVACMode:
        """Returns the current HVAC mode."""
        return self._current_settings.hvac_mode

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new hvac mode."""
        _LOGGER.debug("Setting HVac Mode to %s", hvac_mode)

        self._current_preset = None
        self._current_settings.hvac_mode = hvac_mode

        await self.async_update()
        self.async_write_ha_state()

    @property
    def preset_modes(self) -> list[str] | None:
        """Returns the available preset modes."""
        return list(self._presets.keys())

    @property
    def preset_mode(self) -> str | None:
        """Returns the current preset mode or none."""
        return self._current_preset

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in self._presets:
            raise KeyError("Preset does not exist")

        _LOGGER.debug("Changing preset to %s", preset_mode)

        self._current_preset = preset_mode
        self._current_settings = self._presets[preset_mode].clone()

        await self.async_update()
        self.async_write_ha_state()

    @property
    def fan_modes(self) -> list[str]:
        """Return the list of available fan modes."""
        return self._available_fan_modes

    @property
    def fan_mode(self) -> str:
        """Returns the current fan mode."""
        return self._current_settings.fan_mode

    async def async_set_fan_mode(self, fan_mode: str | FanMode) -> None:
        """Set the the new fan mode."""
        _LOGGER.debug("Changing Fan Mode to %s", fan_mode)

        self._current_preset = None
        self._current_settings.fan_mode = fan_mode

        await self.async_update()
        self.async_write_ha_state()

    @property
    def temperature_unit(self) -> UnitOfTemperature:
        """Gets the current temperature unit."""
        return self._temp_unit

    @property
    def target_temperature_step(self) -> float | None:
        """Return the supported step of target temperature."""
        return self._temp_step

    @property
    def min_temp(self) -> float:
        """Gets the minimum temperature."""
        return self._temp_min

    @property
    def max_temp(self) -> float:
        """Gets the maximum temperature."""
        return self._temp_max

    @property
    def _is_cooling_needed(self) -> bool:
        return (
            self._current_temp - self._current_settings.temp_high > self._temp_tolerance
            and self._current_settings.hvac_mode in self._valid_cool_hvac_modes
            and self._is_any_opening_open is False
        )

    @property
    def _is_heating_needed(self) -> bool:
        return (
            self._current_settings.temp_low - self._current_temp > self._temp_tolerance
            and self._current_settings.hvac_mode in self._valid_heat_hvac_modes
            and self._is_any_opening_open is False
        )

    @property
    def _is_fan_needed(self) -> bool:
        return (
            self._current_settings.hvac_mode == HVACMode.FAN_ONLY
            or self._current_settings.fan_mode == FanMode.ON
            or (
                self._current_settings.fan_mode == FanMode.AUTO
                and (self._is_cooler_active is True or self._is_heater_active is True)
            )
        )

    @property
    def _is_openings_value_locked(self) -> bool:
        _LOGGER.debug("Opening lock expiry %s", self._openings_lock_expiry)
        return (
            self._openings_lock_expiry is not None
            and self._openings_lock_expiry >= datetime.now(timezone.utc)
        )

    @property
    def _is_any_opening_open(self) -> bool:
        if self._is_openings_value_locked:
            _LOGGER.debug("Openings value locked, using locked value")
            return self._openings_locked_value
        else:
            return (
                any(self._current_opening_states.values())
                if self._current_opening_states is not None
                else False
            )

    async def async_update(self) -> None:
        """Update the entity."""
        current_time = datetime.now(timezone.utc)
        cooler_changed: bool = False
        heater_changed: bool = False
        fan_changed: bool = False

        if self._is_initialized is False:
            _LOGGER.debug("Not ready")
            return

        if self._cycle_lock_expiry is None or current_time >= self._cycle_lock_expiry:
            if self._is_cooling_needed is True:
                cooler_changed |= await self._async_cooler_on()
                if cooler_changed:
                    _LOGGER.debug("Cooler required and was enabled")
            else:
                cooler_changed |= await self._async_cooler_off()
                if cooler_changed:
                    _LOGGER.debug("Cooler not required and was disabled")

            if self._is_heating_needed is True:
                heater_changed |= await self._async_heater_on()
                if heater_changed:
                    _LOGGER.debug("Heater required and was enabled")
            else:
                heater_changed |= await self._async_heater_off()
                if heater_changed:
                    _LOGGER.debug("Heater not required and was disabled")

        if self._is_fan_needed is True:
            fan_changed |= await self._async_fan_on()
            if fan_changed:
                _LOGGER.debug("Fan required and was enabled")
        else:
            fan_changed |= await self._async_fan_off()
            if fan_changed:
                _LOGGER.debug("Fan not required and was disabled")

        if cooler_changed or heater_changed:
            self._cycle_lock_expiry = datetime.now(timezone.utc) + self._cycle_delay

        if cooler_changed or heater_changed or fan_changed:
            self.async_write_ha_state()

    async def _async_cooler_on(self) -> bool:
        if self._cooler_switch_id is not None and self._is_cooler_active is False:
            await self.hass.services.async_call(
                HA_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: self._cooler_switch_id},
                context=self._context,
            )

            self._is_cooler_active = True
            return True
        return False

    async def _async_cooler_off(self) -> bool:
        if self._cooler_switch_id is not None and self._is_cooler_active is True:
            await self.hass.services.async_call(
                HA_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self._cooler_switch_id},
                context=self._context,
            )

            self._is_cooler_active = False
            return True
        return False

    async def _async_heater_on(self) -> bool:
        if self._heater_switch_id is not None and self._is_heater_active is False:
            await self.hass.services.async_call(
                HA_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: self._heater_switch_id},
                context=self._context,
            )

            self._is_heater_active = True
            return True
        return False

    async def _async_heater_off(self) -> bool:
        if self._heater_switch_id is not None and self._is_heater_active is True:
            await self.hass.services.async_call(
                HA_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self._heater_switch_id},
                context=self._context,
            )

            self._is_heater_active = False
            return True
        return False

    async def _async_fan_on(self) -> bool:
        if self._fan_switch_id is not None and self._is_fan_active is False:
            await self.hass.services.async_call(
                HA_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: self._fan_switch_id},
                context=self._context,
            )

            self._is_fan_active = True
            return True
        return False

    async def _async_fan_off(self) -> bool:
        if self._fan_switch_id is not None and self._is_fan_active is True:
            await self.hass.services.async_call(
                HA_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: self._fan_switch_id},
                context=self._context,
            )

            self._is_fan_active = False
            return True
        return False

    async def _async_on_temperature_changed(self, event: Event):
        _LOGGER.debug("Temperature sensor updated")

        new_state = event.data.get("new_state")
        self._current_temp = float(new_state.state)
        await self.async_update()
        self.async_write_ha_state()

    def _on_heater_switch_changed(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        is_active = new_state.state == STATE_ON if new_state is not None else False

        if is_active != self._is_heater_active:
            _LOGGER.debug(
                "Heater switch changed and differs from current value, updating"
            )
            self._is_heater_active = is_active

    def _on_cooler_switch_changed(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        is_active = new_state.state == STATE_ON if new_state is not None else False

        if is_active != self._is_cooler_active:
            _LOGGER.debug(
                "Cooler switch changed and differs from current value, updating"
            )
            self._is_cooler_active = is_active

    def _on_opening_entity_changed(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        entity_id = event.data.get("entity_id")
        is_open = (
            new_state.state in [STATE_OPEN, STATE_ON]
            if new_state is not None
            else False
        )

        if self._current_opening_states.get(entity_id, False) != is_open:
            # If there's no delay on the openings or it's expired, create a new one
            if self._is_openings_value_locked is False:
                self._openings_locked_value = self._is_any_opening_open
                self._openings_lock_expiry = (
                    datetime.now(timezone.utc) + self._opening_delay
                )

            _LOGGER.debug("Opening %s changed to state %s", entity_id, is_open)

            self._current_opening_states[entity_id] = is_open
            self.async_write_ha_state()

    def _read_manual_settings(self, state: State) -> ClimateSettings:
        """Read the manually set values from the state into a ClimateSettings object."""
        temp_low: float | None = state.attributes.get(ATTR_MANUAL_TEMP_LOW)
        temp_high: float | None = state.attributes.get(ATTR_MANUAL_TEMP_HIGH)
        hvac_mode: HVACMode = state.attributes.get(
            ATTR_MANUAL_HVAC_MODE, self._default_hvac_mode
        )
        fan_mode: FanMode = state.attributes.get(
            ATTR_MANUAL_FAN_MODE, self._default_fan_mode
        )

        return (
            ClimateSettings(temp_low, temp_high, hvac_mode, fan_mode)
            if temp_low is not None and temp_high is not None
            else None
        )


class ClimateSettings:
    """Class to store current and preset thermostat settings."""

    temp_high: float
    temp_low: float
    hvac_mode: HVACMode
    fan_mode: FanMode

    def __init__(
        self,
        temp_low: float,
        temp_high: float,
        hvac_mode: HVACMode,
        fan_mode: FanMode | None,
    ) -> None:
        """Initialize an instance of the thermostat preset."""
        self.temp_high = temp_high
        self.temp_low = temp_low
        self.hvac_mode = hvac_mode
        self.fan_mode = fan_mode

    def clone(self) -> ClimateSettings:
        """Create a clone of the settings."""
        return ClimateSettings(
            self.temp_low, self.temp_high, self.hvac_mode, self.fan_mode
        )
