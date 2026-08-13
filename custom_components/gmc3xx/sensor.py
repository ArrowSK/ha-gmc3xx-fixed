"""Sensor entities for GMC3xx Radiation Monitor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GMCDataUpdateCoordinator
from .gmc_protocol import GMCSample


@dataclass(frozen=True, kw_only=True)
class GMCDescription:
    key: str
    name: str
    value_fn: Callable[[GMCSample], Any]
    native_unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT


CORE_SENSORS = (
    GMCDescription(key="cpm", name="GMC3xx CPM", value_fn=lambda data: data.cpm, native_unit="CPM"),
    GMCDescription(
        key="voltage", name="GMC3xx Voltage", value_fn=lambda data: data.volt,
        native_unit=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE,
    ),
)
DIAGNOSTIC_MODEL_SENSORS = (
    GMCDescription(
        key="temperature", name="GMC3xx Temperature", value_fn=lambda data: data.temp,
        native_unit=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE,
    ),
    GMCDescription(key="gyro_x", name="GMC3xx Gyroscope X", value_fn=lambda data: data.x),
    GMCDescription(key="gyro_y", name="GMC3xx Gyroscope Y", value_fn=lambda data: data.y),
    GMCDescription(key="gyro_z", name="GMC3xx Gyroscope Z", value_fn=lambda data: data.z),
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GMCDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    descriptions = list(CORE_SENSORS)
    if coordinator.identity is not None and coordinator.identity.has_320_diagnostics:
        descriptions.extend(DIAGNOSTIC_MODEL_SENSORS)
    async_add_entities(GMC3xxSensor(coordinator, description) for description in descriptions)


class GMC3xxSensor(CoordinatorEntity[GMCDataUpdateCoordinator], SensorEntity):
    _attr_has_entity_name = False

    def __init__(self, coordinator: GMCDataUpdateCoordinator, description: GMCDescription) -> None:
        super().__init__(coordinator)
        self._description = description
        self._attr_unique_id = f"{coordinator.expected_serial}_{description.key}"
        self._attr_name = description.name
        self._attr_native_unit_of_measurement = description.native_unit
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class

    @property
    def native_value(self):
        return self._description.value_fn(self.coordinator.data)

    @property
    def device_info(self) -> DeviceInfo:
        identity = self.coordinator.identity
        version = identity.version if identity else "GMC3xx"
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.expected_serial)},
            name="GMC3xx Radiation Monitor",
            manufacturer="GQ Electronics",
            model=version.split()[0],
            sw_version=version,
        )
