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

import unittest

from typedload import load
from slack import MessageBot

template = {
    "type": "message",
    "subtype": "bot_message",
    "text": "This is a message with attachments",
    "username": "BotExample",
    "channel": "XYZ123456",
    "bot_id": "ABC123456",
}


class TestMessageBot(unittest.TestCase):
    def test_message_with_attachments(self):
        event = template.copy()
        event.update({
            "attachments": [
                {"text": "First attachment"},
                {"text": "Second attachment"},
            ]
        })
        msg = load(event, MessageBot)
        assert (
            msg.text
            == "This is a message with attachments\nFirst attachment\nSecond attachment"
        )

    def test_attachment_with_fallback(self):
        event = template.copy()
        event.update({
            "attachments": [
                {"fallback": "First attachment"},
                {"fallback": "Second attachment"},
            ],
        })
        msg = load(event, MessageBot)
        assert (
            msg.text
            == "This is a message with attachments\nFirst attachment\nSecond attachment"
        )
