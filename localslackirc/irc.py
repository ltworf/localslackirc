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
import socket
from pathlib import Path
import time
from typing import Set, Optional, NamedTuple

from localslackirc import msgparsing
from localslackirc import __version__
from localslackirc import slack
from .slackclient.exceptions import SlackConnectionError
from .diff import seddiff


class IrcDisconnectError(Exception):
    ...


class Replies(Enum):
    # https://defs.ircdocs.horse/defs/numerics.html
    RPL_WELCOME = 1
    RPL_YOURHOST = 2
    RPL_MYINFO = 4
    RPL_UMODEIS = 221
    RPL_LUSERCLIENT = 251
    RPL_LUSEROP = 252
    RPL_LUSERCHANNELS = 254
    RPL_AWAY = 301
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
    RPL_WHOISACCOUNT = 330
    RPL_NOTOPIC = 331
    RPL_TOPIC = 332
    RPL_WHOISBOT = 335 # or 336 or 617
    RPL_WHOISTEXT = 335
    RPL_WHOREPLY = 352
    RPL_NAMREPLY = 353
    RPL_ENDOFNAMES = 366
    RPL_ENDOFBANLIST = 368
    RPL_ENDOFWHOWAS = 369

    ERR_UNKNOWNERROR = 400
    ERR_NOSUCHNICK = 401
    ERR_NOSUCHCHANNEL = 403
    ERR_WASNOSUCHNICK = 406
    ERR_INVALIDCAPCMD = 410
    ERR_NOTEXTTOSEND = 412
    ERR_UNKNOWNCOMMAND = 421
    ERR_FILEERROR = 424
    ERR_ERRONEUSNICKNAME = 432
    ERR_NEEDMOREPARAMS = 461
    ERR_UNKNOWNMODE = 472
    ERR_UMODEUNKNOWNFLAG = 501
    RPL_WHOISSECURE = 671
    RPL_WHOISKEYVALUE = 760


#: Inactivity days to hide a MPIM
MPIM_HIDE_DELAY = datetime.timedelta(days=50)


class ServerSettings(NamedTuple):
    nouserlist: bool
    autojoin: bool
    thread_replies: bool
    ignored_channels: Set[str]
    silenced_yellers: Set[str]
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


def registered_command(func):
    async def inner(self, *args, **kwargs):
        if not self.client.is_registered:
            return await self.sendreply(451, 'You have not registered')
        return await func(self, *args, **kwargs)

    return inner


def parse_args(*args, minargs=None):
    if minargs is None:
        minargs = len(args)
    def decorator(func):
        async def inner(self, params):
            kwargs = {}
            for i, arg in enumerate(args):
                try:
                    kwargs[arg] = params[i+1]
                except IndexError:
                    if i >= minargs:
                        break
                    args_text = ''
                    for argc, arg in enumerate(args):
                        if argc >= minargs:
                            args_text += f' [{arg}]'
                        else:
                            args_text += f' {arg}'
                    return await self.sendreply(Replies.ERR_NEEDMOREPARAMS, params[0], f'Not enough parameters. Syntax: /{params[0]}{args_text}')

            return await func(self, **kwargs)

        return inner

    return decorator


class Client:
    nickname = ''
    username = ''
    realname = ''
    hostname = ''

    is_registered = False


