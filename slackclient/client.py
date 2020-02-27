# localslackirc
# Copyright (C) 2018-2020 Salvo "LtWorf" Tomaselli
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

from .exceptions import *

import json
from typing import Any, Dict, List, NamedTuple, Optional

from requests.packages.urllib3.util.url import parse_url
import requests
from ssl import SSLWantReadError
from typedload import load
from websocket import create_connection, WebSocket
from websocket._exceptions import WebSocketConnectionClosedException


class SlackRequest(NamedTuple):
    token: str
    proxies: Optional[Dict[str,str]]

    def do(self, request: str, post_data: Dict[str,str], timeout: Optional[float], files: Optional[Dict]):
        """
        Perform a POST request to the Slack Web API

        Args:
            token (str): your authentication token
            request (str): the method to call from the Slack API. For example: 'channels.list'
            timeout (float): stop waiting for a response after a given number of seconds
            post_data (dict): key/value arguments to pass for the request. For example:
                {'channel': 'CABC12345'}
        """
        domain = "slack.com"

        url = f'https://{domain}/api/{request}'

        # Set user-agent and auth headers
        headers = {
            'user-agent': 'localslackirc',
            'Authorization': f'Bearer {self.token}'
        }

        # Submit the request
        return requests.post(
            url,
            headers=headers,
            data=post_data,
            timeout=timeout,
            files=files,
            proxies=self.proxies
        )


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


class SlackClient:
    """
    The SlackClient object owns the websocket connection and all attached channel information.
    """

    def __init__(self, token: str, proxies: Optional[Dict[str,str]] = None) -> None:
        # Slack client configs
        self._token = token
        self._proxies = proxies
        self._api_requester = SlackRequest(token, proxies)

        # RTM configs
        self._websocket: Optional[WebSocket] = None

    @property
    def fileno(self) -> Optional[int]:
        if self._websocket is not None:
            return self._websocket.fileno()
        return None

    def rtm_connect(self, timeout: Optional[int] = None, **kwargs) -> LoginInfo:
        """
        Connects to the RTM API - https://api.slack.com/rtm
        :Args:
            timeout: in seconds
        """

        # rtm.start returns user and channel info, rtm.connect does not.
        connect_method = "rtm.connect"
        reply = self._api_requester.do(connect_method, timeout=timeout, post_data=kwargs, files=None)

        if reply.status_code != 200:
            raise SlackConnectionError("RTM connection attempt failed")

        login_data = reply.json()
        if login_data["ok"]:
            self._connect_slack_websocket(login_data['url'])
            return load(login_data, LoginInfo)
        else:
            raise SlackLoginError(reply=login_data)

    def _connect_slack_websocket(self, ws_url):
        """Uses http proxy if available"""
        if self._proxies and 'http' in self._proxies:
            parts = parse_url(self._proxies['http'])
            proxy_host, proxy_port = parts.host, parts.port
            auth = parts.auth
            proxy_auth = auth and auth.split(':')
        else:
            proxy_auth, proxy_port, proxy_host = None, None, None

        try:
            self._websocket = create_connection(ws_url,
                                               http_proxy_host=proxy_host,
                                               http_proxy_port=proxy_port,
                                               http_proxy_auth=proxy_auth)
            self._websocket.sock.setblocking(0)  # type: ignore
        except Exception as e:
            raise SlackConnectionError(message=str(e))

    def _websocket_read(self) -> str:
        """
        Returns data if available, otherwise ''. Newlines indicate multiple
        messages
        """
        if self._websocket is None:
            raise SlackConnectionError("Unable to send due to closed RTM websocket")

        data = ''
        while True:
            try:
                data += "{0}\n".format(self._websocket.recv())
            except SSLWantReadError:
                # errno 2 occurs when trying to read or write data, but more
                # data needs to be received on the underlying TCP transport
                # before the request can be fulfilled.
                #
                # Python 2.7.9+ and Python 3.3+ give this its own exception,
                # SSLWantReadError
                return ''
            except WebSocketConnectionClosedException:
                raise SlackConnectionError("Unable to send due to closed RTM websocket")
            return data.rstrip()

    def api_call(self, method: str, timeout: Optional[float] = None, **kwargs) -> Dict[str, Any]:
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
        if 'files' in kwargs:
            files = kwargs.pop('files')
        else:
            files = None
        response = self._api_requester.do(method, kwargs, timeout, files)
        response_json = json.loads(response.text)
        response_json["headers"] = dict(response.headers)
        return response_json

    def rtm_read(self) -> List[Dict[str, Any]]:
        json_data = self._websocket_read()
        data = []
        if json_data != '':
            for d in json_data.split('\n'):
                data.append(json.loads(d))
        return data
