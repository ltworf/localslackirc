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
import logging
import time
import random
from typing import Any, Dict, NamedTuple, Optional

from requests.packages.urllib3.util.url import parse_url
from ssl import SSLError
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


class Server:
    """
    The Server object owns the websocket connection and all attached channel information.
    """

    def __init__(self, token: str, connect: bool = True, proxies: Optional[Dict[str,str]] = None) -> None:
        # Slack client configs
        self.token = token
        self.proxies = proxies
        self.api_requester = SlackRequest(proxies=proxies)

        # Workspace metadata
        self.login_data = Optional[LoginInfo]

        # RTM configs
        self._websocket = None  # type: Optional[WebSocket]
        self.ws_url = None
        self.connected = False
        self.auto_reconnect = True
        self.last_connected_at = 0
        self.reconnect_count = 0
        self.rtm_connect_retries = 0

        # Connect to RTM on load
        if connect:
            self.rtm_connect()

    @property
    def ws_fileno(self) -> Optional[int]:
        if self._websocket is not None:
            return self._websocket.fileno()
        return None

    def rtm_connect(self, reconnect=False, timeout=None, **kwargs) -> None:
        """
        Connects to the RTM API - https://api.slack.com/rtm

        If `auto_reconnect` is set to `True` then the SlackClient is initialized, this method
        will be used to reconnect on websocket read failures, which indicate disconnection

        :Args:
            reconnect (boolean) Whether this method is being called to reconnect to RTM
            timeout (int): Stop waiting for Web API response after this many seconds
            https://api.slack.com/rtm#connecting_with_rtm.connect_vs._rtm.start
        """

        # rtm.start returns user and channel info, rtm.connect does not.
        connect_method = "rtm.connect"
        self.auto_reconnect = kwargs.get('auto_reconnect', True)

        # If this is an auto reconnect, rate limit reconnect attempts
        if self.auto_reconnect and reconnect:
            # Raise a SlackConnectionError after 5 retries within 3 minutes
            recon_count = self.reconnect_count
            if recon_count == 5:
                logging.error("RTM connection failed, reached max reconnects.")
                raise SlackConnectionError("RTM connection failed, reached max reconnects.")
            # Wait to reconnect if the last reconnect was less than 3 minutes ago
            if (time.time() - self.last_connected_at) < 180:
                if recon_count > 0:
                    # Back off after the the first attempt
                    backoff_offset_multiplier = random.randint(1, 4)
                    retry_timeout = (backoff_offset_multiplier * recon_count * recon_count)
                    logging.debug("Reconnecting in %d seconds", retry_timeout)

                    time.sleep(retry_timeout)
                self.reconnect_count += 1
            else:
                self.reconnect_count = 0

        reply = self.api_requester.do(self.token, connect_method, timeout=timeout, post_data=kwargs)

        if reply.status_code != 200:
            if self.rtm_connect_retries < 5 and reply.status_code == 429:
                self.rtm_connect_retries += 1
                retry_after = int(reply.headers.get('retry-after', 120))
                logging.debug("HTTP 429: Rate limited. Retrying in %d seconds", retry_after)
                time.sleep(retry_after)
                self.rtm_connect(reconnect=reconnect, timeout=timeout)
            else:
                raise SlackConnectionError("RTM connection attempt was rate limited 5 times.")
        else:
            self.rtm_connect_retries = 0
            login_data = reply.json()
            if login_data["ok"]:
                self.ws_url = login_data['url']
                self._connect_slack_websocket(self.ws_url)
                if not reconnect:
                    self._parse_slack_login_data(login_data)
            else:
                raise SlackLoginError(reply=reply)

    def _parse_slack_login_data(self, login_data):
        self.login_data = load(login_data, LoginInfo)

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
            self.connected = True
            self.last_connected_at = time.time()
            logging.debug("RTM connected")
            self._websocket.sock.setblocking(0)
        except Exception as e:
            self.connected = False
            raise SlackConnectionError(message=str(e))

    def websocket_safe_read(self) -> str:
        """
        Returns data if available, otherwise ''. Newlines indicate multiple
        messages
        """
        if self._websocket is None:
            return ''

        data = ''
        while True:
            try:
                data += "{0}\n".format(self._websocket.recv())
            except SSLError as e:
                if e.errno == 2:
                    # errno 2 occurs when trying to read or write data, but more
                    # data needs to be received on the underlying TCP transport
                    # before the request can be fulfilled.
                    #
                    # Python 2.7.9+ and Python 3.3+ give this its own exception,
                    # SSLWantReadError
                    return ''
                raise
            except WebSocketConnectionClosedException as e:
                logging.debug("RTM disconnected")
                self.connected = False
                if self.auto_reconnect:
                    self.rtm_connect(reconnect=True)
                else:
                    raise SlackConnectionError("Unable to send due to closed RTM websocket")
            return data.rstrip()

    def api_call(self, method: str, timeout: Optional[float], **kwargs) -> Dict[str, Any]:
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
