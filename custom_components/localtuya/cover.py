"""
Simple platform to locally control Tuya-based cover devices.
Connects to devices using pytuya/tinytuya.

Sample config yaml:

cover:
  - platform: localtuya #REQUIRED
    host: 192.168.0.123 #REQUIRED
    local_key: 1234567891234567 #REQUIRED
    device_id: 123456789123456789abcd #REQUIRED
    name: cover_guests #REQUIRED
    friendly_name: Cover guests #REQUIRED
    protocol_version: 3.3 #REQUIRED
    id: 1 #OPTIONAL
    icon: mdi:blinds #OPTIONAL
    open_cmd: open #OPTIONAL, default is 'on'
    close_cmd: close #OPTIONAL, default is 'off'
    stop_cmd: stop #OPTIONAL, default is 'stop'


"""
import socket
import logging
from time import time, sleep
from threading import Lock

import voluptuous as vol

from homeassistant.components.cover import (
    CoverEntity,
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_STOP,
    SUPPORT_SET_POSITION,
    ATTR_POSITION,
)

from homeassistant.const import (
#    CONF_HOST,
    CONF_ID,
#    CONF_ENTITIES,
#    CONF_COVERS,
#    CONF_DEVICE_ID,
    CONF_FRIENDLY_NAME,
#    CONF_ICON,
#    CONF_NAME,
#    CONF_PLATFORM,
)

import homeassistant.helpers.config_validation as cv


from . import BASE_PLATFORM_SCHEMA, prepare_setup_entities, import_from_yaml
from .const import CONF_OPEN_CMD, CONF_CLOSE_CMD, CONF_STOP_CMD, CONF_GET_POSITION_KEY, CONF_SET_POSITION_KEY, CONF_COVER_COMMAND_KEY
from .pytuya import CoverDevice
from .config_flow import *

_LOGGER = logging.getLogger(__name__)

DEFAULT_OPEN_CMD = "On"
DEFAULT_CLOSE_CMD = "Off"
DEFAULT_STOP_CMD = "Stop"
DEFAULT_SET_POSITION_KEY = 0
DEFAULT_GET_POSITION_KEY = 0
DEFAULT_COVER_COMMAND_KEY = 0


MIN_POSITION = 0
MAX_POSITION = 100
UPDATE_RETRY_LIMIT = 3

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(BASE_PLATFORM_SCHEMA).extend(
    {
        vol.Required(CONF_COVER_COMMAND_KEY, default=DEFAULT_COVER_COMMAND_KEY): cv.positive_int, # Need to modify to validate against vol.In(dps_strings), 
        vol.Required(CONF_SET_POSITION_KEY, default=DEFAULT_SET_POSITION_KEY): cv.positive_int, # Need to modify to validate against vol.In(dps_strings), 
        vol.Required(CONF_GET_POSITION_KEY, default=DEFAULT_GET_POSITION_KEY): cv.positive_int, # Need to modify to validate against vol.In(dps_strings),
        vol.Optional(CONF_OPEN_CMD, default=DEFAULT_OPEN_CMD): cv.string,
        vol.Optional(CONF_CLOSE_CMD, default=DEFAULT_CLOSE_CMD): cv.string,
        vol.Optional(CONF_STOP_CMD, default=DEFAULT_STOP_CMD): cv.string,
    }
)

def flow_schema(dps):
    """Return schema used in config flow."""
    return {
        vol.Required(CONF_COVER_COMMAND_KEY, default=DEFAULT_COVER_COMMAND_KEY): cv.positive_int,
        vol.Required(CONF_SET_POSITION_KEY, default=DEFAULT_SET_POSITION_KEY): cv.positive_int,
        vol.Required(CONF_GET_POSITION_KEY, default=DEFAULT_GET_POSITION_KEY): cv.positive_int,  
        vol.Optional(CONF_OPEN_CMD, default=DEFAULT_OPEN_CMD): str,
        vol.Optional(CONF_CLOSE_CMD, default=DEFAULT_CLOSE_CMD): str,
        vol.Optional(CONF_STOP_CMD, default=DEFAULT_STOP_CMD): str,
    }


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Setup a Tuya cover based on a config entry."""
    device, entities_to_setup = prepare_setup_entities(
        config_entry, "cover", CoverDevice
    )
    if not entities_to_setup:
        return

    # TODO: keeping for now but should be removed
    dps = {}
    dps["101"] = None
    dps["102"] = None

    covers = []
    for device_config in entities_to_setup:
        dps[device_config[CONF_ID]] = None
        covers.append(
            TuyaDevice(
                TuyaCoverCache(device),
                device_config[CONF_FRIENDLY_NAME],
                device_config[CONF_ID],
                device_config.get(CONF_OPEN_CMD),
                device_config.get(CONF_CLOSE_CMD),
                device_config.get(CONF_STOP_CMD),
            )
        )

    device.set_dpsUsed(dps)
    async_add_entities(covers, True)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up of the Tuya cover."""
    return import_from_yaml(hass, config, "cover")


