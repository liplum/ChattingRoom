from typing import Union, Optional, Tuple

from chars import char

linux_esc = 27
linux_csi = 91
linux_o = 79
linux_126 = 126
linux_eot = 4


class linux_control(char):

    def __init__(self, keycode_2: int, keycode_3: int, keycode_4: Optional[int], keycode_5: Optional[int]):
        super().__init__(linux_esc, keycode_2)
        self.keycode_3 = keycode_3
        self.keycode_4 = keycode_4
        self.keycode_5 = keycode_5

    def __eq__(self, other: Union[char, "linux_control", bytes, int, Tuple[int, int], Tuple[int, int, int, int]]):
        if super().__eq__(other):
            if isinstance(other, linux_control):
                return self.keycode_3 == other.keycode_3 and self.keycode_4 == other.keycode_4 and \
                       self.keycode_5 == other.keycode_5
            elif isinstance(other, tuple):
                if len(other) >= 4:
                    return self.keycode_3 == other[2] and self.keycode_4 == other[3] and \
                           self.keycode_5 == other[4]
        return False

    def __repr__(self):
        return f'({self.keycode_1},{self.keycode_2},{self.keycode_3},{self.keycode_4})'

    def __hash__(self):
        return hash((self.keycode_1, self.keycode_2, self.keycode_3, self.keycode_4))

    @staticmethod
    def from_tuple(li: Union[list, tuple]) -> "linux_control":
        l = len(li)
        k2 = li[1]
        k3 = li[2] if l > 2 else 0
        k4 = li[3] if l > 3 else None
        k5 = li[4] if l > 4 else None
        return linux_control(k2, k3, k4, k5)

    def is_printable(self) -> bool:
        return False

    def __str__(self):
        return ""


lc = linux_control


def csi_1(keycode_3: int) -> linux_control:
    return linux_control(linux_csi, keycode_3, None, None)


def csi_2(keycode_3: int, keycode_4: int) -> linux_control:
    return linux_control(linux_csi, keycode_3, keycode_4, None)


def csi_2_end126(keycode_3: int) -> linux_control:
    return linux_control(linux_csi, keycode_3, linux_126, None)


def csi_3_end126(keycode_3: int, keycode_4: int):
    return linux_control(linux_csi, keycode_3, keycode_4, linux_126)


def o_1(keycode_3: int) -> linux_control:
    return linux_control(linux_o, keycode_3, None, None)


lc_eot = char(4)

# 27 91 XX
# esc [ code
lc_up = csi_1(65)
lc_down = csi_1(66)
lc_right = csi_1(67)
lc_left = csi_1(68)

# 27 79 XX
lc_curse_up = o_1(65)
lc_curse_down = o_1(66)
lc_curse_right = o_1(67)
lc_curse_left = o_1(68)

# 27 91 XX 126
lc_pgdown = csi_2_end126(54)
lc_curse_pgdown = csi_1(54)

# 27 91 XX 126
lc_pgup = csi_2_end126(53)
lc_curse_pgup = csi_1(53)

# 27 91 XX
lc_end = csi_1(70)
lc_home = csi_1(72)

# 27 79 XX
lc_curse_end = o_1(70)
lc_curse_home = o_1(72)

# 27 91 XX 126
lc_insert = csi_2_end126(50)
lc_delete = csi_2_end126(51)

# 27 91 XX
lc_curse_delete = csi_1(51)

lc_backspace = char(127)

# 27 79 80
lc_f1 = o_1(80)
lc_f2 = o_1(81)
lc_f3 = o_1(82)
lc_f4 = o_1(83)

# 27 91 49 53 126
lc_f5 = csi_3_end126(49, 53)
lc_f6 = csi_3_end126(49, 55)
lc_f7 = csi_3_end126(49, 56)
lc_f8 = csi_3_end126(49, 57)

lc_f9 = csi_3_end126(50, 48)
lc_f10 = csi_3_end126(50, 49)

lc_f12 = csi_3_end126(50, 52)

lc_line_end = char(10)

lctrl_a = char(1)
lctrl_b = char(2)
lctrl_c = char(3)
lctrl_d = char(4)
lctrl_e = char(5)
lctrl_f = char(6)
lctrl_g = char(7)
lctrl_h = char(8)
lctrl_i = char(9)
lctrl_j = char(10)
"""Ctrl+J and Ctrl+M are the same on Linux"""
lctrl_k = char(11)
lctrl_l = char(12)
lctrl_m = char(10)
"""Ctrl+J and Ctrl+M are the same on Linux"""
lctrl_n = char(14)
lctrl_o = char(15)
lctrl_p = char(16)
"""Ctrl+Q doesn't exist on Linux"""
lctrl_r = char(18)
"""Ctrl+S doesn't exist on Linux"""
lctrl_t = char(20)
lctrl_u = char(21)
lctrl_v = char(22)
lctrl_w = char(23)
lctrl_x = char(24)
lctrl_y = char(25)
"""Ctrl+Z has a special function on Linux"""
