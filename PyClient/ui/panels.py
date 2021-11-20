from typing import Optional, Tuple, Set, List

import keys
import utils
from ui.ctrl import *

CTRL = TypeVar('CTRL', covariant=True, bound=control)


class panel(control, ABC):
    def __init__(self):
        super().__init__()
        self._elements: Set[CTRL] = set()
        self._focused = False
        self._cur_focused: Optional[CTRL] = None
        self._on_elements_changed = event()
        self._on_focused_changed = event()
        self._layout_changed = True

        self.on_prop_changed.add(self._on_layout_changed)

        self._on_elements_changed.add(lambda _, _1, _2: self.on_content_changed(self))
        self._on_focused_changed.add(lambda _, _1, _2: self.on_content_changed(self))

    def _on_layout_changed(self, self2, prop_name):
        self.on_content_changed(self)
        self._layout_changed = True

    def _on_elemt_exit_focus(self, elemt) -> bool:
        """

        :param elemt:
        :return: whether current focused control exited
        """
        if elemt == self.cur_focused:
            self.cur_focused = None
            return True
        return False

    def cache_layout(self):
        pass

    def add(self, elemt: control):
        if elemt not in self._elements:
            self._elements.add(elemt)
            elemt.in_container = True
            elemt.on_content_changed.add(self._on_elemt_content_changed)
            self.on_elements_changed(self, True, elemt)
            elemt.on_exit_focus.add(self._on_elemt_exit_focus)

    def remove(self, elemt: control):
        if elemt in self._elements:
            self._elements.remove(elemt)
            elemt.in_container = False
            elemt.on_content_changed.remove(self._on_elemt_content_changed)
            self.on_elements_changed(self, False, elemt)
            elemt.on_exit_focus.remove(self._on_elemt_exit_focus)

    def _on_elemt_content_changed(self, elemt):
        self.on_content_changed(self)

    @property
    def on_elements_changed(self) -> event:
        """
        Para 1:panel object
        
        Para 2:True->Add,False->Remove
        
        Para 3:operated control

        :return: event(panel,bool,control)
        """
        return self._on_elements_changed

    @property
    def on_focused_changed(self) -> event:
        """
        Para 1:panel object

        Para 2:former focused
        
        Para 3:current focused

        :return: event(panel,control,control)
        """
        return self._on_focused_changed

    @abstractmethod
    def draw_on(self, buf: buffer):
        """
        Draw all content on the buffer
        :param buf:screen buffer
        """
        pass

    @property
    def elements(self) -> Set[control]:
        return self._elements

    @property
    def elemt_count(self) -> int:
        return len(self._elements)

    @property
    def focusable(self) -> bool:
        return True

    @property
    def cur_focused(self) -> control:
        return self._cur_focused

    @cur_focused.setter
    def cur_focused(self, value: control):
        if value is None or value in self.elements:
            former: control = self._cur_focused
            if former != value:
                if former and former.focusable:
                    former.on_lost_focus()
                self._cur_focused = value
                if value and value.focusable:
                    value.on_focused()
                self.on_focused_changed(self, former, value)

    @property
    def elemts_total_width(self):
        return sum(elemt.width for elemt in self.elements)

    @property
    def elemts_total_height(self):
        return sum(elemt.height for elemt in self.elements)

    def go_next_focusable(self):
        pass

    def go_pre_focusable(self):
        pass

    def on_input(self, char: chars.char) -> bool:
        if self.cur_focused:
            return self.cur_focused.on_input(char)
        elif chars.c_esc == char:
            self.on_exit_focus(self)
            return True
        return False


Orientation = str
horizontal = "horizontal"
vertical = "vertical"

OverRange = str
discard = "discard"
expend = "expend"


