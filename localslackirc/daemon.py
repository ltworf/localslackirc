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

import argparse
import asyncio
import logging
import logging.handlers
import os
from os import environ
from os.path import expanduser
from pathlib import Path
import pwd
import sys
from typing import Optional, Set

from . import __version__
from .irc import Server, ServerSettings, IrcDisconnectError
from .slack import Slack


def su() -> None:
    """
    switch user. Useful when starting localslackirc
    as a service as root user.
    """
    if sys.platform.startswith('win'):
        return

    # Nothing to do, already not root
    if os.getuid() != 0:
        return

    username = environ.get('PROCESS_OWNER', 'nobody')
    userdata = pwd.getpwnam(username)
    os.setgid(userdata.pw_gid)
    os.setegid(userdata.pw_gid)
    os.setuid(userdata.pw_uid)
    os.seteuid(userdata.pw_uid)


class ColoredFormatter(logging.Formatter):
    RESET_SEQ = "\033[0m"
    COLOR_SEQ = "%s%%s" + RESET_SEQ

    COLORS = {
        'DEBUG': COLOR_SEQ % "\033[0;36m",
        'INFO': COLOR_SEQ % "\033[32m",
        'WARNING': COLOR_SEQ % "\033[1;33m",
        'ERROR': COLOR_SEQ % "\033[1;31m",
        'CRITICAL': COLOR_SEQ % ("\033[1;33m\033[1;41m"),
        'DEBUG_FILTERS': COLOR_SEQ % "\033[0;35m",
    }

    def format(self, record):
        levelname = record.levelname

        msg = super().format(record)
        if levelname in self.COLORS:
            msg = self.COLORS[levelname] % msg
        return msg


