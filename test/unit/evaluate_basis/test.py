"""Unit tests for FFC. This test compares values computed by the two UFC
functions evaluate_basis and evaluate_basis_derivatives generated by FFC to the
values tabulated by FIAT and to reference values computed by an older version of FFC."""

# Copyright (C) 2010 Kristian B. Oelgaard
#
# This file is part of FFC.
#
# FFC is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# FFC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with FFC. If not, see <http://www.gnu.org/licenses/>.
#
# First added:  2010-02-01
# Last changed: 2010-02-01

import unittest
from .test_against_fiat import main as fiat_main
from ffc.log import CRITICAL, INFO

class EvaluateBasisTests(unittest.TestCase):

    def testAgainstFiat(self):
        "Test evaluate basis against FIAT.FiniteElement.tabulate()."

        error = fiat_main(INFO)
        self.assertEqual(error, 0, "Errors while testing evaluate_basis against FIAT, see fiat_errors.log for details")

if __name__ == "__main__":
    unittest.main()