class TuyaCache:
    """Cache wrapper for pytuya.CoverDevice"""

    def __init__(self, device):
        """Initialize the cache."""
        self._cached_status = ""
        self._cached_status_time = 0
        self._device = device
        self._lock = Lock()

    @property
    def unique_id(self):
        """Return unique device identifier."""
        return self._device.id

    def __get_status(self):
        for _ in range(UPDATE_RETRY_LIMIT):
            try:
                return self._device.status() # ["dps"][coverid]
            except (ConnectionError, socket.timeout):
                pass
        _LOGGER.warning("Failed to get status after %d tries", UPDATE_RETRY_LIMIT)

    def set_status(self, state, coverid):
        """Change the Tuya cover status and clear the cache."""
        self._cached_status = ""
        self._cached_status_time = 0
        for _ in range(UPDATE_RETRY_LIMIT):
            try:
                return self._device.set_status(state, coverid)
            except (ConnectionError, socket.timeout):
                pass
        _LOGGER.warning("Failed to set status after %d tries", UPDATE_RETRY_LIMIT)

    def status(self, coverid):
        """Get state of Tuya cover and cache the results."""
        with self._lock:
            now = time()
            if not self._cached_status or now - self._cached_status_time > 30:
                sleep(0.5)
                self._cached_status = self.__get_status()
                self._cached_status_time = time()
            return self._cached_status

    def set_value (self, index, value):
        """Set a specific value to a specific index to the Tuya device and clear the cache."""
        self._cached_status = ""
        self._cached_status_time = 0
        for i in range(UPDATE_RETRY_LIMIT):
            try:
                return self._device.set_value(index, value)
            except (ConnectionError, socket.timeout):
                pass
        _LOGGER.warning("Failed to set value after %d tries", UPDATE_RETRY_LIMIT)


    # def cached_status(self):
    #     return self._cached_status

    # def support_open(self):
    #     return self._device.support_open()

    # def support_close(self):
    #     return self._device.support_close()

    # def support_stop(self):
    #     return self._device.support_stop()

    # def support_set_position(self):
    #     return self._device.support_set_position()

    # def last_movement(self):
    #     return self._device.last_movement()

    # def is_open(self):
    #     return self._device.is_open()

    # def position(self):
    #     for _ in range(UPDATE_RETRY_LIMIT):
    #         try:
    #             return self._device.position()
    #         except (ConnectionError, socket.timeout):
    #             pass
    #         except KeyError:
    #             return "999"
    #     _LOGGER.warning("Failed to get position after %d tries", UPDATE_RETRY_LIMIT)


    # def set_position(self, position):
    #     for _ in range(UPDATE_RETRY_LIMIT):
    #         try:
    #             return self._device.set_position(position)
    #         except (ConnectionError, KeyError, socket.timeout):
    #             pass
    #     _LOGGER.warning("Failed to set position after %d tries", UPDATE_RETRY_LIMIT)

    # def state(self):
    #     self._device.state()

    # def open_cover(self):
    #     self._device.open_cover() 

    # def close_cover(self):
    #     self._device.close_cover() 

    # def stop_cover(self):
    #     self._device.stop_cover() 


