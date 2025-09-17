import numpy as np
from typing import List
from pyftdi.gpio import GpioSyncController


class MySPI_FTDI4232H:
    SCLK = 0x01  # CH1
    CS = 0x02  # CH4
    SDI = 0x04  # CH3, DAC in
    SDO = 0x08  # CH2, DAC out
    OUT_DIR = SCLK | CS | SDI
    PIN_MASK = SCLK | CS | SDI | SDO
    _prolog = CS
    _epilog = CS

    def __init__(self, device_url, daisy_chain_device_num=0):
        self.gpio = GpioSyncController()
        self.gpio.configure(device_url, self.OUT_DIR, frequency=12e6)
        self._daisy_chain_device_num = daisy_chain_device_num  # number of devices in addition to the first device (e.g., 3 DACs are connected, daisy_chain_device_num = 2)

    def terminate(self):
        self.gpio.close()

    def set_prolog(self, prolog):
        self._prolog = prolog

    def set_epilog(self, epilog):
        self._epilog = epilog

    """
    Convert the bit sequences of the individual pins to a format accepted by the ftdi chip.
    I.e., change the horizontal byte sequence to a vertical byte sequence:
     - One byte for each clock tick. With the bits corresponding to the hardware pins.
    """

    def _rotate_sequence(self, sequence):
        return np.packbits(
            np.unpackbits(sequence, axis=1, bitorder="big"), axis=0, bitorder="little"
        )

    """
    Creates bit sequences for all in/out pins.
    In daisychain mode 'register_address', 'byte_high' and 'byte_low' must be lists.
    The first value in each list (index == 0) corresponds to the last!!! DAC in the chain (i.e., the DAC at the end of the chain).
    """

    def create_data_sequence(
        self,
        register_address: int | List[int],
        byte_high: int | List[int],
        byte_low: int | List[int],
    ):
        if self._daisy_chain_device_num > 0:
            if (
                not isinstance(register_address, List)
                or not isinstance(byte_high, List)
                or not isinstance(byte_low, List)
            ):
                raise ValueError(
                    f"Register address, high byte and low byte must be lists with length {self._daisy_chain_device_num + 1}"
                )
            reg_add_np = np.asarray(register_address)
            byt_hig_np = np.asarray(byte_high)
            byt_low_np = np.asarray(byte_low)

            # if len(np.shape(np.asarray(register_address))) == 0 or len(np.shape(np.asarray(byte_high))) == 0 or len(np.shape(np.asarray(byte_low))) == 0:
            #    raise ValueError(f"Register address, high byte and low byte must be of length {self._daisy_chain_device_num + 1}")
            if (
                reg_add_np.size != (self._daisy_chain_device_num + 1)
                or byt_hig_np.size != (self._daisy_chain_device_num + 1)
                or byt_low_np.size != (self._daisy_chain_device_num + 1)
            ):
                raise ValueError(
                    f"Register address, high byte and low byte must be lists with length {self._daisy_chain_device_num + 1}"
                )
        else:
            if (
                len(np.shape(np.asarray(register_address))) != 0
                or len(np.shape(np.asarray(byte_high))) != 0
                or len(np.shape(np.asarray(byte_low))) != 0
            ):
                raise ValueError(
                    f"Register address, high byte and low byte must be a scalar"
                )

        clk_seq = np.array(
            np.repeat(0xAA, 6 * (self._daisy_chain_device_num + 1)), dtype=np.uint8
        )
        # print("clk:", clk_seq, clk_seq.shape)
        cs_seq = np.zeros((6 * (self._daisy_chain_device_num + 1)), dtype=np.uint8)
        # print("cs:", cs_seq, cs_seq.shape)
        data_seq = np.asarray(
            [register_address, byte_high, byte_low], dtype=np.uint8
        ).reshape(-1, order="F")
        # print("data:", np.unpackbits(data_seq), data_seq.shape)
        data_out_seq = np.packbits(np.repeat(np.unpackbits(data_seq), 2)).astype(
            np.uint8
        )
        # print("data_out:", np.unpackbits(data_out_seq), data_out_seq.shape)
        zero_seq = np.zeros((6 * (self._daisy_chain_device_num + 1)), dtype=np.uint8)
        data_in_seq = zero_seq
        data_mat = np.asarray([clk_seq, cs_seq, data_out_seq, data_in_seq])
        data_mat = np.append(data_mat, np.repeat(zero_seq[None], 4, axis=0), axis=0)
        return data_seq, self._rotate_sequence(data_mat).squeeze()
        """
        else:
            clk_seq = np.array(np.repeat(0xAA, 6), dtype=np.uint8)
            cs_seq = np.zeros((6), dtype=np.uint8)
            data_seq = np.asarray([register_address, byte_high, byte_low], dtype=np.uint8)
            data_out_seq = np.packbits(np.repeat(np.unpackbits(data_seq), 2)).astype(np.uint8)
            zero_seq = np.zeros((6), dtype=np.uint8)
            data_mat = np.asarray([clk_seq, cs_seq, data_out_seq, zero_seq])
            data_mat = np.append(data_mat, np.repeat(zero_seq[None], 4, axis=0), axis=0)
            return data_seq, self._rotate_sequence(data_mat).squeeze()
        """

    def _process_rx_data(self, sequence):
        rx_data_unpacked = np.unpackbits(
            np.asarray(np.frombuffer(bytes(sequence), dtype=np.uint8))[:, None],
            axis=1,
            bitorder="little",
        )
        # rx_data_unpacked_clean = rx_data_unpacked[:,:4]
        # print(np.argwhere(rx_data_unpacked_clean[:,1] == 1).squeeze())
        data_segment1 = rx_data_unpacked[
            2:50:2, :4
        ]  # throw out guard and unused pins, downsample received data
        data_segment1_tx = data_segment1[8:, 2]
        address_segment1_tx = data_segment1[:8, 2]
        data_segment1_rx = data_segment1[8:, 3]
        address_segment1_rx = data_segment1[:8, 3]
        data_segment2 = rx_data_unpacked[52::2, :4]
        data_segment2_tx = data_segment2[8:, 2]
        address_segment2_tx = data_segment2[:8, 2]
        data_segment2_rx = data_segment2[8:, 3]
        address_segment2_rx = data_segment2[:8, 3]
        # print(data_segment1_rx, data_segment2_rx)
        return (
            address_segment1_tx,
            data_segment1_tx,
            address_segment2_tx,
            data_segment2_tx,
        ), (
            address_segment1_rx,
            data_segment1_rx,
            address_segment2_rx,
            data_segment2_rx,
        )
        # print(hex((1 << 7) | 0x01))
        # device_id = np.packbits(np.asarray(np.append([0,0], data_segment2_rx[8:22]), dtype=np.uint8))
        # print(" ".join([hex(i) for i in device_id]))

    def read(self, address, read_delay: int = 1):
        if self._daisy_chain_device_num > 0:
            raise NotImplementedError(
                "Reading in daisychain mode (for DAC81416-08EVM) is not supported"
            )
        if read_delay < 1:
            raise ValueError("read_delay must be at least 1")
        # print("read address:", hex(address), bin((1 << 7 | address)))
        _, sequence = self.create_data_sequence((1 << 7 | address), 0, 0)
        delay_seq = np.repeat(self.CS, read_delay)
        tx_data = np.append(
            np.append(
                self._prolog, np.append(sequence, np.append(delay_seq, sequence))
            ),
            self._epilog,
        )
        return self._process_rx_data(self._transmit_sequence(tx_data))

    def write(self, register_address, byte_high, byte_low):
        _, sequence = self.create_data_sequence(register_address, byte_high, byte_low)
        tx_data = np.append(np.append(self._prolog, sequence), self._epilog)
        self._transmit_sequence(tx_data)

    """
    Sequences are transmitted LSB first.
    """

    def _transmit_sequence(self, sequence):
        return self.gpio.exchange(sequence)


