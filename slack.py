# localslackirc
# Copyright (C) 2018-2022 Salvo "LtWorf" Tomaselli
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

import asyncio
import datetime
from dataclasses import dataclass, field
import json
from time import time
from typing import *

from typedload import load, dump

from diff import seddiff
from slackclient import SlackClient
from slackclient.client import LoginInfo
from log import *


USELESS_EVENTS = {
    'draft_create',
    'draft_delete',
    'accounts_changed',
    'channel_marked',
    'group_marked',
    'mpim_marked',
    'hello',
    'dnd_updated_user',
    'reaction_added',
    'file_deleted',
    'file_public',
    'file_created',
    'file_shared',
    'desktop_notification',
    'mobile_in_app_notification',
}


class ResponseException(Exception):
    pass


class Response(NamedTuple):
    """
    Internally used to parse a response from the API.
    """
    ok: bool
    headers: Dict[str, str]
    ts: Optional[float] = None
    error: Optional[str] = None


@dataclass
class File:
    id: str
    url_private: str
    size: int
    user: str
    name: Optional[str] = None
    title: Optional[str] = None
    mimetype: Optional[str] = None


class Topic(NamedTuple):
    """
    In slack, topic is not just a string, but has other fields.
    """
    value: str


class LatestMessage(NamedTuple):
    ts: float

    @property
    def timestamp(self):
        return datetime.datetime.utcfromtimestamp(self.ts)


@dataclass(frozen=True)
class Channel:
    """
    A channel description.

    real_topic tries to use the purpose if the topic is missing
    """
    id: str
    name_normalized: str
    purpose: Topic
    topic: Topic
    num_members: int = 0
    #: Membership: present on channels, not on groups - but True there.
    is_member: bool = True

    #: Object type. groups have is_group=True, channels is_channel=True
    is_channel: bool = False
    is_group: bool = False
    is_mpim: bool = False

    latest: Optional[LatestMessage] = None

    @property
    def name(self):
        return self.name_normalized

    @property
    def real_topic(self) -> str:
        if self.topic.value:
            t = self.topic.value
        else:
            t = self.purpose.value
        return t.replace('\n', ' | ')

@dataclass(frozen=True)
class MessageThread(Channel):
    thread_ts: str = ''


@dataclass(frozen=True)
class Message:
    channel: str  # The channel id
    user: str  # The user id
    text: str
    thread_ts: Optional[str] = None
    files: List[File] = field(default_factory=list)


class NoChanMessage(NamedTuple):
    user: str
    text: str


class ActionMessage(Message):
    pass


@dataclass
class GroupJoined:
    type: Literal['group_joined']
    channel: Channel


@dataclass
class MessageEdit:
    type: Literal['message']
    subtype: Literal['message_changed']
    channel: str
    previous: NoChanMessage = field(metadata={'name': 'previous_message'})
    current: NoChanMessage = field(metadata={'name': 'message'})

    @property
    def is_changed(self) -> bool:
        return self.previous.text != self.current.text

    @property
    def diffmsg(self) -> Message:
        return Message(
            text=seddiff(self.previous.text, self.current.text),
            channel=self.channel,
            user=self.current.user,
        )


@dataclass
class MessageDelete:
    type: Literal['message']
    subtype: Literal['message_deleted']
    channel: str
    previous_message: NoChanMessage
    thread_ts: Optional[str] = None
    files: List[File] = field(default_factory=list)

    @property
    def user(self) -> str:
        return self.previous_message.user

    @property
    def text(self) -> str:
        return self.previous_message.text


class UserTyping(NamedTuple):
    type: Literal['user_typing']
    user: str
    channel: str


class Profile(NamedTuple):
    real_name: str = 'noname'
    email: Optional[str] = None
    status_text: str = ''
    is_restricted: bool = False
    is_ultra_restricted: bool = False


