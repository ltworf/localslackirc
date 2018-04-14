# localslackirc
# This module is the inverse of dataloader. It converts typed
# data structures to things that json can treat.

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

from typing import Dict, List, NamedTuple

from slackclient import SlackClient
from typedload import load


class ResponseException(Exception):
    pass


class Response(NamedTuple):
    """
    Internally used to parse a response from the API.
    """
    ok: bool
    headers: Dict[str, str]


class Topic(NamedTuple):
    """
    In slack, topic is not just a string, but has other fields.
    """
    value: str


class Channel(NamedTuple):
    """
    A channel description.

    real_topic tries to use the purpose if the topic is missing
    """
    id: str
    name_normalized: str
    purpose: Topic
    topic: Topic
    num_members: int

    @property
    def name(self):
        return self.name_normalized

    @property
    def real_topic(self) -> str:
        if self.topic.value:
            return self.topic.value
        return self.purpose.value


class Slack:
    def __init__(self) -> None:
        #FIXME open the token in a sensible way
        with open('/home/salvo/.localslackcattoken') as f:
            token = f.readline().strip()
        self.client = SlackClient(token)

    def channels(self) -> List[Channel]:
        r = self.client.api_call("channels.list", exclude_archived=1)
        response = load(r, Response)
        if response.ok:
            return load(r['channels'], List[Channel])
        raise ResponseException(response)


if __name__ == '__main__':
    s  = Slack()
    print(s.channels())
