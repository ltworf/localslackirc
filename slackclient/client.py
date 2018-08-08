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
#
# This file was part of python-slackclient
# (https://github.com/slackapi/python-slackclient)
# But has been copied and relicensed under GPL. The copyright applies only
# to the changes made since it was copied.

from .exceptions import *
from .slackrequest import SlackRequest

import json
from typing import Any, Dict, List, NamedTuple, Optional

from requests.packages.urllib3.util.url import parse_url
from ssl import SSLWantReadError
from typedload import load
from websocket import create_connection, WebSocket
from websocket._exceptions import WebSocketConnectionClosedException


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
        self.token = token
        self.proxies = proxies
        self.api_requester = SlackRequest(proxies=proxies)

        # RTM configs
        self._websocket = None  # type: Optional[WebSocket]

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
        reply = self.api_requester.do(self.token, connect_method, timeout=timeout, post_data=kwargs)

        if reply.status_code != 200:
            raise SlackConnectionError("RTM connection attempt failed")

        login_data = reply.json()
        if login_data["ok"]:
            self._connect_slack_websocket(login_data['url'])
            return load(login_data, LoginInfo)
        else:
            raise SlackLoginError(reply=reply)

    def _connect_slack_websocket(self, ws_url):
        """Uses http proxy if available"""
        if self.proxies and 'http' in self.proxies:
            parts = parse_url(self.proxies['http'])
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
            self._websocket.sock.setblocking(0)
        except Exception as e:
            raise SlackConnectionError(message=str(e))

    def websocket_read(self) -> str:
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
        response = self.api_requester.do(self.token, method, kwargs, timeout)
        response_json = json.loads(response.text)
        response_json["headers"] = dict(response.headers)
        return response_json

    def rtm_read(self) -> List[Dict[str, Any]]:
        json_data = self.websocket_read()
        data = []
        if json_data != '':
            for d in json_data.split('\n'):
                data.append(json.loads(d))
        return data
