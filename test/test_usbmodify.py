#!/usr/bin/env python
#
# Copyright (C) 2011 Austin Leirvik <aua at pdx.edu>
# Copyright (C) 2011 Wil Cooley <wcooley at pdx.edu>
# Copyright (C) 2011 Joanne McBride <jirab21@yahoo.com>
# Copyright (C) 2011 Danny Aley <danny.aley@gmail.com>
# Copyright (C) 2011 Erich Ulmer <blurrymadness@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
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
"""Unit tests for usbmodify.py"""

from __future__ import division

import os
import struct
import tempfile
import unittest

import pcapy

from tutil import *
import usbmodify
from usbrevue import Packet

# Why write programs when you can write programs that write programs?
#
# Rather than a lot of nearly-identical test functions, generate test functions
# based on data.
#
# See: http://stackoverflow.com/q/2798956/627003

ModAttrsByRoutineFileBasic_test_data = (
    ('urb = 12345',         'urb',              12345),
    ('event_type = "E"',    'event_type',       'E'),
    ('xfer_type = 3',       'xfer_type',        3),
    ('epnum = 55',          'epnum',            55),
    ('devnum = 12',         'devnum',           12),
    ('busnum = 32',         'busnum',           32),
    ('flag_setup = "1"',    'flag_setup',       '1'),
    ('flag_data = "!"',     'flag_data',        '!'),
    ('ts_sec = 9876543210', 'ts_sec',           9876543210),
    ('ts_usec = 1234567890', 'ts_usec',         1234567890),
    ('status = 42',         'status',           42),
    ('length = 16',         'length',           16),
    ('len_cap = 1',         'len_cap',          1),
    ('xfer_flags = 49294',  'xfer_flags',       49294),
    ('ndesc = 847934',      'ndesc',            847934),
)

class ModAttrsByRoutineFileBasic(unittest.TestCase):
    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile('w', 0) # buf=0 makes it
                                                           # show up immediately
        self.modifier = usbmodify.Modifier(None, self.tmpfile.name, None)

    def tearDown(self):
        self.tmpfile.close()    # tempfile deletes on close

def ModAttrsByRoutineFileBasic_create_test(line, attr, expected):
    """Manufacture a test function"""
    def do_test_expected(self):
        self.tmpfile.write(line)

        for packet in packet_generator():
            self.modifier.apply_routine_file(packet)
            self.assertEqual(getattr(packet, attr), expected)
    return do_test_expected

# Iterate through test data and create and install test functions into
# ModAttrsByRoutineFileBasic class
for vals in ModAttrsByRoutineFileBasic_test_data:
    test_method = ModAttrsByRoutineFileBasic_create_test(*vals)
    test_method.__name__ = 'test_mod_%s' % vals[1]
    setattr(ModAttrsByRoutineFileBasic, test_method.__name__, test_method)

class ModAttrsByRoutineFile(unittest.TestCase):
    """Change each packet attribute to some value. All tests should
    pass.

    """

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile('w', 0) # buf=0 makes it
                                                           # show up immediately
        self.modifier = usbmodify.Modifier(None, self.tmpfile.name, None)

    def tearDown(self):
        self.tmpfile.close()    # tempfile deletes on close


    def test_mod_setup(self):
        self.tmpfile.write('if flag_setup == "S": setup = [12]')

        for packet in packet_generator():
            if packet.flag_setup == "s":
                self.modifier.apply_routine_file(packet)
                self.assertEqual(packet.setup, [12])


    def test_mod_error_count(self):
        self.tmpfile.write('if xfer_type == 0: error_count = 99')

        for packet in packet_generator():
            if packet.xfer_type == 0:
                self.modifier.apply_routine_file(packet)
                self.assertEqual(packet.error_count, 99)


    def test_mod_numdesc(self):
        self.tmpfile.write('if xfer_type == 0: numdesc = 200')

        for packet in packet_generator():
            if packet.xfer_type == 0:
                self.modifier.apply_routine_file(packet)
                self.assertEqual(packet.numdesc, 200)


    def test_mod_interval(self):
        self.tmpfile.write('if xfer_type in [0, 1]: interval = 2')

        for packet in packet_generator():
            if packet.xfer_type in [0, 1]:
                self.modifier.apply_routine_file(packet)
                self.assertEqual(packet.interval, 2)


    def test_mod_start_frame(self):
        self.tmpfile.write('if xfer_type == 0: start_frame = 4')

        for packet in packet_generator():
            if packet.xfer_type == 0:
                self.modifier.apply_routine_file(packet)
                self.assertEqual(packet.start_frame, 4)


