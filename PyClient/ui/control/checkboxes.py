from io import StringIO

import keys
import utils
from ui.ctrl import *
from ui.outputs import CmdBkColor, tintedtxt, CmdFgColor
from ui.themes import check_theme

yes_or_no = check_theme("[Yes]", "[No]", "[  ]")
simple_yes_or_no_ = check_theme("[Y]", "[N]", "[ ]")
square_box = check_theme("[⬛]", "[⬜]", "[ ]")
ballot_box = check_theme("[☑]", "[⬜]", "[ ]")
check_and_x = check_theme("[☑]", "[☒]", "[ ]")
ballot_box_x = check_theme("[🗹]", "[❎]", "[ ]")
bold_check = check_theme("[✅]", "[❌]", "[ ]")


class checkbox(control):

    def __init__(self, value: Optional[bool] = None, theme: check_theme = yes_or_no):
        super().__init__()
        self.theme = theme
        self._checked: Optional[bool] = value

    def paint_on(self, buf: buffer):
        with StringIO() as s:
            if self.left_margin > 0:
                utils.repeatIO(s, " ", self.left_margin)
            s.write(self.cur_render_icon)
            bk = CmdBkColor.White if self.is_focused else None
            fg = CmdFgColor.Black if self.is_focused else None
            buf.addtext(tintedtxt(s.getvalue(), fgcolor=fg, bkcolor=bk), end="")

    @property
    def checked(self) -> Optional[bool]:
        return self._checked

    @checked.setter
    def checked(self, value: Optional[bool]):
        if self.checked != value:
            self._checked = value
            self.on_prop_changed(self, "checked")

    @property
    def cur_render_icon(self) -> str:
        if self.checked is True:
            return self.theme.checked
        elif self.checked is False:
            return self.theme.unchecked
        else:
            return self.theme.null

    @property
    def focusable(self) -> bool:
        return True

    def on_input(self, char: chars.char) -> Is_Consumed:
        if keys.k_enter == char:
            if not self.switch():
                self.checked = True
            return Consumed
        elif chars.c_esc == char:
            self.on_exit_focus(self)
            return Consumed
        return Not_Consumed

    def switch(self) -> bool:
        former = self.checked
        if former is not None:
            self.checked = not former
            return True
        return False

    def cache_layout(self):
        if not self._layout_changed:
            return
        self._layout_changed = False

    @property
    def render_height(self) -> int:
        return 1

    @property
    def render_width(self) -> int:
        return len(self.cur_render_icon)

    @property
    def height(self) -> PROP:
        return self._height

    @height.setter
    def height(self, value: PROP):
        if value != auto:
            value = 1
        self._height = value

    @property
    def width(self) -> PROP:
        return self._width

    @width.setter
    def width(self, value: PROP):
        if value != auto:
            value = 1
        self._width = value