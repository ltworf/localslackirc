# localslackirc
# Copyright (C) 2022 Salvo "LtWorf" Tomaselli
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

from typing import Iterable, Tuple


def preblocks(msg: str) -> Iterable[Tuple[str, bool]]:
    """
    Iterates the preformatted and normal text blocks
    in the message.

    The boolean indicates if the block is preformatted.

    The three ``` ticks are removed by this.
    """
    pre = False

    while True:
        try:
            p = msg.index('```')
        except ValueError:
            break

        yield msg[0:p], pre
        pre = not pre
        msg = msg[p+3:]
    yield msg, pre


def split_tokens(msg: str) -> Iterable[str]:
    """
    yields separately the normal text and the special slack
    <stuff> items
    """
    while True:
        try:
            begin = msg.index('<')
        except ValueError:
            break

        if begin != 0: # There is stuff before
            yield msg[0:begin]
            msg = msg[begin:]
        else: # Tag at the beginning
            end = msg.index('>')
            block = msg[0:end + 1]
            msg = msg[end + 1:]
            yield block
    if msg:
        yield msg