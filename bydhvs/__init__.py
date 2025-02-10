"""Module for communicating with the BYD HVS Battery system.

This module provides the BYDHVS class, which handles communication with
the BYD HVS Battery over TCP/IP sockets. It implements methods to connect
to the battery, send requests, receive and parse responses, and retrieve
data for use in Home Assistant.
"""

import asyncio
import logging

from typing import Optional, Dict, List

import crcmod

_LOGGER = logging.getLogger(__name__)


class BYDHVSError(Exception):
    """Base exception for BYD HVS Battery errors."""


class BYDHVSConnectionError(BYDHVSError):
    """Exception raised when there is a connection error."""


class BYDHVSTimeoutError(BYDHVSError):
    """Exception raised when a timeout occurs during communication."""


CRC16 = crcmod.predefined.mkCrcFun('modbus')


class BYDHVS:
    """Class to communicate with the BYD HVS Battery system."""

    MAX_CELLS = 160
    MAX_TEMPS = 64
    SLEEP_TIME = 3

    def __init__(self, ip_address: str, port: int = 8080) -> None:
        """Initialize the BYDHVS communication class."""
        self.ip_address = ip_address
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.my_state = 0

        # Initialize battery parameters
        self.hvs_soc = 0
        self.hvs_max_volt = 0.0
        self.hvs_min_volt = 0.0
        self.hvs_soh = 0
        self.hvs_serial = ""
        self.hvs_bmu = ""
        self.hvs_bmu_a = ""
        self.hvs_bmu_b = ""
        self.hvs_bms = ""
        self.hvs_modules = 0
        self.hvs_module_cell_count = 0
        self.hvs_module_cell_temp_count = 0
        self.hvs_towers = 0
        self.hvs_grid = ""
        self.hvs_current = 0
        self.hvs_batt_volt = 0.0
        self.hvs_max_temp = 0
        self.hvs_min_temp = 0
        self.hvs_batt_temp = 0
        self.hvs_error = 0
        self.hvs_param_t = ""
        self.hvs_out_volt = 0.0
        self.hvs_power = 0.0
        self.hvs_diff_volt = 0.0
        self.hvs_error_string = ""
        self.hvs_charge_total = 0.0
        self.hvs_discharge_total = 0.0
        self.hvs_eta = 0.0
        self.hvs_batt_type_from_serial = ""
        self.hvs_batt_type = ""
        self.hvs_batt_type_string = ""
        self.hvs_inv_type = ""
        self.hvs_num_cells = 0
        self.hvs_num_temps = 0
        self.tower_attributes: List[Dict] = []
        self.hvs_inv_type_string = ""
        self.balancing_status = ""
        self.balancing_count = 0
        self.max_cell_voltage_mv = 0
        self.min_cell_voltage_mv = 0
        self.max_cell_voltage_cell = 0
        self.min_cell_voltage_cell = 0
        self.max_cell_temp_cell = 0
        self.min_cell_temp_cell = 0
        self.current_tower = 0

