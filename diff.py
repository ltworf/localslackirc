# localslackirc
# Copyright (C) 2018-2021 Salvo "LtWorf" Tomaselli
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

    l1 = a.split(' ')
    l2 = b.split(' ')

    for prefix in count():
        try:
            if l1[prefix] != l2[prefix]:
                break
        except:
            break
    for postfix in count(1):
        try:
            if l1[-postfix] != l2[-postfix]:
                break
        except Exception:
            break
    postfix -= 1



    if prefix and postfix and len(l1) != len(l2):
        prefix -= 1
        postfix -= 1
    px = None if postfix == 0 else -postfix

    print (l1, l2, prefix, postfix)
    print ('s/%s/%s/' % (' '.join(l1[prefix:px]) or '$', ' '.join(l2[prefix:px])))

    return 's/%s/%s/' % (' '.join(l1[prefix:px]) or '$', ' '.join(l2[prefix:px]))