class stack(panel):
    def cache_layout(self):
        self._layout_changed = False
        if self.orientation == vertical:
            if self.elemt_interval == auto:
                if self.height == auto:
                    self._r_elemt_interval = 0
                else:
                    self._r_elemt_interval = self.height // self.elemts_total_height
            else:
                self._r_elemt_interval = self.elemt_interval
        else:  # horizontal
            if self.elemt_interval == auto:
                if self.width == auto:
                    self._r_elemt_interval = 1
                else:
                    self._r_elemt_interval = self.width // self.elemts_total_width
            else:
                self._r_elemt_interval = self.elemt_interval
        h = 0
        w = 0
        for i, elemt in enumerate(self._elements_stack):
            if self.width != auto and w >= self.width and self.over_range == discard:
                continue
            if self.height != auto and h >= self.height and self.over_range == discard:
                continue
            h += elemt.render_height
            w += elemt.render_width
            if i > 0:
                if self.orientation == horizontal:
                    h += self._r_elemt_interval
                else:
                    w += self._r_elemt_interval

        self._r_width = w
        self._r_height = h

    def draw_on(self, buf: buffer):
        if self._layout_changed:
            self.cache_layout()

        if self.orientation == vertical:
            h = 0
            for i, elemt in enumerate(self._elements_stack):
                h += elemt.render_height
                if i > 0:
                    h += self._r_elemt_interval
                if self.height != auto and h >= self.height and self.over_range == discard:
                    break
                elemt: control
                elemt.draw_on(buf)
                interval = utils.repeat("\n", self._r_elemt_interval)
                buf.addtext(text=interval)
        else:
            w = 0
            for i, elemt in enumerate(self._elements_stack):
                w += elemt.render_width
                if i > 0:
                    w += self._r_elemt_interval
                if self.width != auto and w >= self.width and self.over_range == discard:
                    break
                elemt: control
                elemt.draw_on(buf)
                interval = utils.repeat(" ", self._r_elemt_interval)
                buf.addtext(text=interval, end="")
        if not self.in_container:
            buf.addtext()

    def __init__(self):
        super().__init__()
        self._elements_stack: List[control] = []
        self._elemt_interval = auto
        self._r_elemt_interval = 0
        self._orientation = vertical
        self._over_range = discard
        self._cur_focused_index = None
        self._r_width = 0
        self._r_height = 0
        self._is_selected: bool = True

    @property
    def cur_focused_index(self) -> Optional[int]:
        return self._cur_focused_index

    @cur_focused_index.setter
    def cur_focused_index(self, value: Optional[int]):
        if value is None:
            if self._cur_focused_index != value:
                self._cur_focused_index = value
                self.cur_focused = None
        else:
            value = max(value, 0)
            value = min(value, len(self.elements) - 1)
            if self._cur_focused_index != value:
                self._cur_focused_index = value
                self.cur_focused = self._elements_stack[value]

    @property
    def elemt_interval(self) -> PROP:
        return self._elemt_interval

    @elemt_interval.setter
    def elemt_interval(self, value: PROP):
        self._elemt_interval = value
        self.on_prop_changed(self, "elemt_interval")

    @property
    def orientation(self) -> Orientation:
        return self._orientation

    @orientation.setter
    def orientation(self, value: Orientation):
        if self._orientation != value:
            self._orientation = value
            self.on_prop_changed(self, "orientation")

    @property
    def over_range(self) -> OverRange:
        return self._over_range

    @over_range.setter
    def over_range(self, value: OverRange):
        if self._over_range != value:
            self._over_range = value
            self.on_prop_changed(self, "over_range")

    def go_next_focusable(self):
        if self.cur_focused_index is None:
            i = -1
        else:
            i = self.cur_focused_index
        for ci in range(i + 1, self.elemt_count):
            c = self._elements_stack[ci]
            if c.focusable:
                self.cur_focused_index = ci
                break

    def go_pre_focusable(self):
        if self.cur_focused_index is None:
            return
        else:
            i = self.cur_focused_index
        for ci in range(i - 1, 0, -1):
            c = self._elements_stack[ci]
            if c.focusable:
                self.cur_focused_index = ci
                break

    def add(self, elemt: control):
        self._elements_stack.append(elemt)
        super().add(elemt)

    def remove(self, elemt: control):
        try:
            self._elements_stack.remove(elemt)
        except:
            pass
        super().remove(elemt)

    def on_input(self, char: chars.char) -> bool:
        if self.cur_focused and self._is_selected:
            return self.cur_focused.on_input(char)
        elif keys.k_enter == char:
            self._is_selected = True
            return True
        elif keys.k_up == char:
            self.go_pre_focusable()
            return True
        elif keys.k_down == char:
            self.go_next_focusable()
            return True
        elif chars.c_esc == char:
            self.on_exit_focus(self)
            return True
        return False

    def _on_elemt_exit_focus(self, elemt) -> bool:
        if super()._on_elemt_exit_focus(elemt):
            if self.cur_focused is None:
                self.on_exit_focus(self)
                self._is_selected = False
            # self.cur_focused_index = None
            return True
        return False

    @property
    def render_height(self) -> int:
        return self._r_height

    @property
    def render_width(self) -> int:
        return self._r_width


class row:
    def __init__(self):
        self.height: int = 1


class column:
    def __init__(self, width: PROP):
        self.width: PROP = width


class _unit:
    def __init__(self, row: row, column: column):
        self.row = row
        self.column = column

    @property
    def width(self) -> PROP:
        return self.column.width

    @property
    def height(self) -> int:
        return self.row.height


def gen_grid(row_count: int, columns: [column]):
    return grid(rows=[row() for i in range(row_count)], columns=columns)


