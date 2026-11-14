"""A simulated BYD battery (TCP server) for poll() tests.

It answers the requests of BYDHVS.poll() with synthetic frames that look
like a 1-tower HVS with 3 modules (96 cells, 36 temperatures), the same
layout as the maintainer's battery. Every received request is recorded
in `FakeBattery.received`, so tests can check that poll() sends exactly
the expected request sequence (and no additional writes).

Faults can be injected per request name to test the error handling:
    "drop"     - send no answer
    "split"    - send the answer in small chunks with pauses
    "corrupt"  - send the answer with a broken CRC
    "exception"- answer with a Modbus exception frame
    "delay"    - send a response after longer than the client timeout
    "disconnect" - close connection without answering
    "wrong_write_echo" - acknowledge the wrong register/count
    "bad_serial" - respond with non-ASCII bytes and a valid CRC
Each fault in a list is used once, for the next matching request.
"""

import asyncio

from frames import exception_response, read_response, write_response, with_crc

# Request frames exactly as BYDHVS sends them (see BYDHVS._requests).
REQUESTS = {
    "read_serial_number": bytes.fromhex("010300000066c5e0"),
    "read_status_information": bytes.fromhex("01030500001984cc"),
    "read_battery_info": bytes.fromhex("010300100003040e"),
    "start_measure_box_1": bytes.fromhex("0110055000020400018100f853"),
    "read_measurement_status": bytes.fromhex("010305510001d517"),
    "read_cell_volt_temp": bytes.fromhex("01030558004104e5"),
}
NAME_BY_REQUEST = {frame: name for name, frame in REQUESTS.items()}

SERIAL = "P030T020Z2008190034"  # 19 chars; 3rd char "3" (51) = HVS


def _packet0() -> bytes:
    """Serial number, firmware versions, towers/modules, grid type."""
    data = bytearray(0x66 * 2)  # 0x66 registers
    data[0:19] = SERIAL.encode("ascii")  # frame bytes 3-21
    # frame byte n = data[n - 3]
    data[27 - 3:29 - 3] = bytes([3, 26])  # BMU A V3.26
    data[29 - 3:31 - 3] = bytes([3, 27])  # BMU B V3.27
    data[31 - 3:33 - 3] = bytes([3, 31])  # BMS V3.31
    data[33 - 3] = 1  # BMU runs from bank B
    data[34 - 3] = 1  # BMS bank B
    data[36 - 3] = 0x13  # 1 tower (high nibble), 3 modules (low nibble)
    data[38 - 3] = 1  # OnGrid
    return read_response(bytes(data))


def _packet1() -> bytes:
    """Battery status: SOC, voltages, current, temperatures, totals."""
    data = bytearray(0x19 * 2)

    def put16(frame_pos: int, value: int) -> None:
        data[frame_pos - 3:frame_pos - 1] = value.to_bytes(
            2, "big", signed=value < 0
        )

    put16(3, 87)  # SOC %
    put16(5, 334)  # max cell voltage 3.34 V
    put16(7, 331)  # min cell voltage 3.31 V
    put16(9, 99)  # SOH %
    put16(11, -52)  # current -5.2 A
    put16(13, 32040)  # battery voltage 320.4 V
    put16(15, 21)  # max temp
    put16(17, 19)  # min temp
    put16(19, 20)  # battery temp
    put16(29, 0)  # error flags
    data[31 - 3:33 - 3] = bytes([1, 7])  # param table 1.7
    put16(35, 32100)  # output voltage 321.0 V
    # charge/discharge totals: 32 bit, low word first (see _buf2int32_us)
    data[37 - 3:41 - 3] = bytes([0x30, 0x39, 0x00, 0x00])  # 12345 -> 1234.5
    data[41 - 3:45 - 3] = bytes([0x2B, 0x67, 0x00, 0x00])  # 11111 -> 1111.1
    return read_response(bytes(data))


def _packet2() -> bytes:
    """Inverter type (byte 3) and battery type (byte 5, 2 = HVS)."""
    return read_response(bytes([0, 0, 2, 0, 0, 0]))


