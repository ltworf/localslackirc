# localslackirc
# Copyright (C) 2020 Salvo "LtWorf" Tomaselli
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
import gzip
import json
from typing import Dict, Optional, NamedTuple
from urllib import parse


class Response(NamedTuple):
    status: int
    headers: Dict[str, str]
    data: bytes

    def json(self):
        return json.loads(self.data)


class Request:
    def __init__(self, base_url: str) -> None:
        """https://slack.com/api/
        In my case, base_url is "https://slack.com/api/"
        """
        self.base_url = parse.urlsplit(base_url)
        if self.base_url.scheme == 'https':
            self.ssl = True
            self.port = 443
        else:
            self.ssl = False
            self.port = 80

        # Override port if explicitly defined
        if self.base_url.port:
            self.port = self.base_url.port
        self.hostname = self.base_url.hostname
        self.path = self.base_url.path

    async def post(self, path: str, headers: Dict[str, str], data: Dict[str, str], timeout: float=0) -> Response:
        req = f'POST {self.path + path} HTTP/1.1\r\n'
        req += f'Host: {self.hostname}\r\n'
        req += 'Connection: close\r\n'  #FIXME reuse connection
        req += 'Accept-Encoding: gzip\r\n'
        for k, v in headers.items():
            req += f'{k}: {v}\r\n'

        req += f'Content-Type: application/x-www-form-urlencoded\r\n'
        post_data = parse.urlencode(data)
        req += f'Content-Length: {len(post_data)}\r\n'
        req += '\r\n'

        reader, writer = await asyncio.open_connection(self.hostname, self.port, ssl=self.ssl)

        writer.write(req.encode('ascii'))
        writer.write(post_data.encode('ascii'))
        await writer.drain()

        # Read response
        line = await reader.readline()
        status = int(line.split(b' ')[1])

        # Read headers
        headers = {}
        while True:
            line = await reader.readline()
            if line == b'\r\n':
                break
            k, v = line.decode('ascii').split(':', 1)
            headers[k] = v.strip()

        # Read data
        read_data = b''
        if headers.get('transfer-encoding') == 'chunked':
            while True:
                line = await reader.readline()
                if not line.endswith(b'\r\n'):
                    raise Exception('Unexpected end of chunked data')
                size = int(line, 16)
                read_data += (await reader.readexactly(size + 2))[:-2]
                if size == 0:
                    break
        elif 'content-length' in headers:
            size = int(headers['content-length'])
            read_data = await reader.readexactly(size)
        else:
            raise NotImplementedError('Can only handle chunked data' + repr(headers))

        # decompress if needed
        if headers.get('content-encoding') == 'gzip':
            read_data = gzip.decompress(read_data)
        return Response(status, headers, read_data)
