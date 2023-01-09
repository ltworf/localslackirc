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
from enum import Enum
import logging
import re
import signal
import socket
import argparse
from typing import *
import os
from os import environ
from os.path import expanduser
import pwd
from socket import gethostname
import sys
import time


import slack
from log import *
import msgparsing
from diff import seddiff


VERSION = '1.18'


class IrcDisconnectError(Exception): ...


class Replies(Enum):
    RPL_LUSERCLIENT = 251
    RPL_USERHOST = 302
    RPL_UNAWAY = 305
    RPL_NOWAWAY = 306
    RPL_WHOISUSER = 311
    RPL_WHOISSERVER = 312
    RPL_WHOISOPERATOR = 313
    RPL_ENDOFWHO = 315
    RPL_WHOISIDLE = 317
    RPL_ENDOFWHOIS = 318
    RPL_WHOISCHANNELS = 319
    RPL_LIST = 322
    RPL_LISTEND = 323
    RPL_CHANNELMODEIS = 324
    RPL_TOPIC = 332
    RPL_WHOREPLY = 352
    RPL_NAMREPLY = 353
    RPL_ENDOFNAMES = 366
    ERR_NOSUCHNICK = 401
    ERR_NOSUCHCHANNEL = 403
    ERR_UNKNOWNCOMMAND = 421
    ERR_FILEERROR = 424
    ERR_ERRONEUSNICKNAME = 432


class Provider(Enum):
    SLACK = 0


#: Inactivity days to hide a MPIM
MPIM_HIDE_DELAY = datetime.timedelta(days=50)


class ClientSettings(NamedTuple):
    nouserlist: bool
    autojoin: bool
    provider: Provider
    ignored_channels: Set[bytes]
    silenced_yellers: Set[bytes]
    downloads_directory: Path
    formatted_max_lines: int = 0

    def verify(self) -> Optional[str]:
        '''
        Make sure that the configuration is correct.

        In that case return None. Otherwise an error string.
        '''
        if not self.downloads_directory.is_dir():
            return f'{self.downloads_directory} is not a directory'
        return None


