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
from typing import Dict, Optional, NamedTuple, Tuple, Any
from uuid import uuid1
from urllib import parse


def multipart_form(data: Dict[str, Any]) -> Tuple[str, bytes]:
    """
    Convert a dictionary to post data and returns relevant headers.

    The dictionary can contain values as open files, or anything else.
    Anything that is not an open file is cast to str
    """

    if all((not (hasattr(i, 'read') or hasattr(i, 'name')) for i in data.values())):
        return (
            'Content-Type: application/x-www-form-urlencoded\r\n',
            parse.urlencode(data).encode('ascii')
        )

    boundary = str(uuid1()).encode('ascii')

    form_data = b''
    for k, v in data.items():
        form_data += b'--' + boundary + b'\r\n'
        if hasattr(v, 'read') and hasattr(v, 'name'):
            form_data += f'Content-Disposition: form-data; name="{k}"; filename="{v.name}"\r\n'.encode('ascii')
            form_data += b'\r\n' + v.read() + b'\r\n'
        else:
            strv = str(v)
            form_data += f'Content-Disposition: form-data; name="{k}"\r\n'.encode('ascii')
            form_data += b'\r\n' + strv.encode('ascii') + b'\r\n'

    form_data += b'--' + boundary + b'\r\n'

    header = f'Content-Type: multipart/form-data; boundary={boundary.decode("ascii")}\r\n'
    return header, form_data


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
        self._reader: Optional[asyncio.streams.StreamReader] = None
        self._writer: Optional[asyncio.streams.StreamWriter] = None

    async def _connect(self) -> None:
        """
        Connect and possibly close the previous connection
        """
        if self._writer:
            self._writer.close()
        self._reader, self._writer = await asyncio.open_connection(self.hostname, self.port, ssl=self.ssl)

    async def post(self, path: str, headers: Dict[str, str], data: Dict[str,  Any], timeout: float=0) -> Response:
        # Prepare request
        req = f'POST {self.path + path} HTTP/1.1\r\n'
        req += f'Host: {self.hostname}\r\n'
        req += 'Connection: keep-alive\r\n'
        req += 'Accept-Encoding: gzip\r\n'
        for k, v in headers.items():
            req += f'{k}: {v}\r\n'

        header, post_data = multipart_form(data)
        req += header
        req += f'Content-Length: {len(post_data)}\r\n'
        req += '\r\n'

        # Send request

        if self._writer is None or self._reader is None:
            await self._connect()
        assert self._reader is not None
        assert self._writer is not None

        try:
            self._writer.write(req.encode('ascii'))
            self._writer.write(post_data)
            await self._writer.drain()
        except BrokenPipeError:
            await self._connect()
            self._writer.write(req.encode('ascii'))
            self._writer.write(post_data)
            await self._writer.drain()

        # Read response
        line = await self._reader.readline()
        status = int(line.split(b' ')[1])

        # Read headers
        headers = {}
        while True:
            line = await self._reader.readline()
            if line == b'\r\n':
                break
            k, v = line.decode('ascii').split(':', 1)
            headers[k.lower()] = v.strip()

        # Read data
        read_data = b''
        if headers.get('transfer-encoding') == 'chunked':
            while True:
                line = await self._reader.readline()
                if not line.endswith(b'\r\n'):
                    raise Exception('Unexpected end of chunked data')
                size = int(line, 16)
                read_data += (await self._reader.readexactly(size + 2))[:-2]
                if size == 0:
                    break
        elif 'content-length' in headers:
            size = int(headers['content-length'])
            read_data = await self._reader.readexactly(size)
        else:
            raise NotImplementedError('Can only handle chunked data' + repr(headers))

        # decompress if needed
        if headers.get('content-encoding') == 'gzip':
            read_data = gzip.decompress(read_data)
        return Response(status, headers, read_data)
