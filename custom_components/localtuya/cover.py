"""
Platform to locally control Tuya-based cover devices.

It is recommend to setup LocalTUya using the graphical configuration flow:
Configuration-->Integrations-->+-->LocalTuya

YAML may be used as an alternative setup method.

Sample config yaml:

cover:
- platform: localtuya #REQUIRED
  host: 192.168.0.123 #REQUIRED
  local_key: 1234567891234567 #REQUIRED
  device_id: 123456789123456789abcd #REQUIRED
  friendly_name: Cover guests #REQUIRED
  protocol_version: 3.3 #REQUIRED
  name: cover_guests #OPTIONAL
  open_cmd: open #OPTIONAL, default is 'on'
  close_cmd: close #OPTIONAL, default is 'off'
  stop_cmd: stop #OPTIONAL, default is 'stop'
  get_position: 3 #OPTIONAL, default is 0
  set_position: 2 #OPTIONAL, default is 0
  last_movement: 7 #OPTIONAL, default is 0
  id: 1 #OPTIONAL
  icon: mdi:blinds #OPTIONAL
"""
import logging
from time import time, sleep
from threading import Lock

import voluptuous as vol

from homeassistant.components.cover import (
    CoverEntity,
    DOMAIN,
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_STOP,
    SUPPORT_SET_POSITION,
    ATTR_POSITION
)
from homeassistant.const import (
    CONF_ID,
    CONF_FRIENDLY_NAME,
)
import homeassistant.helpers.config_validation as cv

from . import (
    BASE_PLATFORM_SCHEMA,
    LocalTuyaEntity,
    prepare_setup_entities,
    import_from_yaml,
)
from .const import (
    CONF_OPEN_CMD,
    CONF_CLOSE_CMD,
    CONF_STOP_CMD,
    CONF_GET_POSITION,
    CONF_SET_POSITION,
    CONF_LAST_MOVEMENT
)

from .pytuya import TuyaDevice

_LOGGER = logging.getLogger(__name__)

DEFAULT_OPEN_CMD = "open"
DEFAULT_CLOSE_CMD = "close"
DEFAULT_STOP_CMD = "stop"
DEFAULT_SET_POSITION = 0
DEFAULT_GET_POSITION = 0
DEFAULT_LAST_MOVEMENT = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(BASE_PLATFORM_SCHEMA).extend(
    {
        vol.Optional(CONF_OPEN_CMD, default=DEFAULT_OPEN_CMD): cv.string,
        vol.Optional(CONF_CLOSE_CMD, default=DEFAULT_CLOSE_CMD): cv.string,
        vol.Optional(CONF_STOP_CMD, default=DEFAULT_STOP_CMD): cv.string,
        vol.Optional(CONF_SET_POSITION, default=DEFAULT_SET_POSITION): cv.positive_int,
        vol.Optional(CONF_GET_POSITION, default=DEFAULT_GET_POSITION): cv.positive_int,
        vol.Optional(CONF_LAST_MOVEMENT, default=DEFAULT_LAST_MOVEMENT): cv.positive_int,
    }
)


def flow_schema(dps):
    """Return schema used in config flow."""
    return {
            vol.Optional(CONF_OPEN_CMD, default=DEFAULT_OPEN_CMD): str,
            vol.Optional(CONF_CLOSE_CMD, default=DEFAULT_CLOSE_CMD): str,
            vol.Optional(CONF_STOP_CMD, default=DEFAULT_STOP_CMD): str,
            vol.Optional(CONF_SET_POSITION, default=DEFAULT_SET_POSITION): cv.positive_int,
            vol.Optional(CONF_GET_POSITION, default=DEFAULT_GET_POSITION): cv.positive_int,
            vol.Optional(CONF_LAST_MOVEMENT, default=DEFAULT_LAST_MOVEMENT): cv.positive_int,    
        }


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Setup a Tuya cover based on a config entry."""
    device, entities_to_setup = prepare_setup_entities(
        config_entry, DOMAIN
    )
    if not entities_to_setup:
        return

    covers = []
    for device_config in entities_to_setup:
        covers.append(
            LocaltuyaCover(
                TuyaCache(device, config_entry.data[CONF_FRIENDLY_NAME]),
                config_entry,
                device_config[CONF_ID],
            )
        )

    async_add_entities(covers, True)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up of the Tuya cover."""
    return import_from_yaml(hass, config, DOMAIN)


