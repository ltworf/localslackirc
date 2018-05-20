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


def seddiff(a: str, b: str) -> str:
    """
    Original string, changed string

    This is meant to operate on simple word changes
    or similar. Returns the IRC style correction
    format.
    """
    for prefix in count():
        try:
            if a[prefix] != b[prefix]:
                break
        except:
            break
    for postfix in count(1):
        try:
            if a[-postfix] != b[-postfix]:
                break
        except:
            break

    if prefix < 0:
        prefix = 0

    postfix -= 1
    if postfix == 0:
        px = None
    else:
        px = postfix * -1
    return 's/%s/%s/' % (a[prefix:px], b[prefix:px])
