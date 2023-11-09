#!/usr/bin/env python3
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

import os
import sys


def main() -> None:

    # match sys.argv[0].split('/')[-1]:
        # case 'lsi-send':
    lsi_send()


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