class grid(panel):
    """
    Example 1:

    3*2:
    interval width = 2
    interval height = 1
    column[0] width = 4
    column[1] width = 13

    Date__  1/1_______________

    Name__  Liplum____________

    Email_  Liplum@outlook.com
    Example 2:

    6*3:
    interval width = 1
    interval height = 0
    column[0] width = 4
    column[1] width = 13
    column[2] width = 13

    Day_ Event________ With whom____
    1___ Nothing______ Only me______
    2___ Stay home____ My parents___
    3___ Programming__ Only me______
    4___ Sports_______ Friends______
    5___ Study________ Classmates___
    """

    def __init__(self, rows: [row], columns: [column]):
        super().__init__()
        self.rowlen = len(rows)
        self.columnlen = len(columns)
        self.rows = rows
        self.columns = columns

        if self.rowlen == 0:
            self.rows = [row()]
        if self.columnlen == 0:
            self.columns = [column(width=auto)]

        self._elemt_interval_w = auto
        self._elemt_interval_h = auto
        self.gen_unit()
        self._grid: List[List[control]] = utils.fill_2d_array(self.rowlen, self.columnlen, None)
        self._r_width = 0
        self._r_height = 0
        self._r_elemt_interval_w = 0
        self._r_elemt_interval_h = 0

    def gen_unit(self):
        self._units: List[List[_unit]] = utils.gen_2d_arrayX(
            self.rowlen, self.columnlen, lambda i, j: _unit(self.rows[i], self.columns[j]))

    def draw_on(self, buf: buffer):
        if self._layout_changed:
            self.cache_layout()

        for i in range(self.rowlen):
            for j in range(self.columnlen):
                c = self._grid[i][j]
                if c:
                    c.draw_on(buf)
                    w = c.render_width
                    rest = self.columns[j].width - w
                    if rest > 0:
                        buf.addtext(utils.repeat(" ", rest), end="")
                else:
                    buf.addtext(utils.repeat(" ", self.columns[j].width), end="")
                buf.addtext(utils.repeat(" ", self._r_elemt_interval_w), end="")
            buf.addtext(utils.repeat("\n", self._r_elemt_interval_h))
        if not self.in_container:
            buf.addtext()

    def cache_layout(self):
        self._layout_changed = False

        w = 0
        h = 0
        if self.width == auto:
            if self.elemt_interval_w == auto:
                self._r_elemt_interval_w = 1
            else:
                self._r_elemt_interval_w = self.elemt_interval_w

            for j, column in enumerate(self.columns):
                max_width = max(c.render_width for c in self.column_items(j) if c)
                column.width = max_width
                w += max_width
        else:
            occupied_width = 0
            for j, column in enumerate(self.columns):
                max_width = max(c.render_width for c in self.column_items(j) if c)
                column.width = max_width
                w += max_width
                occupied_width += max_width

            if self.elemt_interval_w == auto:
                if columnlen == 1:
                    self._r_elemt_interval_w = 0
                else:
                    self._r_elemt_interval_w = (self.width - occupied_width) // (self.columnlen - 1)
            else:
                self._r_elemt_interval_w = self.elemt_interval_w

        w += self._r_elemt_interval_w * (self.columnlen - 1)

        if self.height == auto:
            if self.elemt_interval_h == auto:
                self._r_elemt_interval_h = 0
            else:
                self._r_elemt_interval_h = self.elemt_interval_h
        else:
            if self.elemt_interval_h == auto:
                if self.rowlen == 1:
                    self._r_elemt_interval_w = 0
                else:
                    self._r_elemt_interval_h = (self.height - self.rowlen) // (self.columnlen - 1)
            else:
                self._r_elemt_interval_h = self.elemt_interval_h

        h += self.rowlen + self._r_elemt_interval_h * (self.rowlen - 1)
        self._r_width = w
        self._r_height = h

        for i in range(self.rowlen):
            for j in range(self.columnlen):
                c = self._grid[i][j]
                if c:
                    c.width = self._units[i][j].width

    def row_items(self, row: int):
        for j in range(self.columnlen):
            yield self._grid[row][j]

    def column_items(self, column: int):
        for i in range(self.rowlen):
            yield self._grid[i][column]

    @property
    def elemt_interval_w(self) -> PROP:
        return self._elemt_interval_w

    @elemt_interval_w.setter
    def elemt_interval_w(self, value: PROP):
        if value != auto and value < 0:
            value = 0
        if self._elemt_interval_w != value:
            self._elemt_interval_w = value
            self.on_prop_changed(self, "elemt_interval_w")

    @property
    def elemt_interval_h(self) -> PROP:
        return self._elemt_interval_h

    @elemt_interval_h.setter
    def elemt_interval_h(self, value: PROP):
        if value != auto and value < 0:
            value = 0
        if self._elemt_interval_h != value:
            self._elemt_interval_h = value
            self.on_prop_changed(self, "elemt_interval_h")

    def __getitem__(self, item: Tuple[int, int]) -> Optional[CTRL]:
        i, j = item
        return self._grid[i][j]

    def __setitem__(self, key: Tuple[int, int], value: control):
        i, j = key
        self.set(i, j, value)

    def set(self, i: int, j: int, ctrl: control):
        former: control = self._grid[i][j]
        if former:
            self.remove(former)
        self._grid[i][j] = ctrl
        self.add(ctrl)

    @property
    def render_height(self) -> int:
        return self._r_height

    @property
    def render_width(self) -> int:
        return self._r_width
