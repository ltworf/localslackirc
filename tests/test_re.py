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

import unittest

from irc import _MENTIONS_REGEXP, _CHANNEL_MENTIONS_REGEXP, _URL_REGEXP


class TestTesto(unittest.TestCase):
    def test_url_re(self):
        cases = [
            # String, matched groups
            ('q1://p1|p', None),
            ('Pinnello <q1://p1|p>', ('q1', 'p1', 'p')),
            ('Pinnello <q1://p1|p> asd asd', ('q1', 'p1', 'p')),
            ('<q1://p1|p> asd asd', ('q1', 'p1', 'p')),
            ('<q1://p1|p a|> asd asd', ('q1', 'p1', 'p a|')),
            ('<q1://p1> asd asd', ('q1', 'p1', '')),
        ]

        for url, expected in cases:
            m = _URL_REGEXP.search(url)
            assert m is None if expected is None else m.groups() == expected
