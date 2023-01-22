# localslackirc
# Copyright (C) 2020-2021 Salvo "LtWorf" Tomaselli
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

import unittest

from localslackirc.diff import seddiff


class TestDiff(unittest.TestCase):

    def test_no_crash(self):
        seddiff('', 'lalala')
        seddiff('lalala', 'lalala')
        seddiff('lalala', '')
        seddiff('lalala', 'lalala allelolela')
        seddiff('lalala allelolela', 'allelolela')
        seddiff('lalala allelolela', 'lalala')

    def test_no_diff(self):
        assert seddiff('ciao', 'ciao') == ''
        assert seddiff('', '') == ''
        assert seddiff('la la', 'la la') == ''

    def test_full_replace(self):
        assert seddiff('vado al mare', 'dormo la sera') == 's/vado al mare/dormo la sera/'
        assert seddiff('ciae å tuttï', 'ciao a tutti') == 's/ciae å tuttï/ciao a tutti/'

    def test_partials(self):
        assert seddiff('vado a dormire al mare', 'vado a nuotare al mare') == 's/dormire/nuotare/'
        assert seddiff('ciae a tutti', 'ciao a tutti') == 's/ciae/ciao/'
        assert seddiff('ciae å tutti', 'ciao a tutti') == 's/ciae å/ciao a/'

    def test_insertion(self):
        assert seddiff('il numero dei fili', 'il numero massimo dei fili') == 's/numero dei/numero massimo dei/'
        assert seddiff('mangio del formaggio e pere', 'mangio del formaggio con le pere') == 's/formaggio e pere/formaggio con le pere/'
        assert seddiff('mangio del formaggio e pere per cena', 'mangio del formaggio con le pere per cena') == 's/formaggio e pere/formaggio con le pere/'
        assert seddiff('mare blu', 'il mare blu') == 's/mare/il mare/'
        assert seddiff('mare, blu', 'il mare, blu') == 's/mare/il mare/'

    def test_append(self):
        assert seddiff('XYZ', 'XYZ (meaning "bla bla bla")') == 's/$/(meaning "bla bla bla")/'