class TuyaDevice(CoverEntity):
    """Representation of a Tuya Cover."""

    def __init__(self, device, friendly_name, coverid, open_cmd, close_cmd, stop_cmd, get_position_key, set_position_key, cover_command_key):
        """Initialize the Tuya cover."""
        self._device = device
        _LOGGER.info("from class TuyaDevice(CoverEntity), self._device was set to=%s", self._device)
        self._available = False
        _LOGGER.info("from class TuyaDevice(CoverEntity), self._available was set to=%s", self._available)
        self._name = friendly_name
        _LOGGER.info("from class TuyaDevice(CoverEntity), self._name was set to=%s", self._name)
        self.cover_id = coverid
        self._status = None
        self._state = None
        self._position = 50
        self._open_cmd = open_cmd
        self._close_cmd = close_cmd
        self._stop_cmd = stop_cmd
        self._get_position_key = get_position_key
        self._set_position_key = set_position_key
        self._cover_commandkey = cover_command_key
        _LOGGER.info("Initialized tuya cover [%s] with switch status [%s] and state [%s]", self._name, self._status, self._state)


    @property
    def name(self):
        """Get name of Tuya device."""
        return self._name

    @property
    def open_cmd(self):
        """Get name of open command."""
        return self._open_cmd

    @property
    def close_cmd(self):
        """Get name of close command."""
        return self._close_cmd

    @property
    def stop_cmd(self):
        """Get name of stop command."""
        return self._stop_cmd


    @property
    def unique_id(self):
        """Return unique device identifier."""
        return f"local_{self._device.unique_id}"

    @property
    def available(self):
        """Return if device is available or not."""
        return self._available

    @property
    def last_movement(self):
        """Return the last movement of the device (should be "Opening" or "Closing")"""
        return self._last_movement

    @property
    def is_open(self):
        """Check if the cover is partially or fully open."""
        is_open = self._state
        if is_open == 'Open':
            return True
        return False

    @property
    def is_closed(self):
        """Check if the cover is fully closed."""
        is_closed = self._state
        if is_closed == 'Closed':
            return True
        return False

    def update(self):
        """Update cover attributes."""
        try:
            self._update_state()
            self._update_last_movement() # FIXME Do I need this function call here?
            self._update_position()      # FIXME Do I need this function call here?
        except:
            self._available = False
        else:
            self._available = True

    def _update_state(self):
        # // FIXME - what if their open and closed position are inverted (position 100=fully open, position 0=fully closed)
        status = self._device.status(self._cover_id) 
        self._state = status
        try:
            position = int(self._device.position())
            _LOGGER.info("_update_state set position=%s", position)
            if position == 100:
                self._state = "Closed"
            else:
                self._state = "Open"
        except TypeError:
            _LOGGER.warning("TypeError from _update_state, about to pass")
            pass

    def _update_position(self): # FIXME Do I need this function?
        position = self._device.position(self._cover_id) 
        self._position = position

    def _update_last_movement(self): # FIXME Do I need this function?
        last_movement = self._device.last_movement(self._cover_id) 
        self._last_movement = last_movement

    @property
    def position(self):
        """Return position of Tuya cover."""
        return self._position 

    @property
    def current_cover_position(self):
        """Return position of Tuya cover."""
        return self._position 

    @property
    def min_position(self):
        """Return minimum position of Tuya cover."""
        return MIN_POSITION

    @property
    def max_position(self):
        """Return maximum position of Tuya cover."""
        return MAX_POSITION 


    @property
    def unique_id(self):
        """Return unique device identifier."""
        return f"local_{self._device.unique_id}"

    @property
    def available(self):
        """Return if device is available or not."""
        _LOGGER.info("def available(self) called, =%s", self._available)
        return self._available

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION
        return supported_features

    @property
    def is_opening(self):
        last_movement = self._last_movement();
        if last_movement == 'Opening':
            return True
        return False

    @property
    def is_closing(self):
        last_movement = self._last_movement();
        if last_movement == 'Closing':
            return True
        return False


    def set_position(self, **kwargs): # FIXME Make sure init is being passed set position DPS key
        """Set the cover to a specific position from 0-100"""
        _LOGGER.debug("Setting position, state: %s", self._device.cached_status())
        if ATTR_POSITION in kwargs:
            converted_position = int(kwargs[ATTR_POSITION])
            if converted_position in range(0,101):
                self._device.set_value(converted_position) # FIXME, make sure this is getting the set position key from setup/config
            else:
                _LOGGER.warning("set_position given number outside range")


    def open_cover(self, **kwargs):
        """Open the cover."""
        self._device.open_cover() # FIXME Make sure init is being passed open_cmd and open/close/stop dps key


    def close_cover(self, **kwargs):
        """Close the cover."""
        self._device.close_cover() # FIXME Make sure init is being passed close_cmd and open/close/stop dps key

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._device.stop_cover() # FIXME Make sure init is being passed stop_cmd and open/close/stop dps key

