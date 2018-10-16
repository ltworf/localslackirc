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


import json
from typing import Any, Optional


def data2retard(data: Any) -> bytes:
    '''
    Converts json data into the retarded format
    used by rocketchat.
    '''
    return json.dumps([json.dumps(data)]).encode('ascii')


def retard2data(data: bytes) -> Optional[Any]:
    '''
    Converts the even more retarded messages from rocket chat
    '''
    if len(data) == 0:
        return None

    # I have no clue of why that would be
    if data[0] == b'o':
        return None

    if data[0] == b'a':
        boh = json.loads(data[1:])
        assert len(boh) == 1
        return json.loads(boh[0])