@dataclass
class MessageBot:
    type: Literal['message']
    subtype: Literal['bot_message']
    _text: str = field(metadata={'name': 'text'})
    username: str
    channel: str
    bot_id: Optional[str] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    thread_ts: Optional[str] = None
    files: List[File] = field(default_factory=list)

    @property
    def text(self):
        r = [self._text]
        for i in self.attachments:
            t = ""
            if 'text' in i:
                t = i['text']
            elif 'fallback' in i:
                t = i['fallback']
            for line in t.split("\n"):
                r.append("| " + line)
        return '\n'.join(r)


class User(NamedTuple):
    id: str
    name: str
    profile: Profile
    is_admin: bool = False
    deleted: bool = False

    @property
    def real_name(self) -> str:
        return self.profile.real_name


class IM(NamedTuple):
    id: str
    user: str


class Join(NamedTuple):
    type: Literal['member_joined_channel']
    user: str
    channel: str


class Leave(NamedTuple):
    type: Literal['member_left_channel']
    user: str
    channel: str


@dataclass
class TopicChange:
    type: Literal['message']
    subtype: Literal['group_topic']
    topic: str
    channel: str
    user: str


@dataclass
class HistoryBotMessage:
    type: Literal['message']
    subtype: Literal['bot_message']
    text: str
    bot_id: Optional[str]
    username: str = 'bot'
    ts: float = 0
    files: List[File] = field(default_factory=list)
    thread_ts: Optional[str] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class HistoryMessage:
    type: Literal['message']
    user: str
    text: str
    ts: float
    files: List[File] = field(default_factory=list)
    thread_ts: Optional[str] = None


class NextCursor(NamedTuple):
    next_cursor: str


class History(NamedTuple):
    ok: Literal[True]
    messages: List[Union[HistoryMessage, HistoryBotMessage]]
    has_more: bool
    response_metadata: Optional[NextCursor] = None


class Conversations(NamedTuple):
    channels: List[Channel]
    response_metadata: Optional[NextCursor] = None


SlackEvent = Union[
    TopicChange,
    MessageDelete,
    MessageEdit,
    Message,
    ActionMessage,
    MessageBot,
    Join,
    Leave,
    GroupJoined,
    UserTyping,
]


@dataclass
class SlackStatus:
    """
    Not related to the slack API.
    This is a structure used internally by this module to
    save the status on disk.
    """
    last_timestamp: float = 0.0

