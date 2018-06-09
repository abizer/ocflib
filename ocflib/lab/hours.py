"""Methods for dealing with OCF lab hours.

All times are assumed to be OST (OCF Standard Time).

Usage:

    >>> from ocflib.lab.hours import Hours
    >>> Hours.get_hours(date(2015, 10, 12))
    Hours(
        date=datetime.date(2015, 10, 12),
        weekday='Monday',
        holiday=None,
        hours=[Hour(open=9, close=21)],
    )
"""
from collections import namedtuple
from datetime import date
from datetime import datetime
from datetime import timedelta
from enum import Enum

import pkg_resources
import yaml

HOURS_FILE = pkg_resources.resource_string(__name__, 'hours.yaml')


class Days(Enum):
    Monday = 0
    Tuesday = 1
    Wednesday = 2
    Thursday = 3
    Friday = 4
    Saturday = 5
    Sunday = 6

def _generate_regular_hours():
    """Load hours from a yaml file and return them in the manner expected by Day().

    The canonical source of OCF lab hours is hours.yaml in this directory.

    >>> _generate_regular_hours()
    {
        Days.Monday: [Hour(time(11, 10), time(13)),
                     Hour(time(14, 10), time(18)),
                     ...],
        Days.Tuesday: ...
        ...
    }
    """

    raw_hours = yaml.safe_load(HOURS_FILE)

    regular_hours = {}
    holidays = []

    def _parsetime(t):
        return datetime.strptime(t, '%H:%M').time()

    for day, hours in raw_hours['hours'].items():
        i_hours = []
        for hour in hours:
            x = hour.split('-')
            i_hours.append(
                Hour(
                    open=_parsetime(x[0]),
                    close=_parsetime(x[1])
                )
            )

        regular_hours[Days[day]] = i_hours

    for data in raw_hours['holidays']:
        i_hours = []
        if data['hours']:
            for hour in data['hours']:
                x = hour.split('-')
                i_hours.append(
                    Hour(
                        open=_parsetime(x[0]),
                        close=_parsetime(x[1])
                    )
                )

        holidays.append((data['start'], data['end'], data['reason'], i_hours))

    return regular_hours, holidays


class Hour:
    def __init__(self, open, close):
        self.open = open
        self.close = close

    def __contains__(self, when):
        if isinstance(when, datetime):
            when = when.time()
        return self.open <= when < self.close

    def __eq__(self, other):
        return self.open == other.open and \
            self.close == other.close

    def __repr__(self):
        return '{}-{}'.format(self.open, self.close)


class Hours(namedtuple('Hours', ['date', 'weekday', 'holiday', 'hours'])):

    @classmethod
    def get_hours(cls, day=None):
        """Return Hours representing the given day.

        If not provided, when defaults to today.
        """
        if not day:
            day = date.today()

        if isinstance(day, datetime):
            day = day.date()

        hours, holidays = _generate_regular_hours()

        # check if it's a holiday
        my_holiday = None
        my_hours = hours[Days(day.weekday())]

        for start, end, name, hours in holidays:
            if start <= day <= end:
                my_holiday = name
                my_hours = hours
                break

        return cls(
            date=day,
            weekday=day.strftime('%A'),
            holiday=my_holiday,
            hours=my_hours,
        )

    @classmethod
    def today(cls):
        return cls.get_hours()

    def lab_is_open(self, when=None):
        """Return whether the lab is open at the given time.

        If not provided, when defaults to now.
        """
        when = self._validate_time(when)

        return any(when in hour for hour in self.hours)

    def time_to_open(self, when=None):
        """Return timedelta object representing time until the lab is open from the given time.

        If not provided, defaults to now"""
        when = self._validate_time(when)

        if self.lab_is_open(when=when):
            return timedelta()

        def date_opens(date):
            return [datetime.combine(date, h.open) for h in Hours.get_hours(date).hours]

        opens = date_opens(self.date)
        # because we assume `when` is in the current day, any hours in future
        # dates don't need to be filtered
        opens = [o for o in opens if o > when]
        date = self.date
        while not opens:
            date += timedelta(days=1)
            opens = date_opens(date)

        return opens[0] - when

    def time_to_close(self, when=None):
        """Return timedelta object representing time until the lab is closed from the given time.

        If not provided, defaults to now"""
        when = self._validate_time(when)

        # because hour intervals should not overlap this should be length 0 or 1
        hours = [hour for hour in self.hours if when in hour]
        if not hours:
            return timedelta()
        return datetime.combine(self.date, hours[0].close) - when

    def _validate_time(self, when):
        if not when:
            return datetime.now()

        if not isinstance(when, datetime):
            raise ValueError('{} must be an instance of datetime'.format(when))

        if not self.date != when.date():
            raise ValueError('{} is on a different day than {}'.format(when, self))

    @property
    def closed_all_day(self):
        return not self.hours
