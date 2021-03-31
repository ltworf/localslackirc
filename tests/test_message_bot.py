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


with_attachments = {
    "type": "message",
    "subtype": "bot_message",
    "text": "This is a message with attachments",
    "username": "BotExample",
    "channel": "XYZ123456",
    "bot_id": "ABC123456",
    "attachments": [
        {"text": "First attachment"},
        {"text": "Second attachment"},
    ],
}


with_attachments_fallback_instead_of_text = {
    "type": "message",
    "subtype": "bot_message",
    "text": "This is a message with attachments",
    "username": "BotExample",
    "channel": "XYZ123456",
    "bot_id": "ABC123456",
    "attachments": [
        {"fallback": "First attachment"},
        {"fallback": "Second attachment"},
    ],
}


class TestMessageBot(unittest.TestCase):
    def test_message_with_attachments(self):
        msg = load(with_attachments, MessageBot)
        assert (
            msg.text
            == "This is a message with attachments\nFirst attachment\nSecond attachment"
        )

    def test_attachment_with_fallback(self):
        msg = load(with_attachments_fallback_instead_of_text, MessageBot)
        assert (
            msg.text
            == "This is a message with attachments\nFirst attachment\nSecond attachment"
        )