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

from functools import lru_cache
from typing import *

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
    members: Set[str]  # Set of user ids

    @property
    def name(self):
        return self.name_normalized

    @property
    def real_topic(self) -> str:
        if self.topic.value:
            return self.topic.value
        return self.purpose.value


class Message(NamedTuple):
    channel: str  # The channel id
    user: str  # The user id
    text: str


class MessageEdit(NamedTuple):
    previous: Message
    current: Message


class MessageDelete(Message):
    pass


class Profile(NamedTuple):
    real_name: str = 'noname'
    email: Optional[str] = None
    status_text: str = ''


class User(NamedTuple):
    id: str
    name: str
    profile: Profile
    is_admin: bool = False

    @property
    def real_name(self) -> str:
        return self.profile.real_name


class Slack:
    def __init__(self) -> None:
        #FIXME open the token in a sensible way
        with open('/home/salvo/.localslackcattoken') as f:
            token = f.readline().strip()
        self.client = SlackClient(token)

    @lru_cache()
    def channels(self) -> List[Channel]:
        """
        Returns the list of slack channels
        """
        result = []  # type: List[Channel]
        r = self.client.api_call("channels.list", exclude_archived=1)
        response = load(r, Response)
        if response.ok:
            result.extend(load(r['channels'], List[Channel]))
        else:
            raise ResponseException(response)

        r = self.client.api_call("groups.list", exclude_archived=1)
        response = load(r, Response)
        if response.ok:
            result.extend(load(r['groups'], List[Channel]))
        else:
            raise ResponseException(response)
        return result

    @lru_cache()
    def get_channel(self, id_: str) -> Channel:
        """
        Returns a channel object from a slack channel id

        raises KeyError if it doesn't exist.
        """
        for c in self.channels():
            if c.id == id_:
                return c
        raise KeyError()

    @lru_cache()
    def get_channel_by_name(self, name: str) -> Channel:
        """
        Returns a channel object from a slack channel id

        raises KeyError if it doesn't exist.
        """
        for c in self.channels():
            if c.name == name:
                return c
        raise KeyError()

    @lru_cache(maxsize=700)
    def get_user(self, id_: str) -> User:
        """
        Returns a user object from a slack user id

        raises KeyError if it does not exist
        """
        r = self.client.api_call("users.info", user=id_)
        response = load(r, Response)
        if response.ok:
            return load(r['user'], User)
        else:
            raise KeyError(response)


    def events_iter(self):
        """
        This yields an event or None. Don't call it without sleeps
        """
        if self.client.rtm_connect(with_team_state=False):
            while True:
                events = self.client.rtm_read()
                for event in events:
                    print(event)
                    t = event.get('type')
                    subt = event.get('subtype')

                    if t == 'message' and not subt:
                        yield load(event, Message)
                    elif t == 'message' and subt == 'message_changed':
                        event['message']['channel'] = event['channel']
                        event['previous_message']['channel'] = event['channel']
                        yield MessageEdit(
                            previous=load(event['previous_message'], Message),
                            current=load(event['message'], Message)
                        )
                    elif t == 'message' and subt == 'message_deleted':
                        event['previous_message']['channel'] = event['channel']
                        yield load(event['previous_message'], MessageDelete)
                yield None


if __name__ == '__main__':
    s  = Slack()
    print(s.channels())
    for event in s.loop():
        print(event)