def _cell_packets() -> list:
    """Packets 5-8 (cell voltages, temperatures, tower data)."""
    packets = []
    for number in range(4):
        data = bytearray(0x41 * 2)
        if number == 0:
            data[5 - 3:7 - 3] = (3340).to_bytes(2, "big")  # max mV
            data[7 - 3:9 - 3] = (3310).to_bytes(2, "big")  # min mV
            data[9 - 3] = 12  # cell with max voltage
            data[10 - 3] = 40  # cell with min voltage
            data[17 - 3] = 0x81  # balancing cells 1 and 8
            data[59 - 3:61 - 3] = (0x0010).to_bytes(2, "big")  # imbalance
            # cell voltages 1-16 from frame byte 101
            for i in range(16):
                data[101 - 3 + i * 2:103 - 3 + i * 2] = (3300 + i).to_bytes(
                    2, "big"
                )
        elif number in (1, 2):
            first_cell = 17 if number == 1 else 81
            for i in range(64 if number == 1 else 48):
                data[5 - 3 + i * 2:7 - 3 + i * 2] = (
                    3300 + first_cell - 1 + i
                ).to_bytes(2, "big")
            if number == 2:
                for i in range(30):  # temperatures 1-30 from byte 103
                    data[103 - 3 + i] = 15 + i % 5
        else:
            for i in range(34):  # temperatures 31-64 from byte 5
                data[5 - 3 + i] = 18
        packets.append(read_response(bytes(data)))
    return packets


class FakeBattery:
    """TCP server answering BYDHVS requests with synthetic frames."""

    def __init__(self) -> None:
        self.received: list = []
        self.faults: dict = {}
        self._server = None
        self.port = 0

    def add_fault(self, request_name: str, fault: str) -> None:
        """Use `fault` for the next `request_name` request."""
        self.faults.setdefault(request_name, []).append(fault)

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle, "127.0.0.1", 0
        )
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        self._server.close()
        await self._server.wait_closed()

    def _answer(self, name: str, cell_packets: list) -> bytes:
        if name == "read_serial_number":
            return _packet0()
        if name == "read_status_information":
            return _packet1()
        if name == "read_battery_info":
            return _packet2()
        if name == "start_measure_box_1":
            return write_response(0x0550, 2)
        if name == "read_measurement_status":
            return read_response(bytes(2))
        if name == "read_cell_volt_temp":
            return cell_packets.pop(0)
        return exception_response(3, 1)

    async def _handle(self, reader, writer) -> None:
        cell_packets = _cell_packets()
        try:
            while True:
                request = await reader.read(1024)
                if not request:
                    break
                name = NAME_BY_REQUEST.get(request, request.hex())
                self.received.append(name)
                fault = None
                if self.faults.get(name):
                    fault = self.faults[name].pop(0)
                if fault == "drop":
                    continue
                if fault == "disconnect":
                    break
                if fault == "exception":
                    writer.write(exception_response(request[1], 2))
                    await writer.drain()
                    continue
                answer = self._answer(name, cell_packets)
                if fault == "delay":
                    await asyncio.sleep(0.45)
                if fault == "wrong_write_echo":
                    answer = write_response(0x0100, 3)
                if fault == "bad_serial":
                    payload = bytearray(answer[:-2])
                    payload[5] = 0xFF
                    answer = with_crc(bytes(payload))
                if fault == "corrupt":
                    answer = answer[:-1] + bytes([answer[-1] ^ 0xFF])
                if fault == "split":
                    for start in range(0, len(answer), 20):
                        writer.write(answer[start:start + 20])
                        await writer.drain()
                        await asyncio.sleep(0.01)
                else:
                    writer.write(answer)
                    await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()


# Request sequence of a successful poll of a 1-tower battery with <= 128
# cells. Only start_measure_box_1 is a write (function 16).
EXPECTED_SEQUENCE = [
    "read_serial_number",
    "read_status_information",
    "read_battery_info",
    "start_measure_box_1",
    "read_measurement_status",
    "read_cell_volt_temp",
    "read_cell_volt_temp",
    "read_cell_volt_temp",
    "read_cell_volt_temp",
]
