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

from slackclient import SlackClient
from typedload import load

class Slack:
    def __init__(self) -> None:
        #FIXME open the token in a sensible way
        with open('/home/salvo/.localslackcattoken') as f:
            token = f.readline().strip()
        self.client = SlackClient(token)
