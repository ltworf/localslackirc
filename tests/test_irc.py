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


def b(s: str) -> bytes:
    return bytes(s, encoding="utf-8")


class TestParseMessage(TestIRC):
    async def test_simple_message(self):
        msg = await self.client.parse_message("hello world")
        self.assertEqual(msg, b"hello world")

    async def test_url(self):
        msg = await self.client.parse_message("See <https://example.com/docs/|the documentation>")
        self.assertEqual(msg, b("See the documentation¹\n  ¹ https://example.com/docs/"))

    async def test_multiple_urls(self):
        msg = await self.client.parse_message("See <https://example.com/docs/|the documentation>. Try also the <https://example.com/faq/|FAQ>")
        self.assertEqual(msg, b("See the documentation¹. Try also the FAQ²\n  ¹ https://example.com/docs/\n  ² https://example.com/faq/"))

    async def test_a_lot_of_urls(self):
        input_msg = "<https://example.com/|url> " * 10
        output = "\n".join([
            "url¹ url² url³ url⁴ url⁵ url⁶ url⁷ url⁸ url⁹ url¹⁰ ",
            "  ¹ https://example.com/",
            "  ² https://example.com/",
            "  ³ https://example.com/",
            "  ⁴ https://example.com/",
            "  ⁵ https://example.com/",
            "  ⁶ https://example.com/",
            "  ⁷ https://example.com/",
            "  ⁸ https://example.com/",
            "  ⁹ https://example.com/",
            "  ¹⁰ https://example.com/",
        ])
        msg = await self.client.parse_message(input_msg)
        self.assertEqual(msg, b(output))

    async def test_url_with_no_label_just_goes_inline(self):
        msg = await self.client.parse_message("Please look at <https://example.com/>")
        self.assertEqual(msg, b("Please look at https://example.com/"))
