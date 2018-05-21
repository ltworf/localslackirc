#!/usr/bin/env python3
#
# This file contains logging support for localslackirc
#
# Like localslackirc this is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
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
# author Hack5190

def startlog():
    """
    open a chat log file. if it exists zero it out and start fresh.
    """
    with open("ircchat.log", "w") as temp:
        temp.write("")


def logger(name, msg):
    """
    log localslackirc users chat messages.
    """
    # load the contents of the chat log.  This needs improvement.
    irclog = open("ircchat.log", 'r')
    content = irclog.readlines()
    irclog.close()

    # loop through the content of the chat log and save the most recent 20. This needs improvement.
    irclog = open("ircchat.log", "w")
    while len(content) > 20:
        content.remove(content[0])
    if len(content) > 0:
        for i in content:
            irclog.write(i.strip('\n\r') + '\n')

    # write current messge to log.
    #irclog.write(name + ':' + msg)
    irclog.write(msg)
    irclog.close()


def searchlog(name, msg):
    """
    loop through the chat log file and search for a match.
    """
    with open("ircchat.log", "r") as ircchat:
      content = ircchat.readlines()

    # loop through the log and search for this message.
    for i in content:
        if msg in i:
            return 1
    # msg not found
    return 0
