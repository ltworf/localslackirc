# localslackirc
# Copyright (C) 2018 Salvo "LtWorf" Tomaselli
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


from itertools import count


_SEPARATORS = set(' .,:;\t\n()[]{}')


def seddiff(a: str, b: str) -> str:
    """
    Original string, changed string

    This is meant to operate on simple word changes
    or similar. Returns the IRC style correction
    format.
    """
    if a == b:
        return ''

    for prefix in count():
        try:
            if a[prefix] != b[prefix]:
                break
        except Exception:
            break
    for postfix in count(1):
        try:
            if a[-postfix] != b[-postfix]:
                break
        except Exception:
            break
    postfix -= 1

    longest = a if len(a) > len(b) else b

    # Move to word boundaries
    while prefix > 0 and longest[prefix] not in _SEPARATORS:
        prefix -= 1
    if longest[prefix] in _SEPARATORS:
        prefix += 1
    while postfix > 0 and longest[-postfix] not in _SEPARATORS:
        postfix -= 1

    if postfix == 0:
        px = None
    else:
        px = -postfix
    return 's/%s/%s/' % (a[prefix:px] or '$', b[prefix:px])