class MyDAC81416:

    REGISTER_MAP = (
        {  # see section 8.6 Register Maps, Table 8-7. in the DACx1416 datasheet
            "NOP": 0x00,
            "DEVICEID": 0x01,
            "STATUS": 0x02,
            "SPICONFIG": 0x03,
            "GENCONFIG": 0x04,
            "BRDCONFIG": 0x05,
            "SYNCCONFIG": 0x06,
            "TOGGCONFIG0": 0x07,
            "TOGGCONFIG1": 0x08,
            "DACPWDWN": 0x09,
            "DACRANGE0": 0xA,
            "DACRANGE1": 0xB,
            "DACRANGE2": 0xC,
            "DACRANGE3": 0xD,
            "TRIGGER": 0xE,
            "BRDCAST": 0xF,
            "DAC0": 0x10,
            "DAC1": 0x11,
            "DAC2": 0x12,
            "DAC3": 0x13,
            "DAC4": 0x14,
            "DAC5": 0x15,
            "DAC6": 0x16,
            "DAC7": 0x17,
            "DAC8": 0x18,
            "DAC9": 0x19,
            "DAC10": 0x1A,
            "DAC11": 0x1B,
            "DAC12": 0x1C,
            "DAC13": 0x1D,
            "DAC14": 0x1E,
            "DAC15": 0x1F,
            "OFFSET0": 0x20,
            "OFFSET1": 0x21,
            "OFFSET2": 0x22,
            "OFFSET3": 0x23,
        }
    )

    """
    number of devices in addition to the first device (e.g., 3 DACs are connected, daisy_chain_device_num = 2)
    """

    def __init__(self, device_url, daisy_chain_device_num=0):
        self.spi = MySPI_FTDI4232H(device_url, daisy_chain_device_num)

    def is_daisy_chain_enabled(self):
        return self.spi._daisy_chain_device_num > 0

    def terminate(self):
        self.spi.terminate()

    def get_device_version_id(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["DEVICEID"]
        )
        device_id_bin = data_segment2_rx[:14]
        version_id_bin = data_segment2_rx[14:]
        return hex(int("".join(device_id_bin.astype(str)), 2)), hex(
            int("".join(version_id_bin.astype(str)), 2)
        )

    def get_status(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["STATUS"]
        )
        crc_alm = data_segment2_rx[13]
        dac_busy = data_segment2_rx[14]
        temp_alm = data_segment2_rx[15]
        return crc_alm, dac_busy, temp_alm

    """
    Write to a DAC register.
    Daisychain mode:
        The list index indicates the position of the DAC. 
        The first element corresponds to the closest DAC (connected via USB).
        Use the get_REGNAME_mask() functions to get the config_mask and reserved_state values associated with the corresponding REGISTER_MAP entry.
    config_mask: 1 indicates a writable bit
    """

    def set_register(
        self,
        address: int | List[int],
        config: int | List[int],
        config_mask: int | List[int],
        reserved_state: int | List[int] = 0,
    ):
        # print("address:", hex(address))
        # print("config:", bin(config))
        # print("mask:", bin(config_mask))
        # print(type(address), type(config), type(config_mask), type(reserved_state))
        if (
            isinstance(address, int)
            and isinstance(config, int)
            and isinstance(config_mask, int)
        ):
            if (config ^ reserved_state) & (~config_mask):
                raise ValueError(
                    "You are writing to read only bits or did not set the reserved bits correctly!"
                )
        else:
            addr_np = np.asarray(address)
            conf_np = np.asarray(config)
            conf_mk_np = np.asarray(config_mask)
            rsrv_st_np = np.asarray(reserved_state)

            # print(addr_np, conf_np, conf_mk_np, rsrv_st_np)
            if len(addr_np) == len(conf_np) == len(conf_mk_np) == len(rsrv_st_np):
                if any((conf_np ^ rsrv_st_np) & (~conf_mk_np)):
                    raise ValueError(
                        "You are writing to read only bits or did not set the reserved bits correctly!"
                    )
            else:
                raise ValueError(
                    "address, config, config_mask, reserved_state must have the same length"
                )
        tolist = lambda x: x.tolist() if isinstance(x, np.ndarray) else x

        self.spi.write(tolist(address), tolist(config >> 8), tolist(config & 0xFF))

    def get_nop_bytes(self):
        config_mask = 0b1111111111111111
        reserved_state = 0
        return 0xFFFF ^ config_mask, config_mask, reserved_state

    def set_nop(self):
        data = self.get_nop_bytes()
        self.set_register(self.REGISTER_MAP["NOP"], data[0], data[1])

    def get_spiconfig(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["SPICONFIG"]
        )
        tempalm_en = data_segment2_rx[4]
        dacbusy_en = data_segment2_rx[5]
        crcalm_en = data_segment2_rx[6]
        softtoggle_en = data_segment2_rx[9]
        dev_pwdwn = data_segment2_rx[10]
        crc_en = data_segment2_rx[11]
        str_en = data_segment2_rx[12]
        sdo_en = data_segment2_rx[13]
        fsdo = data_segment2_rx[14]
        return (
            tempalm_en,
            dacbusy_en,
            crcalm_en,
            softtoggle_en,
            dev_pwdwn,
            crc_en,
            str_en,
            sdo_en,
            fsdo,
        )

    def get_spiconfig_mask(self):
        config_mask = 0b0000111001111110  # 1 is writable
        reserved_state = 0b0000000010000000  # default state of the reserved bits, regular bits are always 0
        return config_mask, reserved_state

    def set_spiconfig(self, config):
        data = self.get_spiconfig_mask()
        self.set_register(self.REGISTER_MAP["SPICONFIG"], config, data[0], data[1])

    def get_genconfig(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["GENCONFIG"]
        )
        ref_pwdwn = data_segment2_rx[1]
        dac_14_15_diff_en = data_segment2_rx[8]
        dac_12_13_diff_en = data_segment2_rx[9]
        dac_10_11_diff_en = data_segment2_rx[10]
        dac_8_9_diff_en = data_segment2_rx[11]
        dac_6_7_diff_en = data_segment2_rx[12]
        dac_4_5_diff_en = data_segment2_rx[13]
        dac_2_3_diff_en = data_segment2_rx[14]
        dac_0_1_diff_en = data_segment2_rx[15]
        return (
            ref_pwdwn,
            dac_14_15_diff_en,
            dac_12_13_diff_en,
            dac_10_11_diff_en,
            dac_8_9_diff_en,
            dac_6_7_diff_en,
            dac_4_5_diff_en,
            dac_2_3_diff_en,
            dac_0_1_diff_en,
        )

    def get_genconfig_mask(self):
        config_mask = 0b0100000011111111  # 1 is writable
        reserved_state = 0b0011111100000000  # default state of the reserved bits, regular bits are always 0
        return config_mask, reserved_state

    def set_genconfig(self, config):
        data = self.get_genconfig_mask()
        self.set_register(self.REGISTER_MAP["GENCONFIG"], config, data[0], data[1])

    def get_brdconfig(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["BRDCONFIG"]
        )
        dac_15_brdcast_en = data_segment2_rx[0]
        dac_14_brdcast_en = data_segment2_rx[1]
        dac_13_brdcast_en = data_segment2_rx[2]
        dac_12_brdcast_en = data_segment2_rx[3]
        dac_11_brdcast_en = data_segment2_rx[4]
        dac_10_brdcast_en = data_segment2_rx[5]
        dac_9_brdcast_en = data_segment2_rx[6]
        dac_8_brdcast_en = data_segment2_rx[7]
        dac_7_brdcast_en = data_segment2_rx[8]
        dac_6_brdcast_en = data_segment2_rx[9]
        dac_5_brdcast_en = data_segment2_rx[10]
        dac_4_brdcast_en = data_segment2_rx[11]
        dac_3_brdcast_en = data_segment2_rx[12]
        dac_2_brdcast_en = data_segment2_rx[13]
        dac_1_brdcast_en = data_segment2_rx[14]
        dac_0_brdcast_en = data_segment2_rx[15]
        return (
            dac_15_brdcast_en,
            dac_14_brdcast_en,
            dac_13_brdcast_en,
            dac_12_brdcast_en,
            dac_11_brdcast_en,
            dac_10_brdcast_en,
            dac_9_brdcast_en,
            dac_8_brdcast_en,
            dac_7_brdcast_en,
            dac_6_brdcast_en,
            dac_5_brdcast_en,
            dac_4_brdcast_en,
            dac_3_brdcast_en,
            dac_2_brdcast_en,
            dac_1_brdcast_en,
            dac_0_brdcast_en,
        )

    def get_brdconfig_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_brdconfig(self, config):
        data = self.get_brdconfig_mask()
        self.set_register(self.REGISTER_MAP["BRDCONFIG"], config, data[0])

    def get_syncconfig(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["SYNCCONFIG"]
        )
        dac_15_sync_en = data_segment2_rx[0]
        dac_14_sync_en = data_segment2_rx[1]
        dac_13_sync_en = data_segment2_rx[2]
        dac_12_sync_en = data_segment2_rx[3]
        dac_11_sync_en = data_segment2_rx[4]
        dac_10_sync_en = data_segment2_rx[5]
        dac_9_sync_en = data_segment2_rx[6]
        dac_8_sync_en = data_segment2_rx[7]
        dac_7_sync_en = data_segment2_rx[8]
        dac_6_sync_en = data_segment2_rx[9]
        dac_5_sync_en = data_segment2_rx[10]
        dac_4_sync_en = data_segment2_rx[11]
        dac_3_sync_en = data_segment2_rx[12]
        dac_2_sync_en = data_segment2_rx[13]
        dac_1_sync_en = data_segment2_rx[14]
        dac_0_sync_en = data_segment2_rx[15]
        return (
            dac_15_sync_en,
            dac_14_sync_en,
            dac_13_sync_en,
            dac_12_sync_en,
            dac_11_sync_en,
            dac_10_sync_en,
            dac_9_sync_en,
            dac_8_sync_en,
            dac_7_sync_en,
            dac_6_sync_en,
            dac_5_sync_en,
            dac_4_sync_en,
            dac_3_sync_en,
            dac_2_sync_en,
            dac_1_sync_en,
            dac_0_sync_en,
        )

    def get_syncconfig_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_syncconfig(self, config):
        data = self.get_syncconfig_mask()
        self.set_register(self.REGISTER_MAP["SYNCCONFIG"], config, data[0])

    def get_toggconfig0(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["TOGGCONFIG0"]
        )
        dac_15_ab_togg_en = data_segment2_rx[0:2]
        dac_14_ab_togg_en = data_segment2_rx[2:4]
        dac_13_ab_togg_en = data_segment2_rx[4:6]
        dac_12_ab_togg_en = data_segment2_rx[6:8]
        dac_11_ab_togg_en = data_segment2_rx[8:10]
        dac_10_ab_togg_en = data_segment2_rx[10:12]
        dac_9_ab_togg_en = data_segment2_rx[12:14]
        dac_8_ab_togg_en = data_segment2_rx[14:16]
        return (
            dac_15_ab_togg_en,
            dac_14_ab_togg_en,
            dac_13_ab_togg_en,
            dac_12_ab_togg_en,
            dac_11_ab_togg_en,
            dac_10_ab_togg_en,
            dac_9_ab_togg_en,
            dac_8_ab_togg_en,
        )

    def get_toggconfig0_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_toggconfig0(self, config):
        data = self.get_toggconfig0_mask()
        self.set_register(self.REGISTER_MAP["TOGGCONFIG0"], config, data[0])

    def get_toggconfig1(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["TOGGCONFIG1"]
        )
        dac_7_ab_togg_en = data_segment2_rx[0:2]
        dac_6_ab_togg_en = data_segment2_rx[2:4]
        dac_5_ab_togg_en = data_segment2_rx[4:6]
        dac_4_ab_togg_en = data_segment2_rx[6:8]
        dac_3_ab_togg_en = data_segment2_rx[8:10]
        dac_2_ab_togg_en = data_segment2_rx[10:12]
        dac_1_ab_togg_en = data_segment2_rx[12:14]
        dac_0_ab_togg_en = data_segment2_rx[14:16]
        return (
            dac_7_ab_togg_en,
            dac_6_ab_togg_en,
            dac_5_ab_togg_en,
            dac_4_ab_togg_en,
            dac_3_ab_togg_en,
            dac_2_ab_togg_en,
            dac_1_ab_togg_en,
            dac_0_ab_togg_en,
        )

    def get_toggconfig1_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_toggconfig1(self, config):
        data = self.get_toggconfig1_mask()
        self.set_register(self.REGISTER_MAP["TOGGCONFIG1"], config, data[0])

    def get_dacpwdwn(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["DACPWDWN"]
        )
        dac_15_pwdwn = data_segment2_rx[0]
        dac_14_pwdwn = data_segment2_rx[1]
        dac_13_pwdwn = data_segment2_rx[2]
        dac_12_pwdwn = data_segment2_rx[3]
        dac_11_pwdwn = data_segment2_rx[4]
        dac_10_pwdwn = data_segment2_rx[5]
        dac_9_pwdwn = data_segment2_rx[6]
        dac_8_pwdwn = data_segment2_rx[7]
        dac_7_pwdwn = data_segment2_rx[8]
        dac_6_pwdwn = data_segment2_rx[9]
        dac_5_pwdwn = data_segment2_rx[10]
        dac_4_pwdwn = data_segment2_rx[11]
        dac_3_pwdwn = data_segment2_rx[12]
        dac_2_pwdwn = data_segment2_rx[13]
        dac_1_pwdwn = data_segment2_rx[14]
        dac_0_pwdwn = data_segment2_rx[15]
        return (
            dac_15_pwdwn,
            dac_14_pwdwn,
            dac_13_pwdwn,
            dac_12_pwdwn,
            dac_11_pwdwn,
            dac_10_pwdwn,
            dac_9_pwdwn,
            dac_8_pwdwn,
            dac_7_pwdwn,
            dac_6_pwdwn,
            dac_5_pwdwn,
            dac_4_pwdwn,
            dac_3_pwdwn,
            dac_2_pwdwn,
            dac_1_pwdwn,
            dac_0_pwdwn,
        )

    def get_dacpwdwn_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_dacpwdwn(self, config):
        data = self.get_dacpwdwn_mask()
        self.set_register(self.REGISTER_MAP["DACPWDWN"], config, data[0])

    def get_dacrange0_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_dacrange0(self, config):  # dacrange is not readable
        data = self.get_dacrange0_mask()
        self.set_register(self.REGISTER_MAP["DACRANGE0"], config, data[0])

    def get_dacrange1_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_dacrange1(self, config):
        data = self.get_dacrange1_mask()
        self.set_register(self.REGISTER_MAP["DACRANGE1"], config, data[0])

    def get_dacrange2_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_dacrange2(self, config):
        data = self.get_dacrange2_mask()
        self.set_register(self.REGISTER_MAP["DACRANGE2"], config, data[0])

    def get_dacrange3_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_dacrange3(self, config):
        data = self.get_dacrange3_mask()
        self.set_register(self.REGISTER_MAP["DACRANGE3"], config, data[0])

    def get_trigger_mask(self):
        config_mask = 0b0000000111111111  # 1 is writable
        reserved_state = 0b0000000000000000  # default state of the reserved bits, regular bits are always 0
        return config_mask, reserved_state

    def set_trigger(self, config):  # trigger is not readable
        data = self.get_trigger_mask()
        self.set_register(self.REGISTER_MAP["TRIGGER"], config, data[0], data[1])

    def get_brdcast(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["BRDCAST"]
        )
        return data_segment2_rx

    def get_brdcast_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_brdcast(self, config):
        data = self.get_brdcast_mask()
        self.set_register(self.REGISTER_MAP["BRDCAST"], config, data[0])

    def get_offset0(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["OFFSET0"]
        )
        offset_14_15 = data_segment2_rx[:8]
        offset_12_13 = data_segment2_rx[8:]
        return offset_14_15, offset_12_13

    def get_offset0_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_offset0(self, config):
        data = self.get_offset0_mask()
        self.set_register(self.REGISTER_MAP["OFFSET0"], config, data[0])

    def get_dacn(self, dac_index: int):
        if 0 <= dac_index <= 15:
            (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
                self.REGISTER_MAP[f"DAC{dac_index}"]
            )
            return data_segment2_rx
        else:
            raise ValueError("Invalid DAC index")

    def get_dacn_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_dacn(self, dac_index: int, config):
        data = self.get_dacn_mask()
        if 0 <= dac_index <= 15:
            self.set_register(self.REGISTER_MAP[f"DAC{dac_index}"], config, data[0])
        else:
            raise ValueError("Invalid DAC index")

    def get_offset1(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["OFFSET1"]
        )
        offset_10_11 = data_segment2_rx[:8]
        offset_8_9 = data_segment2_rx[8:]
        return offset_10_11, offset_8_9

    def get_offset1_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_offset1(self, config):
        data = self.get_offset1_mask()
        self.set_register(self.REGISTER_MAP["OFFSET1"], config, data[0])

    def get_offset2(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["OFFSET2"]
        )
        offset_6_7 = data_segment2_rx[:8]
        offset_4_5 = data_segment2_rx[8:]
        return offset_6_7, offset_4_5

    def get_offset2_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_offset2(self, config):
        data = self.get_offset2_mask()
        self.set_register(self.REGISTER_MAP["OFFSET2"], config, data[0])

    def get_offset3(self):
        (_, _, _, _), (_, _, _, data_segment2_rx) = self.spi.read(
            self.REGISTER_MAP["OFFSET3"]
        )
        offset_2_3 = data_segment2_rx[:8]
        offset_0_1 = data_segment2_rx[8:]
        return offset_2_3, offset_0_1

    def get_offset3_mask(self):
        config_mask = 0b1111111111111111  # 1 is writable
        reserved_state = 0
        return config_mask, reserved_state

    def set_offset3(self, config):
        data = self.get_offset3_mask()
        self.set_register(self.REGISTER_MAP["OFFSET3"], config, data[0])
