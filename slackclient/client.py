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

import json
import logging
from typing import Any, Dict, List, Optional

from .server import Server, LoginInfo
from .exceptions import *

LOG = logging.getLogger(__name__)


class SlackClient:
    '''
    This is a rather useless wrapper class
    '''
    def __init__(self, token: str, proxies: Optional[Dict[str,str]] = None) -> None:

        self.server = Server(token, proxies)

    def rtm_connect(self) -> LoginInfo:
        self.server.rtm_connect()
        if self.server.login_data is None:
            raise SlackConnectionError('No login data available')
        return self.server.login_data

    @property
    def fileno(self) -> Optional[int]:
        return self.server.ws_fileno

    def api_call(self, method: str, timeout: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        '''
        Call the Slack Web API as documented here: https://api.slack.com/web

        :Args:
            method (str): The API Method to call. See
            `the full list here <https://api.slack.com/methods>`_
        :Kwargs:
            (optional) kwargs: any arguments passed here will be bundled and sent to the api
            requester as post_data and will be passed along to the API.

            Example::
                sc.server.api_call(
                    "channels.setPurpose",
                    channel="CABC12345",
                    purpose="Writing some code!"
                )
        '''
        response_body = self.server.api_call(method, timeout=timeout, **kwargs)
        try:
            result = response_body
        except ValueError as json_decode_error:
            raise ParseResponseError(response_body, json_decode_error)
        return result

    def rtm_read(self) -> List[Dict[str, Any]]:
        '''
        Reads from the RTM Websocket stream then calls `self.process_changes(item)` for each line
        in the returned data.

        Multiple events may be returned, always returns a list [], which is empty if there are no
        incoming messages.
        :Returns:
            data (json) - The server response. For example::

                [{u'presence': u'active', u'type': u'presence_change', u'user': u'UABC1234'}]

        :Raises:
            SlackNotConnected if self.server is not defined.
        '''
        # in the future, this should handle some events internally i.e. channel
        # creation
        if self.server:
            json_data = self.server.websocket_read()
            data = []
            if json_data != '':
                for d in json_data.split('\n'):
                    data.append(json.loads(d))
            return data
        else:
            raise SlackNotConnected
