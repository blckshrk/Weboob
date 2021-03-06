# -*- coding: utf-8 -*-

# Copyright(C) 2010-2013 Romain Bignon
#
# This file is part of weboob.
#
# weboob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# weboob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with weboob. If not, see <http://www.gnu.org/licenses/>.


from datetime import date as real_date, datetime as real_datetime, timedelta
import dateutil.parser
import time
import re
try:
    from dateutil import tz
except ImportError:
    raise ImportError('Please install python-dateutil')


__all__ = ['local2utc', 'utc2local', 'LinearDateGuesser', 'date', 'datetime', 'new_date', 'new_datetime']


def local2utc(dateobj):
    dateobj = dateobj.replace(tzinfo=tz.tzlocal())
    dateobj = dateobj.astimezone(tz.tzutc())
    return dateobj


def utc2local(dateobj):
    dateobj = dateobj.replace(tzinfo=tz.tzutc())
    dateobj = dateobj.astimezone(tz.tzlocal())
    return dateobj


class date(real_date):
    def strftime(self, fmt):
        return strftime(self, fmt)


class datetime(real_datetime):
    def strftime(self, fmt):
        return strftime(self, fmt)

    def combine(self, date, time):
        return datetime(date.year, date.month, date.day, time.hour, time.minute, time.microsecond, time.tzinfo)

    def date(self):
        return date(self.year, self.month, self.day)


def new_date(d):
    """ Generate a safe date from a datetime.date object """
    return date(d.year, d.month, d.day)


def new_datetime(d):
    """
    Generate a safe datetime from a datetime.date or datetime.datetime object
    """
    kw = [d.year, d.month, d.day]
    if isinstance(d, real_datetime):
        kw.extend([d.hour, d.minute, d.second, d.microsecond, d.tzinfo])
    return datetime(*kw)


# No support for strftime's "%s" or "%y".
# Allowed if there's an even number of "%"s because they are escaped.
_illegal_formatting = re.compile(r"((^|[^%])(%%)*%[sy])")


def _findall(text, substr):
    # Also finds overlaps
    sites = []
    i = 0
    while True:
        j = text.find(substr, i)
        if j == -1:
            break
        sites.append(j)
        i = j+1
    return sites


def strftime(dt, fmt):
    if dt.year >= 1900:
        return super(type(dt), dt).strftime(fmt)
    illegal_formatting = _illegal_formatting.search(fmt)
    if illegal_formatting:
        raise TypeError("strftime of dates before 1900 does not handle" + illegal_formatting.group(0))

    year = dt.year
    # For every non-leap year century, advance by
    # 6 years to get into the 28-year repeat cycle
    delta = 2000 - year
    off = 6*(delta // 100 + delta // 400)
    year = year + off

    # Move to around the year 2000
    year = year + ((2000 - year)//28)*28
    timetuple = dt.timetuple()
    s1 = time.strftime(fmt, (year,) + timetuple[1:])
    sites1 = _findall(s1, str(year))

    s2 = time.strftime(fmt, (year+28,) + timetuple[1:])
    sites2 = _findall(s2, str(year+28))

    sites = []
    for site in sites1:
        if site in sites2:
            sites.append(site)

    s = s1
    syear = "%4d" % (dt.year,)
    for site in sites:
        s = s[:site] + syear + s[site+4:]
    return s


class LinearDateGuesser(object):
    """
    The aim of this class is to guess the exact date object from
    a day and a month, but not a year.

    It works with a start date (default is today), and all dates must be
    sorted from recent to older.
    """

    def __init__(self, current_date=None, date_max_bump=timedelta(7)):
        self.date_max_bump = date_max_bump
        if current_date is None:
            current_date = date.today()
        self.current_date = current_date

    def try_assigning_year(self, day, month, start_year, max_year):
        """
        Tries to create a date object with day, month and start_year and returns
        it.
        If it fails due to the year not matching the day+month combination
        (i.e. due to a ValueError -- TypeError and OverflowError are not
        handled), the previous or next years are tried until max_year is
        reached.
        In case initialization still fails with max_year, this function raises
        a ValueError.
        """
        while True:
            try:
                return date(start_year, month, day)
            except ValueError as e:
                if start_year == max_year:
                    raise e
                start_year += cmp(max_year, start_year)

    def set_current_date(self, current_date):
        self.current_date = current_date

    def guess_date(self, day, month, change_current_date=True):
        """ Returns a date object built from a given day/month pair. """

        today = self.current_date
        # The website only provides dates using the 'DD/MM' string, so we have to
        # determine the most possible year by ourselves. This implies tracking
        # the current date.
        # However, we may also encounter "bumps" in the dates, e.g. "12/11,
        # 10/11, 10/11, 12/11, 09/11", so we have to be, well, quite tolerant,
        # by accepting dates in the near future (say, 7 days) of the current
        # date. (Please, kill me...)
        # We first try to keep the current year
        naively_parsed_date = self.try_assigning_year(day, month, today.year, today.year - 5)
        if (naively_parsed_date.year != today.year):
            # we most likely hit a 29/02 leading to a change of year
            if change_current_date:
                self.set_current_date(naively_parsed_date)
            return naively_parsed_date

        if (naively_parsed_date > today + self.date_max_bump):
            # if the date ends up too far in the future, consider it actually
            # belongs to the previous year
            parsed_date = date(today.year - 1, month, day)
            if change_current_date:
                self.set_current_date(parsed_date)
        elif (naively_parsed_date > today and naively_parsed_date <= today + self.date_max_bump):
            # if the date is in the near future, consider it is a bump
            parsed_date = naively_parsed_date
            # do not keep it as current date though
        else:
            # if the date is in the past, as expected, simply keep it
            parsed_date = naively_parsed_date
            # and make it the new current date
            if change_current_date:
                self.set_current_date(parsed_date)
        return parsed_date

DATE_TRANSLATE_FR = [(re.compile(u'janvier', re.I),   u'january'),
                     (re.compile(u'février', re.I),   u'february'),
                     (re.compile(u'mars', re.I),      u'march'),
                     (re.compile(u'avril', re.I),     u'april'),
                     (re.compile(u'mai', re.I),       u'may'),
                     (re.compile(u'juin', re.I),      u'june'),
                     (re.compile(u'juillet', re.I),   u'july'),
                     (re.compile(u'août', re.I),      u'august'),
                     (re.compile(u'septembre', re.I), u'september'),
                     (re.compile(u'octobre', re.I),   u'october'),
                     (re.compile(u'novembre', re.I),  u'november'),
                     (re.compile(u'décembre', re.I),  u'december'),
                     (re.compile(u'lundi', re.I),     u'monday'),
                     (re.compile(u'mardi', re.I),     u'tuesday'),
                     (re.compile(u'mercredi', re.I),  u'wednesday'),
                     (re.compile(u'jeudi', re.I),     u'thursday'),
                     (re.compile(u'vendredi', re.I),  u'friday'),
                     (re.compile(u'samedi', re.I),    u'saturday'),
                     (re.compile(u'dimanche', re.I),  u'sunday')]

def parse_french_date(date):
    for fr, en in DATE_TRANSLATE_FR:
        date = fr.sub(en, date)

    return dateutil.parser.parse(date)
