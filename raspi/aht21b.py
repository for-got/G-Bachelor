from time import sleep


class AHT21B:
    # default AHT21B i2c address
    AHT21B_ADDRESS = 0x38
    # write
    AHT21B_TD = 0x70
    # read
    AHT21B_RD = 0x71
    # init ack
    AHT21B_INIT_ACK = 0x18
    # init
    AHT21B_INIT_1 = [0xA8, 0x00, 0x00]  # NOR mode
    AHT21B_INIT_2 = [0xBE, 0x08, 0x00]
    # register
    AHT21B_REG = [0X1B, 0x1C, 0x1E]
    # measure
    AHT21B_MEASURE = [0xAC, 0x33, 0x00]

    def __init__(self, bus, address=AHT21B_ADDRESS):
        self.bus = bus
        self.address = address
        self.res = []

        self.reset_reg()
        self.init()
        # bus.write_byte(self.address, self.AHT21B_INIT_CHECK)
        # if int(bus.read_byte(self.address)) != self.AHT21B_INIT_ACK:
        #    print('RESET REG!')

    def init(self):
        self.bus.write_i2c_block_data(self.address, self.AHT21B_TD, self.AHT21B_INIT_1)
        sleep(0.1)
        self.bus.write_i2c_block_data(self.address, self.AHT21B_TD, self.AHT21B_INIT_2)
        sleep(0.1)

    def reset_reg(self):
        for reg in self.AHT21B_REG:
            self.bus.write_i2c_block_data(self.address, self.AHT21B_TD, [reg, 0, 0])
            sleep(0.1)
            res = self.bus.read_i2c_block_data(self.address, self.AHT21B_RD, 3)
            sleep(0.1)
            self.bus.write_i2c_block_data(self.address, self.AHT21B_TD, [0xB0 | reg, res[1], res[2]])
            sleep(0.1)

    def measure(self):  # send measure command
        self.bus.write_i2c_block_data(self.address, self.AHT21B_TD, self.AHT21B_MEASURE)
        sleep(0.1)
        self.res = self.bus.read_i2c_block_data(self.address, self.AHT21B_RD, 7)
        # res[0:6] == [status, h, h, h/t, t, t, crc]

    def temperature(self):
        self.measure()
        raw = (self.res[3] & 0x0F) << 16 | self.res[4] << 8 | self.res[5]
        return float(raw / 0x100000) * 200.0 - 50.0

    def humidity(self):
        self.measure()
        raw = self.res[1] << 12 | self.res[2] << 4 | self.res[3] >> 4
        return float(raw / 0x100000) * 100.0

    def read_raw(self):
        return self.bus.read_i2c_block_data(self.address, self.AHT21B_RD, 32)


if __name__ == "__main__":
    from smbus2 import SMBus

    bus = SMBus(1)
    sensor = AHT21B(bus, address=0x38)
    print(sensor.humidity())
    print(sensor.temperature())
    bus.close()
