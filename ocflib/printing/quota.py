from collections import namedtuple
from datetime import datetime

import pymysql


WEEKDAY_QUOTA = 8
WEEKEND_QUOTA = 16
SEMESTERLY_QUOTA = 100

UserQuota = namedtuple('UserQuota', (
    'user',
    'daily',
    'semesterly',
))


Job = namedtuple('Job', (
    'user',
    'time',
    'pages',
    'queue',
    'printer',
    'doc_name',
    'filesize',
))

Refund = namedtuple('Refund', (
    'user',
    'time',
    'pages',
    'staffer',
    'reason',
))


def daily_quota(day=None):
    """Return the daily quota for a given day.

    :param day: date object (defaults to today)
    """
    if day is None:
        day = datetime.today()

    if day.weekday() in {5, 6}:
        return WEEKEND_QUOTA
    else:
        return WEEKDAY_QUOTA


def get_quota(c, user):
    """Return a UserQuota representing the user's quota."""
    if user == 'pubstaff':
        return UserQuota('pubstaff', 500, 500)

    c.execute(
        'SELECT `today`, `semester` FROM `printed` WHERE `user` = %s',
        (user,)
    )

    row = c.fetchone()
    if not row:
        row = {'today': 0, 'semester': 0}
    semesterly = max(0, SEMESTERLY_QUOTA - int(row['semester']))
    return UserQuota(
        user=user,
        daily=max(0, min(semesterly, daily_quota() - int(row['today']))),
        semesterly=semesterly,
    )


def _namedtuple_to_query(query, nt):
    """Return a filled-out query and arguments.

    The return value can be exploded and passed directly into execute.

    >>> query = 'INSERT INTO jobs ({}) VALUES ({});'
    >>> namedtuple_to_query(query, job)
    ('INSERT INTO jobs (`user`, `pages`) VALUES (%s, %s)', ('ckuehl', 42))
    """
    return (
        query.format(
            ', '.join('`{}`'.format(column) for column in nt._fields),
            ', '.join('%s' for _ in nt._fields),
        ),
        tuple(getattr(nt, column) for column in nt._fields),
    )


def add_job(c, job):
    """Add a new job to the database."""
    c.execute(*_namedtuple_to_query('INSERT INTO jobs ({}) VALUES ({})', job))


def add_refund(c, refund):
    """Add a new refund to the database."""
    c.execute(*_namedtuple_to_query('INSERT INTO refunds ({}) VALUES ({})', refund))


def get_connection(user='anonymous', password=None, db='ocfprinting', **kwargs):
    """Return a connection to MySQL.

    By default, returns an unprivileged connection which can be used for
    querying most data.

    If you need rw access, pass a user and password argument.
    """
    if 'unix_socket' not in kwargs:
        kwargs.setdefault('host', 'mysql.ocf.berkeley.edu')
    return pymysql.connect(
        user=user,
        password=password,
        db=db,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        charset='utf8mb4',
        **kwargs
    )
