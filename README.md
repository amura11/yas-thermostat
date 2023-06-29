# Yet Another Smart Thermostat for HomeAssistant
[![GitHub Release][releases-shield]][releases]
[![HACS Validation][validation-shield]](validation)
[![hacs][hacsbadge]][hacs]

[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

A simple dual range smart thermostat integration for controlling siwtch entities based on a single temperature sensor. Instead of relying on an existing climate entity this integration allows the user to use any temperature sensor as an input and any switch entities for the output. This allows for greater freedom of control over your devices. This integration isn't meant to handle every possible scenario, instead handle a specific set of scenarios very well. It supports the following features:
 - Dual range temperature contol
 - Unlimited custom presets
 - Heater, cooler, and fan control
 - Compatability with existing thermostat card controls

## Basic Configuration Options

 Name | Key | Description | Required | Default
-- | -- | -- | -- | --
Name | `name` | The name of the entity | ✔ |
Temperature Sensor | `temp_sensor` | The sensor to use as the current temperature. | ✔ |
Heater Switch ID* | `heater_switch` | The ID of the switch entity to toggle when heating is needed. |
Cooler Switch ID* | `cooler_switch` | The ID of the switch entity to toggle when cooling is needed. |
Fan Switch ID* | `fan_switch` | The ID of the switch entity to toggle when the fan is needed. |
Opening Entity IDs | `openings` | The list of IDs for openings such as windows and doors. When one of these is in an active state all heating/cooling/fan operations will be stopped. | | `null`
Preset List** | `preset_modes` | This list of presets that are available to the component. | ✔ |
Default Preset | `default_preset` | The name of the default preset to use when initializing the component. This value is also used when a preset fails to be read from the previous state. | | The first preset in the list
Cycle Delay | `cycle_delay` | The minimum ammount of time to wait after the heating/cooling state has been changed before it can be changed again. | | 5 Minutes
Opening Delay | `opening_delay` | The ammount of time to wait after an opening has changed state to change the heating/cooling state. This ensures that an opening that is only opened for a small period of time doesn't change the heating/cooling state. | | 30 Seconds
Temperature Step | `temp_step` | The ammount the temperature will increase/decrease in a single step. | | 1.0
Temperature Tolerance | `temp_tolerance` | The difference from the target temperature required to start an HVAC cycle. | | 0.7
Temperature Max | `max_temp` | The maximum temperature the thermostat can be set to. | | 35
Temperature Min | `min_temp` | The minimum temperature the thermostat can be set to. | | 7
Default HVAC Mode | `default_hvac_mode` | The default HVAC mode to use for a preset if it is not set. | | `OFF`
Default Fan Mode | `default_fan_mode` | The default fan mode to use for a preset if it is not set. | | `OFF`

\* At least one of these entities is required, the rest can be omitted if they aren't needed

\*\* At least one preset must be defined

## Preset Configuration Options
 Name | Key | Description | Required | Default
-- | -- | -- | -- | --
Name | `name` | The name of the preset | ✔ |
Target High Temperature | `target_temp_high` | The target temperature range upper bound. | ✔ |
Target Low Temperature | `target_temp_low` | The target temperature range lower bound. | ✔ |
HVAC Mode | `hvac_mode` | The HVAC mode to set for the preset. | | `OFF`*
Fan Mode | `fan_mode` | The fan mode to set for the preset. | | `OFF`*

\* The default value can be changed in the main configuration, `OFF` is the default default

## Full Configuration Example
```
  - platform: yas_thermostat
    name: My Thermostat
    temp_sensor: input_number.fake_temp
    heater_switch: input_boolean.fake_heater
    cooler_switch: input_boolean.fake_cooler
    fan_switch: input_boolean.fake_fan
    openings: [input_boolean.fake_opening_1, input_boolean.fake_opening_2]
    default_preset: Preset2
    cycle_delay: 00:10:00
    opening_delay: 00:00:15
    temp_step: 0.1
    temp_tolerance: 0.5
    max_temp: 32
    min_temp: 15
    default_hvac_mode: heat_cool
    default_fan_mode: auto
    preset_modes:
    - name: Preset1
      target_temp_low: 10.123
      target_temp_high: 20.455
      fan_mode: "off"
      hvac_mode: heat
    - name: Preset2
      target_temp_low: 10.123
      target_temp_high: 20.455
```

[releases-shield]: https://img.shields.io/github/release/amura11/yas-thermostat.svg?style=for-the-badge
[releases]: https://github.com/amura11/yas-thermostat/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/amura11/yas-thermostat.svg?style=for-the-badge
[commits]: https://github.com/amura11/yas-thermostat/commits/main
[license-shield]: https://img.shields.io/github/license/amura11/yas-thermostat.svg?style=for-the-badge
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[validation-shield]: https://img.shields.io/github/actions/workflow/status/amura11/yas-thermostat/validate.yml?style=for-the-badge&label=HACS%20Validation
[validation]: https://github.com/amura11/yas-thermostat/actions/workflows/validate.yml