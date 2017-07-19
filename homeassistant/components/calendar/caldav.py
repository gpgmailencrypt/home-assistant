"""
Support for calDAV calendar events

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/calDAV/
"""

import voluptuous as vol
from datetime import timedelta, datetime, date

from homeassistant.components.google import (CONF_OFFSET,
                                             CONF_DEVICE_ID,
                                             CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.calendar import CalendarEventDevice
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA

from homeassistant.util import Throttle

REQUIREMENTS = ['caldav==0.5.0',
                'icalendar==3.11.3']

CONF_CALDAV_SENSOR_TRACK = 'track'
CONF_CALDAV_SENSOR_SEARCH = 'search'

CALENDAR_SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_CALDAV_SENSOR_TRACK): cv.boolean,
    vol.Optional(CONF_CALDAV_SENSOR_SEARCH): vol.Any(cv.string, None),
    vol.Optional(CONF_OFFSET): cv.string,
})

CONF_CALDAV_CALENDAR_NAME = 'cal_id'
CONF_CALDAV_SENSOR = 'sensors'

CALENDAR_SCHEMA = vol.Schema({
    vol.Required(CONF_CALDAV_CALENDAR_NAME): cv.string,
    vol.Required(CONF_CALDAV_SENSOR, None):
        vol.All(cv.ensure_list, [CALENDAR_SENSOR_SCHEMA])
})

CONF_CALDAV_URL = 'url'
CONF_CALDAV_USER = 'user'
CONF_CALDAV_PASSWORD = 'password'
CONF_CALDAV_CA_PATH = 'cert_path'
CONF_CALDAV_ENTITIES = 'entities'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CALDAV_URL): cv.string,
    vol.Required(CONF_CALDAV_USER): cv.string,
    vol.Required(CONF_CALDAV_PASSWORD): cv.string,
    vol.Required(CONF_CALDAV_ENTITIES, None):
        vol.All(cv.ensure_list, [CALENDAR_SCHEMA]),
    vol.Optional(CONF_CALDAV_CA_PATH): cv.string,
})

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


def setup_platform(hass, config, add_devices, discovery_info=None):
    from caldav import DAVClient

    client = DAVClient(config.get(CONF_CALDAV_URL),
                       username=config.get(CONF_CALDAV_USER),
                       password=config.get(CONF_CALDAV_PASSWORD),
                       ssl_verify_cert=config.get(CONF_CALDAV_CA_PATH, None)
                       )
    principal = client.principal()

    for calendar in config[CONF_CALDAV_ENTITIES]:
        add_devices([CalDAVCalendarEventDevice(hass, principal,
                                               calendar[CONF_CALDAV_CALENDAR_NAME], data)
                     for data in calendar[CONF_CALDAV_SENSOR] if data[CONF_CALDAV_SENSOR_TRACK]])


class CalDAVCalendarEventDevice(CalendarEventDevice):
    """A calendar event device."""

    def __init__(self, hass, principal, calendar_id, data):
        """Create the Calendar event device."""
        calendars = principal.calendars()

        for cal in calendars:
            if cal.name == calendar_id:
                self.data = CalDAVCalendarData(cal, data.get(CONF_CALDAV_SENSOR_SEARCH))

        super().__init__(hass, data)


class CalDAVCalendarData(object):
    """Class to utilize calendar service object to get next event."""

    def __init__(self, calendar, search=None):
        """Setup how we are going to search the google calendar."""
        self.calendar = calendar
        self.search = search
        self.event = None

    def __convert_vevent(self, vevent):
        event = dict()
        event['summary'] = vevent.get('SUMMARY', '')
        event['start'] = dict()
        start = vevent.get('DTSTART', '').dt
        if type(start) is date:
            event['start']['date'] = start.isoformat()
        elif type(start) is datetime:
            event['start']['dateTime'] = start.isoformat()
        else:
            raise ValueError('Invalid start time')
        event['end'] = dict()
        end = vevent.get('DTEND', '').dt
        if type(end) is date:
            event['end']['date'] = end.isoformat()
        elif type(end) is datetime:
            event['end']['dateTime'] = end.isoformat()
        else:
            raise ValueError('Invalid end time')
        event['location'] = vevent.get('LOCATION', '')
        event['description'] = vevent.get('DESCRIPTION', '')

        return event

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        from icalendar import Calendar
        """Get the latest data."""
        events = self.calendar.date_search(datetime.utcnow(),
                                           datetime.utcnow() + timedelta(days=1))

        items = []
        for event in events:
            cal = Calendar.from_ical(event.data)
            for e in cal.walk('vevent'):
                if self.search:
                    if self.search in e['SUMMARY']:
                        items.append(self.__convert_vevent(e))
                else:
                    items.append(self.__convert_vevent(e))

        self.event = items[0] if len(items) == 1 else None
        return True
