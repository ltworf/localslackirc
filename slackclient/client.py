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
#
# This file was part of python-slackclient
# (https://github.com/slackapi/python-slackclient)
# But has been copied and relicensed under GPL. The copyright applies only
# to the changes made since it was copied.

import asyncio
import json
from typing import Any, Dict, List, NamedTuple, Optional

from typedload import load
import websockets
from websockets.client import connect as wsconnect

from .exceptions import *
from .http import Request


class Team(NamedTuple):
    id: str
    name: str
    domain: str


class Self(NamedTuple):
    id: str
    name: str


class LoginInfo(NamedTuple):
    team: Team
    self: Self
    url: str


class SlackClient:
    """
    The SlackClient object owns the websocket connection and all attached channel information.
    """

    def __init__(self, token: str, cookie: Optional[str]) -> None:
        # Slack client configs
        self._token = token
        self._cookie = cookie

        # RTM configs
        self._websocket: Optional[websockets.client.WebSocketClientProtocol] = None
        self._request = Request('https://slack.com/api/')
        self._wsid = 0

    async def wspacket(self, **kwargs) -> None:
        """
        Send data over websocket
        """
        if self._websocket is None:
            raise Exception('No websocket at this point')
        kwargs['id'] = self._wsid
        self._wsid += 1
        await self._websocket.send(json.dumps(kwargs))

    def __del__(self):
        try:
            asyncio.get_running_loop()
            loop = True
        except RuntimeError:
            loop = False

        if self._websocket and loop:
            asyncio.create_task(self._websocket.close())
        del self._request

    async def _do(self, request: str, post_data: Dict[str, Any], timeout: float):
        """
        Perform a POST request to the Slack Web API

        Args:
            request (str): the method to call from the Slack API. For example: 'channels.list'
            timeout (float): stop waiting for a response after a given number of seconds
            post_data (dict): key/value arguments to pass for the request. For example:
                {'channel': 'CABC12345'}
        """
        # Set user-agent and auth headers
        headers = {
            'user-agent': 'localslackirc',
            'Authorization': f'Bearer {self._token}'
        }
        if self._cookie:
            headers['cookie'] = self._cookie

        return await self._request.post(request, headers, post_data, timeout)

    async def login(self, timeout: float = 0.0) -> LoginInfo:
        """
        Performs a login to slack.
        """
        reply = await self._do('rtm.connect', {}, timeout=timeout)
        if reply.status != 200:
            raise SlackConnectionError("RTM connection attempt failed")
        login_data = reply.json()
        if not login_data["ok"]:
            raise SlackLoginError(reply=login_data)
        return load(login_data, LoginInfo)

    async def rtm_connect(self, timeout: Optional[int] = None) -> LoginInfo:
        """
        Connects to the RTM API - https://api.slack.com/rtm
        :Args:
            timeout: in seconds
        """
        r = await self.login()
        self._websocket = await wsconnect(r.url)
        return r


    async def api_call(self, method: str, timeout: float = 0.0, **kwargs) -> Dict[str, Any]:
        """
        Call the Slack Web API as documented here: https://api.slack.com/web

        :Args:
            method (str): The API Method to call. See here for a list: https://api.slack.com/methods
        :Kwargs:
            (optional) timeout: stop waiting for a response after a given number of seconds
            (optional) kwargs: any arguments passed here will be bundled and sent to the api
            requester as post_data
                and will be passed along to the API.

        Example::
            sc.server.api_call(
                "channels.setPurpose",
                channel="CABC12345",
                purpose="Writing some code!"
            )

        Returns:
            str -- returns HTTP response text and headers as JSON.

            Examples::

                u'{"ok":true,"purpose":"Testing bots"}'
                or
                u'{"ok":false,"error":"channel_not_found"}'

            See here for more information on responses: https://api.slack.com/web
        """
        response = await self._do(method, kwargs, timeout)
        response_json = response.json()
        response_json["headers"] = dict(response.headers)
        return response_json

    async def rtm_read(self) -> List[Dict[str, Any]]:
        assert self._websocket
        json_data: str = await self._websocket.recv()  # type: ignore
        data = []
        if json_data != '':
            for d in json_data.split('\n'):
                data.append(json.loads(d))
        return data
