#!/usr/bin/env python3
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

import re
import select
import socket
import argparse
from typing import *
from os.path import expanduser

import slack


# How slack expresses mentioning users
_MENTIONS_REGEXP = re.compile(r'<@([0-9A-Za-z]+)>')


class Client:
    def __init__(self, s, sl_client, nouserlist):
        self.nick = b''
        self.username = b''
        self.realname = b''

        self.s = s
        self.sl_client = sl_client
        
        self.nouserlist = nouserlist

    def _nickhandler(self, cmd: bytes) -> None:
        _, nick = cmd.split(b' ', 1)
        self.nick = nick.strip()

    def _userhandler(self, cmd: bytes) -> None:
        #TODO USER salvo 8 * :Salvatore Tomaselli
        self.s.send(b':serenity 001 %s :Hi, welcome to IRC\n' % self.nick)
        self.s.send(b':serenity 002 %s :Your host is serenity, running version miniircd-1.2.1\n' % self.nick)
        self.s.send(b':serenity 003 %s :This server was created sometime\n' % self.nick)
        self.s.send(b':serenity 004 %s serenity miniircd-1.2.1 o o\n' % self.nick)
        self.s.send(b':serenity 251 %s :There are 1 users and 0 services on 1 server\n' % self.nick)

    def _pinghandler(self, cmd: bytes) -> None:
        _, lbl = cmd.split(b' ', 1)
        self.s.send(b':serenity PONG serenity %s\n' % lbl)

    def _joinhandler(self, cmd: bytes) -> None:
        _, channel_name = cmd.split(b' ', 1)

        try:
            slchan = self.sl_client.get_channel_by_name(channel_name[1:].decode())
        except:
            return
        userlist = []  # type List[bytes]
        for i in self.sl_client.get_members(slchan.id):
            try:
                u = self.sl_client.get_user(i)
            except:
                continue
            name = u.name.encode('utf8')
            prefix = b'@' if u.is_admin else b''
            userlist.append(prefix + name)

        users = b' '.join(userlist)

        self.s.send(b':%s!salvo@127.0.0.1 JOIN %s\n' % (self.nick, channel_name))
        self.s.send(b':serenity 331 %s %s :%s\n' % (self.nick, channel_name, slchan.real_topic.encode('utf8')))
        self.s.send(b':serenity 353 %s = %s :%s\n' % (self.nick, channel_name, b'' if self.nouserlist else users))
        self.s.send(b':serenity 366 %s %s :End of NAMES list\n' % (self.nick, channel_name))

    def _privmsghandler(self, cmd: bytes) -> None:
        _, dest, msg = cmd.split(b' ', 2)
        msg = msg[1:]
        message = self._addmagic(msg.decode('utf8'))

        if dest.startswith(b'#'):
            self.sl_client.send_message(
                self.sl_client.get_channel_by_name(dest[1:].decode()).id,
                message
            )
        else:
            try:
                self.sl_client.send_message_to_user(
                    self.sl_client.get_user_by_name(dest.decode()).id,
                    message
                )
            except:
                print('Impossible to find user ', dest)

    def _listhandler(self, cmd: bytes) -> None:
        for c in self.sl_client.channels():
            self.s.send(b':serenity 322 %s %s %d :%s\n' % (
                self.nick,
                b'#' + c.name.encode('utf8'),
                c.num_members,
                c.real_topic.encode('utf8'),
            ))
        self.s.send(b':serenity 323 %s :End of LIST\n' % self.nick)

    def _modehandler(self, cmd: bytes) -> None:
        params = cmd.split(b' ', 2)
        self.s.send(b':serenity 324 %s %s +\n' % (self.nick, params[1]))

    def _whohandler(self, cmd: bytes) -> None:
        _, name = cmd.split(b' ', 1)
        if not name.startswith(b'#'):
            print('WHO not supported on ', name)
            return
        channel = self.sl_client.get_channel_by_name(name.decode()[1:])
        if not self.nouserlist:
            for i in self.sl_client.get_members(channel.id):
                user = self.sl_client.get_user(i)
                self.s.send(b':serenity 352 %s %s 127.0.0.1 serenity %s H :0 %s\n' % (
                    self.nick,
                    name,
                    user.name.encode('utf8'),
                    user.real_name.encode('utf8'),
                ))
        self.s.send(b':serenity 315 %s %s :End of WHO list\n' % (self.nick, name))

    def sendmsg(self, from_: bytes, to: bytes, message: bytes) -> None:
        self.s.send(b':%s!salvo@127.0.0.1 PRIVMSG %s :%s\n' % (
            from_,
            to, #private message, or a channel
            message,
        ))

    def _addmagic(self, msg: str) -> str:
        """
        Adds magic codes and various things to
        outgoing messages
        """
        msg = msg.replace('@here', '<!here>')
        msg = msg.replace('@channel', '<!channel>')
        msg = msg.replace('@yell', '<!channel>')
        msg = msg.replace('@shout', '<!channel>')
        msg = msg.replace('@attention', '<!channel>')

        # Extremely inefficient code to generate mentions
        # Just doing them client-side on the receiving end is too mainstream
        for username in self.sl_client.get_usernames():
            if username in msg:
                msg = msg.replace(
                    username,
                    '<@%s>' % self.sl_client.get_user_by_name(username).id
                )
        return msg

    def parse_message(self, msg: str) -> Iterator[bytes]:
        for i in msg.split('\n'):
            if not i:
                continue

            # Replace all mentions with @user
            while True:
                mention = _MENTIONS_REGEXP.search(i)
                if not mention:
                    break
                i = (
                    i[0:mention.span()[0]] +
                    self.sl_client.get_user(mention.groups()[0]).name +
                    i[mention.span()[1]:]
                )

            i = i.replace('&gt;', '>')
            i = i.replace('&lt;', '<')
            i = i.replace('&amp;', '&')

            encoded = i.encode('utf8')

            encoded = encoded.replace(b'<!here>', b'[YELLING]' + self.nick)
            encoded = encoded.replace(b'<!channel>', b'[YELLING]' + self.nick)

            yield encoded


    def _message(self, sl_ev: Union[slack.Message, slack.MessageFileShare, slack.MessageDelete, slack.MessageBot], prefix: str=''):
        """
        Sends a message to the irc client
        """
        if hasattr(sl_ev, 'user'):
            source = self.sl_client.get_user(sl_ev.user).name.encode('utf8')
            if source == self.nick:
                return
        else:
            source = b'bot'
        try:
            dest = b'#' + self.sl_client.get_channel(sl_ev.channel).name.encode('utf8')
        except KeyError:
            dest = source
        except Exception as e:
            print('Error: ', str(e))
            return
        for msg in self.parse_message(prefix + sl_ev.text):
            self.sendmsg(
                source,
                dest,
                msg
            )

    def slack_event(self, sl_ev):
        #TODO handle p2p messages
        if isinstance(sl_ev, slack.MessageDelete):
            self._message(sl_ev, '[deleted]')
        elif isinstance(sl_ev, slack.Message):
            self._message(sl_ev)
        elif isinstance(sl_ev, slack.MessageFileShare):
            prefix ='[File upload] %s %d %s\n' % (
                        sl_ev.file.mimetype,
                        sl_ev.file.size,
                        sl_ev.file.url_private,
                    )
            self._message(sl_ev, prefix)
        elif isinstance(sl_ev, slack.MessageEdit):
            if sl_ev.is_changed:
                self._message(sl_ev.diffmsg)
        elif isinstance(sl_ev, slack.MessageBot):
            self._message(sl_ev, '[%s]' % sl_ev.username)


    def command(self, cmd: bytes) -> None:
        if b' ' in cmd:
            cmdid, _ = cmd.split(b' ', 1)
        else:
            cmdid = cmd

        handlers = {
            b'NICK': self._nickhandler,
            b'USER': self._userhandler,
            b'PING': self._pinghandler,
            b'JOIN': self._joinhandler,
            b'PRIVMSG': self._privmsghandler,
            b'LIST': self._listhandler,
            b'WHO': self._whohandler,
            b'MODE': self._modehandler,
            #QUIT
            #CAP LS
            #USERHOST
            #Unknown command:  b'TOPIC #cama :titolo del canale'
            #Unknown command:  b'whois TAMARRO'
            #Unknown command:  b'PART #support-sdp :Konversation terminated!'
        }

        if cmdid in handlers:
            handlers[cmdid](cmd)
        else:
            self.s.send(b':serenity 421 %s %s :Unknown command\n' % (self.nick, cmdid))
            print('Unknown command: ', cmd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', type=int, action='store', dest='port',
                                default=9007, required=False,
                                help='set port number')
    parser.add_argument('-i', '--ip', type=str, action='store', dest='ip',
                                default='127.0.0.1', required=False,
                                help='set ip address')
    parser.add_argument('-t', '--tokenfile', type=str, action='store', dest='tokenfile',
                                default=expanduser('~')+'/.localslackirc',
                                required=False,
                                help='set the token file')
    parser.add_argument('-u', '--nouserlist', action='store_true',
                                dest='nouserlist', required=False,
                                help='don\'t display userlist')
    parser.add_argument('-o', '--override', action='store_true',
                                dest='overridelocalip', required=False,
                                help='allow non 127. addresses, this is potentially dangerous')

    args = parser.parse_args()
    # Exit if their chosden ip isn't local. User can override with -o if they so dare
    if not args.ip.startswith('127') and not args.overridelocalip:
        exit('supplied ip isn\'t local\nlocalslackirc has no encryption or ' \
                'authentication, it\'s recommended to only allow local connections\n' \
                'you can override this with -o')

    sl_client = slack.Slack(args.tokenfile)
    sl_events = sl_client.events_iter()
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serversocket.bind((args.ip, args.port))
    serversocket.listen(1)

    poller = select.poll()

    while True:
        s, _ = serversocket.accept()
        ircclient = Client(s, sl_client, args.nouserlist)

        poller.register(s.fileno(), select.POLLIN)
        if sl_client.fileno is not None:
            poller.register(sl_client.fileno, select.POLLIN)

        # Main loop
        timeout = 0.1
        while True:
            s_event = poller.poll(timeout)  # type: List[Tuple[int,int]]
            sl_event = next(sl_events)

            if s_event:
                text = s.recv(1024)
                if len(text) == 0:
                    break
                #FIXME handle the case when there is more to be read
                for i in text.split(b'\n')[:-1]:
                    i = i.strip()
                    if i:
                        ircclient.command(i)

            if sl_event:
                print(sl_event)
                ircclient.slack_event(sl_event)
                timeout = 0.1
            else:
                timeout = 7

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
