#!/usr/bin/env python3
# localslackirc
# Copyright (C) 2023-2024 Salvo "LtWorf" Tomaselli
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

import argparse
import os
import sys
import socket


def lsi_write():
    parser = argparse.ArgumentParser(
        description='Send a message to a slack user or channel.'
    )
    parser.add_argument('--control-socket', type=str, action='store', dest='control_socket', default=None,
                        help='Path to the localslackirc unix control socket')
    parser.add_argument(type=str, action='store', dest='destination',
                        help='Destination user or channel')
    args = parser.parse_args()
    control_socket = args.control_socket or find_socket()

    if not control_socket:
        sys.exit('Please specify the path to the socket')

    while data := sys.stdin.readline():
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(control_socket)

        s.send(b'write\n')
        s.send(args.destination.encode('utf8') + b'\n')
        s.send(data.encode('utf8'))
        s.shutdown(socket.SHUT_WR)


def lsi_send():
    parser = argparse.ArgumentParser(
        description='Send a file to a slack user or channel.'
    )
    parser.add_argument('-f', '--filename', type=str, action='store', dest='filename',
                        help='Name to give to the file', default='filename')
    parser.add_argument('--control-socket', type=str, action='store', dest='control_socket', default=None,
                        help='Path to the localslackirc unix control socket')
    parser.add_argument('-F', '--file', type=str, action='store', dest='source',
                        help='Path of the file to send. If not specified stdin is used', default=None)
    parser.add_argument(type=str, action='store', dest='destination',
                        help='Destination user or channel')


    args = parser.parse_args()

    if args.source:
        args.filename = args.source.split('/')[-1]

    control_socket = args.control_socket or find_socket()

    if not control_socket:
        sys.exit('Please specify the path to the socket')

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(control_socket)

    assert '\n' not in args.destination
    assert '\n' not in args.filename
    s.send(b'sendfile\n')
    s.send(args.destination.encode('utf8') + b'\n')
    s.send(args.filename.encode('utf8') + b'\n')

    if args.source:
        with open(args.source, "rb") as f:
            while chunk := f.read(4096):
                s.send(chunk)
    else:
        while chunk := sys.stdin.buffer.read(1024):
            s.send(chunk)
    s.shutdown(socket.SHUT_WR)

    response = s.recv(1024).decode('utf8')

    print(response)

    if response != 'ok':
        sys.exit(1)


def main() -> None:

    match sys.argv[0].split('/')[-1]:
        case 'lsi-send':
            lsi_send()
        case 'lsi-write':
            lsi_write()


def find_socket() -> None | str:
    '''
    Returns the control socket of localslackirc or raises

    It looks in the runtime directory used in the .service file
    and looks for sockets in that directory.
    '''
    RUNDIR = '/run/localslackirc/'
    candidates = []

    try:
        for s in os.listdir(RUNDIR):
            if os.access(RUNDIR + s, os.W_OK | os.R_OK | os.X_OK):
                candidates.append(RUNDIR + s)
        if len(candidates) == 1:
            return candidates[0]
    except Exception:
        pass
    return None


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
