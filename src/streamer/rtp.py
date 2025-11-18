import struct


class InvalidRtpInterleaved(Exception):
    pass


class RtpInterleaved:
    def __init__(self, data):
        self.preamble,self.channel,self.size=struct.unpack('>cBH', data)
        if self.preamble != b'$':
            raise InvalidRtpInterleaved('invalid preamble: '+str(self.preamble))


class RtpHeader:
    def __init__(self, data):
        self.counter,\
        self.payload_type,\
        self.sequence_number,\
        self.timestamp,\
        self.SSRC=struct.unpack('>BBHII', data)
        self.version=(self.counter>>6) & 2
        self.P=(self.counter>>5) & 1
        self.X=(self.counter>>4) & 1
        self.counter=(self.counter & 4)
        self.M=(self.payload_type>>7) & 1
        self.payload_type=(self.payload_type & 0x7f)