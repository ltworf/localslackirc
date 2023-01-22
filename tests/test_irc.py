# localslackirc
# Copyright (C) 2021 Antonio Terceiro
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

from unittest import IsolatedAsyncioTestCase, mock
from localslackirc.irc import Server, Client

class TestIRC(IsolatedAsyncioTestCase):
    def setUp(self):
        slack_client = mock.AsyncMock()
        settings = mock.MagicMock()
        settings.silenced_yellers = set()
        self.server = Server(slack_client, settings)
        self.server.client = Client()


class TestAnnoyanceAvoidance(TestIRC):
    async def test_yelling_prevention(self):
        self.server.client.nickname = 'aldo'

        # Mention generated
        msg = await self.server.parse_slack_message("<!here> watch this!", 'rose.adams','#asd')
        assert msg == 'yelling [aldo]: watch this!'

        # Add rose.adams to silenced yellers
        self.server.settings.silenced_yellers.add('rose.adams')

        # Mention no longer generated
        msg = await self.server.parse_slack_message("<!here> watch this!", 'rose.adams', '#asd')
        assert msg == 'yelling: watch this!'

        # No effect on regular messages
        msg = await self.server.parse_slack_message("hello world", 'rose.adams', '#asd')
        assert msg == 'hello world'


class TestParseMessage(TestIRC):
    async def test_simple_message(self):
        msg = await self.server.parse_slack_message("hello world", 'ciccio', '#asd')
        self.assertEqual(msg, "hello world")

    async def test_url(self):
        msg = await self.server.parse_slack_message("See <https://example.com/docs/|the documentation>", 'ciccio', '#asd')
        self.assertEqual(msg, "See the documentation¹\n  ¹ https://example.com/docs/")

    async def test_url_aggressive_shortening(self):
        msg = await self.server.parse_slack_message("See <https://example.com/docs/iqjweoijsodijijaoij?oiwje|https://example.com/docs/iqjweoijsodijijaoij>", 'ciccio', '#asd')
        self.assertEqual(msg, "See LINK¹\n  ¹ https://example.com/docs/iqjweoijsodijijaoij?oiwje")

    async def test_multiple_urls(self):
        msg = await self.server.parse_slack_message("See <https://example.com/docs/|the documentation>. Try also the <https://example.com/faq/|FAQ>", 'ciccio', '#asd')
        self.assertEqual(msg, "See the documentation¹. Try also the FAQ²\n  ¹ https://example.com/docs/\n  ² https://example.com/faq/")

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
        msg = await self.server.parse_slack_message(input_msg, 'ciccio', '#asd')
        self.assertEqual(msg, output)

    async def test_url_with_no_label_just_goes_inline(self):
        msg = await self.server.parse_slack_message("Please look at <https://example.com/>", 'ciccio', '#asd')
        self.assertEqual(msg, "Please look at https://example.com/")

    async def test_replace_label_for_urls_with_no_different_text(self):
        msg = await self.server.parse_slack_message("<https://example.com/|https://example.com/>", 'ciccio', '#asd')
        self.assertEqual(msg, "LINK¹\n  ¹ https://example.com/")