class TuyaCache:
    """Cache wrapper for pytuya.TuyaDevice"""

    def __init__(self, device, friendly_name):
        _LOGGER.info("initiating TuyaCache")
        """Initialize the cache."""
        self._cached_status = ""
        self._cached_status_time = 0
        self._device = device
        self._friendly_name = friendly_name
        self._lock = Lock()

    @property
    def unique_id(self):
        """Return unique device identifier."""
        return self._device.id

    def __get_status(self):
        for i in range(5):
            try:
                status = self._device.status()
                return status
            except Exception:
                print(
                    "Failed to update status of device [{}]".format(
                        self._device.address
                    )
                )
                sleep(1.0)
                if i + 1 == 3:
                    _LOGGER.error(
                        "Failed to update status of device %s", self._device.address
                    )
                    raise ConnectionError("Failed to update status .")

    def set_dps(self, value, dps_index):
        _LOGGER.debug("set_dps where value=%s dps_index=%s", value, dps_index)
        """Change the Tuya cover status and clear the cache."""
        self._cached_status = ""
        self._cached_status_time = 0
        for i in range(5):
            try:
                return self._device.set_dps(value, dps_index)
            except Exception:
                print(
                    "Failed to set status of device [{}]".format(self._device.address)
                )
                if i + 1 == 3:
                    _LOGGER.error(
                        "Failed to set status of device %s", self._device.address
                    )
                    return
        self.update()

    def status(self):
        """Get state of Tuya cover and cache the results."""
        self._lock.acquire()
        try:
            now = time()
            if not self._cached_status or now - self._cached_status_time > 15:
                sleep(0.5)
                self._cached_status = self.__get_status()
                self._cached_status_time = time()
            return self._cached_status
        finally:
            self._lock.release()

class LocaltuyaCover(LocalTuyaEntity, CoverEntity):
    """Tuya cover devices."""

    def __init__(
        self,
        device,
        config_entry,
        coverid,
        **kwargs,
    ):
        super().__init__(device, config_entry, coverid, **kwargs)
        self._position = None
        self._current_cover_position = None
        self._last_movement = None
        self._last_position_set = None
        self._last_command = None
        print(
            "Initialized tuya cover  [{}] with switch status [{}]".format(
                self.name, self._status
            )
        )

    @property
    def is_closed(self):
        """Check if the cover is fully closed."""
        return self._current_cover_position == 100

    def status_updated(self):
        """Device status was updated."""
        _LOGGER.info("status_updated called ")
        _LOGGER.info("self._config=%s", self._config)
        _LOGGER.info("self._config_entry=%s", self._config_entry)
        _LOGGER.info("CONF_LAST_MOV=%s CONF_SET_POS=%s CONF_GET_POS=%s self._dps_id=%s", CONF_LAST_MOVEMENT, CONF_SET_POSITION, CONF_GET_POSITION, self._dps_id)
        self.dps("7")
        _LOGGER.info("self.dps(7)=%s", self.dps("7"))
        self._last_movement = self.dps(str(self._config.get(CONF_LAST_MOVEMENT)))
        _LOGGER.info("last_movement set to =%s", self._last_movement)
        self._last_position = self.dps(str(self._config.get(CONF_SET_POSITION)))
        _LOGGER.info("last_position_set set to =%s", self._last_position_set)
        self._current_cover_position = self.dps(str(self._config.get(CONF_GET_POSITION)))
        _LOGGER.info("current_cover_position set to =%s", self._current_cover_position)
        self._last_command = self.dps(str(self._dps_id))
        _LOGGER.info("last_command set to =%s", self._last_command)

    @property
    def current_cover_position(self):
        """Return position of Tuya cover."""
        return self._current_cover_position 

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION     
        #TODO set supported features dynamically based on config or yaml input

    def set_cover_position(self, **kwargs):
        """Set the cover to a specific position from 0-100"""
        if ATTR_POSITION in kwargs:
            converted_position = int(kwargs[ATTR_POSITION])
            if converted_position in range(0,101):
                _LOGGER.debug("set_cover_position about to set position to =%s", converted_position)
                self._device.set_dps(converted_position, self._config[CONF_SET_POSITION])
            else:
                _LOGGER.warning("set_position given number outside range")

    def open_cover(self, **kwargs):
        """Open the cover."""
        self._device.set_dps(self._config[CONF_OPEN_CMD], self._dps_id)

    def close_cover(self, **kwargs):
        """Close cover."""
        self._device.set_dps(self._config[CONF_CLOSE_CMD], self._dps_id)

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._device.set_dps(self._config[CONF_STOP_CMD], self._dps_id)