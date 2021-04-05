# localslackirc
# Copyright (C) 2021 Antonio Terceiro
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

from unittest import IsolatedAsyncioTestCase, mock
from irc import Client, Provider

class TestIRC(IsolatedAsyncioTestCase):
    def setUp(self):
        stream_writer = mock.AsyncMock()
        slack_client = mock.AsyncMock()
        settings = mock.MagicMock()
        settings.provider = Provider.SLACK
        self.client = Client(stream_writer, slack_client, settings)


class TestParseMessage(TestIRC):
    async def test_simple_message(self):
        msg = await self.client.parse_message("hello world")
        self.assertEqual(msg, b"hello world")
