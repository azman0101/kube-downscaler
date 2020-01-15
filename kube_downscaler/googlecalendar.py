# -*- coding: utf-8 -*-
from __future__ import print_function

import datetime
import logging
import os.path
from abc import ABC
import abc

import humanize
from dateutil.parser import *
from dateutil.relativedelta import *
from dateutil.rrule import rrulestr
from google.auth.exceptions import DefaultCredentialsError
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError, UnknownApiNameOrVersion
from httplib2 import ServerNotFoundError
from tzlocal import get_localzone  # $ pip install tzlocal

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# httplib2.debuglevel = 4
# one_week = relativedelta(weeks=+1)
# in_one_week = datetime.datetime.utcnow()+one_week
# service = build('calendar', 'v3', developerKey=KEY)
#
# # Call the Calendar API
# now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
# print('Getting the upcoming 10 events')
# events_result = service.events().list(calendarId=CAL_ID,
#                                       timeMin=now,
#                                       singleEvents=True, timeMax=in_one_week.isoformat() + 'Z',
#                                       ).execute()
#
# events = events_result.get('items', [])
#
# recurring_events = set()
# if not events:
#     print('No upcoming events found.')
# for event in events:
#     if event.get('recurringEventId', None):
#         recurring = '==> Is a recurring event...'
#         recurring_events.add(event['recurringEventId'])
#         root_ev = service.events().get(calendarId=CAL_ID, eventId=event['recurringEventId']).execute()
#         rulez = rrulestr(root_ev['recurrence'][0])
#     else:
#         recurring = ''
#     start = event['start'].get('dateTime', event['start'].get('date'))
#     stop = event['end'].get('dateTime', event['end'].get('date'))
#     print(start, "-->", stop, event['summary'], recurring)
#     print("range duration: %s" % humanize.naturaldelta(parse(start) - parse(stop)))
#     print("%s" % humanize.naturaltime(datetime.datetime.now().astimezone(get_localzone()) - parse(start)))
#


class KubeCalendar(metaclass=abc.ABCMeta):
    _credentials: dict = None
    _client = None
    _next_range = None

    DEFAULT_DOWNTIME = None
    DEFAULT_UPTIME = None

    @property
    @abc.abstractmethod
    def next_range(self):
        return

    @property
    @abc.abstractmethod
    def credentials(self):
        return

    @credentials.setter
    @abc.abstractmethod
    def credentials(self, new_credentials):
        return

    @abc.abstractmethod
    def load(self, credentials: dict = None):
        self.credentials = credentials

    @abc.abstractmethod
    def connect(self):
        return


class GoogleCalendar(KubeCalendar, ABC):
    API_KEY_VAR_NAME = "API_KEY"
    CAL_ID_VAR_NAME = "CAL_ID"
    DOWNTIME_STRING_VAR_NAME = "DEFAULT_DOWNTIME_STRING"
    _events = None
    _next_range = None

    @property
    def next_range(self):
        return self._next_range

    @property
    def credentials(self):
        return self._credentials

    @credentials.setter
    def credentials(self, new_credentials):
        self._credentials = new_credentials

    def load(self, credentials: dict = None):
        if credentials is None:
            credentials = dict()
            if self.API_KEY_VAR_NAME in os.environ:
                api_key = os.environ.get(self.API_KEY_VAR_NAME).encode('utf-8')
                credentials[self.API_KEY_VAR_NAME] = api_key
            if self.CAL_ID_VAR_NAME in os.environ:
                cal_id = os.environ.get(self.CAL_ID_VAR_NAME)
                credentials[self.CAL_ID_VAR_NAME] = cal_id
        super().load(credentials=credentials)

    def connect(self):
        if self.API_KEY_VAR_NAME in self._credentials.keys():
            try:
                service = build('calendar', 'v3', developerKey=self._credentials[self.API_KEY_VAR_NAME],
                                cache_discovery=False)
                now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
                one_week = relativedelta(weeks=+1)
                in_one_week = datetime.datetime.utcnow() + one_week
                events_result = service.events().list(calendarId=self._credentials[self.CAL_ID_VAR_NAME],
                                                      timeMin=now,
                                                      singleEvents=True, timeMax=in_one_week.isoformat() + 'Z',
                                                      ).execute()
                self._get_calendar_events(service, events_result)
            except HttpError as err:
                logger.info('An HTTP error has occurred.  Please check YT Developer Key.')
                return err
            except DefaultCredentialsError as err:
                logger.info('Please check your API key.')
                raise DefaultCredentialsError
            except UnknownApiNameOrVersion:
                logger.info('Please check your API name or version.')
                raise UnknownApiNameOrVersion
            except ServerNotFoundError:
                logger.info('Server not found.  Please connect and try again.')
                raise ServerNotFoundError
            except TypeError as e:
                logger.info('Keyword must be a string. %s' % e)
                raise TypeError

    def _get_calendar_events(self, service: Resource, events_result: dict):
        # Get event with a specific summary
        events = [e for e in events_result.get('items', []) if
                  e['summary'] == os.environ.get(self.DOWNTIME_STRING_VAR_NAME)]
        recurring_events = set()
        if not events:
            logger.info('No upcoming events found.')
            # TODO: Add option to enforce crash if no event.
        else:
            self._events = events
        events.sort(key=lambda item: parse(item['start']['dateTime']), reverse=False)
        self._store_calendar_next_events(events[0])
        for event in events:
            if event.get('recurringEventId', None):
                recurring = '==> Is a recurring event...'
                recurring_events.add(event['recurringEventId'])
                root_ev = service.events().get(calendarId=self._credentials[self.CAL_ID_VAR_NAME],
                                               eventId=event['recurringEventId']).execute()
                rulez = rrulestr(root_ev['recurrence'][0])
            else:
                recurring = '==> Is NOT a recurring event...'
            start = event['start'].get('dateTime', event['start'].get('date'))
            stop = event['end'].get('dateTime', event['end'].get('date'))
            logger.info("%s --> %s %s %s" % (start, stop, event['summary'], recurring))
            logger.info("range duration: %s" % humanize.naturaldelta(parse(start) - parse(stop)))
            logger.info("%s" % humanize.naturaltime(datetime.datetime.now().astimezone(get_localzone()) - parse(start)))
            # 2020-04-09T20:00:00+02:00-2020-04-13T07:00:00+02:00
            # 2020-05-04T20:00:00+02:00

    def _store_calendar_next_events(self, next_range):
        start = next_range['start'].get('dateTime', next_range['start'].get('date'))
        stop = next_range['end'].get('dateTime', next_range['end'].get('date'))
        self._next_range = "{}-{}".format(start, stop)
