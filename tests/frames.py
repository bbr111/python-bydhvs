"""Helpers to build synthetic Modbus RTU frames for the tests.

The battery answers in Modbus RTU format, sent over TCP:

    read  (function 3):  [address, 3, byte_count, data..., crc_lo, crc_hi]
    write (function 16): [address, 16, reg_hi, reg_lo, count_hi, count_lo,
                          crc_lo, crc_hi]                      (8 bytes)
    exception:           [address, function | 0x80, code, crc_lo, crc_hi]

The CRC is Modbus CRC16, appended low byte first. A frame including its
CRC has a CRC16 of 0, which is what BYDHVS._check_packet() tests.
"""

from bydhvs import CRC16


def with_crc(frame: bytes) -> bytes:
    """Append the Modbus CRC16 (low byte first) to a frame."""
    crc = CRC16(frame)
    return frame + bytes([crc & 0xFF, crc >> 8])


def read_response(data: bytes) -> bytes:
    """Return a valid function 3 response carrying `data`."""
    return with_crc(bytes([1, 3, len(data)]) + data)


def write_response(register: int = 0x0550, count: int = 2) -> bytes:
    """Return a valid function 16 (write) confirmation."""
    return with_crc(
        bytes([1, 16]) + register.to_bytes(2, "big") + count.to_bytes(2, "big")
    )


def exception_response(function: int = 3, code: int = 2) -> bytes:
    """Return a valid Modbus exception response."""
    return with_crc(bytes([1, function | 0x80, code]))
