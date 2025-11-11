"""Example for bydhvs"""
import asyncio
from bydhvs import BYDHVS, BYDHVSError


async def main():
    """Main func"""
    # Replace with IP address of your BYD HVS battery system
    battery_ip = '192.168.16.254'
    battery_port = '8080'

    battery = BYDHVS(ip_address=battery_ip, port=battery_port)

    try:
        # Perform the polling to retrieve data
        await battery.poll()

        # Get the collected data
        data = battery.get_data()

        # Print the retrieved data
        print("Battery Data:")
        print(f"Serial Number       : {data['serial_number']}")
        print(f"BMU Firmware        : {data['bmu_firmware']}")
        print(f"BMU Firmware_A      : {data['bmu_firmware_a']}")
        print(f"BMU Firmware_B      : {data['bmu_firmware_b']}")
        print(f"BMS Firmware        : {data['bms_firmware']}")
        print(f"Modules             : {data['modules']}")
        print(f"ModuleCellCount     : {data['module_cell_count']}")
        print(f"ModuleCellTempCount : {data['module_cell_temp_count']}")
        print(f"Towers              : {data['towers']}")
        print(f"Grid Type           : {data['grid_type']}")
        print(f"SOC                 : {data['soc']}%")
        print(f"Max Voltage         : {data['max_voltage']} V")
        print(f"Min Voltage         : {data['min_voltage']} V")
        print(f"SOH                 : {data['soh']}%")
        print(f"Current             : {data['current']} A")
        print(f"Battery Voltage     : {data['battery_voltage']} V")
        print(f"Max Temperature     : {data['max_temperature']} °C")
        print(f"Min Temperature     : {data['min_temperature']} °C")
        print(f"Battery Temperature : {data['battery_temperature']} °C")
        print(f"Voltage Difference  : {data['voltage_difference']} V")
        print(f"Power               : {data['power']} W")
        print(f"Error Number        : {data['error_number']}")
        print(f"Error String        : {data['error_string']}")
        print(f"Charge Total        : {data['charge_total']} kWh")
        print(f"Discharge Total     : {data['discharge_total']} kWh")
        print(f"ETA                 : {data['eta']}")
        print(f"Battery Type        : {data['battery_type']}")
        print(f"Battery Type String : {data['battery_type_string']}")
        print(f"Inverter Type       : {data['inverter_type']}")
        print(f"State Action List   : {data['state_action_list']}")
        for idx, tower in enumerate(data['tower_attributes']):
            print(f"\nTower {idx + 1}:")
            print(f"""  Max Cell Voltage (mV): {
                  tower.get('max_cell_voltage_mv')}""")
            print(f"""  Min Cell Voltage (mV): {
                  tower.get('min_cell_voltage_mv')}""")
            print(f"""  Max Cell Voltage Cell: No. {
                  tower.get('max_cell_voltage_cell')}""")
            print(f"""  Min Cell Voltage Cell: No. {
                  tower.get('min_cell_voltage_cell')}""")
            print(f"  Max Cell Temp         : {tower.get('max_cell_temp')}°C")
            print(f"  Min Cell Temp         : {tower.get('min_cell_temp')}°C")
            print(f"""  Max Cell Temp Cell    : No.{
                  tower.get('max_cell_temp_cell')}""")
            print(f"""  Min Cell Temp Cell    : No.{
                  tower.get('min_cell_temp_cell')}""")
            print(f"  Balancing Status      : {tower.get('balancing_status')}")
            print(f"  Balancing Count       : {tower.get('balancing_count')}")
            print(f"  Current               : {tower.get('current')} A")
            print(f"  Total Charge          : {tower.get('charge_total')} kWh")
            print(f"""  Discharge Total       : {
                tower.get('discharge_total')} kWh""")
            print(f"  ETA                   : {tower.get('eta')}")
            print(f"  Battery Volt          : {tower.get('battery_volt')}")
            print(f"  Output Volt           : {tower.get('out_volt')}")
            print(f"""  SOCDiagnosis          : {
                  tower.get('hvs_soc_diagnosis')}%""")
            print(f"  State of Health       : {tower.get('soh')}%")
            print(f"  State                 : {tower.get('state')}")
            print(f"  State_String          : {tower.get('state_string')}")
            print(f"  Cell Voltages         : {tower.get('cell_voltages')}")
            print(f"""  Cell Temperatures     : {
                tower.get('cell_temperatures')}""")

    except BYDHVSError as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    asyncio.run(main())
