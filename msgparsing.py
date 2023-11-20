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

from enum import Enum
from typing import Iterable, NamedTuple, Optional

try:
    from emoji import emojize, demojize # type: ignore
except ModuleNotFoundError:
    def emojize(string:str, *args, **kwargs) -> str:  # type: ignore
        return string
    def demojize(string, str, delimiters: tuple[str, str]) -> str:  # type: ignore
        return string


SLACK_SUBSTITUTIONS = [
    ('&amp;', '&'),
    ('&gt;', '>'),
    ('&lt;', '<'),
]

__all__ = [
    'SLACK_SUBSTITUTIONS',
    'tokenize',
    'Itemkind',
    'PreBlock',
    'SpecialItem',
    'get_emoji_code',
]


def get_emoji_code(msg: str) -> str:
    '''
    Pass a single emoji and get the code without delimiters.
    '''
    return demojize(msg, ('', ''))


def preblocks(msg: str) -> Iterable[tuple[str, bool]]:
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


class Itemkind(Enum):
    YELL = 0  # HERE, EVERYONE and such
    MENTION = 1 # @user
    CHANNEL = 2 # #channel
    OTHER = 3 # Everything else


class PreBlock(NamedTuple):
    """
    Block of preformatted text
    """
    txt: str

    @property
    def lines(self) -> int:
        return self.txt.count('\n')


class SpecialItem(NamedTuple):
    """
    A link or a mention
    """
    txt: str

    @property
    def kind(self) -> Itemkind:
        k = self.txt[1]
        if k == '!':
            return Itemkind.YELL
        elif k == '@':
            return Itemkind.MENTION
        elif k == '#':
            return Itemkind.CHANNEL
        return Itemkind.OTHER

    @property
    def val(self) -> str:
        """
        Return the value
        """

        sep = self.txt.find('|')

        # No human readable, just take the whole thing
        if sep == -1:
            sep = len(self.txt) - 1


        if self.kind != Itemkind.OTHER:
            return self.txt[2:sep]
        return self.txt[1:sep]

    @property
    def human(self) -> Optional[str]:
        """
        Return the eventual human readable
        message
        """
        sep = self.txt.find('|')

        if sep == -1:
            return None
        return self.txt[sep+1:-1]


def split_tokens(msg: str) -> Iterable[SpecialItem|str]:
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
            yield SpecialItem(block)
    if msg:
        yield msg


def convertpre(msg: str) -> str:
    """
    Fixes a preformatted block so that it can
    be displayed by an irc client.

    Links can be present in preformatted blocks
    with the format <http://> and MAYBE with
    <http://blabla|bla> but no channel or user
    mentions are allowed, and emoji substitution
    should not happen here.
    """
    r = []

    for t in split_tokens(msg):
        if isinstance(t, str):
            r.append(t)
            continue

        if t.kind != Itemkind.OTHER:
            raise ValueError(f'Unexpected slack item in preformatted block {t}')
        elif t.human: # For some very strange reason slack converts text like "asd.com" into links
            r.append(t.human)
        else:
            r.append(t.val)

    l = ''.join(r)
    for s in SLACK_SUBSTITUTIONS:
        l = l.replace(s[0], s[1])
    return l


def tokenize(msg: str) -> Iterable[PreBlock|SpecialItem|str]:
    """
    Yields the various possible tokens

    Changes the &gt; codes

    Puts the emoji in place
    """
    for txt, pre in preblocks(msg):
        if pre:
            yield PreBlock(convertpre(txt))
        else:
            for t in split_tokens(txt):
                if isinstance(t, str):
                    # Replace emoji codes (e.g. :thumbsup:)
                    t = emojize(t, language='alias')
                    # Usual substitutions
                    for s in SLACK_SUBSTITUTIONS:
                        t = t.replace(s[0], s[1])  # type: ignore
                yield  t

