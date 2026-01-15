import struct


class InvalidRtpInterleaved(Exception):
    pass


class RtpInterleaved:
    def __init__(self, data):
        self.preamble,self.channel,self.size=struct.unpack('>cBH', data)
        if self.preamble != b'$':
            raise InvalidRtpInterleaved('invalid preamble: '+str(self.preamble))

    def __repr__(self):
        return f'channel:{self.channel} size:{self.size}'


class RtpHeader:
    def __init__(self, data):
        self._first_byte,\
        self._second_byte,\
        self.sequence_number,\
        self.timestamp,\
        self.SSRC=struct.unpack('>BBHII', data)
        self.version=(self._first_byte>>6) & 2
        self.P=(self._first_byte>>5) & 1
        self.X=(self._first_byte>>4) & 1
        self.counter=(self._first_byte & 4)
        self.M=(self._second_byte>>7) & 1
        self.payload_type=(self._second_byte & 0x7f)

    def __bytes__(self):
        return struct.pack('>BBHII',self._first_byte,
                           self._second_byte,
                           self.sequence_number,
                           self.timestamp,
                           self.SSRC)

    def __repr__(self):
        return f'RTP [P:{self.P} X:{self.X} counter:{self.counter} M:{self.M} PT:{self.payload_type}]'
