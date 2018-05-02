#!/usr/bin/env python3
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
# modifications by Hack5190@gmail.com

import sys
import getopt
import re
import select
import socket
from typing import *

import slack


# How slack expresses mentioning users
_MENTIONS_REGEXP = re.compile(r'<@([0-9A-Za-z]+)>')


class Client:
    def __init__(self, s, sl_client):
        self.nick = b''
        self.username = b''
        self.realname = b''

        self.s = s
        self.sl_client = sl_client

     def _ignorehandler(self, cmd: bytes) -> None:
         dummy=1

    def _nickhandler(self, cmd: bytes) -> None:
        _, nick = cmd.split(b' ', 1)
        self.nick = nick.strip()

    def _userhandler(self, cmd: bytes) -> None:
        #TODO USER salvo 8 * :Salvatore Tomaselli
        self.s.send(b':serenity 001 %s :Welcome to localslackirc, The IRC <-> SLACK Personal Bridge\n' % self.nick)
        self.s.send(b':serenity 002 %s :Running version miniircd-1.2.1\n' % self.nick)

    def _pinghandler(self, cmd: bytes) -> None:
        _, lbl = cmd.split(b' ', 1)
        self.s.send(b':serenity PONG serenity %s\n' % lbl)

    def _joinhandler(self, cmd: bytes) -> None:
        _, channel_name = cmd.split(b' ', 1)

        try:
            slchan = self.sl_client.get_channel_by_name(channel_name[1:].decode())
        except:
            return
        # Hack5190 "-u no-userlist"
        if uuser=='0':
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

        self.s.send(b':%s!localslackirc@127.0.0.1 JOIN %s\n' % (self.nick, channel_name))
        self.s.send(b':serenity 331 %s %s :%s\n' % (self.nick, channel_name, slchan.real_topic.encode('utf8')))
        # Hack5190 "-u no-userlist"
        if uuser=='0':
            self.s.send(b':serenity 353 %s = %s :%s\n' % (self.nick, channel_name, users))
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
        for i in self.sl_client.get_members(channel.id):
            user = self.sl_client.get_user(i)
            self.s.send(b':serenity 352 %s %s --- ZNC-Bouncer serenity %s H :0 %s\n' % (
                self.nick,
                name,
                user.name.encode('utf8'),
                user.real_name.encode('utf8'),
            ))
        self.s.send(b':serenity 315 %s %s :End of WHO list\n' % (self.nick, name))

    def sendmsg(self, from_: bytes, to: bytes, message: bytes) -> None:
        self.s.send(b':%s!localslackirc@127.0.0.1 PRIVMSG %s :%s\n' % (
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

        # Hack5190 - Code to convert txt emoji to Slack emoji
        # https://www.webpagefx.com/tools/emoji-cheat-sheet/
        msg = msg.replace(':)', ':smile:')
        msg = msg.replace(':(', ':frowning:')
        msg = msg.replace(':p', ':stuck_out_tongue:')
        msg = msg.replace(';)', ':wink:')
        msg = msg.replace(':*', ':kissing:')

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

            # Hack5190 - Add code to convert slack emoji to txt emoji
            # https://www.webpagefx.com/tools/emoji-cheat-sheet/
            i = i.replace(':slightly_smiling_face:', ':)')
            i = i.replace(':frowning:', ':(')
            i = i.replace(':stuck_out_tongue:', ':p')
            i = i.replace(':wink:', ';)')
            i = i.replace(':kissing:', ':*')
            
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
            b'ISON': self._ignorehandler,
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
    ###############################
    # t == token-filename
    # i == IP-Address
    # p == port-number
    # u == no-userlist
    ###############################
    utoken='./localslackcattoken'
    uip='127.0.0.1'
    uport='9007'
    global uuser
    uuser='0'

    # Read command line args
    myopts, args = getopt.getopt(sys.argv[1:],"t:i:p:u:")

    ###############################
    # o == option
    # a == argument passed
    ###############################
    #FIXME when option selected and no argument provided - CRASH!
    for o, a in myopts:
        if o == '-t':
            utoken=a
        elif o == '-i':
            uip=a
        elif o == '-p':
            uport=a
        elif o == '-u':
            if a =='no-userlist':
                uuser='1'
        else:
            print("Usage: %s -t token-filename -i IP-address -p port-number -u no-userlist" % sys.argv[0])

    sl_client = slack.Slack()
    sl_events = sl_client.events_iter()
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serversocket.bind((uip, int(uport)))
    serversocket.listen(1)

    poller = select.poll()

    while True:
        s, _ = serversocket.accept()
        ircclient = Client(s, sl_client)

        poller.register(s.fileno(), select.POLLIN)

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