class Slack:
    def __init__(self, token: str, cookie: Optional[str], previous_status: Optional[bytes]) -> None:
        """
        A slack client object.

        token: The slack token
        cookie: If the slack instance also uses a cookie, it must be passed here
        previous_status: Opaque bytestring to restore internal status
                from a different object. Obtained from get_status()
        """
        self.client = SlackClient(token, cookie)
        self._usercache: Dict[str, User] = {}
        self._usermapcache: Dict[str, User] = {}
        self._usermapcache_keys: List[str]
        self._imcache: Dict[str, str] = {}
        self._channelscache: List[Channel] = []
        self._get_members_cache: Dict[str, Set[str]] = {}
        self._get_members_cache_cursor: Dict[str, Optional[str]] = {}
        self._internalevents: List[SlackEvent] = []
        self._sent_by_self: Set[float] = set()
        self._wsblock: int = 0 # Semaphore to block the socket and avoid events being received before their API call ended.
        self.login_info: Optional[LoginInfo] = None
        if previous_status is None:
            self._status = SlackStatus()
        else:
            self._status = load(json.loads(previous_status), SlackStatus)

    def close(self):
        del self.client

    async def login(self) -> None:
        """
        Set the login_info field
        """
        log('Login in slack')
        self.login_info = await self.client.login(15)

    async def get_history(self, channel: Union[Channel, IM, str], ts: str, cursor: Optional[NextCursor]=None, limit: int=1000, inclusive: bool=False) -> History:
        p = await self.client.api_call(
            'conversations.history',
            channel=channel if isinstance(channel, str) else channel.id,
            oldest=ts,
            limit=limit,
            cursor=cursor.next_cursor if cursor else None,
            inclusive=inclusive,
        )
        return load(p, History)

    async def _thread_history(self, channel: str, thread_id: str) -> List[Union[HistoryMessage, HistoryBotMessage]]:
        r: List[Union[HistoryMessage, HistoryBotMessage]] = []
        cursor = None
        log('Thread history', channel, thread_id)
        while True:
            log('Cursor')
            p = await self.client.api_call(
                'conversations.replies',
                channel=channel,
                ts=thread_id,
                limit=1000,
                cursor=cursor,
            )
            try:
                response = load(p, History)
            except Exception as e:
                    log('Failed to parse', e)
                    log(p)
                    break
            r += [i for i in response.messages if i.ts != i.thread_ts]
            if response.has_more and response.response_metadata:
                cursor = response.response_metadata.next_cursor
            else:
                break
        log('Thread fetched')
        r[0].thread_ts = None
        return r

    async def _history(self) -> None:
        '''
        Obtain the history from the last known event and
        inject fake events as if the messages are coming now.
        '''
        log('Fetching history...')

        if self._status.last_timestamp == 0:
            log('No last known timestamp. Unable to fetch history')
            return

        last_timestamp = self._status.last_timestamp
        FOUR_DAYS = 60 * 60 * 24 * 4
        if time() - last_timestamp > FOUR_DAYS:
            log('Last timestamp is too old. Defaulting to 4 days.')
            last_timestamp = time() - FOUR_DAYS
        dt = datetime.datetime.fromtimestamp(last_timestamp)
        log(f'Last known timestamp {dt}')

        chats: Sequence[Union[IM, Channel]] = []
        chats += await self.channels() + await self.get_ims()  # type: ignore
        for channel in chats:
            if isinstance(channel, Channel):
                if not channel.is_member:
                    continue

                log(f'Downloading logs from channel {channel.name_normalized}')
            else:
                log(f'Downloading logs from IM {channel.user}')

            cursor = None
            while True: # Loop to iterate the cursor
                log('Calling cursor')
                try:
                    response = await self.get_history(channel, str(last_timestamp))
                except Exception as e:
                    log('Failed to parse', e)
                    break
                msg_list = list(response.messages)
                while msg_list:
                    msg = msg_list.pop(0)

                    # The last seen message is sent again, skip it
                    if msg.ts == last_timestamp:
                        continue
                    # Update the last seen timestamp
                    if self._status.last_timestamp < msg.ts:
                        self._status.last_timestamp = msg.ts

                    # History for the thread
                    if msg.thread_ts and float(msg.thread_ts) == msg.ts:
                        l = await self._thread_history(channel.id, msg.thread_ts)
                        l.reverse()
                        msg_list = l + msg_list
                        continue

                    # Inject the events
                    if isinstance(msg, HistoryMessage):
                        self._internalevents.append(Message(
                            channel=channel.id,
                            text=msg.text,
                            user=msg.user,
                            thread_ts=msg.thread_ts,
                            files=msg.files,
                        ))
                    elif isinstance(msg, HistoryBotMessage):
                        self._internalevents.append(MessageBot(
                            type='message', subtype='bot_message',
                            _text=msg.text,
                            attachments=msg.attachments,
                            username=msg.username,
                            channel=channel.id,
                            bot_id=msg.bot_id,
                            thread_ts=msg.thread_ts,
                        ))

                if response.has_more and response.response_metadata:
                    cursor = response.response_metadata.next_cursor
                else:
                    break

    def get_status(self) -> bytes:
        '''
        A status string that will be passed back when this is started again
        '''
        return json.dumps(dump(self._status), ensure_ascii=True).encode('ascii')


    async def away(self, is_away: bool) -> None:
        """
        Forces the aways status or lets slack decide
        """
        status = 'away' if is_away else 'auto'
        r = await self.client.api_call('users.setPresence', presence=status)
        response = load(r, Response)
        if not response.ok:
            raise ResponseException(response.error)

    async def typing(self, channel: Union[Channel, str]) -> None:
        """
        Sends a typing event to slack
        """
        if isinstance(channel, Channel):
            ch_id = channel.id
        else:
            ch_id = channel
        await self.client.wspacket(type='typing', channel=ch_id)

    async def topic(self, channel: Channel, topic: str) -> None:
        r = await self.client.api_call('conversations.setTopic', channel=channel.id, topic=topic)
        response = load(r, Response)
        if not response.ok:
            raise ResponseException(response.error)

    async def kick(self, channel: Channel, user: User) -> None:
        r = await self.client.api_call('conversations.kick', channel=channel.id, user=user.id)
        response = load(r, Response)
        if not response.ok:
            raise ResponseException(response.error)

    async def join(self, channel: Channel) -> None:
        r = await self.client.api_call('conversations.join', channel=channel.id)
        response = load(r, Response)
        if not response.ok:
            raise ResponseException(response.error)

    async def invite(self, channel: Channel, user: Union[User, List[User]]) -> None:
        if isinstance(user, User):
            ids = user.id
        else:
            if len(user) > 30:
                raise ValueError('No more than 30 users allowed')
            ids = ','.join(i.id for i in user)

        r = await self.client.api_call('conversations.invite', channel=channel.id, users=ids)
        response = load(r, Response)
        if not response.ok:
            raise ResponseException(response.error)

    async def get_members(self, channel: Union[str, Channel]) -> Set[str]:
        """
        Returns the list (as a set) of users in a channel.

        It performs caching. Every time the function is called, a new batch is
        requested, until all the users are cached, and then no new requests
        are performed, and the same data is returned.

        When events happen, the cache needs to be updated or cleared.
        """
        if isinstance(channel, Channel):
            id_ = channel.id
        else:
            id_ = channel

        cached = self._get_members_cache.get(id_, set())
        cursor = self._get_members_cache_cursor.get(id_)
        if cursor == '':
            # The cursor is fully iterated
            return cached
        kwargs = {}
        if cursor:
            kwargs['cursor'] = cursor
        r = await self.client.api_call('conversations.members', channel=id_, limit=5000, **kwargs)  # type: ignore
        response = load(r, Response)
        if not response.ok:
            raise ResponseException(response.error)

        newusers = load(r['members'], Set[str])

        # Generate all the Join events, if this is not the 1st iteration
        if id_ in self._get_members_cache:
            for i in newusers.difference(cached):
                self._internalevents.append(Join('member_joined_channel', user=i, channel=id_))

        self._get_members_cache[id_] = cached.union(newusers)
        self._get_members_cache_cursor[id_] = r.get('response_metadata', {}).get('next_cursor')
        return self._get_members_cache[id_]

    async def channels(self, refresh: bool = False) -> List[Channel]:
        """
        Returns the list of slack channels

        if refresh is set, the local cache is cleared
        """
        if refresh:
            self._channelscache.clear()

        if self._channelscache:
            return self._channelscache

        cursor = None
        while True:
            r = await self.client.api_call(
                'conversations.list',
                cursor=cursor,
                exclude_archived=True,
                types='public_channel,private_channel,mpim',
                limit=1000, # In vain hope that slack would not ignore this
            )
            response = load(r, Response)

            if response.ok:
                conv = load(r, Conversations)
                self._channelscache += conv.channels
                # For this API, slack sends an empty string as next cursor, just to show off their programming "skillz"
                if not conv.response_metadata or not conv.response_metadata.next_cursor:
                    break
                cursor = conv.response_metadata.next_cursor
            else:
                raise ResponseException(response.error)
        return self._channelscache

    async def get_channel(self, id_: str) -> Channel:
        """
        Returns a channel object from a slack channel id

        raises KeyError if it doesn't exist.
        """
        for i in range(2):
            for c in await self.channels(refresh=bool(i)):
                if c.id == id_:
                    return c
        raise KeyError()

    async def get_channel_by_name(self, name: str) -> Channel:
        """
        Returns a channel object from a slack channel id

        raises KeyError if it doesn't exist.
        """
        for i in range(2):
            for c in await self.channels(refresh=bool(i)):
                if c.name == name:
                    return c
        raise KeyError()

    async def get_thread(self, thread_ts: str, original_channel: str) -> MessageThread:
        """
        Creates a fake channel class for a chat thread
        """
        channel = (await self.get_channel(original_channel)).name_normalized

        # Get head message
        history = await self.get_history(original_channel, thread_ts, None, 1, True)

        msg = history.messages.pop()
        user = (await self.get_user(msg.user)).name if isinstance(msg, HistoryMessage) else 'bot'

        # Top message is a file
        if msg.text == '' and msg.files:
            f = msg.files[0]
            original_txt = f'{f.title} {f.mimetype} {f.url_private}'
        else:
            original_txt = msg.text.strip().replace('\n', ' | ')

        t = Topic(f'{user} in {channel}: {original_txt}')
        return MessageThread(
            id=original_channel,
            name_normalized=f'threaded-{thread_ts}',
            purpose=t,
            topic=t,
            thread_ts=thread_ts,
        )

    async def get_im(self, im_id: str) -> Optional[IM]:
        if not im_id.startswith('D'):
            return None
        for uid, imid in self._imcache.items():
            if im_id == imid:
                return IM(user=uid, id=imid)

        for im in await self.get_ims():
            self._imcache[im.user] = im.id
            if im.id == im_id:
                return im;
        return None

    async def get_ims(self) -> List[IM]:
        """
        Returns a list of the IMs

        Some bullshit slack invented because 1 to 1 conversations
        need to have an ID to send to, you can't send directly to
        a user.
        """
        r = await self.client.api_call(
            "conversations.list",
            exclude_archived=True,
            types='im', limit=1000
        )
        response = load(r, Response)
        if response.ok:
            return load(r['channels'], List[IM])
        raise ResponseException(response.error)

    async def get_user_by_name(self, name: str) -> User:
        return self._usermapcache[name]

    async def prefetch_users(self) -> None:
        """
        Prefetch all team members for the slack team.
        """
        r = await self.client.api_call("users.list")
        response = load(r, Response)
        if response.ok:
            for user in load(r['members'], List[User]):
                self._usercache[user.id] = user
                self._usermapcache[user.name] = user
            self._usermapcache_keys = list()

    async def get_user(self, id_: str) -> User:
        """
        Returns a user object from a slack user id

        raises KeyError if it does not exist
        """
        if id_ in self._usercache:
            return self._usercache[id_]

        r = await self.client.api_call("users.info", user=id_)
        response = load(r, Response)
        if response.ok:
            u = load(r['user'], User)
            self._usercache[id_] = u
            if u.name not in self._usermapcache:
                self._usermapcache_keys = list()
            self._usermapcache[u.name] = u
            return u
        else:
            raise KeyError(response)

    async def send_file(self, channel_id: str, filename: str) -> None:
        """
        Send a file to a channel or group or whatever
        """
        with open(filename, 'rb') as f:
            r = await self.client.api_call(
                'files.upload',
                channels=channel_id,
                file=f,
            )
        response = load(r, Response)
        if response.ok:
            return
        raise ResponseException(response.error)

    def _triage_sent_by_self(self) -> None:
        """
        Clear all the old leftovers in
        _sent_by_self
        """
        r = []
        for i in self._sent_by_self:
            if time() - i >= 10:
                r.append(i)
        for i in r:
            self._sent_by_self.remove(i)

    async def send_message(self, channel: Union[Channel, MessageThread], msg: str, action: bool) -> None:
        thread_ts = channel.thread_ts if isinstance(channel, MessageThread) else None
        return await self._send_message(channel.id, msg, action, thread_ts)

    async def _send_message(self, channel_id: str, msg: str, action: bool, thread_ts: Optional[str]) -> None:
        """
        Send a message to a channel or group or whatever
        """
        if action:
            api = 'chat.meMessage'
        else:
            api = 'chat.postMessage'

        try:
            kwargs = {}

            if thread_ts:
                kwargs['thread_ts'] = thread_ts

            self._wsblock += 1
            r = await self.client.api_call(
                api,
                channel=channel_id,
                text=msg,
                as_user=True,
                **kwargs,  # type: ignore
            )
            response = load(r, Response)
            if response.ok and response.ts:
                self._sent_by_self.add(response.ts)
                return
            raise ResponseException(response.error)
        finally:
            self._wsblock -= 1

    async def send_message_to_user(self, user: User, msg: str, action: bool):
        """
        Send a message to a user, pass the user id
        """

        # 1 to 1 chats are like channels, but use a dedicated API,
        # so to deliver a message to them, a channel id is required.
        # Those are called IM.

        if user.id in self._imcache:
            # channel id is cached
            channel_id = self._imcache[user.id]
        else:
            # Find the channel id
            found = False
            # Iterate over all the existing conversations
            for i in await self.get_ims():
                if i.user == user.id:
                    channel_id = i.id
                    found = True
                    break
            # A conversation does not exist, create one
            if not found:
                r = await self.client.api_call(
                    "im.open",
                    return_im=True,
                    user=user.id,
                )
                response = load(r, Response)
                if not response.ok:
                    raise ResponseException(response.error)
                channel_id = r['channel']['id']

            self._imcache[user.id] = channel_id

        await self._send_message(channel_id, msg, action, None)

    async def event(self) -> Optional[SlackEvent]:
        """
        This returns the events from the slack websocket
        """
        if self._internalevents:
            return self._internalevents.pop()

        try:
            events = await self.client.rtm_read()
        except Exception:
            events = []
            log('Connecting to slack...')
            self.login_info = await self.client.rtm_connect(5)
            await self._history()
            log('Connected to slack')
            return None

        while self._wsblock: # Retry until the semaphore is free
            await asyncio.sleep(0.01)

        for event in events:
            t = event.get('type')
            ts = float(event.get('ts', 0))

            if ts > self._status.last_timestamp:
                self._status.last_timestamp = ts

            if ts in self._sent_by_self:
                self._sent_by_self.remove(ts)
                continue

            if t in USELESS_EVENTS:
                continue

            debug(event)
            loadable_events = Union[TopicChange, MessageBot, MessageEdit, MessageDelete, GroupJoined, Join, Leave, UserTyping]
            try:
                ev: Optional[loadable_events] = load(
                    event,
                    loadable_events  # type: ignore
                )
            except Exception:
                ev = None

            if isinstance(ev, (Join, Leave)) and ev.channel in self._get_members_cache:
                if isinstance(ev, Join):
                    self._get_members_cache[ev.channel].add(ev.user)
                else:
                    self._get_members_cache[ev.channel].remove(ev.user)

            if ev:
                return ev

            subt = event.get('subtype')

            try:
                if t == 'message' and (not subt or subt == 'me_message'):
                    msg = load(event, Message)

                    # In private chats, pretend that my own messages
                    # sent from another client actually come from
                    # the other user, and prepend them with "I say: "
                    im = await self.get_im(msg.channel)
                    if im and im.user != msg.user:
                        msg = Message(user=im.user, text='I say: ' + msg.text, channel=im.id, thread_ts=msg.thread_ts)
                    if subt == 'me_message':
                        return ActionMessage(*msg)  # type: ignore
                    else:
                        return msg
                elif t == 'message' and subt == 'slackbot_response':
                    return load(event, Message)
                elif t == 'user_change':
                    # Changes in the user, drop it from cache
                    u = load(event['user'], User)
                    if u.id in self._usercache:
                        del self._usercache[u.id]
                        #FIXME don't know if it is wise, maybe it gets lost forever del self._usermapcache[u.name]
                    #TODO make an event for this
                else:
                    log(event)
            except Exception as e:
                log('Exception: %s' % e)
            self._triage_sent_by_self()
        return None
