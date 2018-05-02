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

from functools import lru_cache
from os.path import expanduser
from typing import *

from slackclient import SlackClient
from typedload import load, dump

from diff import seddiff


USELESS_EVENTS = {
    'channel_marked',
    'group_marked',
    'hello',
    'dnd_updated_user',
    'reaction_added',
    'user_typing',
}


def _loadwrapper(value, type_):
    try:
        return load(value, type_)
    except Exception as e:
        print(e)
        pass


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
    num_members: int = 0

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

    @property
    def is_changed(self) -> bool:
        return self.previous.text != self.current.text

    @property
    def diffmsg(self) -> Message:
        m = dump(self.current)
        m['text'] = seddiff(self.previous.text, self.current.text)
        return load(m, Message)


class MessageDelete(Message):
    pass


class FileDeleted(NamedTuple):
    file_id: str
    channel_ids: List[str] = []


class Profile(NamedTuple):
    real_name: str = 'noname'
    email: Optional[str] = None
    status_text: str = ''
    is_restricted: bool = False
    is_ultra_restricted: bool = False


class File(NamedTuple):
    id: str
    url_private: str
    size: int
    name: Optional[str] = None
    title: Optional[str] = None
    mimetype: Optional[str] = None


class MessageFileShare(NamedTuple):
    file: File
    user: str
    upload: bool
    username: str
    channel: str
    user_profile: Optional[Profile] = None
    text: str = ''


class MessageBot(NamedTuple):
    text: str
    username: str
    channel: str
    bot_id: Optional[str] = None


class User(NamedTuple):
    id: str
    name: str
    profile: Profile
    is_admin: bool = False

    @property
    def real_name(self) -> str:
        return self.profile.real_name


class IM(NamedTuple):
    id: str
    user: str


SlackEvent = Union[
    MessageDelete,
    MessageEdit,
    Message,
    FileDeleted,
    MessageFileShare,
    MessageBot,
]


class Slack:
    def __init__(self) -> None:
        home = expanduser("~")
        try:
            with open('.localslackcattoken') as f:
                token = f.readline().strip()
        except FileNotFoundError:
            exit("Slack token file not found")
        self.client = SlackClient(token)
        self._usercache = {}  # type: Dict[str, User]
        self._usermapcache = {}  # type: Dict[str, User]

    @lru_cache()
    def get_members(self, id_: str) -> List[str]:
        r = self.client.api_call('conversations.members', channel=id_, limit=5000)
        response = load(r, Response)
        if response.ok:
            return load(r['members'], List[str])
        raise ResponseException(response)

    @lru_cache()
    def channels(self) -> List[Channel]:
        """
        Returns the list of slack channels
        """
        result = []  # type: List[Channel]
        r = self.client.api_call("channels.list", exclude_archived=True, exclude_members=True)
        response = load(r, Response)
        if response.ok:
            result.extend(load(r['channels'], List[Channel]))
        else:
            raise ResponseException(response)

        r = self.client.api_call("groups.list", exclude_archived=True, exclude_members=True)
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

    @property
    def fileno(self) -> Optional[int]:
        return self.client.fileno

    def get_ims(self) -> List[IM]:
        """
        Returns a list of the IMs

        Some bullshit slack invented because 1 to 1 conversations
        need to have an ID to send to, you can't send directly to
        a user.
        """
        r = self.client.api_call(
            "im.list",
        )
        response = load(r, Response)
        if response.ok:
            return load(r['ims'], List[IM])
        raise ResponseException(response)

    def get_user_by_name(self, name) -> User:
        return self._usermapcache[name]

    def get_usernames(self) -> List[str]:
        return list(self._usermapcache.keys())

    def get_user(self, id_: str) -> User:
        """
        Returns a user object from a slack user id

        raises KeyError if it does not exist
        """
        if id_ in self._usercache:
            return self._usercache[id_]

        r = self.client.api_call("users.info", user=id_)
        response = load(r, Response)
        if response.ok:
            u = load(r['user'], User)
            self._usercache[id_] = u
            self._usermapcache[u.name] = u
            return u
        else:
            raise KeyError(response)

    def send_message(self, channel_id: str, msg: str) -> None:
        """
        Send a message to a channel or group or whatever
        """
        r = self.client.api_call(
            "chat.postMessage",
            channel=channel_id,
            text=msg,
            as_user=True,
        )
        response = load(r, Response)
        if response.ok:
            return
        raise ResponseException(response)

    def send_message_to_user(self, user_id: str, msg: str):

        # Find the channel id
        channel_id = None
        for i in self.get_ims():
            if i.user == user_id:
                channel_id = i.id
                break

        # A conversation does not exist, create one
        if not channel_id:
            r = self.client.api_call(
                "im.open",
                return_im=True,
                user=user_id,
            )
            response = load(r, Response)
            if not response.ok:
                raise ResponseException(response)
            channel_id = r['channel']['id']
        self.send_message(channel_id, msg)


    def events_iter(self) -> Iterator[Optional[SlackEvent]]:
        """
        This yields an event or None. Don't call it without sleeps
        """
        if self.client.rtm_connect():
            while True:
                try:
                    events = self.client.rtm_read()
                except:
                    if not self.client.rtm_connect():
                        raise
                    events = []

                for event in events:
                    t = event.get('type')
                    subt = event.get('subtype')

                    if t == 'message' and not subt:
                        yield _loadwrapper(event, Message)
                    elif t == 'message' and subt == 'file_share':
                        yield _loadwrapper(event, MessageFileShare)
                    elif t == 'message' and subt == 'message_changed':
                        event['message']['channel'] = event['channel']
                        event['previous_message']['channel'] = event['channel']
                        yield MessageEdit(
                            previous=load(event['previous_message'], Message),
                            current=load(event['message'], Message)
                        )
                    elif t == 'message' and subt == 'message_deleted':
                        event['previous_message']['channel'] = event['channel']
                        yield _loadwrapper(event['previous_message'], MessageDelete)
                    elif t == 'message' and subt == 'bot_message':
                        yield _loadwrapper(event, MessageBot)
                    elif t == 'user_change':
                        # Changes in the user, drop it from cache
                        u = load(event['user'], User)
                        if u.id in self._usercache:
                            del self._usercache[u.id]
                            #FIXME don't know if it is wise, maybe it gets lost forever del self._usermapcache[u.name]
                        #TODO make an event for this
                    elif t == 'file_deleted':
                        yield _loadwrapper(event, FileDeleted)
                    elif t in USELESS_EVENTS:
                        continue
                    else:
                        print(event)
                yield None
