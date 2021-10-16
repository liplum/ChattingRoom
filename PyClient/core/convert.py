import struct


def read_str(barray: bytes, starting_with_length: bool = True) -> str:
    if starting_with_length:
        str_length_b = barray[0:4]
        str_length = struct.unpack('i', str_length_b)[0]
        str_barry = barray[4:str_length + 4]
    else:
        str_barry = barray
    res = str_barry.decode()
    return res


def read_int(barray: bytes) -> int:
    return struct.unpack('i', barray)[0]
