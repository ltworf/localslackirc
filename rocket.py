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
from struct import Struct
from time import sleep, monotonic
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from websocket import create_connection, WebSocket
from websocket._exceptions import WebSocketConnectionClosedException
from typedload import load

from slack import Channel, File, FileShared, IM, SlackEvent, Topic, User
from slackclient.client import Team, Self, LoginInfo

CALL_TIMEOUT = 10


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

    if data[0:1] == b'c':
        return load(json.loads(data[1:]), Tuple[int, str])
    print('Strange data: ', repr(data))
    assert False


class ChannelType(Struct):
    CHANNEL = 'p'
    QUERY = 'd'
    #TODO = 'c'

class Rocket:
    def __init__(self, url: str, token: str) -> None:
        self.url = url
        self.token  = token
        self._call_id = 100
        self._internalevents = []  # type: List[Dict[str, Any]]
        self._channels = []  # type: List[Channel]

        self._connect()

    @property
    def login_info(self):
        #TODO
        return LoginInfo(
            team=Team(
                id='',
                name='',
                domain='',
            ),
            self=Self(
                id='',
                name='rchat_is_retarded',
            ),
        )

    def _update_channels(self) -> None:
        data = self._call('rooms/get', [], True)  # type: List[Dict[str, Any]]
        self._channels.clear()

        for i in data:
            # Subscribe to it
            self._send_json(
                {
                    'msg': 'sub',
                    'id': 'b',
                    'name': 'stream-room-messages',
                    'params': [
                        i['_id'],
                        {
                            'useCollection': False,
                            'args':[]
                        }
                    ]
                }
            )


            # If it's a real channel
            if i.get('t') == ChannelType.CHANNEL:
                self._channels.append(Channel(
                    id=i['_id'],
                    name_normalized=i['fname'],
                    purpose=Topic(i.get('topic', '')),
                    topic=Topic(i.get('topic', '')),
                ))

    def _send_json(self, data: Dict[str, Any]) -> None:
        """
        Sends something raw over the websocket (normally a dictionary
        """
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
        self._call('login', [{"resume": self.token}], False)
        self._update_channels()


    def _call(self, method: str, params: List[Any], wait_return: bool) -> Optional[Any]:
        """
        Does a remote call.

        if wait_return is true, it will wait for the response and
        return it. Otherwise the response will be ignored.
        """
        self._call_id += 1
        data = {
            'msg':'method',
            'method': method,
            'params': params,
            'id': str(self._call_id),
        }
        self._send_json(data)

        if wait_return:
            initial = monotonic()
            while initial + CALL_TIMEOUT > monotonic():
                r = self._read(str(self._call_id))
                if r:
                    return r
                sleep(0.05)
            raise TimeoutError()
        else:
            return None


    def away(self, is_away: bool) -> None:
        raise NotImplemented()

    def get_members(self, id_: str) -> Set[str]:
        return set() #FIXME
        raise NotImplemented()

    def channels(self) -> List[Channel]:
        return self._channels

    def get_channel(self, id_: str) -> Channel:
        for i in self._channels:
            if i.id == id_:
                return i
        raise KeyError()

    def get_channel_by_name(self, name: str) -> Channel:
        for i in self._channels:
            if i.name == name:
                return i
        raise KeyError()

    def get_ims(self) -> List[IM]:
        raise NotImplemented()

    def get_user_by_name(self, name: str) -> User:
        raise NotImplemented()

    def get_usernames(self) -> List[str]:
        raise NotImplemented()

    def prefetch_users(self) -> None:
        pass

    def get_user(self, id_: str) -> User:
        raise NotImplemented()

    def get_file(self, f: Union[FileShared, str]) -> File:
        raise NotImplemented()

    def send_file(self, channel_id: str, filename: str) -> None:
        raise NotImplemented()

    def send_message(self, channel_id: str, msg: str) -> None:
        raise NotImplemented()

    def send_message_to_user(self, user_id: str, msg: str):
        raise NotImplemented()

    @property
    def fileno(self) -> Optional[int]:
        return self._websocket.fileno()

    def _read(self, event_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        try:
            _, raw_data = self._websocket.recv_data()
        except SSLWantReadError:
            return None
        except:
            self._connect()
            return None
        data = retard2data(raw_data)

        # Handle the stupid ping thing directly here
        if data == {'msg': 'ping'}:
            self._send_json({'msg': 'pong'})
            return None

        # Search for results of function calls
        if data is not None and event_id is not None:
            if data.get('msg') == 'result' and data.get('id') == event_id:
                return data['result']
            else:
                # Not the needed item, append it there so it will be returned by the iterator later
                self._internalevents.append(data)
                return None
        else:
            return data

    def events_iter(self): # -> Iterator[Optional[SlackEvent]]:
        while True:
            while self._internalevents:
                yield self._internalevents.pop()

            data = self._read()
            if not data:
                yield None
                continue

            yield data