class Daemon:
    irc_server = None
    sl_client = None

    @classmethod
    def run(cls):
        su()

        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(cls().main())
        except KeyboardInterrupt:
            return

    @classmethod
    def create_default_logger(cls):
        # stderr logger
        log_format = '%(asctime)s:%(levelname)s:%(name)s' \
                     ':%(filename)s:%(lineno)d:%(funcName)s %(message)s'
        handler = logging.StreamHandler(sys.stderr)
        if sys.platform != 'win32' and sys.stderr.isatty():
            handler.setFormatter(ColoredFormatter(log_format))
        return handler

    def setup_loggers(self, level: int, syslog: bool = False):
        logging.root.handlers = []

        logging.root.setLevel(level)
        logging.root.addHandler(self.create_default_logger())

        if syslog:
            handler = logging.handlers.SysLogHandler(address='/dev/log')
            handler.setFormatter(logging.Formatter('localslackirc: %(message)s'))
            handler.setLevel(logging.INFO)
            logging.root.addHandler(handler)


    async def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-v', '--version', action='version', version=f'''localslackirc {__version__}''')
        parser.add_argument('-p', '--port', type=int, action='store', dest='port',
                                    default=9007, required=False,
                                    help='set port number. Defaults to 9007')
        parser.add_argument('-i', '--ip', type=str, action='store', dest='ip',
                                    default='127.0.0.1', required=False,
                                    help='set ip address')
        parser.add_argument('-t', '--tokenfile', type=str, action='store', dest='tokenfile',
                                    default=expanduser('~')+'/.localslackirc',
                                    required=False,
                                    help='set the token file')
        parser.add_argument('-c', '--cookiefile', type=str, action='store', dest='cookiefile',
                                    default=None,
                                    required=False,
                                    help='set the cookie file (for slack only, for xoxc tokens)')
        parser.add_argument('-u', '--nouserlist', action='store_true',
                                    dest='nouserlist', required=False,
                                    help='don\'t display userlist')
        parser.add_argument('-j', '--autojoin', action='store_true',
                                    dest='autojoin', required=False,
                                    help="Automatically join all remote channels")
        parser.add_argument('-r', '--thread-replies', action='store_true',
                                    dest='thread_replies', required=False,
                                    help="Receive thread messages in main channel instead of a custom thread channel (you'll not be able to answer in threads)")
        parser.add_argument('-o', '--override', action='store_true',
                                    dest='overridelocalip', required=False,
                                    help='allow non 127. addresses, this is potentially dangerous')
        parser.add_argument('-f', '--status-file', type=str, action='store', dest='status_file', required=False, default=None,
                                    help='Path to the file to keep the internal status.')
        parser.add_argument('-s', '--syslog', action='store_true', dest='syslog', required=False, default=False,
                                    help='Log into syslog.')
        parser.add_argument('-d', '--debug', action='store_true', dest='debug', required=False, default=False,
                                    help='Enables debugging logs.')
        parser.add_argument('--ignored-channels', type=str, action='store', dest='ignored_channels', default='',
                                    help='Comma separated list of channels to not join when autojoin is enabled')
        parser.add_argument('--downloads-directory', type=str, action='store', dest='downloads_directory', default='/tmp',
                                    help='Where to create files for automatic downloads')
        parser.add_argument('--formatted-max-lines', type=int, action='store', dest='formatted_max_lines', default=0,
                                    help='Maximum amount of lines in a formatted text to send to the client rather than store in a file.\n'
                                    'Setting to 0 (the default) will send everything to the client')
        parser.add_argument('--silenced-yellers', type=str, action='store', dest='silenced_yellers', default='',
                                    help='Comma separated list of nicknames that won\'t generate notifications when using @channel and @here')

        args = parser.parse_args()

        self.setup_loggers(
            level=logging.DEBUG if bool(environ.get('DEBUG', args.debug)) else logging.INFO,
            syslog=bool(environ.get('SYSLOG', args.syslog))
        )

        status_file_str: Optional[str] = environ.get('STATUS_FILE', args.status_file)
        status_file = None
        if status_file_str is not None:
            logging.info('Status file at: %s', status_file_str)
            status_file = Path(status_file_str)

        ip: str = environ.get('IP_ADDRESS', args.ip)
        overridelocalip: bool = environ['OVERRIDE_LOCAL_IP'].lower() == 'true' if 'OVERRIDE_LOCAL_IP' in environ else args.overridelocalip

        # Exit if their chosden ip isn't local. User can override with -o if they so dare
        if not ip.startswith('127') and not overridelocalip:
            exit('supplied ip isn\'t local\nlocalslackirc has no encryption or ' \
                    'authentication, it\'s recommended to only allow local connections\n' \
                    'you can override this with -o')

        port = int(environ.get('PORT', args.port))

        autojoin: bool = environ['AUTOJOIN'].lower() == 'true' if 'AUTOJOIN' in environ else args.autojoin
        nouserlist: bool = environ['NOUSERLIST'].lower() == 'true' if 'NOUSERLIST' in environ else args.nouserlist
        thread_replies: bool = environ['THREAD_REPLIES'].lower() == 'true' if 'THREAD_REPLIES' in environ else args.thread_replies

        # Splitting ignored channels
        ignored_channels_str = environ.get('IGNORED_CHANNELS', args.ignored_channels)
        if autojoin and len(ignored_channels_str):
            ignored_channels: Set[str] = {
                ('' if i.startswith('#') else '#') + i
                for i in ignored_channels_str.split(',')
            }
        else:
            ignored_channels = set()

        if 'DOWNLOADS_DIRECTORY' in environ:
            downloads_directory = Path(environ['DOWNLOADS_DIRECTORY'])
        else:
            downloads_directory = Path(args.downloads_directory)

        try:
            formatted_max_lines = int(environ.get('FORMATTED_MAX_LINES', args.formatted_max_lines))
        except ValueError:
            exit('FORMATTED_MAX_LINES is not a valid int')

        yellers_str = environ.get('SILENCED_YELLERS', args.silenced_yellers)
        if yellers_str:
            silenced_yellers = {i.strip() for i in yellers_str.split(',')}
        else:
            silenced_yellers = set()

        if 'TOKEN' in environ:
            token = environ['TOKEN']
        else:
            try:
                with open(args.tokenfile, 'r', encoding='utf8') as f:
                    token = f.readline().strip()
            except IsADirectoryError:
                exit(f'Not a file {args.tokenfile}')
            except (FileNotFoundError, PermissionError):
                exit(f'Unable to open the token file {args.tokenfile}')

        if 'COOKIE' in environ:
            cookie: Optional[str] = environ['COOKIE']
        else:
            try:
                if args.cookiefile:
                    with open(args.cookiefile, 'r', encoding='utf8') as f:
                        cookie = f.readline().strip()
                else:
                    cookie = None
            except (FileNotFoundError, PermissionError):
                exit(f'Unable to open the cookie file {args.cookiefile}')
            except IsADirectoryError:
                exit(f'Not a file {args.cookiefile}')

        if token.startswith('xoxc-') and not cookie:
            exit('The cookie is needed for this kind of slack token')

        previous_status = None
        if status_file is not None and status_file.exists():
            previous_status = status_file.read_text('utf8')
        self.sl_client = Slack(token, cookie, previous_status)

        serversettings = ServerSettings(
            nouserlist=nouserlist,
            autojoin=autojoin,
            thread_replies=thread_replies,
            ignored_channels=ignored_channels,
            downloads_directory=downloads_directory,
            formatted_max_lines=formatted_max_lines,
            silenced_yellers=silenced_yellers,
        )
        verify = serversettings.verify()
        if verify is not None:
            exit(verify)

        self.irc_server = Server(self.sl_client, serversettings)

        try:
            while True:
                try:
                    await self.irc_server.listener(ip, port)
                except (IrcDisconnectError, ConnectionResetError):
                    logging.info('IRC disconnected')
        finally:
            if status_file:
                logging.info('Writing status to %s', status_file)
                status_file.write_text(self.sl_client.get_status(), 'utf8')
            self.sl_client.close()
