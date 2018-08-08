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
        return self.server.rtm_connect()

    @property
    def fileno(self) -> Optional[int]:
        return self.server.ws_fileno

    def api_call(self, method: str, timeout: Optional[float] = None, **kwargs) -> Dict[str, Any]:
        return self.server.api_call(method, timeout=timeout, **kwargs)

    def rtm_read(self) -> List[Dict[str, Any]]:
        return self.server.rtm_read()