# Initialize the requests
# self.my_requests = [
#     bytes.fromhex("010300000066c5e0"),  # 0
#     bytes.fromhex("01030500001984cc"),  # 1
#     bytes.fromhex("010300100003040e"),  # 2
#     bytes.fromhex("0110055000020400018100f853"),  # 3 Start measurement
#     bytes.fromhex("010305510001d517"),  # 4
#     bytes.fromhex("01030558004104e5"),  # 5
#     bytes.fromhex("01030558004104e5"),  # 6
#     bytes.fromhex("01030558004104e5"),  # 7
#     bytes.fromhex("01030558004104e5"),  # 8
#     bytes.fromhex("01100100000306444542554700176f"),  # 9
#       Switching for more than 4 modules
#     bytes.fromhex("0110055000020400018100f853"),  # 10
#       Start measurement of remaining cells
#     bytes.fromhex("010305510001d517"),  # 11
#     bytes.fromhex("01030558004104e5"),  # 12
#     bytes.fromhex("01030558004104e5"),  # 13
#     bytes.fromhex("01030558004104e5"),  # 14
#     bytes.fromhex("01030558004104e5"),  # 15
#     bytes.fromhex("01100550000204000281000853"),  # 16 - Switch to Box 2
# ]

        self.my_requests = {
            # Request 0
            'read_serial_number': bytes.fromhex("010300000066c5e0"),
            # Request 1
            'read_status_information': bytes.fromhex("01030500001984cc"),
            # Request 2
            'read_battery_info': bytes.fromhex("010300100003040e"),
            # Request 3 and 10
            'start_measure_box_1': bytes.fromhex("0110055000020400018100f853"),
            # Request 4 and 11
            'read_measurement_status': bytes.fromhex("010305510001d517"),
            # Requests 5-8 and 12-15
            'read_cell_volt_temp': bytes.fromhex("01030558004104e5"),
            # Request 9
            'switch_pass': bytes.fromhex("01100100000306444542554700176f"),
            # Request 16
            'start_measure_box_2': bytes.fromhex("01100550000204000281000853"),
            'start_measure_box_3': bytes.fromhex("01100550000204000381005993"),
            # BMU
            'EVT_MSG_0_0': bytes.fromhex("011005a000020400008100A6D7"),
            # BMS tower 1
            'EVT_MSG_0_1': bytes.fromhex("011005a000020400018100f717"),
            # BMS tower 2
            'EVT_MSG_0_2': bytes.fromhex("011005a0000204000281000717"),
            # BMS tower 3
            'EVT_MSG_0_3': bytes.fromhex("011005a00002040003810056D7"),
        }

        self.my_errors = [
            "High temperature during charging (cells)",
            "Low temperature during charging (cells)",
            "Overcurrent during discharging",
            "Overcurrent during charging",
            "Main circuit failure",
            "Short circuit alarm",
            "Cell imbalance",
            "Current sensor error",
            "Battery overvoltage",
            "Battery undervoltage",
            "Cell overvoltage",
            "Cell undervoltage",
            "Voltage sensor error",
            "Temperature sensor error",
            "High temperature during discharging (cells)",
            "Low temperature during discharging (cells)",
        ]

        self.stat_tower = [
            "Battery Over Voltage",                         # Bit 0
            "Battery Under Voltage",                        # Bit 1
            "Cells OverVoltage",                            # Bit 2
            "Cells UnderVoltage",                           # Bit 3
            "Cells Imbalance",                              # Bit 4
            "Charging High Temperature(Cells)",             # Bit 5
            "Charging Low Temperature(Cells)",              # Bit 6
            "DisCharging High Temperature(Cells)",          # Bit 7
            "DisCharging Low Temperature(Cells)",           # Bit 8
            "Charging OverCurrent(Cells)",                  # Bit 9
            "DisCharging OverCurrent(Cells)",               # Bit 10
            "Charging OverCurrent(Hardware)",               # Bit 11
            "Short Circuit",                                # Bit 12
            "Inversly Connection",                          # Bit 13
            "Interlock switch Abnormal",                    # Bit 14
            "AirSwitch Abnormal"                            # Bit 15
        ]

        self.my_inverters = [
            "Fronius HV",  # 0
            "Goodwe HV",  # 1
            "Fronius HV",  # 2
            "Kostal HV",  # 3
            "Goodwe HV",  # 4
            "SMA SBS3.7/5.0",  # 5
            "Kostal HV",  # 6
            "SMA SBS3.7/5.0",  # 7
            "Sungrow HV",  # 8
            "Sungrow HV",  # 9
            "Kaco HV",  # 10
            "Kaco HV",  # 11
            "Ingeteam HV",  # 12
            "Ingeteam HV",  # 13
            "SMA SBS 2.5 HV",  # 14
            "undefined",  # 15
            "SMA SBS 2.5 HV",  # 16
            "Fronius HV",  # 17
            "undefined",  # 18
            "SMA STP",  # 19
        ]

    async def connect(self) -> None:
        """Establish a connection to the battery."""
        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.ip_address, self.port
            )
            _LOGGER.debug("Connected to %s:%s", self.ip_address, self.port)
            self.my_state = 2  # Next state
        except TimeoutError as e:
            _LOGGER.error(
                "Timeout connecting to %s:%s - %s",
                self.ip_address, self.port, e
            )
            raise BYDHVSTimeoutError(
                f"Timeout connecting to {self.ip_address}:{self.port}"
            ) from e
        except OSError as e:
            _LOGGER.error(
                "OS error connecting to %s:%s - %s",
                self.ip_address, self.port, e
            )
            raise BYDHVSConnectionError(
                f"OS error connecting to {self.ip_address}:{self.port}"
            ) from e

    async def send_request(self, request: bytes) -> None:
        """Send a request to the battery."""
        if self.writer:
            try:
                self.writer.write(request)
                await self.writer.drain()
                _LOGGER.debug("Sent: %s", request.hex())
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                _LOGGER.error("Error sending data: %s", e)
                self.my_state = 0
        else:
            _LOGGER.error("No connection available")

    async def receive_response(self) -> Optional[bytes]:
        """Receive a response from the battery."""
        if self.reader:
            try:
                data = await asyncio.wait_for(
                    self.reader.read(1024), timeout=5
                    )
                _LOGGER.debug("Received: %s", data.hex())
                return data
            except TimeoutError:
                _LOGGER.error("Socket timeout")
                self.my_state = 0
            except asyncio.IncompleteReadError as e:
                _LOGGER.error("Incomplete read error: %s", e)
                self.my_state = 0
            except (ConnectionResetError, OSError) as e:
                _LOGGER.error("Error receiving data: %s", e)
                self.my_state = 0
        else:
            _LOGGER.error("No connection available")
        return None

    def check_packet(self, data: bytes) -> bool:
        """Check if the received packet is valid."""
        if len(data) < 5:
            return False
        if data[0] != 1:
            return False
        function_code = data[1]
        data_length = data[2]
        packet_length = data_length + 5  # 3 Header, 2 CRC
        if function_code == 3:
            if packet_length != len(data):
                return False
        elif function_code != 16:
            return False
        crc = CRC16(data)
        return crc == 0

    @staticmethod
    def buf2int16_si(data: bytes, pos: int) -> int:
        """Convert buffer to signed 16-bit integer."""
        return int.from_bytes(data[pos:pos + 2], byteorder='big', signed=True)

    @staticmethod
    def buf2int16_us(data: bytes, pos: int) -> int:
        """Convert buffer to unsigned 16-bit integer."""
        return int.from_bytes(data[pos:pos + 2], byteorder='big', signed=False)

    @staticmethod
    def buf2int32_us(data: bytes, pos: int) -> int:
        """Convert buffer to unsigned 32-bit integer."""
        return (
            data[pos + 2] * 16777216
            + data[pos + 3] * 65536
            + data[pos] * 256
            + data[pos + 1]
        )

    def parse_packet0(self, data: bytes) -> None:
        """Parse packet 0 containing serial number and firmware versions."""
        self.hvs_serial = data[3:22].decode('ascii').strip()

        # Hardware type
        hardware_type = data[5]
        if hardware_type == 51:
            self.hvs_batt_type_from_serial = "HVS"
        elif hardware_type in (49, 50):
            self.hvs_batt_type_from_serial = "LVS"

        # Firmware versions
        self.hvs_bmu_a = f"V{data[27]}.{data[28]}"
        self.hvs_bmu_b = f"V{data[29]}.{data[30]}"
        if data[33] == 0:
            self.hvs_bmu = self.hvs_bmu_a + "-A"
        else:
            self.hvs_bmu = self.hvs_bmu_b + "-B"
        self.hvs_bms = f"V{data[31]}.{data[32]}-{chr(data[34] + 65)}"

        # Number of towers and modules
        self.hvs_modules = data[36] % 16
        self.hvs_towers = data[36] // 16

        # Grid type
        grid_type_map = {0: "OffGrid", 1: "OnGrid", 2: "Backup"}
        self.hvs_grid = grid_type_map.get(data[38], "Unknown")

    def parse_packet1(self, data: bytes) -> None:
        """Parse packet 1 containing battery status information."""
        self.hvs_soc = self.buf2int16_si(data, 3)
        self.hvs_max_volt = round(self.buf2int16_si(data, 5) / 100.0, 2)
        self.hvs_min_volt = round(self.buf2int16_si(data, 7) / 100.0, 2)
        self.hvs_soh = self.buf2int16_si(data, 9)
        self.hvs_current = round(self.buf2int16_si(data, 11) / 10.0, 1)
        self.hvs_batt_volt = round(self.buf2int16_us(data, 13) / 100.0, 1)
        self.hvs_max_temp = self.buf2int16_si(data, 15)
        self.hvs_min_temp = self.buf2int16_si(data, 17)
        self.hvs_batt_temp = self.buf2int16_si(data, 19)
        self.hvs_error = self.buf2int16_si(data, 29)
        self.hvs_param_t = f"{data[31]}.{data[32]}"
        self.hvs_out_volt = round(self.buf2int16_us(data, 35) / 100.0, 1)
        self.hvs_power = round(self.hvs_current * self.hvs_out_volt, 2)
        self.hvs_diff_volt = round(self.hvs_max_volt - self.hvs_min_volt, 2)

        # Construct error string based on error codes
        self.hvs_error_string = "; ".join(
            [
                err
                for i, err in enumerate(self.my_errors)
                if self.hvs_error & (1 << i)
            ]
        ) or "No Error"

        self.hvs_charge_total = self.buf2int32_us(data, 37) / 10
        self.hvs_discharge_total = self.buf2int32_us(data, 41) / 10
        if self.hvs_charge_total:
            self.hvs_eta = self.hvs_discharge_total / self.hvs_charge_total
        else:
            self.hvs_eta = 0

    def parse_packet2(self, data: bytes) -> None:
        """Parse packet 2 containing battery type and inverter information."""
        self.hvs_batt_type = data[5]
        self.hvs_inv_type = data[3]

        # Map battery type to module and cell counts
        batt_type_map = {
            0: {'string': 'LVM', 'cell_count': 0, 'temp_count': 0},
            1: {'string': 'HVM', 'cell_count': 16, 'temp_count': 8},
            2: {'string': 'HVS', 'cell_count': 32, 'temp_count': 12},
        }

        batt_info = batt_type_map.get(self.hvs_batt_type, {})
        self.hvs_batt_type_string = batt_info.get('string', '')
        self.hvs_module_cell_count = batt_info.get('cell_count', 0)
        self.hvs_module_cell_temp_count = batt_info.get('temp_count', 0)
        self.hvs_num_cells = self.hvs_modules * self.hvs_module_cell_count
        self.hvs_num_temps = self.hvs_modules * self.hvs_module_cell_temp_count

        if self.hvs_batt_type_from_serial == "LVS":
            self.hvs_batt_type = "LVS"
            self.hvs_module_cell_count = 7
            self.hvs_num_cells = self.hvs_modules * 7
            self.hvs_num_temps = 0
            self.hvs_module_cell_temp_count = 0

        if self.hvs_inv_type < len(self.my_inverters):
            self.hvs_inv_type_string = self.my_inverters[self.hvs_inv_type]
        else:
            self.hvs_inv_type_string = "undefined"

        self.hvs_num_cells = min(self.hvs_num_cells, self.MAX_CELLS)
        self.hvs_num_temps = min(self.hvs_num_temps, self.MAX_TEMPS)

        _LOGGER.debug(
            "Number of cells: %s, Number of temperatures: %s, Modules: %s",
            self.hvs_num_cells,
            self.hvs_num_temps,
            self.hvs_modules,
        )

    def parse_packet5(self, data: bytes, tower_number=0) -> None:
        """Parse packet 5 containing cell voltage and balancing status."""
        tower = self.tower_attributes[tower_number]

        tower['max_cell_voltage_mv'] = self.buf2int16_si(data, 5)
        tower['min_cell_voltage_mv'] = self.buf2int16_si(data, 7)
        tower['max_cell_voltage_cell'] = data[9]
        tower['min_cell_voltage_cell'] = data[10]
        tower['max_cell_temp'] = data[12]
        tower['min_cell_temp'] = data[14]
        tower['max_cell_temp_cell'] = data[15]
        tower['min_cell_temp_cell'] = data[16]

        # Balancing flags (Bytes 17 to 32)
        tower['balancing_status'] = data[17:33].hex()
        tower['balancing_count'] = bin(int(data[17:33].hex(), 16)).count('1')

        tower['charge_total'] = self.buf2int32_us(data, 33)
        tower['discharge_total'] = self.buf2int32_us(data, 37)
        if tower['charge_total']:
            tower['eta'] = tower['discharge_total'] / tower['charge_total']
        else:
            tower['eta'] = 0
        tower['battery_volt'] = round(self.buf2int16_si(data, 45) / 10.0, 1)
        tower['out_volt'] = round(self.buf2int16_si(data, 51) / 10.0, 1)
        tower['hvs_soc_diagnosis'] = round(
            self.buf2int16_si(data, 53) / 10.0, 1
            )
        tower['soh'] = round(self.buf2int16_si(data, 55), 1)
        tower['state'] = f"{data[59]}{data[60]}"
        # tower['state_string'] = self.stat_tower[tower['state']]

        tower['state_string'] = "; ".join(
            [
                err
                for i, err in enumerate(self.stat_tower)
                if int(tower['state']) & (1 << i)
            ]
        ) or "No Error"

        # Cell voltages (Bytes 101 to 132) for cells 1 to 16
        tower['cell_voltages'] = [
            self.buf2int16_si(data, 101 + i * 2) for i in range(16)
        ]

    def parse_packet6(self, data: bytes, tower_number=0) -> None:
        """Parse packet 6 containing additional cell voltages."""
        tower = self.tower_attributes[tower_number]
        max_cells = min(self.hvs_num_cells - 16, 64)
        tower['cell_voltages'].extend([
            self.buf2int16_si(data, 5 + i * 2) for i in range(max_cells)
        ])

    def parse_packet7(self, data: bytes, tower_number=0) -> None:
        """Parse packet 7 containing more cell voltages and temperatures."""
        tower = self.tower_attributes[tower_number]
        max_cells = min(self.hvs_num_cells - 80, 48)
        tower['cell_voltages'].extend([
            self.buf2int16_si(data, 5 + i * 2) for i in range(max_cells)
        ])

        max_temps = min(self.hvs_num_temps, 30)
        tower['cell_temperatures'] = list(data[103:103 + max_temps])

    def parse_packet8(self, data: bytes, tower_number=0) -> None:
        """Parse packet 8 containing additional cell temperatures."""
        tower = self.tower_attributes[tower_number]
        max_temps = min(self.hvs_num_temps - 30, 34)
        tower['cell_temperatures'].extend(list(data[5:5 + max_temps]))

    def parse_packet12(self, data: bytes, tower_number=0) -> None:
        """Parse packet 12 for systems with more than 128 cells."""
        tower = self.tower_attributes[tower_number]
        balancing_data = int.from_bytes(data[17:33], 'big')
        tower['balancing_count'] = bin(balancing_data).count('1')

        tower['cell_voltages'].extend([
            self.buf2int16_si(data, 101 + i * 2) for i in range(16)
        ])

    def parse_packet13(self, data: bytes, tower_number=0) -> None:
        """Parse packet 13 for systems with more than 144 cells."""
        tower = self.tower_attributes[tower_number]
        start_cell = 144
        max_cells = min(self.hvs_num_cells - start_cell, 16)
        tower['cell_voltages'].extend([
            self.buf2int16_si(data, 5 + i * 2) for i in range(max_cells)
        ])

    async def close(self) -> None:
        """Close the connection to the battery."""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            self.reader = None
            self.writer = None
            _LOGGER.debug("Connection closed")

    async def poll(self) -> None:
        """Perform a polling cycle to retrieve data from the battery."""
        if self.my_state != 0:
            _LOGGER.warning("Already polling")
            return
        self.my_state = 1
        await self.connect()
        if self.my_state == 0:
            await self.close()
            return  # Connection failed

        # State machine for polling process
        state_actions = {
            2: self.state2_send_request0,
            3: self.state3_send_request1,
            4: self.state4_send_request2,
            5: self.state5_start_measurement,
            6: self.state6_send_request4,
            7: self.state7_send_request5,
            8: self.state8_send_request6,
            9: self.state9_send_request7,
            10: self.state10_send_request8,
            11: self.state11_send_request9,
            12: self.state12_send_request10,
            13: self.state13_send_request11,
            14: self.state14_send_request12,
            15: self.state15_send_request13,
        }

        while self.my_state != 0:
            action = state_actions.get(self.my_state)
            if action:
                await action()
            else:
                _LOGGER.error("Unknown state: %s", self.my_state)
                self.my_state = 0

        # Close the connection
        await self.close()
        self.my_state = 0

    async def state2_send_request0(self) -> None:
        """State 2: Send request 0 and parse packet 0."""
        await self.send_request(self.my_requests['read_serial_number'])
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.parse_packet0(data)

            # Initialize tower attributes after knowing hvsTowers
            self.tower_attributes = [{} for _ in range(self.hvs_towers or 1)]
            for tower in self.tower_attributes:
                tower['cell_voltages'] = []
                tower['cell_temperatures'] = []
            self.my_state = 3
        else:
            _LOGGER.error("Invalid or no data received in state 2")
            self.my_state = 0

    async def state3_send_request1(self) -> None:
        """State 3: Send request 1 and parse packet 1."""
        await self.send_request(self.my_requests['read_status_information'])
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.parse_packet1(data)
            self.my_state = 4
        else:
            _LOGGER.error("Invalid or no data received in state 3")
            self.my_state = 0

    async def state4_send_request2(self) -> None:
        """State 4: Send request 2 and parse packet 2."""
        await self.send_request(self.my_requests['read_battery_info'])
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.parse_packet2(data)
            # Decide whether to continue with detailed query
            if self.hvs_num_cells > 0 and self.hvs_num_temps > 0:
                self.my_state = 5
            else:
                self.my_state = 0  # End polling if no detailed data available
        else:
            _LOGGER.error("Invalid or no data received in state 4")
            self.my_state = 0

    async def state5_start_measurement(self) -> None:
        """State 5: Start measurement and proceed with detailed queries."""
        if self.current_tower == 0:
            await self.send_request(self.my_requests['start_measure_box_1'])
        elif self.current_tower == 1:
            await self.send_request(self.my_requests['start_measure_box_2'])
        elif self.current_tower == 2:
            await self.send_request(self.my_requests['start_measure_box_3'])
        data = await self.receive_response()
        if data and self.check_packet(data):
            # Wait time as per original code (e.g., 8 seconds)
            await asyncio.sleep(self.SLEEP_TIME)
            self.my_state = 6
        else:
            _LOGGER.error("Invalid or no data received in state 5")
            self.my_state = 0

    async def state6_send_request4(self) -> None:
        """State 6: Send request 4"""
        await self.send_request(self.my_requests['read_measurement_status'])
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.my_state = 7
        else:
            _LOGGER.error("Invalid or no data received in state 6")
            self.my_state = 0

    async def state7_send_request5(self) -> None:
        """State 7: Send request 5 and parse with parse_packet5 for tower 0"""
        await self.send_request(
            self.my_requests['read_cell_volt_temp']
            )
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.parse_packet5(data, self.current_tower)
            self.my_state = 8
        else:
            _LOGGER.error("Invalid or no data received in state 7")
            self.my_state = 0

    async def state8_send_request6(self) -> None:
        """ State 8: Send request 6 and parse with parse_packet6 for tower 0"""
        await self.send_request(
            self.my_requests['read_cell_volt_temp']
            )
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.parse_packet6(data, self.current_tower)
            self.my_state = 9
        else:
            _LOGGER.error("Invalid or no data received in state 8")
            self.my_state = 0

    async def state9_send_request7(self) -> None:
        """State 9: Send request 7 and parse with parse_packet7 for tower 0"""
        await self.send_request(
            self.my_requests['read_cell_volt_temp']
            )
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.parse_packet7(data, self.current_tower)
            self.my_state = 10
        else:
            _LOGGER.error("Invalid or no data received in state 9")
            self.my_state = 0

    async def state10_send_request8(self) -> None:
        """State 10: Send request 8 and parse with parse_packet8 for tower 0"""
        await self.send_request(
            self.my_requests['read_cell_volt_temp']
            )
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.parse_packet8(data, self.current_tower)
            # Check if we have more than 128 cells
            if self.hvs_num_cells > 128:
                self.my_state = 11
            else:
                if self.current_tower + 1 < self.hvs_towers:
                    self.current_tower += 1
                    self.my_state = 5
                else:
                    self.my_state = 0  # Polling completed
        else:
            _LOGGER.error("Invalid or no data received in state 10")
            self.my_state = 0

    async def state11_send_request9(self) -> None:
        """Handle additional cells for more than 128 cells (e.g., 5 modules)"""
        # State 11: Send request 9 - Switch to second pass
        await self.send_request(self.my_requests['switch_pass'])
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.my_state = 12
        else:
            _LOGGER.error("Invalid or no data received in state 11")
            self.my_state = 0

    async def state12_send_request10(self) -> None:
        """State 12: Send request 10 - Start measurement"""
        if self.current_tower == 0:
            await self.send_request(self.my_requests['start_measure_box_1'])
        elif self.current_tower == 1:
            await self.send_request(self.my_requests['start_measure_box_2'])
        elif self.current_tower == 2:
            await self.send_request(self.my_requests['start_measure_box_3'])
        data = await self.receive_response()
        if data and self.check_packet(data):
            # Wait time as per original code (e.g., 3 seconds)
            await asyncio.sleep(self.SLEEP_TIME)
            self.my_state = 13
        else:
            _LOGGER.error("Invalid or no data received in state 12")
            self.my_state = 0

    async def state13_send_request11(self) -> None:
        """State 13: Send request 11"""
        await self.send_request(self.my_requests['read_measurement_status'])
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.my_state = 14
        else:
            _LOGGER.error("Invalid or no data received in state 13")
            self.my_state = 0

    async def state14_send_request12(self) -> None:
        """State 14: Send request 12 and parse with parse_packet12"""
        await self.send_request(
            self.my_requests['read_cell_volt_temp']
            )
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.parse_packet12(data, self.current_tower)
            self.my_state = 15
        else:
            _LOGGER.error("Invalid or no data received in state 14")
            self.my_state = 0

    async def state15_send_request13(self) -> None:
        """State 15: Send request 13 and parse with parse_packet13"""
        await self.send_request(
            self.my_requests['read_cell_volt_temp']
            )
        data = await self.receive_response()
        if data and self.check_packet(data):
            self.parse_packet13(data, self.current_tower)
            if self.current_tower + 1 < self.hvs_towers:
                self.current_tower += 1
                self.my_state = 5
            else:
                self.my_state = 0  # Letzter Turm erreicht
        else:
            _LOGGER.error("Invalid or no data received in state 15")
            self.my_state = 0

    def get_data(self) -> dict:
        """Retrieve the collected data."""
        return {
            "serial_number": self.hvs_serial,
            "bmu_firmware": self.hvs_bmu,
            "bmu_firmware_a": self.hvs_bmu_a,
            "bmu_firmware_b": self.hvs_bmu_b,
            "bms_firmware": self.hvs_bms,
            "modules": self.hvs_modules,
            "module_cell_count": self.hvs_module_cell_count,
            "module_cell_temp_count": self.hvs_module_cell_temp_count,
            "towers": self.hvs_towers,
            "grid_type": self.hvs_grid,
            "soc": self.hvs_soc,
            "max_voltage": self.hvs_max_volt,
            "min_voltage": self.hvs_min_volt,
            "soh": self.hvs_soh,
            "current": self.hvs_current,
            "battery_voltage": self.hvs_batt_volt,
            "max_temperature": self.hvs_max_temp,
            "min_temperature": self.hvs_min_temp,
            "battery_temperature": self.hvs_batt_temp,
            "voltage_difference": self.hvs_diff_volt,
            "power": self.hvs_power,
            "error_number": self.hvs_error,
            "error_string": self.hvs_error_string,
            "param_t": self.hvs_param_t,
            "output_voltage": self.hvs_out_volt,
            "charge_total": self.hvs_charge_total,
            "discharge_total": self.hvs_discharge_total,
            "eta": self.hvs_eta,
            "battery_type_from_serial": self.hvs_batt_type_from_serial,
            "battery_type": self.hvs_batt_type,
            "battery_type_string": self.hvs_batt_type_string,
            "inverter_type": self.hvs_inv_type_string,
            "number_of_cells": self.hvs_num_cells,
            "number_of_temperatures": self.hvs_num_temps,
            "tower_attributes": self.tower_attributes,
        }
