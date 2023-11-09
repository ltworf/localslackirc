# localslackirc
# Copyright (C) 2023 Salvo "LtWorf" Tomaselli
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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from irc import Client as IrcClient


async def handle_client(ircclient: "IrcClient", reader, writer) -> None:
    ...


async def listen(socket_path: str, ircclient: "IrcClient") -> None:
    server = await asyncio.start_unix_server(lambda r,w: handle_client(ircclient, r, w), socket_path)
    async with server:
        await server.serve_forever()
