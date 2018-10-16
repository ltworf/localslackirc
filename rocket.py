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
from ssl import SSLWantReadError
from typing import Any, Optional

from websocket import create_connection, WebSocket
from websocket._exceptions import WebSocketConnectionClosedException


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
    if data[0:1] == b'o':
        return None

    if data[0:1] == b'a':
        boh = json.loads(data[1:])
        assert len(boh) == 1
        return json.loads(boh[0])
    print('Strange data: ', repr(data))
    assert False


class Rocket:
    def __init__(self, url: str, token: str) -> None:
        self.url = url
        self.token  = token
        self._connect()

    def _send_json(self, data: Any) -> None:
        self._websocket.send(data2retard(data))

    def _connect(self) -> None:
        self._websocket = create_connection(
            self.url,
            headers=[
                f'Cookie: rc_token={self.token}',
            ]
        )
        self._websocket.sock.setblocking(0)
        self._send_json(
            {
                'msg': 'connect',
                'version': '1',
                'support': ['1', 'pre1', 'pre2']
            }
        )
        self._send_json(
            {"msg":"method","method":"login","params":[{"resume": self.token}],"id":"1"}
        )

    @property
    def fileno(self) -> Optional[int]:
        return self._websocket.fileno()

    def events_iter(self): # -> Iterator[Optional[SlackEvent]]:
        while True:
            try:
                _, raw_data = self._websocket.recv_data()
            except SSLWantReadError:
                yield None
                continue
            except:
                self._connect()
                continue

            data = retard2data(raw_data)

            # Handle the stupid ping thing directly here
            if data == {'msg': 'ping'}:
                self._send_json({'msg': 'pong'})
                continue
            yield data
