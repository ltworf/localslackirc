#! /usr/bin/env python3
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

import select
import socket
from typing import *

import slack


class Client:
    def __init__(self, s, sl_client):
        self.nick = b''
        self.username = b''
        self.realname = b''

        self.s = s
        self.sl_client = sl_client

    def _nickhandler(self, cmd: bytes) -> None:
        _, self.nick = cmd.split(b' ', 1)

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

        slchan = self.sl_client.get_channel_by_name(channel_name[1:].decode())
        userlist = []  # type List[bytes]
        for i in slchan.members:
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
        self.s.send(b':serenity 353 %s = %s :%s\n' % (self.nick, channel_name, users))
        self.s.send(b':serenity 366 %s %s :End of NAMES list\n' % (self.nick, channel_name))

    def _privmsghandler(self, cmd: bytes) -> None:
        #Unknown command:  b'PRIVMSG #cama :ciao mpare'
        #Unknown command:  b'PRIVMSG TAMARRO :qi'
        _, dest, msg = cmd.split(b' ', 2)
        msg = msg[1:]

        if dest.startswith(b'#'):
            self.sl_client.send_message(
                self.sl_client.get_channel_by_name(dest[1:].decode()).id,
                msg.decode('utf8')
            )
        else:
            #FIXME not implemented
            print('Private messaging not implemented yet')

    def _listhandler(self, cmd: bytes) -> None:
        for c in self.sl_client.channels():
            self.s.send(b':serenity 322 %s %s %d :%s\n' % (
                self.nick,
                b'#' + c.name.encode('utf8'),
                len(c.members),
                c.real_topic.encode('utf8'),
            ))
        self.s.send(b':serenity 323 quno :End of LIST\n')

    def sendmsg(self, from_: bytes, to: bytes, message: bytes) -> None:
        self.s.send(b':%s!salvo@127.0.0.1 PRIVMSG %s :%s\n' % (
            from_,
            to, #private message, or a channel
            message,
        ))

    def slack_event(self, sl_ev):
        #TODO handle p2p messages
        if isinstance(sl_ev, slack.Message):
            # Skip my own messages
            if self.sl_client.get_user(sl_ev.user).name.encode('utf8') == self.nick:
                return
            self.sendmsg(
                self.sl_client.get_user(sl_ev.user).name.encode('utf8'),
                b'#' + self.sl_client.get_channel(sl_ev.channel).name.encode('utf8'),
                sl_ev.text.encode('utf8')
            )

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
            #QUIT
            #CAP LS
            #WHO
            #USERHOST
            #Unknown command:  b'MODE #cama'
            #Unknown command:  b'MODE #cama +b'
            #Unknown command:  b'TOPIC #cama :titolo del canale'
            #Unknown command:  b'whois TAMARRO'
        }

        if cmdid in handlers:
            handlers[cmdid](cmd)
        else:
            print('Unknown command: ', cmd)



def main():
    sl_client = slack.Slack()
    sl_events = sl_client.events_iter()
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serversocket.bind(('127.0.0.1', 9007))
    serversocket.listen(1)

    poller = select.poll()
    s, _ = serversocket.accept()
    ircclient = Client(s, sl_client)


    poller.register(s.fileno(), select.POLLIN)

    # Main loop
    while True:
        s_event = poller.poll(0.1)  # type: List[Tuple[int,int]]
        sl_event = next(sl_events)

        if s_event:
            text = s.recv(1024)
            #FIXME handle the case when there is more to be read
            for i in text.split(b'\n')[:-1]:
                ircclient.command(i)

        if sl_event:
            print(sl_event)
            ircclient.slack_event(sl_event)



if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
