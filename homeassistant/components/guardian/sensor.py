"""Sensors for the Elexa Guardian integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_FAHRENHEIT,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PairedSensorEntity, ValveControllerEntity
from .const import (
    API_SYSTEM_DIAGNOSTICS,
    API_SYSTEM_ONBOARD_SENSOR_STATUS,
    CONF_UID,
    DATA_COORDINATOR,
    DATA_COORDINATOR_PAIRED_SENSOR,
    DATA_UNSUB_DISPATCHER_CONNECT,
    DOMAIN,
    SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED,
)

SENSOR_KIND_BATTERY = "battery"
SENSOR_KIND_TEMPERATURE = "temperature"
SENSOR_KIND_UPTIME = "uptime"

SENSOR_ATTRS_MAP = {
    SENSOR_KIND_BATTERY: ("Battery", DEVICE_CLASS_BATTERY, None, PERCENTAGE),
    SENSOR_KIND_TEMPERATURE: (
        "Temperature",
        DEVICE_CLASS_TEMPERATURE,
        None,
        TEMP_FAHRENHEIT,
    ),
    SENSOR_KIND_UPTIME: ("Uptime", None, "mdi:timer", TIME_MINUTES),
}

PAIRED_SENSOR_SENSORS = [SENSOR_KIND_BATTERY, SENSOR_KIND_TEMPERATURE]
VALVE_CONTROLLER_SENSORS = [SENSOR_KIND_TEMPERATURE, SENSOR_KIND_UPTIME]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Guardian switches based on a config entry."""

    @callback
    def add_new_paired_sensor(uid: str) -> None:
        """Add a new paired sensor."""
        coordinator = hass.data[DOMAIN][DATA_COORDINATOR_PAIRED_SENSOR][entry.entry_id][
            uid
        ]

        entities = []
        for kind in PAIRED_SENSOR_SENSORS:
            name, device_class, icon, unit = SENSOR_ATTRS_MAP[kind]
            entities.append(
                PairedSensorSensor(
                    entry, coordinator, kind, name, device_class, icon, unit
                )
            )

        async_add_entities(entities, True)

    # Handle adding paired sensors after HASS startup:
    hass.data[DOMAIN][DATA_UNSUB_DISPATCHER_CONNECT][entry.entry_id].append(
        async_dispatcher_connect(
            hass,
            SIGNAL_PAIRED_SENSOR_COORDINATOR_ADDED.format(entry.data[CONF_UID]),
            add_new_paired_sensor,
        )
    )

    sensors: list[PairedSensorSensor | ValveControllerSensor] = []

    # Add all valve controller-specific binary sensors:
    for kind in VALVE_CONTROLLER_SENSORS:
        name, device_class, icon, unit = SENSOR_ATTRS_MAP[kind]
        sensors.append(
            ValveControllerSensor(
                entry,
                hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id],
                kind,
                name,
                device_class,
                icon,
                unit,
            )
        )

    # Add all paired sensor-specific binary sensors:
    for coordinator in hass.data[DOMAIN][DATA_COORDINATOR_PAIRED_SENSOR][
        entry.entry_id
    ].values():
        for kind in PAIRED_SENSOR_SENSORS:
            name, device_class, icon, unit = SENSOR_ATTRS_MAP[kind]
            sensors.append(
                PairedSensorSensor(
                    entry, coordinator, kind, name, device_class, icon, unit
                )
            )

    async_add_entities(sensors)


class PairedSensorSensor(PairedSensorEntity, SensorEntity):
    """Define a binary sensor related to a Guardian valve controller."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        kind: str,
        name: str,
        device_class: str | None,
        icon: str | None,
        unit: str | None,
    ) -> None:
        """Initialize."""
        super().__init__(entry, coordinator, kind, name, device_class, icon)

        self._attr_native_unit_of_measurement = unit

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        if self._kind == SENSOR_KIND_BATTERY:
            self._attr_native_value = self.coordinator.data["battery"]
        elif self._kind == SENSOR_KIND_TEMPERATURE:
            self._attr_native_value = self.coordinator.data["temperature"]


class ValveControllerSensor(ValveControllerEntity, SensorEntity):
    """Define a generic Guardian sensor."""

    def __init__(
        self,
        entry: ConfigEntry,
        coordinators: dict[str, DataUpdateCoordinator],
        kind: str,
        name: str,
        device_class: str | None,
        icon: str | None,
        unit: str | None,
    ) -> None:
        """Initialize."""
        super().__init__(entry, coordinators, kind, name, device_class, icon)

        self._attr_native_unit_of_measurement = unit

    async def _async_continue_entity_setup(self) -> None:
        """Register API interest (and related tasks) when the entity is added."""
        if self._kind == SENSOR_KIND_TEMPERATURE:
            self.async_add_coordinator_update_listener(API_SYSTEM_ONBOARD_SENSOR_STATUS)

    @callback
    def _async_update_from_latest_data(self) -> None:
        """Update the entity."""
        if self._kind == SENSOR_KIND_TEMPERATURE:
            self._attr_available = self.coordinators[
                API_SYSTEM_ONBOARD_SENSOR_STATUS
            ].last_update_success
            self._attr_native_value = self.coordinators[
                API_SYSTEM_ONBOARD_SENSOR_STATUS
            ].data["temperature"]
        elif self._kind == SENSOR_KIND_UPTIME:
            self._attr_available = self.coordinators[
                API_SYSTEM_DIAGNOSTICS
            ].last_update_success
            self._attr_native_value = self.coordinators[API_SYSTEM_DIAGNOSTICS].data[
                "uptime"
            ]
