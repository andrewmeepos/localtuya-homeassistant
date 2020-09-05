"""
Simple platform to locally control Tuya-based cover devices.

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
    get_position_key: 3 #OPTIONAL, default is '0'

"""
import logging
import requests

import voluptuous as vol

from homeassistant.components.cover import (
    CoverEntity,
    PLATFORM_SCHEMA,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_STOP,
    SUPPORT_SET_POSITION,
)

"""from . import DATA_TUYA, TuyaDevice"""
from homeassistant.components.cover import CoverEntity, PLATFORM_SCHEMA
from homeassistant.const import (CONF_HOST, CONF_ID, CONF_FRIENDLY_NAME, CONF_ICON, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from time import time, sleep
from threading import Lock

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'localtuyacover'

REQUIREMENTS = ['pytuya==7.0.9']

CONF_DEVICE_ID = 'device_id'
CONF_LOCAL_KEY = 'local_key'
CONF_PROTOCOL_VERSION = 'protocol_version'

CONF_OPEN_CMD = 'open_cmd'
CONF_CLOSE_CMD = 'close_cmd'
CONF_STOP_CMD = 'stop_cmd'
CONF_GET_POSITION_KEY = 'get_position_key'

DEFAULT_ID = '1'
DEFAULT_PROTOCOL_VERSION = 3.3
DEFAULT_OPEN_CMD = 'on'
DEFAULT_CLOSE_CMD = 'off'
DEFAULT_STOP_CMD = 'stop'
DEFAULT_GET_POSITION_KEY = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ICON): cv.icon,
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Required(CONF_LOCAL_KEY): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_FRIENDLY_NAME): cv.string,
    vol.Required(CONF_PROTOCOL_VERSION, default=DEFAULT_PROTOCOL_VERSION): vol.Coerce(float),
    vol.Optional(CONF_ID, default=DEFAULT_ID): cv.string,
    vol.Optional(CONF_OPEN_CMD, default=DEFAULT_OPEN_CMD): cv.string,
    vol.Optional(CONF_CLOSE_CMD, default=DEFAULT_CLOSE_CMD): cv.string,
    vol.Optional(CONF_STOP_CMD, default=DEFAULT_STOP_CMD): cv.string,
    vol.Optional(CONF_GET_POSITION_KEY, default=DEFAULT_GET_POSITION_KEY): cv.positive_int,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Tuya cover devices."""
    from . import pytuya

    _LOGGER.info("running def setup_platform from cover.py")
    _LOGGER.info("conf_open_cmd= %s, conf_close_cmd=%s, conf_stop_cmd=%s, conf_get_position_key=%s", config.get(CONF_OPEN_CMD), config.get(CONF_CLOSE_CMD), config.get(CONF_STOP_CMD), config.get(CONF_GET_POSITION_KEY))


   # _LOGGER.info("conf_close_cmd is %s",config.get(CONF_CLOSE_CMD))
   # _LOGGER.info("conf_STOP_cmd is %s", config.get(CONF_STOP_CMD))
   # _LOGGER.info("setting up blank covers array - covers = [] ")
    covers = []
    pytuyadevice = pytuya.CoverEntity(config.get(CONF_DEVICE_ID), config.get(CONF_HOST), config.get(CONF_LOCAL_KEY))
    _LOGGER.info("defined pytuyadevice = pytuya.CoverEntity --> %s", pytuyadevice)
    pytuyadevice.set_version(float(config.get(CONF_PROTOCOL_VERSION)))
   # _LOGGER.info("setting blank dps = {}")
    dps = {}
    dps[config.get(CONF_ID)]=None
   # dps["101"]=None
   # dps["102"]=None
   # _LOGGER.info("about to pytuyadevice.set_dpsUsed(dps) where dps = %s", dps)
    pytuyadevice.set_dpsUsed(dps)

    cover_device = TuyaCoverCache(pytuyadevice)
    covers.append(
            TuyaDevice(
                cover_device,
                config.get(CONF_NAME),
                config.get(CONF_FRIENDLY_NAME),
                config.get(CONF_ICON),
                config.get(CONF_ID),
                config.get(CONF_OPEN_CMD),
                config.get(CONF_CLOSE_CMD),
                config.get(CONF_STOP_CMD),
                config.get(CONF_GET_POSITION_KEY),
            )
	)
    print('Setup localtuya cover [{}] with device ID [{}] '.format(config.get(CONF_FRIENDLY_NAME), config.get(CONF_ID)))
    _LOGGER.info("covers.appended TuyaDevice where -->   name=%s | friendly_name=%s |  ID=%s |  open_cmd=%s | close_cmd=%s | stop_cmd=%s | get_position_key=%s", config.get(CONF_NAME), config.get(CONF_FRIENDLY_NAME), config.get(CONF_ID), config.get(CONF_OPEN_CMD), config.get(CONF_CLOSE_CMD), config.get(CONF_STOP_CMD), config.get(CONF_GET_POSITION_KEY) )
    _LOGGER.info("about to add_entities of covers --> covers=%s", covers)
    add_entities(covers, True)


class TuyaCoverCache:
    """Cache wrapper for pytuya.CoverEntity"""

    def __init__(self, device):
        """Initialize the cache."""
        self._cached_status = ''
        self._cached_status_time = 0
        self._device = device
        self._lock = Lock()

    @property
    def unique_id(self):
       # _LOGGER.info("def unique_id called")
        """Return unique device identifier."""
        return self._device.id

    def __get_status(self):
       # _LOGGER.info("running def __get_status from cover")
        for i in range(5):
            try:
                _LOGGER.info("running def __get_status from cover.py where try=%s", i)
                status = self._device.status()
                _LOGGER.info("status=%s", status)
                return status
            except Exception:
                print('Failed to update status of device [{}]'.format(self._device.address))
                _LOGGER.info("Failed to update status, sleeping for 1 second")
                sleep(1.0)
                if i+1 == 3:
                    _LOGGER.error("Failed to update status of device %s where i+1==3 , returning none and raising ConnectionError", self._device.address )
#                    return None
                    raise ConnectionError("Failed to update status .")

    def set_status(self, state, switchid):
        _LOGGER.info("running def set_status from cover")
        """Change the Tuya switch status and clear the cache."""
        self._cached_status = ''
        self._cached_status_time = 0
        for i in range(5):
            try:
                _LOGGER.info("Running try %s from def set_status from cover where state=%s and switchid=%s", i,  state, switchid)
                return self._device.set_status(state, switchid)
            except Exception:
                print('Failed to set status of device [{}]'.format(self._device.address))
                _LOGGER.info("Failed to set status")
                if i+1 == 3:
                    _LOGGER.error("Failed to set status on try i+1==3 of device %s", self._device.address )
                    return
#                    raise ConnectionError("Failed to set status.")

    def set_value (self, index, value):
        """Set a specific value to a specific index to the Tuya device and clear the cache."""
        self._cached_status = ''
        self._cached_status_time = 0
        for i in range(5):
            try:
                _LOGGER.info("Running a try from def set_value from cover where index=%s and value=%s", index, value)
                return self._device.set_value(index, value)
            except Exception:
                print('Failed to set_value of device [{}]'.format(self._device.address))
                if i+1 == 3:
                    _LOGGER.error("Failed to set value of device %s", self._device.address )
                    return
#                    raise ConnectionError("Failed to set value.")


    def status(self):
        """Get state of Tuya switch and cache the results."""
        _LOGGER.info("running def status(self) from cover")
        self._lock.acquire()
        try:
            now = time()
          #  _LOGGER.info("now set to = %s", now)
            if not self._cached_status or now - self._cached_status_time > 30:
           #     _LOGGER.info("status if not conditions met, sleeping for 0.5")
                sleep(0.5)
                self._cached_status = self.__get_status()
                _LOGGER.info("def status(self) ran get(status) and set self._cached_status to =%s", self._cached_status)
                self._cached_status_time = time()
            return self._cached_status
        finally:
            self._lock.release()

class TuyaDevice(CoverEntity):
    """Tuya cover devices."""

    def __init__(self, device, name, friendly_name, icon, switchid, open_cmd, close_cmd, stop_cmd, get_position_key):
        self._device = device
        self._available = False
        self._name = friendly_name
        self._friendly_name = friendly_name
        self._icon = icon
        self._switch_id = switchid
        self._status = self._device.status()
        _LOGGER.info("from init, self._status is now =%s", self._status)
        self._state = self._status['dps'][self._switch_id]
        _LOGGER.info("from init, self._state is now =%s", self._state)

        if (get_position_key>0):  # Do not need to validate that it is an integer, as the integer validation was handled above with cv.positive_int
            _LOGGER.info("get_position_key was=%s, set self._position via dps", get_position_key)
           # self._position = self._status['dps'][get_position_key]
            self._position = self._device.status()['dps'][str(get_position_key)]
            _LOGGER.info("position set to = %s", self._position)
        else:
            _LOGGER.info("get_position_key was=%s, set self._position to 50", get_position_key)
            self._position = 50 # If the current position key has not been set, set current position to 50

        self._open_cmd = open_cmd
        self._close_cmd = close_cmd
        self._stop_cmd = stop_cmd
        self._get_position_key = get_position_key
        _LOGGER.info("running def __init__ of TuyaDevice(CoverEntity) from cover.py with self=%s available=%s name=%s friendly_name=%s icon=%s switchid=%s status=%s state=%s position=%s  open_cmd=%s close_cmd=%s stop_cmd=%s get_position_key=%s", self, self._available,  name, friendly_name, icon, switchid, self._status, self._state, self._position,  open_cmd, close_cmd, stop_cmd, get_position_key)
        print('Initialized tuya cover [{}] with switch status [{}] and state [{}]'.format(self._name, self._status, self._state))

    @property
    def name(self):
        """Get name of Tuya switch."""
    #    _LOGGER.info("def name(self) called")
        return self._name

    @property
    def open_cmd(self):
        """Get name of open command."""
        _LOGGER.info("def open_cmd(self) called")
        return self._open_cmd

    @property
    def close_cmd(self):
        """Get name of close command."""
        _LOGGER.info("def close_cmd(self) called")
        return self._close_cmd

    @property
    def stop_cmd(self):
        """Get name of stop command."""
        _LOGGER.info("def stop_cmd(self) called")
        return self._stop_cmd

    @property
    def get_position_key(self):
        """Get name of position key."""
        _LOGGER.info("def get_position_key(self) called")
        return self._get_position_key

    @property
    def unique_id(self):
        """Return unique device identifier."""
    #    _LOGGER.info("def unique_id(self) called")
        return f"local_{self._device.unique_id}"

    @property
    def available(self):
        """Return if device is available or not."""
        _LOGGER.info("def available(self) called, =%s", self._available)
        return self._available

    @property
    def supported_features(self):
        """Flag supported features."""
    #    _LOGGER.info("def supported_features(self) called")
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION
        return supported_features

    @property
    def icon(self):
        """Return the icon."""
    #    _LOGGER.info("def icon(self) called")
        return self._icon

    @property
    def current_cover_position(self):
        _LOGGER.info("def current_cover_position(self) called, =%s", self._position)
        #self.update()
        #state = self._state
       # _LOGGER.info("curr_pos() : %i", self._position)
        #print('curr_pos() : state [{}]'.format(state))
        return self._position

    @property
    def is_opening(self):
        #self.update()
        state = self._state
        #print('is_opening() : state [{}]'.format(state))
        if state == 'on':
            _LOGGER.info("def is_opening(self) returned True")
            return True
        _LOGGER.info("def is_opening(self) returned False")
        return False

    @property
    def is_closing(self):
#        _LOGGER.info("def is_closing(self called")
        #self.update()
        state = self._state
        #print('is_closing() : state [{}]'.format(state))
        if state == 'off':
            _LOGGER.info("def is_closing(self) returned True")
            return True
        _LOGGER.info("def is_closing(self) returned False")
        return False

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
#        _LOGGER.info("def is_closed(self) called")
        #self.update()
        state = self._state
        #print('is_closed() : state [{}]'.format(state))
        if state == 'off':
            _LOGGER.info("def is_closed(self) returned state==off =False")
            return False
        if state == 'on':
            _LOGGER.info("def is_closed(self) returned state==on =True")
            return True
        _LOGGER.info("def is_closed(self) state was not on or off")
        return None

    def set_cover_position(self, **kwargs):
        _LOGGER.info("def set_cover_position(self), **kwargs called where self=%s, see next log for pos arg", self)
        """Move the cover to a specific position."""

        newpos = float(kwargs["position"])
        newpos = int(newpos)
        _LOGGER.info("Set new pos: %f", newpos)

        if (self.get_position_key>0):
            _LOGGER.info("position key set, set new position value") #FIXME
            self._device.set_value(2,newpos) #FIXME
        else:

            currpos = self.current_cover_position
            posdiff = abs(newpos - currpos)
            mydelay = posdiff / 2.0
            if newpos > currpos:
                _LOGGER.info("Opening to %f: delay %f", newpos, mydelay )
                self.open_cover()
            else:
                _LOGGER.info("Closing to %f: delay %f", newpos, mydelay )
                self.close_cover()
            sleep( mydelay )
            self.stop_cover()
            self._position = 50

    def open_cover(self, **kwargs):
        """Open the cover."""
        _LOGGER.info("running open_cover from cover")
        self._device.set_status(self._open_cmd, self._switch_id)
#        self._state = 'on'
#        self._device._device.open_cover()

    def close_cover(self, **kwargs):
        _LOGGER.info("running close_cover from cover")
        """Close cover."""
        _LOGGER.info('about to set_status from cover of off, %s', self._switch_id)
        self._device.set_status(self._close_cmd, self._switch_id)
#        self._state = 'off'
#        self._device._device.close_cover()

    def stop_cover(self, **kwargs):
        _LOGGER.info("running stop_cover from cover")
        """Stop the cover."""
        self._device.set_status(self._stop_cmd, self._switch_id)
#        self._state = 'stop'
#        self._device._device.stop_cover()

    def update(self):
        """Get state of Tuya switch."""
        _LOGGER.info("running update(self) from cover")
        try:
            self._status = self._device.status()
            self._state = self._status['dps'][self._switch_id]
            if(self._get_position_key>0):
                _LOGGER.info("update(self) sees position key=%s, time to update position to =%s", self._get_position_key, self._status['dps'][str(self._get_position_key)])
                self._position=self._status['dps'][str(self._get_position_key)]
                _LOGGER.info("update updated position to self._position=", self._position)


            #print('update() : state [{}]'.format(self._state))
        except Exception:
            self._available = False
        else:
            self._available = True