class ModByModule(unittest.TestCase):
    """Change different packet attributes with a user-supplied module."""




class ModDataByExp(unittest.TestCase):
    """Change a data byte to a value based on two other data
    bytes. All tests should pass.

    """

    def test_add(self):
        modifier = usbmodify.Modifier(None, None, ['data[0] = data[1] + data[2]'])

        for packet in packet_generator():
            modifier.apply_cmdline_exps(packet)
            if len(packet.data):
                self.assertEqual(packet.data[0], packet.data[1] + packet.data[2])


    def test_sub(self):
        modifier = usbmodify.Modifier(None, None, ['data[0] = data[1] - data[2]'])

        for packet in packet_generator():
            modifier.apply_cmdline_exps(packet)
            if len(packet.data):
                self.assertEqual(packet.data[0], packet.data[1] - packet.data[2])


    def test_mult(self):
        modifier = usbmodify.Modifier(None, None, ['data[0] = data[1] * data[2]'])

        for packet in packet_generator():
            modifier.apply_cmdline_exps(packet)
            if len(packet.data):
                self.assertEqual(packet.data[0], packet.data[1] * packet.data[2])


    def test_div(self):
        modifier = usbmodify.Modifier(None, None, ['data[0] = data[1] / (data[2] + 1)'])

        for packet in packet_generator():
            modifier.apply_cmdline_exps(packet)
            if len(packet.data):
                self.assertEqual(packet.data[0], packet.data[1] / (packet.data[2] + 1))


    def test_bit_and(self):
        modifier = usbmodify.Modifier(None, None, ['data[0] = data[1] & data[2]'])

        for packet in packet_generator():
            modifier.apply_cmdline_exps(packet)
            if len(packet.data):
                self.assertEqual(packet.data[0], packet.data[1] & packet.data[2])


    def test_bit_or(self):
        modifier = usbmodify.Modifier(None, None, ['data[0] = data[1] | data[2]'])

        for packet in packet_generator():
            modifier.apply_cmdline_exps(packet)
            if len(packet.data):
                self.assertEqual(packet.data[0], packet.data[1] | packet.data[2])


    def test_bit_not(self):
        modifier = usbmodify.Modifier(None, None, ['data[0] = ~ data[1]'])

        for packet in packet_generator():
            modifier.apply_cmdline_exps(packet)
            if len(packet.data):
                self.assertEqual(packet.data[0], ~ packet.data[1])


    def test_bit_xor(self):
        modifier = usbmodify.Modifier(None, None, ['data[0] = data[1] ^ data[2]'])

        for packet in packet_generator():
            modifier.apply_cmdline_exps(packet)
            if len(packet.data):
                self.assertEqual(packet.data[0], packet.data[1] ^ packet.data[2])


    def test_logical_and(self):
        modifier = usbmodify.Modifier(None, None, ['data[0] = data[1] and data[2]'])

        for packet in packet_generator():
            modifier.apply_cmdline_exps(packet)
            if len(packet.data):
                self.assertEqual(packet.data[0], packet.data[1] and packet.data[2])


    def test_logical_or(self):
        modifier = usbmodify.Modifier(None, None, ['data[0] = data[1] or data[2]'])

        for packet in packet_generator():
            modifier.apply_cmdline_exps(packet)
            if len(packet.data):
                self.assertEqual(packet.data[0], packet.data[1] or packet.data[2])


    def test_logical_not(self):
        modifier = usbmodify.Modifier(None, None, ['data[0] = not data[1]'])

        for packet in packet_generator():
            modifier.apply_cmdline_exps(packet)
            if len(packet.data):
                self.assertEqual(packet.data[0], not packet.data[1])


    def test_logical_xor(self):
        modifier = usbmodify.Modifier(None, None, ['data[0] = bool(data[1]) ^ bool(data[2])'])

        for packet in packet_generator():
            modifier.apply_cmdline_exps(packet)
            if len(packet.data):
                self.assertEqual(packet.data[0], bool(packet.data[1]) ^ bool(packet.data[2]))



