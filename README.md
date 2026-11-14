# python-bydhvs
Python Wrapper for BYD b-Box HVM/HVS/LVS

This is a python module to communicate with an BYD HVM/HVS/LVS.

inspired by (https://github.com/christianh17/ioBroker.bydhvs)

If used with **BYD Be Connect** at the same time. This module is **not** working correctly.

Tested with 2 Towers and 5 Modules. Thx @st0ne-dot-at

Installation
------------
The module is available from the [Python Package Index](https://pypi.python.org/pypi)


    $ pip3 install bydhvs

On a Fedora-based system or a CentOS/RHEL host with EPEL.

    $ sudo dnf -y install python3-bydhvs

Usage
-----

The file ``example.py`` contains an example about how to use this module.

Error handling
--------------

``poll()`` reads all data in one fixed request sequence. It only returns
normally if the whole sequence succeeded; then ``get_data()`` returns the
new values. Otherwise it raises one of these exceptions (all derive from
``BYDHVSError``):

| Exception | Meaning |
|---|---|
| ``BYDHVSTimeoutError`` | No connection or no answer within the timeout |
| ``BYDHVSConnectionError`` | Connection could not be opened or broke |
| ``BYDHVSProtocolError`` | Invalid answer (CRC, Modbus exception, wrong length); subclass of ``BYDHVSConnectionError`` |
| ``BYDHVSError`` | Other problems, e.g. ``poll()`` already running, more than 3 towers |

After an exception, do not use ``get_data()``: it can contain a mix of old
and new values. Up to version 0.4.14, ``poll()`` returned normally even if a
step failed.

A missing or broken answer to a read request that returns the same data
every time (serial number, status, battery info, measurement status) is
retried once. Cell data reads and write requests are never repeated.

Tests
-----

The tests use synthetic frames and a simulated battery (``tests/fake_battery.py``),
no real battery is needed:

    $ pip install crcmod pytest
    $ python -m pytest

Build
-----
To build dev prepare system:

    $ python -m pip install --upgrade pip
    $ pip install build

build package:
  
    $ python -m build

License
-------

``python-byd`` is licensed under GPL-3.0 license, for more details check LICENSE.