class Server:
    def __init__(self, sl_client: slack.Slack, settings: ServerSettings):
        self.hostname = 'localhost'
        self.client = None
        self.ignored_channels: Set[str] = settings.ignored_channels
        self.channels = {}
        self.known_threads: dict[str, slack.MessageThread] = {}

        self.settings = settings
        self.sl_client = sl_client
        self.usersent = False # Used to hold all events until the IRC client sends the initial USER message
        self.held_events: list[slack.SlackEvent] = []
        self.mentions_regex_cache: dict[str, Optional[re.Pattern]] = {}  # Cache for the regexp to perform mentions. Key is channel id
        self.annoy_users: dict[str, int] = {} # Users to annoy pretending to type when they type

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

    async def from_slack(self):
        while True:
            ev = await self.sl_client.event()
            if ev:
                logging.debug(ev)
                await self.slack_event(ev)

    async def irc_command(self, line):
        logging.debug('R - ' + line)

        if not line:
            return

        cmd, _, text = line.partition(' ')

        args = []
        while text and not text.startswith(':'):
            arg, _, text = text.partition(' ')
            args.append(arg)

        if text.startswith(':'):
            args.append(text[1:])

        try:
            func = getattr(self, 'cmd_%s' % cmd.lower())
        except AttributeError:
            return await self.sendreply(Replies.ERR_UNKNOWNCOMMAND, cmd, 'Unknown command')
        else:
            try:
                return await func([cmd] + args)
            except IrcDisconnectError:
                raise
            except Exception as e:
                logging.exception(e)
                await self.sendreply(Replies.ERR_UNKNOWNERROR, cmd, f'Error: {e}')

    async def sendcmd(self, sender, cmd, *args):
        args_text = ''
        for arg in args[:-1]:
            args_text += ' %s' % arg

        if args:
            args_text += ' '
            if ' ' in args[-1] or args[-1].startswith(':'):
                args_text += ':'
            args_text += args[-1]

        if sender is self:
            sender_text = self.hostname
        elif isinstance(sender, Client):
            sender_text = f'{sender.nickname}!{sender.username}@{sender.hostname}'
        elif isinstance(sender, slack.User):
            sender_text = f'{sender.name}!{sender.id}@{self.hostname}'
        else:
            sender_text = sender

        line = ''
        if sender_text is not None:
            line = f':{sender_text} '
        line += f'{cmd}{args_text}'
        logging.debug('S - ' + line)
        self.writer.write(line.encode('utf8') + b'\r\n')
        await self.writer.drain()

    async def sendreply(self, code, *args):
        codeint = code if isinstance(code, int) else code.value

        return await self.sendcmd(self, '%03d' % codeint, self.client.nickname or '*', *args)

    @parse_args('username', 'mode', '_', 'realname')
    async def cmd_user(self, username, mode, _, realname):
        if self.client.is_registered:
            # If the user is already registered, the normal behavior is to
            # ignore a new USER command.
            return

        self.client.username = username
        self.client.realname = realname

        if self.client.username and self.client.nickname:
            await self.registered()

    @parse_args('nickname')
    async def cmd_nick(self, nickname):
        if not self.client.is_registered:
            self.client.nickname = nickname

            if self.client.username and self.client.nickname:
                await self.registered()
        elif nickname != self.sl_client.login_info.self.name:
            await self.sendreply(Replies.ERR_ERRONEUSNICKNAME, nickname, 'Incorrect nickname, use %s' % self.sl_client.login_info.self.name)

    async def registered(self):
        self.client.is_registered = True

        await self.sendreply(Replies.RPL_WELCOME, f'Welcome to the Slack Server {self.sl_client.login_info.team.name}, {self.client.nickname}!')
        await self.sendreply(Replies.RPL_YOURHOST, f'Your host is {self.hostname}, running version localslackirc-{__version__}')

        if self.settings.autojoin and not self.settings.nouserlist:
            # We're about to load many users for each chan; instead of requesting each
            # profile on its own, batch load the full directory.
            await self.sl_client.prefetch_users()

        await self.sendreply(Replies.RPL_LUSERCLIENT, 'There are %s users and %s bots on 1 server' % (await self.sl_client.count_regular_users(), await self.sl_client.count_bots()))
        await self.sendreply(Replies.RPL_LUSEROP, await self.sl_client.count_admins(), 'Slack Workspace Admins')

        # Prefetch channels list
        channels = await self.sl_client.channels()
        await self.sendreply(Replies.RPL_LUSERCHANNELS, len(channels), 'channels formed')

        if self.client.nickname != self.sl_client.login_info.self.name:
            await self.sendcmd(self.client, 'NICK', self.sl_client.login_info.self.name)
            self.client.nickname = self.sl_client.login_info.self.name

        if self.settings.autojoin:
            mpim_cutoff = datetime.datetime.utcnow() - MPIM_HIDE_DELAY

            for sl_chan in channels.values():
                if not sl_chan.is_member:
                    continue

                if sl_chan.is_mpim and (sl_chan.latest is None or sl_chan.latest.timestamp < mpim_cutoff):
                    continue

                channel_name = '#%s' % sl_chan.name_normalized
                if channel_name in self.ignored_channels:
                    logging.info(f'Not joining {channel_name} on IRC, marked as ignored')
                    continue
                await self.join_channel(channel_name, sl_chan)
        else:
            for sl_chan in channels.values():
                channel_name = '#%s' % sl_chan.name_normalized
                self.ignored_channels.add(channel_name)

        # Eventual channel joining done, sending the held events
        self._usersent = True
        for ev in self.held_events:
            await self.slack_event(ev)
        self.held_events = []

    @parse_args('message', minargs=0)
    async def cmd_quit(self, message: str = None) -> None:
        raise IrcDisconnectError()

    @registered_command
    @parse_args('token', minargs=0)
    async def cmd_ping(self, token: str = '') -> None:
        await self.sendcmd(self, 'PONG', self.hostname, token)

    @parse_args('cmd')
    async def cmd_cap(self, cmd):
        if cmd == 'LS':
            return await self.sendcmd(self, 'CAP', '*', 'LS', '')
        if cmd == 'END':
            return

        await self.sendreply(Replies.ERR_INVALIDCAPCMD, '*', cmd, 'Invalid CAP subcommand')

    async def get_regexp(self, dest: slack.User|slack.Channel) -> Optional[re.Pattern]:
        #del self.mentions_regex_cache[sl_ev.channel]
        # No nick substitutions for private chats
        if isinstance(dest, slack.User):
            return None

        dest_id = dest.id
        # Return from cache
        if dest_id in self.mentions_regex_cache:
            return self.mentions_regex_cache[dest_id]

        usernames = []
        for j in await self.sl_client.get_members(dest):
            u = await self.sl_client.get_user(j)
            usernames.append(u.name)

        if len(usernames) == 0:
            self.mentions_regex_cache[dest_id] = None
            return None

        # Extremely inefficient code to generate mentions
        # Just doing them client-side on the receiving end is too mainstream
        regexs = (r'((://\S*){0,1}\b%s\b)' % username for username in usernames)
        regex = re.compile('|'.join(regexs))
        self.mentions_regex_cache[dest_id] = regex
        return regex

    async def addmagic(self, msg: str, dest: slack.User|slack.Channel) -> str:
        """
        Adds magic codes and various things to
        outgoing messages
        """
        for i in msgparsing.SLACK_SUBSTITUTIONS:
            msg = msg.replace(i[1], i[0])

        msg = msg.replace('@here', '<!here>')
        msg = msg.replace('@channel', '<!channel>')
        msg = msg.replace('@everyone', '<!everyone>')

        regex = await self.get_regexp(dest)
        if regex is None:
            return msg

        matches = list(re.finditer(regex, msg))
        matches.reverse() # I want to replace from end to start or the positions get broken
        for m in matches:
            username = m.string[m.start():m.end()]
            if username.startswith('://'):
                continue # Match inside a url

            msg = msg[0:m.start()] + '<@%s>' % (await self.sl_client.get_user_by_name(username)).id + msg[m.end():]

        return msg

    @registered_command
    @parse_args('dest', 'msg')
    async def cmd_privmsg(self, dest: str, msg: str):
        if not msg:
            return await self.sendreply(Replies.ERR_NOTEXTTOSEND, 'No text to send')

        # Handle sending "/me does something"
        # b'PRIVMSG #much_private :\x01ACTION saluta tutti\x01'
        if msg.startswith('\x01ACTION ') and msg.endswith('\x01'):
            action = True
            _, msg = msg.split(' ', 1)
            msg = msg[:-1]
        else:
            action = False

        if dest in self.known_threads:
            dest_object: slack.User|slack.Channel|slack.MessageThread = self.known_threads[dest]
        elif dest.startswith('#'):
            try:
                dest_object = await self.sl_client.get_channel_by_name(dest[1:])
            except KeyError:
                return await self.sendreply(Replies.ERR_NOSUCHCHANNEL, dest, 'No such channel')
        else:
            try:
                dest_object = await self.sl_client.get_user_by_name(dest)
            except KeyError:
                return await self.sendreply(Replies.ERR_NOSUCHNICK, dest, 'No such nick')

        message = await self.addmagic(msg, dest_object)

        if isinstance(dest_object, slack.User):
            try:
                await self.sl_client.send_message_to_user(dest_object, message, action)
            except slack.ResponseException as e:
                await self.sendreply(Replies.ERR_NOSUCHNICK, dest, f'Unable to send message: {e}')
            if not dest_object.is_bot and await self.sl_client.is_user_away(dest_object):
                await self.sendreply(Replies.RPL_AWAY, dest, dest_object.profile.status_text or 'Away')
        else:
            try:
                await self.sl_client.send_message(dest_object, message, action)
            except slack.ResponseException as e:
                await self.sendreply(Replies.ERR_NOSUCHCHANNEL, dest, f'Unable to send message: {e}')

    @registered_command
    async def cmd_list(self, _) -> None:
        for c in (await self.sl_client.channels(refresh=True)).values():
            topic = (await self.parse_slack_message(c.real_topic, '', '')).replace('\n', ' | ')
            await self.sendreply(Replies.RPL_LIST, '#' + c.name, str(c.num_members), topic)

        await self.sendreply(Replies.RPL_LISTEND, 'End of LIST')

    @registered_command
    @parse_args('channel', 'modes', minargs=1)
    async def cmd_mode(self, channel: str, modes: str = None) -> None:
        if channel.startswith('#'):
            if modes:
                for mode in modes:
                    if mode == 'b':
                        return await self.sendreply(Replies.RPL_ENDOFBANLIST, channel, 'End of Channel Ban List')
                    if mode not in ('+', '-'):
                        return await self.sendreply(Replies.ERR_UNKNOWNMODE, mode, 'is an unknown mode char to me')
            else:
                await self.sendreply(Replies.RPL_CHANNELMODEIS, channel, '+')
        else:
            if modes:
                await self.sendreply(Replies.ERR_UMODEUNKNOWNFLAG, 'Unknown MODE flag')
            else:
                await self.sendreply(Replies.RPL_UMODEIS, channel, '+')

    @registered_command
    @parse_args('user', 'duration', minargs=1)
    async def cmd_annoy(self, user: str, duration: str = None) -> None:
        try:
            if duration:
                duration = abs(int(duration))
            else:
                duration = 10 # 10 minutes default
        except ValueError:
            await self.sendreply(Replies.ERR_NEEDMOREPARAMS, 'Syntax: /annoy user [duration]')
            return

        try:
            user_id = (await self.sl_client.get_user_by_name(user)).id
        except KeyError:
            return await self.sendreply(Replies.ERR_NOSUCHNICK, user, 'No such nick')

        self.annoy_users[user_id] = int(time.time()) + (duration * 60)
        await self.sendcmd(self, 'NOTICE', self.client.nickname, f'Will annoy {user} for {duration} minutes')

    @registered_command
    @parse_args('channel_name', 'filename')
    async def cmd_sendfile(self, channel_name: str, filename: str) -> None:
        if channel_name in self.known_threads:
            dest_channel = self.known_threads[channel_name]
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
                return await self.sendreply(Replies.ERR_NOSUCHCHANNEL, channel_name, 'No such nick/channel')

        try:
            await self.sl_client.send_file(dest, filename, thread_ts)
            await self.sendcmd(self, 'NOTICE', self.client.nickname, 'Upload of %s completed' % filename)
        except FileNotFoundError as e:
            await self.sendreply(Replies.ERR_FILEERROR, str(e))
        except slack.ResponseException as e:
            await self.sendreply(Replies.ERR_FILEERROR, f'Unable to send file {e}')

    @registered_command
    @parse_args('channel_name', 'message', minargs=1)
    async def cmd_part(self, channel_name: str, message: str = '') -> None:
        self.ignored_channels.add(channel_name)
        await self.sendcmd(self.client, 'PART', channel_name, message)

    @registered_command
    @parse_args('message', minargs=0)
    async def cmd_away(self, message: str = None) -> None:
        if message:
            await self.sl_client.away(True)
            await self.sendreply(Replies.RPL_NOWAWAY, 'You have been marked as being away')
        else:
            await self.sl_client.away(False)
            await self.sendreply(Replies.RPL_UNAWAY, 'You are no longer marked as being away')

    @registered_command
    @parse_args('channel_name', 'topic', minargs=1)
    async def cmd_topic(self, channel_name: str, topic: str = None) -> None:
        if not channel_name.startswith('#'):
            return await self.sendreply(Replies.ERR_NOSUCHCHANNEL, channel_name, 'No such channel')

        try:
            channel = await self.sl_client.get_channel_by_name(channel_name[1:])
        except KeyError:
            return await self.sendreply(Replies.ERR_NOSUCHCHANNEL, channel_name, 'No such channel')

        if not topic:
            topic = (await self.parse_slack_message(channel.real_topic, '', channel_name)).replace('\n', ' | ')
            if topic:
                return await self.sendreply(Replies.RPL_TOPIC, channel_name, channel.topic.value)
            else:
                return await self.sendreply(Replies.RPL_NOTOPIC, channel_name, 'No topic is set.')

        try:
            await self.sl_client.topic(channel, topic)
        except slack.ResponseException as e:
            await self.sendreply(Replies.ERR_UNKNOWNCOMMAND, f'Unable to set topic to {topic}: {e}')

    @registered_command
    @parse_args('nickname')
    async def cmd_whowas(self, nickname: str) -> None:
        await self.sendreply(Replies.ERR_WASNOSUCHNICK, nickname, 'There was no such nickname')
        await self.sendreply(Replies.RPL_ENDOFWHOWAS, nickname, 'End of WHOWAS')

    @registered_command
    @parse_args('nickname')
    async def cmd_whois(self, nickname: str) -> None:
        if '*' in nickname:
            return await self.sendreply(Replies.ERR_UNKNOWNCOMMAND, 'Wildcards are not supported')

        try:
            user = await self.sl_client.get_user_by_name(nickname)
        except KeyError:
            return await self.sendreply(Replies.ERR_NOSUCHNICK, nickname, 'No such nick')

        await self.sendreply(Replies.RPL_WHOISUSER, nickname, user.id, self.hostname, '*', user.real_name)

        # Profile information
        if user.profile.title:
            await self.sendreply(Replies.RPL_WHOISOPERATOR, nickname, user.profile.title)
        if user.profile.email:
            await self.sendreply(Replies.RPL_WHOISACCOUNT, nickname, user.profile.email, 'email')
        if user.profile.phone:
            await self.sendreply(Replies.RPL_WHOISACCOUNT, nickname, user.profile.phone.replace(' ', ''), 'phone')
        if user.profile.image_original:
            await self.sendreply(Replies.RPL_WHOISACCOUNT, nickname, user.profile.image_original, 'avatar')

        # Display common channels
        channels = []
        for chan in (await self.sl_client.channels(refresh=False)).values():
            if user.id in await self.sl_client.get_members(chan, refresh=False):
                channels.append(f'#{chan.name}')
        if channels:
            await self.sendreply(Replies.RPL_WHOISCHANNELS, nickname, ' '.join(channels))

        await self.sendreply(Replies.RPL_WHOISSERVER, nickname, self.hostname, self.sl_client.login_info.team.name)

        # Do not display 'Away' status for bots and apps
        if user.is_bot:
            await self.sendreply(Replies.RPL_WHOISBOT, nickname, 'is a bot')
        elif user.is_app_user:
            await self.sendreply(Replies.RPL_WHOISBOT, nickname, 'is an App')
        elif await self.sl_client.is_user_away(user) or user.profile.status_text:
            await self.sendreply(Replies.RPL_AWAY, nickname, user.profile.status_text or 'Away')

        # Privileges
        if user.is_owner:
            await self.sendreply(Replies.RPL_WHOISOPERATOR, nickname, 'is a Workspace Owner')
        elif user.is_admin:
            await self.sendreply(Replies.RPL_WHOISOPERATOR, nickname, 'is a Workspace Admin')

        if user.has_2fa:
            await self.sendreply(Replies.RPL_WHOISSECURE, nickname, 'is using 2FA')

        # Not really idle time, but last user edit
        await self.sendreply(Replies.RPL_WHOISIDLE, nickname, int(time.time() - user.updated), 'seconds idle')

        await self.sendreply(Replies.RPL_ENDOFWHOIS, nickname, 'End of /WHOIS list.')

    @registered_command
    @parse_args('channel_name', 'nickname', 'message', minargs=2)
    async def cmd_kick(self, channel_name: str, nickname: str, message: str = None) -> None:
        try:
            channel = await self.sl_client.get_channel_by_name(channel_name[1:])
        except KeyError:
            return await self.sendreply(Replies.ERR_NOSUCHCHANNEL, channel_name, 'No such channel')

        try:
            user = await self.sl_client.get_user_by_name(nickname)
        except KeyError:
            return await self.sendreply(Replies.ERR_NOSUCHNICK, nickname, 'No such nick')

        try:
            await self.sl_client.kick(channel, user)
        except slack.ResponseException as e:
            await self.sendreply(Replies.ERR_UNKNOWNCOMMAND, 'Error: %s' % e)

    @registered_command
    async def cmd_userhost(self, args: list[str]) -> None:
        nicknames = args[1:]

        replies = []
        for nickname in nicknames:
            try:
                user = await self.sl_client.get_user_by_name(nickname)
            except KeyError:
                continue

            admin = '*' if user.is_admin else ''
            away = '-' if await self.sl_client.is_user_away(user) else '+'
            replies.append(f'{nickname}{admin}={away}{self.hostname}')

        await self.sendreply(Replies.RPL_USERHOST, ' '.join(replies))

    @registered_command
    @parse_args('nickname', 'channel_name')
    async def cmd_invite(self, nickname: str, channel_name: str) -> None:
        try:
            channel = await self.sl_client.get_channel_by_name(channel_name[1:])
        except KeyError:
            return await self.sendreply(Replies.ERR_NOSUCHCHANNEL, channel_name, 'No such channel')

        try:
            user = await self.sl_client.get_user_by_name(nickname)
        except KeyError:
            return await self.sendreply(Replies.ERR_NOSUCHNICK, nickname, 'No such nick')

        try:
            await self.sl_client.invite(channel, user)
        except slack.ResponseException as e:
            await self.sendreply(Replies.ERR_UNKNOWNCOMMAND, f'Error: {e}')

    @registered_command
    @parse_args('name')
    async def cmd_who(self, name: str) -> None:
        if not name.startswith('#'):
            try:
                user = await self.sl_client.get_user_by_name(name)
            except KeyError:
                return await self.sendreply(Replies.RPL_ENDOFWHO, name, 'End of WHO list')

            await self.sendreply(Replies.RPL_WHOREPLY, name, user.name, self.hostname, self.hostname, user.name, 'H', '0 %s' % user.real_name)
        else:
            try:
                channel = await self.sl_client.get_channel_by_name(name[1:])
            except KeyError:
                return await self.sendreply(Replies.RPL_ENDOFWHO, name, 'End of WHO list')

            for i in await self.sl_client.get_members(channel.id):
                try:
                    user = await self.sl_client.get_user(i)
                except slack.ResponseException:
                    pass
                else:
                    await self.sendreply(Replies.RPL_WHOREPLY, name, user.name, self.hostname, self.hostname, user.name, 'H', '0 %s' % user.real_name)
        await self.sendreply(Replies.RPL_ENDOFWHO, name, 'End of WHO list')

    @registered_command
    @parse_args('channels')
    async def cmd_join(self, channels: str) -> None:
        for channel_name in channels.split(','):
            if channel_name in self.ignored_channels:
                self.ignored_channels.remove(channel_name)

            try:
                slchan = await self.sl_client.get_channel_by_name(channel_name[1:])
            except KeyError:
                await self.sendreply(Replies.ERR_NOSUCHCHANNEL, channel_name, 'No such channel')
                continue

            if not slchan.is_member:
                try:
                    await self.sl_client.join(slchan)
                except slack.ResponseException as e:
                    await self.sendreply(Replies.ERR_NOSUCHCHANNEL, channel_name, f'Unable to join server channel: {e}')

            await self.join_channel(channel_name, slchan)

    async def join_channel(self, channel_name: str, slchan: slack.Channel|slack.MessageThread):
        if not self.settings.nouserlist:
            l = await self.sl_client.get_members(slchan.id)

            userlist: list[str] = []
            for i in l:
                try:
                    u = await self.sl_client.get_user(i)
                except KeyError:
                    continue
                if u.deleted:
                    # Disabled user, skip it
                    continue
                name = u.name
                prefix = '@' if u.is_admin else ''
                userlist.append(prefix + name)

            users = ' '.join(userlist)

        try:
            yelldest = '#' + (await self.sl_client.get_channel(slchan.id)).name
        except KeyError:
            yelldest = ''

        topic = (await self.parse_slack_message(slchan.real_topic, '', yelldest)).replace('\n', ' | ')
        await self.sendcmd(self.client, 'JOIN', channel_name)
        await self.sendcmd(self, 'MODE', channel_name, '+')
        await self.sendreply(Replies.RPL_TOPIC, channel_name, topic)
        await self.sendreply(Replies.RPL_NAMREPLY, '=', channel_name, '' if self.settings.nouserlist else users)
        await self.sendreply(Replies.RPL_ENDOFNAMES, channel_name, 'End of NAMES list')

    async def parse_slack_message(self, i: str, source: str, destination: str) -> str:
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
                         yell = ' [%s]:' % self.client.nickname
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

    async def send_message_edit(self, sl_ev: slack.MessageEdit) -> None:
        if not sl_ev.is_changed:
            return

        diffmsg = slack.Message(
            subtype = sl_ev.current.subtype,
            text=seddiff(sl_ev.previous.text, sl_ev.current.text),
            channel=sl_ev.channel,
            user=sl_ev.previous.user,
            thread_ts=sl_ev.previous.thread_ts,
            username=sl_ev.username
        )

        await self.send_message(diffmsg)

    async def send_message_delete(self, sl_ev: slack.MessageDelete) -> None:
        msg = slack.Message(
            subtype = sl_ev.previous.subtype,
            text=f'[deleted] {sl_ev.previous.text}',
            channel=sl_ev.channel,
            user=sl_ev.previous.user,
            thread_ts=sl_ev.previous.thread_ts,
            username=sl_ev.username
        )

        await self.send_message(msg)

    async def send_message(self, sl_ev: slack.Message|slack.MessageBot, prefix: str = ''):
        """
        Sends a message to the irc client
        """
        if sl_ev.subtype in ('channel_join', 'channel_leave'):
            return

        if sl_ev.username:
            source = sl_ev.username
        elif sl_ev.user:
            source = (await self.sl_client.get_user(sl_ev.user)).name
        else:
            source = 'bot'

        text = sl_ev.text

        try:
            yelldest = dest = '#' + (await self.sl_client.get_channel(sl_ev.channel)).name
        except KeyError:
            im = await self.sl_client.get_im(sl_ev.channel)
            if im and im.user != sl_ev.user:
                source = (await self.sl_client.get_user(im.user)).name
                text = f'I say: {text}'

            dest = self.client.nickname
            yelldest = ''
        except slack.ResponseException as e:
            logging.error('Error: %s', str(e))
            return

        if dest in self.ignored_channels:
            # Ignoring messages, channel was left on IRC
            return

        if sl_ev.files:
            for f in sl_ev.files:
                text += f'\n[file upload] {f.name}\n{f.mimetype} {f.size} bytes\n{f.url_private}'

        lines = (await self.parse_slack_message(prefix + text, source, yelldest))

        if sl_ev.thread_ts:
            # Threaded message, only for chans
            thread = await self.sl_client.get_thread(sl_ev.thread_ts, sl_ev.channel, source)

            if self.settings.thread_replies:
                messages = await self.sl_client.get_thread_history(sl_ev.channel, sl_ev.thread_ts)
                latest_message = await self.parse_slack_message(messages[-2].text, source, yelldest)
                lines = f'> {latest_message}\n{lines}'
            else:
                dest = '#' + thread.name

                if dest in self.ignored_channels:
                    return

                # Join thread channel if needed
                if dest not in self.known_threads:
                    await self.join_channel(dest, thread)
                    self.known_threads[dest] = thread

        for i in lines.split('\n'):
            if not i:
                continue
            if sl_ev.is_action:
                i = '\x01ACTION ' + i + '\x01'

            await self.sendcmd(f'{source}!{source}@{self.hostname}', 'PRIVMSG', dest, i)

    async def member_joined_or_left(self, sl_ev: slack.Join|slack.Leave, joined: bool) -> None:
        """
        Handle join events from slack, by sending a JOIN notification
        to IRC.
        """

        #Invalidate cache since the users in the channel changed
        if sl_ev.channel in self.mentions_regex_cache:
            del self.mentions_regex_cache[sl_ev.channel]

        user = await self.sl_client.get_user(sl_ev.user)
        if user.deleted:
            return

        channel = '#' + (await self.sl_client.get_channel(sl_ev.channel)).name
        if channel in self.ignored_channels:
            return

        if joined:
            await self.sendcmd(user, 'JOIN', channel)
        else:
            await self.sendcmd(user, 'PART', channel)

    async def topic_changed(self, sl_ev: slack.TopicChange) -> None:
        user = await self.sl_client.get_user(sl_ev.user)
        channel = '#' + (await self.sl_client.get_channel(sl_ev.channel, refresh=True)).name

        if channel in self.ignored_channels:
            return

        await self.sendcmd(user, 'TOPIC', channel, sl_ev.topic)

    async def slack_event(self, sl_ev: slack.SlackEvent) -> None:
        if not self.client.is_registered:
            self.held_events.append(sl_ev)
            return

        if isinstance(sl_ev, slack.Message):
            await self.send_message(sl_ev)
        elif isinstance(sl_ev, slack.MessageDelete):
            await self.send_message_delete(sl_ev)
        elif isinstance(sl_ev, slack.MessageEdit):
            await self.send_message_edit(sl_ev)
        elif isinstance(sl_ev, slack.MessageBot):
            await self.send_message(sl_ev, f'[{sl_ev.username}] ')
        elif isinstance(sl_ev, slack.Join):
            await self.member_joined_or_left(sl_ev, True)
        elif isinstance(sl_ev, slack.Leave):
            await self.member_joined_or_left(sl_ev, False)
        elif isinstance(sl_ev, slack.TopicChange):
            await self.topic_changed(sl_ev)
        elif isinstance(sl_ev, slack.GroupJoined):
            channel_name = '#' + sl_ev.channel.name_normalized
            await self.join_channel(channel_name, sl_ev.channel)
        elif isinstance(sl_ev, slack.UserTyping):
            if sl_ev.user not in self.annoy_users:
                return
            if time.time() > self.annoy_users[sl_ev.user]:
                del self.annoy_users[sl_ev.user]
                await self.sendcmd(self, 'NOTICE', self.client.nickname, f'No longer annoying {(await self.sl_client.get_user(sl_ev.user)).name}')
                return
            await self.sl_client.typing(sl_ev.channel)
