from abc import ABC, abstractmethod
from enum import Enum, IntEnum, auto, unique
from datetime import datetime
from typing import Union, Optional, NoReturn, Tuple, List


class i_logger:
    def __init__(self):
        self.logfile: Optional[str] = None

    def msg(self, text) -> NoReturn:
        pass

    def tip(self, text) -> NoReturn:
        pass

    def warn(self, text) -> NoReturn:
        pass

    def error(self, text) -> NoReturn:
        pass


@unique
class CmdFgColor(IntEnum):
    Black = 30
    Red = 31
    Green = 32
    Yellow = 33
    Blue = 34
    Violet = 35
    Cyan = 36
    White = 37


class CmdBkColor(IntEnum):
    Black = 40
    Red = 41
    Green = 42
    Yellow = 43
    Blue = 44
    Violet = 45
    Cyan = 46
    White = 47


class AlertColor(IntEnum):
    Msg = CmdFgColor.White
    Tip = CmdFgColor.Blue
    Warn = CmdFgColor.Yellow
    Error = CmdFgColor.Red


def tinted_print(text: str, fgcolor: Optional[CmdFgColor] = None, bkcolor: Optional[CmdBkColor] = None,
                 end='\n') -> NoReturn:
    fg = 0 if fgcolor is None else int(fgcolor)
    bk = 0 if bkcolor is None else int(bkcolor)
    print(f"\033[0;{fg};{bk}m{text}\033[0m", end=end)


def gen_tinted_text(text: str, fgcolor: Optional[CmdFgColor], bkcolor: Optional[CmdBkColor] = None, end='\n') -> str:
    fg = 0 if fgcolor is None else int(fgcolor)
    bk = 0 if bkcolor is None else int(bkcolor)
    return f"\033[0;{fg};{bk}m{text}\033[0m{end}"


class cmd_logger(i_logger):

    def __init__(self, output_to_cmd: bool = True, logfile: Optional[str] = None):
        super().__init__()
        self.logfile: Optional[str] = logfile
        self.output_to_cmd = output_to_cmd

    def msg(self, text: str) -> NoReturn:
        self.alert_print(text, AlertColor.Msg, "Message")

    def tip(self, text: str) -> NoReturn:
        self.alert_print(text, AlertColor.Tip, "Tip")

    def warn(self, text: str) -> NoReturn:
        self.alert_print(text, AlertColor.Warn, "Warn")

    def error(self, text: str) -> NoReturn:
        self.alert_print(text, AlertColor.Error, "Error")

    def alert_print(self, text: str, color: Union[CmdFgColor, AlertColor], alertLevel: str) -> None:
        time_stamp = datetime.now().strftime("%Y%m%d-%H:%M:%S")
        t = f"{time_stamp}[{alertLevel}]{text}"
        tinted_print(t, color)
        if self.logfile is not None:
            with open(self.logfile, "w+") as log:
                log.writelines(t)


class i_display:
    def display_text(self, text: str = "", end: str = '\n', fgcolor: Optional[CmdFgColor] = None,
                     bkcolor: Optional[CmdBkColor] = None) -> NoReturn:
        pass

    def display_image(self, file_path: str):
        pass

    def render(self):
        pass


class cmd_display(i_display):
    """
    It uses buffer to store all items used be rendered soon until call render(self)
    """

    def __init__(self):
        self.render_list: List[str] = []

    def display_text(self, text: str = "", end: str = '\n', fgcolor: Optional[CmdFgColor] = None,
                     bkcolor: Optional[CmdBkColor] = None) -> NoReturn:
        self.render_list.append(gen_tinted_text(text, fgcolor, bkcolor, end))

    def clear_render_list(self):
        self.render_list = []

    def render(self):
        for text in self.render_list:
            print(text, end='')
        self.clear_render_list()