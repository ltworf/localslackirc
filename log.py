# localslackirc
# Copyright (C) 2020 Salvo "LtWorf" Tomaselli
#
# localslackirc is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# author Salvo "LtWorf" Tomaselli <tiposchi@tiscali.it>

from os import isatty
from syslog import LOG_INFO, LOG_DEBUG, syslog
from syslog import openlog as _openlog
from typing import Union

__all__ = [
    'log',
    'openlog',
    'set_debug',
    'debug',
]


tty = isatty(1) and isatty(2)
debug_enabled = False


def openlog(suffix: str) -> None:
    """
    Opens the syslog connection if needed
    otherwise does nothing.
    """
    if tty:
        return
    if suffix:
        suffix = f'-{suffix}'
    _openlog(f'localslackirc{suffix}')


def log(*args) -> None:
    """
    Logs to stdout or to syslog depending on if
    running with a terminal attached.
    """
    if tty:
        print(*args)
        return
    syslog(LOG_INFO, ' '.join(str(i) for i in args))


def set_debug(state: Union[str, bool]) -> None:
    global debug_enabled
    debug_enabled = bool(state)


def debug(*args) -> None:
    if not debug_enabled:
        return
    if tty:
        print(*args)
    syslog(LOG_DEBUG, ' '.join(str(i) for i in args))