class Client:
    def __init__(
                    self,
                    s: asyncio.streams.StreamWriter,
                    sl_client: slack.Slack,
                    settings: ClientSettings,

    ):
        self.nick = b''
        self.username = b''
        self.realname = b''
        self.parted_channels: Set[bytes] = settings.ignored_channels
        self.known_threads: dict[bytes, slack.MessageThread] = {}
        self.hostname = gethostname().encode('utf8')

        self.settings = settings
        self.s = s
        self.sl_client = sl_client
        self._usersent = False # Used to hold all events until the IRC client sends the initial USER message
        self._held_events: list[slack.SlackEvent] = []
        self._mentions_regex_cache: dict[str, Optional[re.Pattern]] = {}  # Cache for the regexp to perform mentions. Key is channel id
        self._annoy_users: dict[str, int] = {} # Users to annoy pretending to type when they type

    async def _nickhandler(self, cmd: bytes) -> None:
        if b' ' not in cmd:
            self.nick = b'localslackirc'
        else:
            _, nick = cmd.split(b' ', 1)
            self.nick = nick.strip()
        assert self.sl_client.login_info
        if self.nick != self.sl_client.login_info.self.name.encode('ascii'):
            await self._sendreply(Replies.ERR_ERRONEUSNICKNAME, 'Incorrect nickname, use %s' % self.sl_client.login_info.self.name)

    async def _sendreply(self, code: int|Replies, message: str|bytes, extratokens: Iterable[str|bytes] = []) -> None:
        codeint = code if isinstance(code, int) else code.value
        bytemsg = message if isinstance(message, bytes) else message.encode('utf8')

        extratokens = list(extratokens)

        extratokens.insert(0, self.nick)

        self.s.write(b':%s %03d %s :%s\r\n' % (
            self.hostname,
            codeint,
            b' '.join(i if isinstance(i, bytes) else i.encode('utf8') for i in extratokens),
            bytemsg,
        ))
        await self.s.drain()


    async def _userhandler(self, cmd: bytes) -> None:
        #TODO USER salvo 8 * :Salvatore Tomaselli
        assert self.sl_client.login_info
        await self._sendreply(1, 'Welcome to localslackirc')
        await self._sendreply(2, 'Your team name is: %s' % self.sl_client.login_info.team.name)
        await self._sendreply(2, 'Your team domain is: %s' % self.sl_client.login_info.team.domain)
        await self._sendreply(2, 'Your nickname must be: %s' % self.sl_client.login_info.self.name)
        await self._sendreply(2, f'Version: {VERSION}')
        await self._sendreply(Replies.RPL_LUSERCLIENT, 'There are 1 users and 0 services on 1 server')

        if self.settings.autojoin and not self.settings.nouserlist:
            # We're about to load many users for each chan; instead of requesting each
            # profile on its own, batch load the full directory.
            await self.sl_client.prefetch_users()

        if self.settings.autojoin:
            mpim_cutoff = datetime.datetime.utcnow() - MPIM_HIDE_DELAY

            for sl_chan in await self.sl_client.channels():
                if not sl_chan.is_member:
                    continue

                if sl_chan.is_mpim and (sl_chan.latest is None or sl_chan.latest.timestamp < mpim_cutoff):
                    continue

                channel_name = '#%s' % sl_chan.name_normalized
                if channel_name in self.ignored_channels:
                    logging.info(f'Not joining {channel_name} on IRC, marked as ignored')
                    continue
                await self._send_chan_info(channel_name_b, sl_chan)
        else:
            for sl_chan in await self.sl_client.channels():
                channel_name = '#%s' % sl_chan.name_normalized
                self.parted_channels.add(channel_name.encode('utf-8'))

        # Eventual channel joining done, sending the held events
        self._usersent = True
        for ev in self._held_events:
            await self.slack_event(ev)
        self._held_events = []

    async def _pinghandler(self, cmd: bytes) -> None:
        _, lbl = cmd.split(b' ', 1)
        self.s.write(b':%s PONG %s %s\r\n' % (self.hostname, self.hostname, lbl))
        await self.s.drain()

    async def _joinhandler(self, cmd: bytes) -> None:
        _, channel_names_b = cmd.split(b' ', 1)

        for channel_name_b in channel_names_b.split(b','):
            if channel_name_b in self.parted_channels:
                self.parted_channels.remove(channel_name_b)

            channel_name = channel_name_b[1:].decode()
            try:
                slchan = await self.sl_client.get_channel_by_name(channel_name)
            except Exception:
                await self._sendreply(Replies.ERR_NOSUCHCHANNEL, f'Unable to find channel: {channel_name}')
                continue

            if not slchan.is_member:
                try:
                    await self.sl_client.join(slchan)
                except Exception:
                    await self._sendreply(Replies.ERR_NOSUCHCHANNEL, f'Unable to join server channel: {channel_name}')

            try:
                await self._send_chan_info(channel_name_b, slchan)
            except Exception:
                await self._sendreply(Replies.ERR_NOSUCHCHANNEL, f'Unable to join channel: {channel_name}')

    async def _send_chan_info(self, channel_name: bytes, slchan: slack.Channel|slack.MessageThread):
        if not self.settings.nouserlist:
            l = await self.sl_client.get_members(slchan.id)

            userlist: list[bytes] = []
            for i in l:
                try:
                    u = await self.sl_client.get_user(i)
                except Exception:
                    continue
                if u.deleted:
                    # Disabled user, skip it
                    continue
                name = u.name.encode('utf8')
                prefix = b'@' if u.is_admin else b''
                userlist.append(prefix + name)

            users = b' '.join(userlist)
        try:
            yelldest = b'#' + (await self.sl_client.get_channel(slchan.id)).name.encode('utf8')
        except KeyError:
            yelldest = b''

        topic = (await self.parse_message(slchan.real_topic, b'', yelldest)).replace('\n', ' | ')
        self.s.write(b':%s!%s@127.0.0.1 JOIN %s\r\n' % (self.nick, self.nick, channel_name))
        await self.s.drain()
        await self._sendreply(Replies.RPL_TOPIC, topic, [channel_name])
        await self._sendreply(Replies.RPL_NAMREPLY, b'' if self.settings.nouserlist else users, ['=', channel_name])
        await self._sendreply(Replies.RPL_ENDOFNAMES, 'End of NAMES list', [channel_name])

    async def _privmsghandler(self, cmd: bytes) -> None:
        _, dest, msg = cmd.split(b' ', 2)
        if msg.startswith(b':'):
            msg = msg[1:]

        # Handle sending "/me does something"
        # b'PRIVMSG #much_private :\x01ACTION saluta tutti\x01'
        if msg.startswith(b'\x01ACTION ') and msg.endswith(b'\x01'):
            action = True
            _, msg = msg.split(b' ', 1)
            msg = msg[:-1]
        else:
            action = False

        if dest in self.known_threads:
            dest_object: slack.User|slack.Channel|slack.MessageThread = self.known_threads[dest]
        elif dest.startswith(b'#'):
            try:
                dest_object = await self.sl_client.get_channel_by_name(dest[1:].decode())
            except KeyError:
                await self._sendreply(Replies.ERR_NOSUCHCHANNEL, f'Unknown channel {dest.decode()}')
                return
        else:
            try:
                dest_object = await self.sl_client.get_user_by_name(dest.decode())
            except KeyError:
                await self._sendreply(Replies.ERR_NOSUCHNICK, f'Unknown user {dest.decode()}')
                return

        message = await self._addmagic(msg.decode('utf8'), dest_object)

        if isinstance(dest_object, slack.User):
            await self.sl_client.send_message_to_user(
                dest_object,
                message,
                action,
            )
        else:
            await self.sl_client.send_message(
                dest_object,
                message,
                action,
            )

    async def _listhandler(self, cmd: bytes) -> None:
        for c in await self.sl_client.channels(refresh=True):
            topic = (await self.parse_message(c.real_topic, b'', b'')).replace('\n', ' | ')
            await self._sendreply(Replies.RPL_LIST, topic, ['#' + c.name, str(c.num_members)])
        await self._sendreply(Replies.RPL_LISTEND, 'End of LIST')

    async def _modehandler(self, cmd: bytes) -> None:
        params = cmd.split(b' ', 2)
        await self._sendreply(Replies.RPL_CHANNELMODEIS, '', [params[1], '+'])

    async def _annoyhandler(self, cmd: bytes) -> None:
        params = cmd.split(b' ')
        params.pop(0)

        try:
            user = params.pop(0).decode('utf8')
            if params:
                duration = abs(int(params.pop()))
            else:
                duration = 10 # 10 minutes default
        except Exception:
            await self._sendreply(Replies.ERR_UNKNOWNCOMMAND, 'Syntax: /annoy user [duration]')
            return

        try:
            user_id = (await self.sl_client.get_user_by_name(user)).id
        except KeyError:
            await self._sendreply(Replies.ERR_NOSUCHCHANNEL, f'Unable to find user: {user}')
            return

        self._annoy_users[user_id] = int(time.time()) + (duration * 60)
        await self._sendreply(0, f'Will annoy {user} for {duration} minutes')

    async def _sendfilehandler(self, cmd: bytes) -> None:
        #/sendfile #destination filename
        params = cmd.split(b' ', 2)
        try:
            bchannel_name = params[1]
            channel_name = params[1].decode('utf8')
            filename = params[2].decode('utf8')
        except IndexError:
            await self._sendreply(Replies.ERR_UNKNOWNCOMMAND, 'Syntax: /sendfile #channel filename')
            return

        if bchannel_name in self.known_threads:
            dest_channel = self.known_threads[bchannel_name]
            dest = dest_channel.id
            thread_ts = dest_channel.thread_ts
        else:
            thread_ts = None
            try:
                if channel_name.startswith('#'):
                    dest = (await self.sl_client.get_channel_by_name(channel_name[1:])).id
                else:
                    dest = (await self.sl_client.get_user_by_name(channel_name)).id
            except KeyError:
                await self._sendreply(Replies.ERR_NOSUCHCHANNEL, f'Unable to find destination: {channel_name}')
                return

        try:
            await self.sl_client.send_file(dest, filename, thread_ts)
            await self._sendreply(0, 'Upload of %s completed' % filename)
        except Exception as e:
            await self._sendreply(Replies.ERR_FILEERROR, f'Unable to send file {e}')

    async def _parthandler(self, cmd: bytes) -> None:
        name = cmd.split(b' ')[1]
        self.parted_channels.add(name)

    async def _awayhandler(self, cmd: bytes) -> None:
        is_away = b' ' in cmd
        await self.sl_client.away(is_away)
        response = Replies.RPL_NOWAWAY if is_away else Replies.RPL_UNAWAY
        await self._sendreply(response, 'Away status changed')

    async def _topichandler(self, cmd: bytes) -> None:
        try:
            _, channel_b, topic_b = cmd.split(b' ', 2)
            channel_name = channel_b.decode()[1:]
            topic = topic_b.decode()[1:]
        except Exception as e:
            await self._sendreply(Replies.ERR_UNKNOWNCOMMAND, 'Error: %s' % e)
            return

        try:
            channel = await self.sl_client.get_channel_by_name(channel_name)
        except KeyError:
            await self._sendreply(Replies.ERR_NOSUCHCHANNEL, f'Unknown channel: {channel_name}')
            return

        try:
            await self.sl_client.topic(channel, topic)
        except Exception:
            await self._sendreply(Replies.ERR_UNKNOWNCOMMAND, f'Unable to set topic to {topic}')

    async def _whoishandler(self, cmd: bytes) -> None:
        users = cmd.split(b' ')
        del users[0]

        if len(users) != 1:
            await self._sendreply(Replies.ERR_UNKNOWNCOMMAND, 'Syntax: /whois nickname')
            return

        # Seems that oftc only responds to the last one
        username = users.pop()

        if b'*' in username:
            await self._sendreply(Replies.ERR_UNKNOWNCOMMAND, 'Wildcards are not supported')
            return
        uusername = username.decode()
        try:
            user = await self.sl_client.get_user_by_name(uusername)
        except KeyError:
            await self._sendreply(Replies.ERR_NOSUCHNICK, f'Unknown user {uusername}')
            return

        await self._sendreply(Replies.RPL_WHOISUSER, user.real_name, [username, '', 'localhost'])
        if user.profile.email:
            await self._sendreply(Replies.RPL_WHOISUSER, f'email: {user.profile.email}', [username, '', 'localhost'])
        if user.is_admin:
            await self._sendreply(Replies.RPL_WHOISOPERATOR, f'{uusername} is an IRC operator', [username])
        await self._sendreply(Replies.RPL_ENDOFWHOIS, '', extratokens=[username])

    async def _kickhandler(self, cmd: bytes) -> None:
        try:
            _, channel_b, username_b, message = cmd.split(b' ', 3)
            channel_name = channel_b.decode()[1:]
            username = username_b.decode()
        except Exception as e:
            await self._sendreply(Replies.ERR_UNKNOWNCOMMAND, 'Error: %s' % e)
            return

        try:
            channel = await self.sl_client.get_channel_by_name(channel_name)
        except KeyError:
            await self._sendreply(Replies.ERR_NOSUCHCHANNEL, f'Unknown channel: {channel_name}')
            return

        try:
            user = await self.sl_client.get_user_by_name(username)
        except KeyError:
            await self._sendreply(Replies.ERR_NOSUCHNICK, f'Unknown user: {username}')
            return

        try:
            await self.sl_client.kick(channel, user)
        except Exception as e:
            await self._sendreply(Replies.ERR_UNKNOWNCOMMAND, 'Error: %s' % e)

    async def _quithandler(self, cmd: bytes) -> None:
        raise IrcDisconnectError()

    async def _userhosthandler(self, cmd: bytes) -> None:
        nicknames = cmd.split(b' ')
        del nicknames[0] # Remove the command itself
        #TODO replace + with - in case of away
        #TODO append a * to the nickname for OP

        replies = (b'%s=+unknown' % i for i in nicknames)
        await self._sendreply(Replies.RPL_USERHOST, '', replies)

    async def _invitehandler(self, cmd: bytes) -> None:
        try:
            _, username_b, channel_b = cmd.split(b' ', 2)
            username = username_b.decode()
            channel_name = channel_b.decode()[1:]
        except Exception as e:
            await self._sendreply(Replies.ERR_UNKNOWNCOMMAND, 'Error: %s' % e)
            return

        try:
            channel = await self.sl_client.get_channel_by_name(channel_name)
        except KeyError:
            await self._sendreply(Replies.ERR_NOSUCHCHANNEL, f'Unknown channel: {channel_name}')
            return

        try:
            user = await self.sl_client.get_user_by_name(username)
        except KeyError:
            await self._sendreply(Replies.ERR_NOSUCHNICK, f'Unknown user: {username}')
            return

        try:
            await self.sl_client.invite(channel, user)
        except Exception as e:
            await self._sendreply(Replies.ERR_UNKNOWNCOMMAND, 'Error: %s' % e)

    async def _whohandler(self, cmd: bytes) -> None:
        _, name = cmd.split(b' ', 1)
        if not name.startswith(b'#'):
            try:
                user = await self.sl_client.get_user_by_name(name.decode())
            except KeyError:
                return
            await self._sendreply(Replies.RPL_WHOREPLY, '0 %s' % user.real_name, [name, user.name, '127.0.0.1', self.hostname, user.name, 'H'])
            return

        try:
            channel = await self.sl_client.get_channel_by_name(name.decode()[1:])
        except KeyError:
            return

        for i in await self.sl_client.get_members(channel.id):
            try:
                user = await self.sl_client.get_user(i)
                await self._sendreply(Replies.RPL_WHOREPLY, '0 %s' % user.real_name, [name, user.name, '127.0.0.1', self.hostname, user.name, 'H'])
            except Exception:
                pass
        await self._sendreply(Replies.RPL_ENDOFWHO, 'End of WHO list', [name])

    async def sendmsg(self, from_: bytes, to: bytes, message: bytes) -> None:
        self.s.write(b':%s!%s@127.0.0.1 PRIVMSG %s :%s\r\n' % (
            from_,
            from_,
            to, #private message, or a channel
            message,
        ))
        await self.s.drain()

    async def _get_regexp(self, dest: slack.User|slack.Channel) -> Optional[re.Pattern]:
        #del self._mentions_regex_cache[sl_ev.channel]
        # No nick substitutions for private chats
        if isinstance(dest, slack.User):
            return None

        dest_id = dest.id
        # Return from cache
        if dest_id in self._mentions_regex_cache:
            return self._mentions_regex_cache[dest_id]

        usernames = []
        for j in await self.sl_client.get_members(dest):
            u = await self.sl_client.get_user(j)
            usernames.append(u.name)

        if len(usernames) == 0:
            self._mentions_regex_cache[dest_id] = None
            return None

        # Extremely inefficient code to generate mentions
        # Just doing them client-side on the receiving end is too mainstream
        regexs = (r'((://\S*){0,1}\b%s\b)' % username for username in usernames)
        regex = re.compile('|'.join(regexs))
        self._mentions_regex_cache[dest_id] = regex
        return regex

    async def _addmagic(self, msg: str, dest: slack.User|slack.Channel) -> str:
        """
        Adds magic codes and various things to
        outgoing messages
        """
        for i in msgparsing.SLACK_SUBSTITUTIONS:
            msg = msg.replace(i[1], i[0])
        if self.settings.provider == Provider.SLACK:
            msg = msg.replace('@here', '<!here>')
            msg = msg.replace('@channel', '<!channel>')
            msg = msg.replace('@everyone', '<!everyone>')

        regex = await self._get_regexp(dest)
        if regex is None:
            return msg

        matches = list(re.finditer(regex, msg))
        matches.reverse() # I want to replace from end to start or the positions get broken
        for m in matches:
            username = m.string[m.start():m.end()]
            if username.startswith('://'):
                continue # Match inside a url
            elif self.settings.provider == Provider.SLACK:
                msg = msg[0:m.start()] + '<@%s>' % (await self.sl_client.get_user_by_name(username)).id + msg[m.end():]
        return msg

    async def parse_message(self, i: str, source: bytes, destination: bytes) -> str:
        """
        This converts a slack message into a message for IRC.

        It will replace mentions and shouts with the IRC equivalent.

        It will save preformatted text into txt files and link them
        if the settings are such.

        It will put the links at the end like with emails.
        """

        r = ''

        # Url replacing
        links = ''
        refs = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
        refn = 1

        for t in msgparsing.tokenize(i):
            if isinstance(t, str): # A normal nice string
                r += t
            elif isinstance(t, msgparsing.PreBlock): # Preformatted block
                # Store long formatted text into txt files
                if self.settings.formatted_max_lines and t.lines > self.settings.formatted_max_lines:
                    import tempfile
                    with tempfile.NamedTemporaryFile(
                            mode='wt',
                            dir=self.settings.downloads_directory,
                            suffix='.txt',
                            prefix='localslackirc-attachment-',
                            delete=False) as tmpfile:
                        tmpfile.write(t.txt)
                        r += f'\n === PREFORMATTED TEXT AT file://{tmpfile.name}\n'
                else: # Do not store to file
                    r += f'```{t.txt}```'
            elif isinstance(t, msgparsing.SpecialItem):
                if t.kind == msgparsing.Itemkind.MENTION: # User mention
                    r += (await self.sl_client.get_user(t.val)).name
                elif t.kind == msgparsing.Itemkind.CHANNEL: # Channel mention
                    r += '#' + (await self.sl_client.get_channel(t.val)).name_normalized
                elif t.kind == msgparsing.Itemkind.YELL: # Channel shouting
                    if (source not in self.settings.silenced_yellers) and (destination not in self.settings.silenced_yellers):
                         yell = ' [%s]:' % self.nick.decode('utf8')
                    else:
                        yell = ':'
                    if t.val == 'here':
                        r += 'yelling' + yell
                    elif t.val == 'channel':
                        r += 'YELLING LOUDER' + yell
                    else:
                        r += 'DEAFENING YELL' + yell
                else: # Link
                    label = t.human
                    if label is None:
                        r += t.val
                    else:
                        if '://' in label:
                            label = 'LINK'
                        ref = str(refn).translate(refs)
                        links += f'\n  {ref} {t.val}'
                        r += label + ref
                        refn += 1
        return r + links

    async def _messageedit(self, sl_ev: slack.MessageEdit) -> None:
        if not sl_ev.is_changed:
            return
        try:
            yelldest = b'#' + (await self.sl_client.get_channel(sl_ev.channel)).name.encode('utf8')
        except KeyError:
            yelldest = b''
        source = (await self.sl_client.get_user(sl_ev.previous.user)).name.encode('utf8')
        previous = await self.parse_message(sl_ev.previous.text, source, yelldest)
        current = await self.parse_message(sl_ev.current.text, source, yelldest)

        diffmsg = slack.Message(
            text=seddiff(sl_ev.previous.text, sl_ev.current.text),
            channel=sl_ev.channel,
            user=sl_ev.previous.user,
            thread_ts=sl_ev.previous.thread_ts
        )

        await self._message(diffmsg)

    async def _message(self, sl_ev: slack.Message|slack.MessageDelete|slack.MessageBot|slack.ActionMessage, prefix: str=''):
        """
        Sends a message to the irc client
        """
        if not isinstance(sl_ev, slack.MessageBot):
            source = (await self.sl_client.get_user(sl_ev.user)).name.encode('utf8')
        else:
            source = b'bot'

        try:
            yelldest = dest = b'#' + (await self.sl_client.get_channel(sl_ev.channel)).name.encode('utf8')
        except KeyError:
            dest = self.nick
            yelldest = b''
        except Exception as e:
            log('Error: ', str(e))
            return
        if dest in self.parted_channels:
            # Ignoring messages, channel was left on IRC
            return

        if sl_ev.thread_ts:
            # Threaded message
            thread = await self.sl_client.get_thread(sl_ev.thread_ts, sl_ev.channel)
            dest = b'#' + thread.name.encode('utf8')

            # Join thread channel if needed
            if dest not in self.known_threads or dest in self.parted_channels:
                if dest in self.parted_channels:
                    self.parted_channels.remove(dest)
                await self._send_chan_info(dest, self.known_threads.get(dest, thread))
                self.known_threads[dest] = self.known_threads.get(dest, thread)

        text = sl_ev.text

        if sl_ev.files:
            for f in sl_ev.files:
                text+=f'\n[file upload] {f.name}\n{f.mimetype} {f.size} bytes\n{f.url_private}'

        lines = (await self.parse_message(prefix + text, source, yelldest)).encode('utf-8')
        for i in lines.split(b'\n'):
            if not i:
                continue
            if isinstance(sl_ev, slack.ActionMessage):
                i = b'\x01ACTION ' + i + b'\x01'
            await self.sendmsg(
                source,
                dest,
                i
            )

    async def _joined_parted(self, sl_ev: slack.Join|slack.Leave, joined: bool) -> None:
        """
        Handle join events from slack, by sending a JOIN notification
        to IRC.
        """

        #Invalidate cache since the users in the channel changed
        if sl_ev.channel in self._mentions_regex_cache:
            del self._mentions_regex_cache[sl_ev.channel]

        user = await self.sl_client.get_user(sl_ev.user)
        if user.deleted:
            return
        channel = await self.sl_client.get_channel(sl_ev.channel)
        dest = b'#' + channel.name.encode('utf8')
        if dest in self.parted_channels:
            return
        name = user.name.encode('utf8')
        rname = user.real_name.replace(' ', '_').encode('utf8')
        if joined:
            self.s.write(b':%s!%s@127.0.0.1 JOIN :%s\r\n' % (name, rname, dest))
        else:
            self.s.write(b':%s!%s@127.0.0.1 PART %s\r\n' % (name, rname, dest))
        await self.s.drain()

    async def slack_event(self, sl_ev: slack.SlackEvent) -> None:
        if not self._usersent:
            self._held_events.append(sl_ev)
            return

        if isinstance(sl_ev, slack.MessageDelete):
            await self._message(sl_ev, '[deleted] ')
        elif isinstance(sl_ev, slack.Message):
            await self._message(sl_ev)
        elif isinstance(sl_ev, slack.ActionMessage):
            await self._message(sl_ev)
        elif isinstance(sl_ev, slack.MessageEdit):
            await self._messageedit(sl_ev)
        elif isinstance(sl_ev, slack.MessageBot):
            await self._message(sl_ev, '[%s] ' % sl_ev.username)
        elif isinstance(sl_ev, slack.Join):
            await self._joined_parted(sl_ev, True)
        elif isinstance(sl_ev, slack.Leave):
            await self._joined_parted(sl_ev, False)
        elif isinstance(sl_ev, slack.TopicChange):
            await self._sendreply(Replies.RPL_TOPIC, sl_ev.topic, ['#' + (await self.sl_client.get_channel(sl_ev.channel)).name])
        elif isinstance(sl_ev, slack.GroupJoined):
            channel_name = '#%s' % sl_ev.channel.name_normalized
            await self._send_chan_info(channel_name.encode('utf-8'), sl_ev.channel)
        elif isinstance(sl_ev, slack.UserTyping):
            if sl_ev.user not in self._annoy_users:
                return
            if time.time() > self._annoy_users[sl_ev.user]:
                del self._annoy_users[sl_ev.user]
                await self._sendreply(0, f'No longer annoying {(await self.sl_client.get_user(sl_ev.user)).name}')
                return
            await self.sl_client.typing(sl_ev.channel)


        if not line:
            return

        cmd, _, text = line.partition(' ')

    if token.startswith('xoxc-') and not cookie:
        exit('The cookie is needed for this kind of slack token')

    provider = Provider.SLACK

    # Parameters are dealt with

    async def listener(self, ip, port) -> None:
        loop = asyncio.get_running_loop()

        serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        serversocket.bind((ip, port))
        serversocket.listen(1)
        serversocket.setblocking(False)

        s, _ = await loop.sock_accept(serversocket)
        serversocket.close()
        self.reader, self.writer = await asyncio.open_connection(sock=s)

        try:
            await self.sl_client.login()
        except SlackConnectionError as e:
            logging.error('Unable to connect to slack: %s', e)
            await self.sendcmd(None, 'ERROR', f'Unable to connect to slack: {e}')
            self.writer.close()
            return

        self.hostname = '%s.slack.com' % self.sl_client.login_info.team.domain

        self.client = Client()
        self.client.hostname = self.hostname

        try:
            from_irc_task = asyncio.create_task(self.from_irc(self.reader))
            from_slack_task = asyncio.create_task(self.from_slack())

            await asyncio.gather(
                from_irc_task,
                from_slack_task,
            )
        except SlackConnectionError as e:
            await self.sendcmd(None, 'ERROR', f'Connection error with slack: {e}')
        finally:
            logging.info('Closing connections')
            self.writer.close()
            logging.info('Cancelling running tasks')
            from_irc_task.cancel()
            from_slack_task.cancel()
            self.client = None

    async def from_irc(self, reader):
        while True:
            try:
                cmd = await reader.readline()
            except Exception as e:
                logging.exception(e)
                raise IrcDisconnectError() from e

            if self.reader.at_eof():
                raise IrcDisconnectError()

            await self.irc_command(cmd.strip().decode('utf8'))

async def from_irc(reader, ircclient: Client):
    while True:
        try:
            cmd = await reader.readline()
        except Exception:
            raise IrcDisconnectError()
        await ircclient.command(cmd.strip())


async def to_irc(sl_client: slack.Slack, ircclient: Client):
    while True:
        ev = await sl_client.event()
        if ev:
            log(ev)
            await ircclient.slack_event(ev)


def term_f(*args):
    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
