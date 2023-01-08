# localslackirc
# Copyright (C) 2018-2020 Salvo "LtWorf" Tomaselli
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
#
# This file was part of python-slackclient
# (https://github.com/slackapi/python-slackclient)
# But has been copied and relicensed under GPL. The copyright applies only
# to the changes made since it was copied.

class SlackClientError(Exception):
    """
    Base exception for all errors raised by the SlackClient library
    """
    def __init__(self, msg: str) -> None:
        super(SlackClientError, self).__init__(msg)

    def __str__(self) -> str:
        reply = getattr(self, 'reply', None)
        msg = getattr(self, 'msg', None)
        return f'message={msg} reply={reply}'


class SlackConnectionError(SlackClientError):
    def __init__(self, message='', reply=None) -> None:
        super(SlackConnectionError, self).__init__(message)
        self.reply = reply


class SlackLoginError(SlackClientError):
    def __init__(self, message='', reply=None) -> None:
        super(SlackLoginError, self).__init__(message)
        self.reply = reply
