import numpy as np
from typing import List
from dac81416_08evm import MyDAC81416


class MyRISController:

    VOLTAGE_RANGES = {"0-5V": 0, "0-10V": 0x01, "0-20V": 0x02, "0-40V": 0x04}

    MIN_VOLTAGES = {"0-5V": 0, "0-10V": 0, "0-20V": 0, "0-40V": 0}
    MAX_VOLTAGES = {"0-5V": 5, "0-10V": 10, "0-20V": 20, "0-40V": 40}

    """
    !!!BEFORE INITIALIZING, TURN ON VCC/SUPPLY VOLTAGE (5V,10V,20V,40V)!!!
    Initializes the RISController class. Multiple DACs are supported via daisychain or multiple USB connections.
    Multiple USB connections: 
        device_url: must include a list of all ftdi device addresses
        unit_cell_num: must include a list of all unit cell numbers
    Daisychain:
        device_url: must include a single ftdi device address
        unit_cell_num: must include a list of all unit cell numbers
        daisy_chain_device_num: number of devices in addition to the first device (e.g., 3 DACs are connected, daisy_chain_device_num = 2)
    """

    def __init__(
        self,
        device_url: str | List[str],
        unit_cell_num: int | List[int] = 9,
        daisy_chain_device_num: int = 0,
    ):
        if isinstance(device_url, str):
            self.dac = [MyDAC81416(device_url, daisy_chain_device_num)]
        else:
            self.dac = [MyDAC81416(durl) for durl in device_url]

        if not isinstance(unit_cell_num, int):
            if daisy_chain_device_num > 0 or len(self.dac) == len(unit_cell_num):
                noms = np.asarray(unit_cell_num)
                if all(1 <= noms) and all(noms <= 16):
                    self._unit_cell_num = noms
                else:
                    raise ValueError("unit_cell_num (elements) must be between 1 an 16")
            else:
                raise ValueError(
                    "unit_cell_num and device_url must have the same length"
                )
        else:
            if isinstance(device_url, str) or (
                isinstance(device_url, List) and len(device_url) == 1
            ):
                if daisy_chain_device_num == 0:
                    if 1 <= unit_cell_num <= 16:
                        self._unit_cell_num = unit_cell_num
                    else:
                        raise ValueError(
                            "unit_cell_num (elements) must be between 1 an 16"
                        )
                else:
                    if isinstance(unit_cell_num, List) and len(unit_cell_num) == (
                        daisy_chain_device_num + 1
                    ):
                        noms = np.asarray(unit_cell_num)
                        if all(1 <= noms) and all(noms <= 16):
                            self._unit_cell_num = noms
                        else:
                            raise ValueError(
                                "unit_cell_num (elements) must be between 1 an 16"
                            )
                    else:
                        raise ValueError(
                            f"unit_cell_num must have the length {daisy_chain_device_num + 1}"
                        )
            elif daisy_chain_device_num > 0:
                if isinstance(unit_cell_num, List) and len(unit_cell_num) == (
                    daisy_chain_device_num + 1
                ):
                    noms = np.asarray(unit_cell_num)
                    if all(1 <= noms) and all(noms <= 16):
                        self._unit_cell_num = noms
                    else:
                        raise ValueError(
                            "unit_cell_num (elements) must be between 1 an 16"
                        )
                else:
                    raise ValueError(
                        f"unit_cell_num must have the length {daisy_chain_device_num + 1}"
                    )
            else:
                raise ValueError(
                    "unit_cell_num and device_url must have the same length if not daisychained"
                )
        self.daisy_chain_device_num = daisy_chain_device_num

    def configure(
        self,
        voltage_range_identifier: str,
        dac_idx: int = 0,
        daisy_chain_safty_device: int = 0,
    ):
        
        self.daisy_chain_safety_device = daisy_chain_safty_device

        # print("Power-on Device")
        self.power_on_dac(dac_idx=dac_idx)
        # print("Setting Voltage Range")
        self.set_voltage_range(voltage_range_identifier, dac_idx=dac_idx)
        self.power_on_ref(dac_idx=dac_idx)
        # print("Enabling DAC Channels")
        self.enable_dac_channels(dac_idx=dac_idx)

        self._set_safty_voltage(
            voltage_range_identifier, safty_dac_idx=daisy_chain_safty_device
        )

    def power_on_ref(self, dac_idx: int = 0):
        config = 0b0011111100000000
        if self.daisy_chain_device_num == 0:
            self.dac[dac_idx].set_genconfig(config)
        else:
            mdac = self.dac[0]
            data = mdac.get_genconfig_mask()
            mdac.set_register(
                np.repeat(
                    mdac.REGISTER_MAP["GENCONFIG"], self.daisy_chain_device_num + 1
                ),
                np.repeat(config, self.daisy_chain_device_num + 1),
                np.repeat(data[0], self.daisy_chain_device_num + 1),
                np.repeat(data[1], self.daisy_chain_device_num + 1),
            )

    def power_off_ref(self, dac_idx: int = 0):
        config = 0b0111111100000000
        if self.daisy_chain_device_num == 0:
            self.dac[dac_idx].set_genconfig(config)
        else:
            mdac = self.dac[0]
            data = mdac.get_genconfig_mask()
            mdac.set_register(
                np.repeat(
                    mdac.REGISTER_MAP["GENCONFIG"], self.daisy_chain_device_num + 1
                ),
                np.repeat(config, self.daisy_chain_device_num + 1),
                np.repeat(data[0], self.daisy_chain_device_num + 1),
                np.repeat(data[1], self.daisy_chain_device_num + 1),
            )

    def power_on_dac(self, dac_idx: int = 0):
        config = 0b101010000100
        if self.daisy_chain_device_num == 0:
            self.dac[dac_idx].set_spiconfig(config)
        else:
            mdac = self.dac[0]
            data = mdac.get_spiconfig_mask()
            mdac.set_register(
                np.repeat(
                    mdac.REGISTER_MAP["SPICONFIG"], self.daisy_chain_device_num + 1
                ),
                np.repeat(config, self.daisy_chain_device_num + 1),
                np.repeat(data[0], self.daisy_chain_device_num + 1),
                np.repeat(data[1], self.daisy_chain_device_num + 1),
            )

    def power_off_dac(self, dac_idx: int = 0):
        config = 0b101010100100
        if self.daisy_chain_device_num == 0:
            self.dac[dac_idx].set_spiconfig(config)
        else:
            mdac = self.dac[0]
            data = mdac.get_spiconfig_mask()
            mdac.set_register(
                np.repeat(
                    mdac.REGISTER_MAP["SPICONFIG"], self.daisy_chain_device_num + 1
                ),
                np.repeat(config, self.daisy_chain_device_num + 1),
                np.repeat(data[0], self.daisy_chain_device_num + 1),
                np.repeat(data[1], self.daisy_chain_device_num + 1),
            )

    def set_voltage_range(self, voltage_range_identifier: str, dac_idx: int = 0):
        range_data = self.VOLTAGE_RANGES[voltage_range_identifier]
        self.active_voltage_range = voltage_range_identifier
        config = (range_data << 12) | (range_data << 8) | (range_data << 4) | range_data
        if self.daisy_chain_device_num == 0:
            self.dac[dac_idx].set_dacrange0(config)
            self.dac[dac_idx].set_dacrange1(config)
            self.dac[dac_idx].set_dacrange2(config)
            self.dac[dac_idx].set_dacrange3(config)
        else:
            mdac = self.dac[0]
            data = mdac.get_dacrange0_mask()
            mdac.set_register(
                np.repeat(
                    mdac.REGISTER_MAP["DACRANGE0"], self.daisy_chain_device_num + 1
                ),
                np.repeat(config, self.daisy_chain_device_num + 1),
                np.repeat(data[0], self.daisy_chain_device_num + 1),
                np.repeat(data[1], self.daisy_chain_device_num + 1),
            )
            mdac.set_register(
                np.repeat(
                    mdac.REGISTER_MAP["DACRANGE1"], self.daisy_chain_device_num + 1
                ),
                np.repeat(config, self.daisy_chain_device_num + 1),
                np.repeat(data[0], self.daisy_chain_device_num + 1),
                np.repeat(data[1], self.daisy_chain_device_num + 1),
            )
            mdac.set_register(
                np.repeat(
                    mdac.REGISTER_MAP["DACRANGE2"], self.daisy_chain_device_num + 1
                ),
                np.repeat(config, self.daisy_chain_device_num + 1),
                np.repeat(data[0], self.daisy_chain_device_num + 1),
                np.repeat(data[1], self.daisy_chain_device_num + 1),
            )
            mdac.set_register(
                np.repeat(
                    mdac.REGISTER_MAP["DACRANGE3"], self.daisy_chain_device_num + 1
                ),
                np.repeat(config, self.daisy_chain_device_num + 1),
                np.repeat(data[0], self.daisy_chain_device_num + 1),
                np.repeat(data[1], self.daisy_chain_device_num + 1),
            )

    def enable_dac_channels(self, dac_idx: int = 0):
        if self.daisy_chain_device_num == 0:
            # Enable DAC channels 0-__unit_cell_num__ and DAC15
            mask = ((1 << self._unit_cell_num) - 1) | (1 << 15)
            config = 0xFFFF ^ mask
            self.dac[dac_idx].set_dacpwdwn(config)
        else:
            mdac = self.dac[0]
            data = mdac.get_dacpwdwn_mask()
            mask = ((1 << self._unit_cell_num) - 1)
            mask[self.daisy_chain_safety_device] |= (1 << 15)
            config = 0xFFFF ^ mask
            
            mdac.set_register(
                np.repeat(
                    mdac.REGISTER_MAP["DACPWDWN"], self.daisy_chain_device_num + 1
                ),
                config,
                np.repeat(data[0], self.daisy_chain_device_num + 1),
                np.repeat(data[1], self.daisy_chain_device_num + 1),
            )

    def disable_dac_channels(self, dac_idx: int = 0):
        config = 0xFFFF
        if self.daisy_chain_device_num == 0:
            self.dac[dac_idx].set_dacpwdwn(config)
        else:
            mdac = self.dac[0]
            data = mdac.get_dacpwdwn_mask()
            mdac.set_register(
                np.repeat(
                    mdac.REGISTER_MAP["DACPWDWN"], self.daisy_chain_device_num + 1
                ),
                np.repeat(config, self.daisy_chain_device_num + 1),
                np.repeat(data[0], self.daisy_chain_device_num + 1),
                np.repeat(data[1], self.daisy_chain_device_num + 1),
            )

    """
    sets the output voltages.
    single or multiple DAC via USB:
        data is a vector of codes corresponding to voltages
    daisychain mode:
        data is a matrix of codes corresponding to voltages
        matrix must be of dimension (max{unit_cell_num}, daisychain_device_num)
        unused dac channels should be set to 0
    """

    def _set_output_voltage(self, data: np.ndarray, dac_idx: int = 0):
        if self.daisy_chain_device_num == 0:
            if not np.shape(data)[0] == self._unit_cell_num:
                raise ValueError("Invalid number of dac channels")
            for i in range(self._unit_cell_num):
                self.dac[dac_idx].set_dacn(i, int(data[i]))
        else:
            mdac = self.dac[0]
            mask = mdac.get_dacn_mask()
            if not np.shape(data) == (
                np.max(self._unit_cell_num),
                self.daisy_chain_device_num + 1,
            ):
                raise ValueError(
                    f"Invalid shape of 'data': should be ({np.max(self._unit_cell_num)},{self.daisy_chain_device_num + 1})"
                )
            for i in range(np.max(self._unit_cell_num)):
                mdac.set_register(
                    np.repeat(
                        mdac.REGISTER_MAP[f"DAC{i}"], self.daisy_chain_device_num + 1
                    ),
                    data[i],
                    np.repeat(mask[0], self.daisy_chain_device_num + 1),
                    np.repeat(mask[1], self.daisy_chain_device_num + 1),
                )

    def _get_output_voltages(self):
        raise NotImplementedError("Unable to read DAC81416 channel registers.")
        data = np.zeros((self._unit_cell_num))
        for i in range(self._unit_cell_num):
            data[i] = np.packbits(np.asarray(self.dac.get_dacn(i))).view(np.uint16)
        return data

    """
    daisychain mode:
        voltage array must be of shape ({np.max(self._unit_cell_num)},{self.daisy_chain_device_num + 1})
        the first dac index (:,0) corresponds to the last DAC in the chain!!!
    """

    def set_pattern(self, voltages: np.ndarray, dac_idx: int = 0):
        if self.daisy_chain_device_num > 0:
            if not np.shape(voltages) == (
                np.max(self._unit_cell_num),
                self.daisy_chain_device_num + 1,
            ):
                raise ValueError(
                    f"Invalid shape of voltage array. Is: {np.shape(voltages)}, should be: {(np.max(self._unit_cell_num), self.daisy_chain_device_num + 1)}"
                )
        else:
            if not np.shape(voltages)[0] == self._unit_cell_num:
                raise ValueError(
                    f"Invalid shape of voltage array. Is: {np.shape(voltages)}, should be: {(np.max(self._unit_cell_num))}"
                )

        data = (
            2**16
            / (
                self.MAX_VOLTAGES[self.active_voltage_range]
                - self.MIN_VOLTAGES[self.active_voltage_range]
            )
            * (voltages - self.MIN_VOLTAGES[self.active_voltage_range])
        )
        # print(data, np.astype(np.round(data), int), type(data))
        self._set_output_voltage(np.astype(np.round(data), int), dac_idx=dac_idx)

    def get_pattern(self):
        # documentation/hardware bug, unable to read DAC channel registers
        raise NotImplementedError("Unable to read DAC81416 channel registers.")
        data = np.asarray(self._get_output_voltages())
        voltages = (
            data
            * (
                self.MAX_VOLTAGES[self.active_voltage_range]
                - self.MIN_VOLTAGES[self.active_voltage_range]
            )
            / (2**16)
            + self.MIN_VOLTAGES[self.active_voltage_range]
        )
        return voltages

    def _set_safty_voltage(
        self,
        voltage_range_identifier: str,
        safety_voltage: float = 3.0,
        safty_dac_idx: int = 0,
    ):

        dac_value = int(
            round(
                (
                    (safety_voltage - self.MIN_VOLTAGES[voltage_range_identifier])
                    / (
                        self.MAX_VOLTAGES[voltage_range_identifier]
                        - self.MIN_VOLTAGES[voltage_range_identifier]
                    )
                )
                * (2**16 - 1)
            )
        )
        if self.daisy_chain_device_num == 0:
            self.dac[safty_dac_idx].set_dacn(15, dac_value)
        else:
            mdac = self.dac[0]
            mask, reserved = mdac.get_dacn_mask()
            values = np.zeros(self.daisy_chain_device_num + 1, dtype=int)
            values[safty_dac_idx] = dac_value  # Only set on the safety device
            mdac.set_register(
                np.repeat(mdac.REGISTER_MAP["DAC15"], self.daisy_chain_device_num + 1),
                values,
                np.repeat(mask, self.daisy_chain_device_num + 1),
                np.repeat(reserved, self.daisy_chain_device_num + 1),
            )