class BadData(unittest.TestCase):
    """Check that invalid attribute values will be rejected."""

    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile('w', 0)
        self.modifier = usbmodify.Modifier(None, self.tmpfile.name, None)

    def tearDown(self):
        self.tmpfile.close()

    def test_bad_urb(self):
        self.tmpfile.write('urb = 100 ** 100')

        for packet in packet_generator():

            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)

    def test_bad_type(self):
        self.tmpfile.write('event_type = "XX"')

        for packet in packet_generator():
            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_xfer_type(self):
        self.tmpfile.write('xfer_type = -44')

        for packet in packet_generator():
            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_epnum(self):
        self.tmpfile.write('epnum = AB')

        for packet in packet_generator():
            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_devnum(self):
        self.tmpfile.write('devnum = YZ')

        for packet in packet_generator():
            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_busnum(self):
        self.tmpfile.write('busnum = -100')

        for packet in packet_generator():
            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_flag_setup(self):
        self.tmpfile.write('flag_setup = C')

        for packet in packet_generator():
            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_ts_sec(self):
        self.tmpfile.write('ts_sec = 100 ** 100')

        for packet in packet_generator():
            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_ts_usec(self):
        self.tmpfile.write('ts_usec = -100 ** 100')

        for packet in packet_generator():
            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_status(self):
        self.tmpfile.write('status = "a string"')

        for packet in packet_generator():
            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_length(self):
        self.tmpfile.write('length = -1')

        for packet in packet_generator():
            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_len_cap(self):
        self.tmpfile.write('len_cap = 10 ** 10')

        for packet in packet_generator():
            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_setup(self):
        self.tmpfile.write('if flag_setup == "S": setup = [-4]')

        for packet in packet_generator():
            if packet.flag_setup == "S":
                self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_error_count(self):
        self.tmpfile.write('if xfer_type == 0: error_count = 4.5')

        for packet in packet_generator():
            if packet.xfer_type == 0:
                self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_numdesc(self):
        self.tmpfile.write('if xfer_type == 0: numdesc = -7 ** 0.5')

        for packet in packet_generator():
            if packet.xfer_type == 0:
                self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_interval(self):
        self.tmpfile.write('if xfer_type in [0, 1]: interval = -2.5 ** 100')

        for packet in packet_generator():
            if packet.xfer_type in [0, 1]:
                self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_start_frame(self):
        self.tmpfile.write('if xfer_type == 0: start_frame = 500.0 * 0.284794')

        for packet in packet_generator():
            if packet.xfer_type == 0:
                self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_xfer_flags(self):
        self.tmpfile.write('xfer_flags = "abcde"')

        for packet in packet_generator():
            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)


    def test_bad_ndesc(self):
        self.tmpfile.write('ndesc = -0.1 ** -100')

        for packet in packet_generator():
            self.assertRaises(ValueError, self.modifier.apply_routine_file, packet)




def packet_generator():
    pcap = pcapy.open_offline(test_data('testdump_usbmodify.pcap'))

    while True:
        (hdr, pack) = pcap.next()
        if hdr is None:
            return # EOF
        yield Packet(hdr, pack)





if __name__ == "__main__":
    unittest.main()
