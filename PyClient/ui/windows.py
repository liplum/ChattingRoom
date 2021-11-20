import traceback
from io import StringIO
from typing import Union, Type, Dict, Iterable

import GLOBAL
import i18n
import keys
import ui.panels as panels
import ui.states
import utils
from cmd import WrongUsageError, CmdError, CmdNotFound, analyze_cmd_args, compose_full_cmd, is_quoted
from cmd import cmdmanager
from core.chats import i_msgmager
import core.operations as op
from core.settings import entity as settings
from ui import outputs as output
from ui.controls import label, textbox, button, fix_text_label
from ui.ctrl import *
from ui.k import kbinding
from ui.notice import notified
from ui.outputs import CmdBkColor, CmdFgColor
from ui.outputs import buffer
from ui.panels import stack, gen_grid, column
from ui.states import ui_state, ui_smachine
from utils import get, fill_2d_array, multiget, all_none
from core.shared import *

T = TypeVar('T')
CTRL = TypeVar('CTRL', bound=control)

tab_name2type: Dict[str, Type["tab"]] = {}
tab_type2name: Dict[Type["tab"], str] = {}


def i18n_label(i18n_key: str, *args, **kwargs):
    return label(CGT(lambda: i18n.trans(i18n_key, *args, **kwargs)))


def common_hotkey(char: chars.char, tab: "tab", client: "client", tablist: "tablist"):
    """

    :param tab:
    :param char:
    :param client:
    :param tablist:
    :return: (True | None) Whether the char wasn't consumed
    """
    if chars.c_q == char:
        client.stop()
    elif chars.c_a == char:
        tablist.back()
    elif chars.c_s == char:
        tablist.switch()
    elif chars.c_d == char:
        tablist.next()
    elif chars.c_x == char:
        tablist.remove_cur()
    elif chars.c_n == char:
        tablist.new_chat_tab()
    else:
        return True


def find_best_incomplete_chat_tab(tablist: "tablist", server: server_token,
                                  account: userid) -> Optional["chat_tab"]:
    possible = []
    for t in tablist.chat_tabs_it:
        if t.authenticated:
            continue
        ts = t.connected
        ta = t.user_info.uid if t.user_info else None
        if (ts and ts != server) or (ta and ta != account):
            continue
        else:
            possible.append(t)
    if len(possible) == 0:
        return None
    return possible[0]


def add_tabtype(name: str, tabtype: Type["tab"]):
    tab_name2type[name] = tabtype
    tab_type2name[tabtype] = name


class CannotRestoreTab(Exception):
    def __init__(self, tabtype: Type["tab"]):
        super().__init__()
        self.tabtype = tabtype


class CannotStoreTab(Exception):
    def __init__(self, tab: "tab"):
        super().__init__()
        self.tab = tab


class xtextbox(textbox):
    def __init__(self, cursor_icon: str = '^'):
        super().__init__(cursor_icon)
        kbs = kbinding()
        self.kbs = kbs
        kbs.bind(keys.k_backspace, lambda c: self.delete())
        kbs.bind(keys.k_delete, lambda c: self.delete(left=False))
        kbs.bind(keys.k_left, lambda c: self.left())
        kbs.bind(keys.k_right, lambda c: self.right())
        kbs.bind(keys.k_home, lambda c: self.home())
        kbs.bind(keys.k_end, lambda c: self.end())
        kbs.bind(chars.c_esc, lambda c: self.on_exit_focus(self))
        spapp = super().append
        kbs.on_any = lambda c: spapp(chars.to_str(c)) if c.is_printable() else None

    def append(self, ch: Union[str, chars.char]) -> bool:
        if isinstance(ch, str):
            super().append(ch)
        elif isinstance(ch, chars.char):
            consumed = self.kbs.trigger(ch)
            if not consumed:
                return super().append(to_str(ch))
        return False


class tab(notified, ABC):
    def __init__(self, client: "client", tablist: "tablist"):
        super().__init__()
        self.tablist = tablist
        self.client = client

    def on_input(self, char: chars.char):
        pass

    def draw_on(self, buf: buffer):
        pass

    @classmethod
    def deserialize(cls, data: dict, client: "client", tablist: "tablist") -> T:
        pass

    @classmethod
    def serialize(cls, self: T) -> dict:
        pass

    @classmethod
    def serializable(cls) -> bool:
        return False

    @property
    @abstractmethod
    def title(self) -> str:
        pass

    def add_string(self, string: str):
        pass

    def on_added(self):
        pass

    def on_removed(self):
        pass

    def on_focused(self):
        pass

    def on_lost_focus(self):
        pass

    def __hash__(self) -> int:
        return id(self)

    def __eq__(self, other):
        return id(self) == id(other)


class chat_tab(tab):
    def __init__(self, client: "client", tablist: "tablist"):
        super().__init__(client, tablist)
        self.textbox = xtextbox()
        self.history: List[str] = []
        self.max_display_line = 10
        self.fill_until_max = True
        self.msg_manager: i_msgmager = self.client.msg_manager
        self.network: "i_network" = self.client.network
        self.logger: "i_logger" = self.client.logger
        self.first_loaded = False
        self.focused = False
        self._unread_number = 0

        self._connected: Optional[server_token] = None
        self._joined: Optional[roomid] = None
        self._user_info: Optional[uentity] = None

        def set_client(state: ui_state) -> None:
            state.client = self.client
            state.textbox = self.textbox
            state.tablist = self.tablist
            state.tab = self

        def gen_state(statetype: type) -> ui_state:
            if issubclass(statetype, ui_state):
                s = statetype()
                set_client(s)
                return s
            else:
                return statetype()

        self.sm = ui_smachine(state_pre=set_client, stype_pre=gen_state, allow_repeated_entry=False)
        self.sm.enter(cmd_mode)
        self.textbox.on_append.add(lambda b, p, c: client.mark_dirty())
        self.textbox.on_delete.add(lambda b, p, c: client.mark_dirty())
        self.textbox.on_cursor_move.add(lambda b, f, c: client.mark_dirty())
        self.textbox.on_list_replace.add(lambda b, f, c: client.mark_dirty())

    @property
    def unread_number(self) -> int:
        return self._unread_number

    @unread_number.setter
    def unread_number(self, value: int):
        if self._unread_number != value:
            self._unread_number = value
            self.client.mark_dirty()

    def send_text(self):
        info = self.user_info
        if self.connected and self.joined and info:
            if info.verified:
                inputs = self.textbox.inputs
                self.client.send_text(info, self.joined, inputs)
            else:
                self.add_string(i18n.trans("tabs.chat_tab.account_unverified", account=info.uid, ip=self.connected.ip))
        else:
            self.logger.error(f"[Tab][{self}]Haven't connected a server yet.")
        self.textbox.clear()

    @property
    def joined(self) -> Optional[roomid]:
        return self._joined

    def join(self, value):
        self._joined = value
        self.client.mark_dirty()

    @property
    def connected(self) -> Optional[server_token]:
        return self._connected

    def connect(self, server_token):
        if not self.network.is_connected(server_token):
            try:
                self.network.connect(server_token, strict=True)
            except:
                self.logger.error(f"[Tab][{self}]Cannot connect the server {server_token}")
                return
        self._connected = server_token
        self.client.mark_dirty()
        # self.logger.error(f"[Tab][{self}]Cannot access a unconnected/disconnected server.")

    @property
    def user_info(self) -> Optional[uentity]:
        return self._user_info

    @user_info.setter
    def user_info(self, value: Optional[uentity]):
        self._user_info = value
        self.client.mark_dirty()

    @property
    def authenticated(self) -> bool:
        return self.connected and self.user_info and self.user_info.verified

    def _add_msg(self, time, uid, text):
        configs = settings()
        date_format = configs.DateFormat
        self.history.append(f"{time.strftime(date_format)}\n  {uid}:  {text}")

    def first_load(self):
        self.history = []
        if self.connected and self.joined:
            li = self.msg_manager.load_until_today(self.connected, self.joined, self.max_display_line)
            for time, uid, text in li:
                self._add_msg(time, uid, text)
        self.first_loaded = True

    def draw_on(self, buf: buffer):
        if not self.first_loaded:
            self.first_load()

        self.render_connection_info(buf)
        buf.addtext(self.distext)
        self.sm.draw_on(buf)
        buf.addtext(self.textbox.distext)

    def render_connection_info(self, buf: buffer):
        if self.connected:
            if self.joined:
                tip = i18n.trans('tabs.chat_tab.joined',
                                 ip=self.connected.ip, port=self.connected.port, room_id=self.joined)
            else:
                tip = i18n.trans('tabs.chat_tab.connected',
                                 ip=self.connected.ip, port=self.connected.port)
        else:
            tip = i18n.trans('tabs.chat_tab.no_connection')
        buf.addtext(text=tip, bkcolor=CmdBkColor.White, fgcolor=CmdFgColor.Black, end='\n')

    @property
    def distext(self) -> str:
        if len(self.history) < self.max_display_line:
            displayed = self.history
            have_rest = True
        else:
            displayed = self.history[-self.max_display_line:]
            have_rest = False

        if have_rest and self.fill_until_max:
            with StringIO() as s:
                s.write(utils.compose(displayed, connector="\n"))
                displayed_len = len(displayed)
                s.write(utils.fill("", "\n", self.max_display_line - displayed_len))
                return s.getvalue()
        else:
            return utils.compose(displayed, connector="\n")

    def on_input(self, char):
        self.sm.on_input(char)

    @property
    def title(self) -> str:
        if GLOBAL.DEBUG:
            return f"chat tab<{hash(self)}>"
        if self.connected and self.joined:
            badge = ""
            if self.user_info:
                if self.user_info.verified:
                    if self.unread_number > 0:
                        badge = f"[{self.unread_number}]"
                else:
                    badge = f"[{i18n.trans('tabs.chat_tab.badge.unverified')}]"
            else:
                badge = f"[{i18n.trans('tabs.chat_tab.badge.unlogin')}]"
            return f"{badge}{str(self.joined)}"
        return i18n.trans("tabs.chat_tab.name")

    def add_string(self, string: str):
        self.history.append(string)

    def on_added(self):
        self.msg_manager.on_received.add(self._on_received_msg)

    def _on_received_msg(self, manager, server, room_id, msg_unit):
        if server == self.connected and room_id == self.joined:
            time, uid, text = msg_unit
            self._add_msg(time, uid, text)
            if not self.focused:
                self.unread_number += 1

    def on_removed(self):
        self.msg_manager.on_received.remove(self._on_received_msg)

    @classmethod
    def deserialize(cls, data: dict, client: "client", tablist: "tablist") -> "chat_tab":
        t = chat_tab(client, tablist)
        server = get(data, "server")
        room_id = get(data, "room_id")
        account = get(data, "account")
        server = to_server_token(server)
        if all_none(server, room_id, account):
            raise CannotRestoreTab(chat_tab)
        if server:
            t.connect(server)
            if account:
                t.user_info = uentity(server, account)
        if room_id:
            t.join(room_id)
        return t

    @classmethod
    def serialize(cls, self: "chat_tab") -> dict:
        if all_none(self.connected, self.joined, self.user_info):
            raise CannotStoreTab(self)
        d = {
            "server": f"{self.connected.ip}:{self.connected.port}" if self.connected else None,
            "room_id": self.joined if self.joined else None,
            "account": self.user_info.uid if self.user_info else None
        }
        return d

    def on_focused(self):
        self.focused = True
        self.unread_number = 0

    def on_lost_focus(self):
        self.focused = False

    @classmethod
    def serializable(cls) -> bool:
        return True

    def __repr__(self) -> str:
        c = f" {self.connected.ip}:{self.connected.port}" if self.connected else ""
        j = f"-{self.joined}" if self.joined else ""
        a = f"-{self.user_info.uid}" if self.user_info else ""
        return f"<chat_tab{c}{j}{a}>"

    def __hash__(self):
        account = self.user_info.uid if self.user_info else None
        return hash((self.connected, self.joined, account))

    def __eq__(self, other):
        if isinstance(other, chat_tab):
            return self.connected == other.connected and self.joined == other.joined and self.user_info == other.user_info
        else:
            return False


add_tabtype("chat_tab", chat_tab)


class settings_tab(tab):
    @property
    def title(self) -> str:
        return "settings_tab"


add_tabtype("settings_tab", settings_tab)


class test_tab(tab):

    def __init__(self, client: "client", tablist: "tablist"):
        super().__init__(client, tablist)
        self.stack = stack()
        self.stack.on_content_changed.add(lambda _: self.on_content_changed(self))
        self.stack.add(fix_text_label("Label A"))
        self.account_tbox = xtextbox()
        self.account_tbox.space_placeholder = "_"
        account_stack = stack()
        account_stack.add(fix_text_label("Account"))
        account_stack.add(self.account_tbox)
        account_stack.orientation = panels.horizontal
        self.stack.add(account_stack)
        self.stack.add(fix_text_label("Test Label B"))
        self.stack.add(fix_text_label("Test"))
        self.input_box = xtextbox()
        self.input_box.space_placeholder = "_"
        self.stack.add(self.input_box)
        button_content = "Button"

        def button_content_getter() -> str:
            return button_content

        def _click_button():
            nonlocal button_content
            button_content = "Clicked"
            self.client.mark_dirty()

        self.button = button(CGT(button_content_getter), _click_button)
        self.button.margin = 2
        self.stack.add(self.button)
        # self.stack.orientation = panels.horizontal

        self.stack.elemt_interval = 1
        self._stack_focused = True

        def _on_stack_exit_focus(stak):
            self._stack_focused = False

        self.stack.on_exit_focus.add(_on_stack_exit_focus)

    def draw_on(self, buf: buffer):
        self.stack.draw_on(buf)
        if GLOBAL.DEBUG:
            stak = self.stack
            c = stak.cur_focused
            info = f"focused index= {stak.cur_focused_index}\nfocused control= {c}\n"
            buf.addtext(info)
            if c:
                pass

    @property
    def title(self) -> str:
        return "Test"

    def on_input(self, char: chars.char):
        self.stack.on_input(char)
        """if self._stack_focused:
            self.stack.on_input(char)
        else:
            if keys.k_enter == char:
                self._stack_focused = True
            elif self._stack_focused:
                consumed = common_hotkey(char, self, self.client, self.tablist)
        """


class grid_tab(tab):

    def __init__(self, client: "client", tablist: "tablist"):
        super().__init__(client, tablist)
        self.grid = gen_grid(2, [column(15), column(20)])
        l1_1 = label("Label 1 1")
        l1_2 = label("Label 1 2")
        l2_1 = label("Label 2 1")
        l2_2 = label("Label 2 2")
        account_tbox = xtextbox()
        account_tbox.space_placeholder = "_"
        account_stack = stack()
        # account_stack.over_range = panels.expend
        account_stack.add(label("Account"))
        account_stack.add(account_tbox)
        account_stack.orientation = panels.horizontal
        b = button("Button", lambda: None)
        b.margin = 2
        self.grid[0, 0] = account_stack
        self.grid[0, 1] = l1_2
        self.grid[1, 0] = l2_1
        self.grid[1, 1] = b
        self.grid.elemt_interval_w = 5
        self.grid.elemt_interval_h = 1

    def draw_on(self, buf: buffer):
        self.grid.draw_on(buf)

    @property
    def title(self) -> str:
        return "grid tab"


class main_menu_tab(tab):
    @property
    def title(self) -> str:
        return "main_menu_tab"


add_tabtype("main_menu_tab", main_menu_tab)

FIndex = Tuple[int, int]


class login_tab(tab):

    def __init__(self, client: "client", tablist: "tablist"):
        super().__init__(client, tablist)
        self.network: i_network = self.client.network
        self.container_row = 4
        self.container_column = 2
        self.container: List[List[CTRL]] = fill_2d_array(self.container_row, self.container_column, None)
        self.l_server_ip: label = self.set(
            i18n_label("tabs.login_tab.labels.server_ip"),
            0, 0)
        self.l_server_port: label = self.set(
            i18n_label("tabs.login_tab.labels.server_port"),
            1, 0)
        self.l_account: label = self.set(
            i18n_label("tabs.login_tab.labels.account"),
            2, 0)
        self.l_password: label = self.set(
            i18n_label("tabs.login_tab.labels.password"),
            3, 0)

        self.l_server_ip.width = 15
        self.l_server_port.width = 15
        self.l_account.width = 15
        self.l_password.width = 15

        self.t_server_ip: textbox = self.set(xtextbox(), 0, 1)
        self.t_server_port: textbox = self.set(xtextbox(), 1, 1)
        self.t_account: textbox = self.set(xtextbox(), 2, 1)
        self.t_password: textbox = self.set(xtextbox(), 3, 1)

        self.t_server_ip.width = 16
        self.t_server_ip.max_inputs_count = 15

        self.t_server_port.width = 8
        self.t_server_port.max_inputs_count = 7

        self.t_account.width = 16
        self.t_account.max_inputs_count = 15

        self.t_password.width = 16
        self.t_password.max_inputs_count = 15

        self._focused_index = (0, 0)
        self._focused: Optional[CTRL] = None

        self._textbox_index = 0
        # self.go_next_focusable()
        self.textbox_index = 0

    @property
    def textbox_index(self) -> int:
        return self._textbox_index

    @textbox_index.setter
    def textbox_index(self, value: int):
        value = min(value, self.container_row - 1)
        value = max(value, 0)
        self._textbox_index = value
        self.focused = self.container[value][1]
        self.focused_index = (1, value)

    @property
    def focused_index(self) -> FIndex:
        return self._focused_index

    @focused_index.setter
    def focused_index(self, value: FIndex):
        i, j = self.focused_index
        if 0 <= i < self.container_column and 0 <= j < self.container_row:
            self._focused_index = value

    @property
    def focused(self) -> Optional[CTRL]:
        return self._focused

    @focused.setter
    def focused(self, value: Optional[CTRL]):
        if self._focused == value:
            return
        if self._focused:
            self._focused.on_lost_focus()
        self._focused = value
        if value and value.focusable:
            value.on_focused()
        # TODO:Change this
        self.client.mark_dirty()

    def mark_dirt(self):
        self.client.mark_dirty()

    def set(self, control: control, i: int, j: int) -> T:
        self.container[i][j] = control
        control.on_content_changed.add(lambda _: self.mark_dirt())
        control.in_container = True
        return control

    def login(self):
        ip = self.t_server_ip.inputs.strip()
        port = self.t_server_port.inputs.strip()
        full = f"{ip}:{port}" if port != "" else ip
        account = self.t_account.inputs.strip()
        password = self.t_password.inputs.strip()
        token = to_server_token(full)
        if token:
            chat = chat_tab(self.client, self.tablist)
            chat.connect(token)
            chat.user_info = uentity(token, account)
            self.tablist.replace(self, chat)
            op.login(self.network, token, account, password)

    def on_input(self, char: chars.char):
        if keys.k_up == char:
            self.textbox_index -= 1
        elif keys.k_down == char or chars.c_table == char:
            self.textbox_index += 1
        elif keys.k_enter == char:
            if self.textbox_index < self.container_row - 1:
                self.textbox_index += 1
            else:
                self.login()
        elif chars.c_esc == char:
            if isinstance(self.focused, textbox):
                tb: textbox = self.focused
                tb.clear()
        else:
            f: ctrl.control = self.focused
            consumed = False
            if f:
                consumed = f.on_input(char)

    def draw_on(self, buf: buffer):
        for i in range(self.container_row):
            buf.addtext("\t", end="")
            for j in range(self.container_column):
                ct = self.container[i][j]
                if ct:
                    ct.draw_on(buf)
                buf.addtext("  ", end="")
            buf.addtext()

        if GLOBAL.DEBUG:
            buf.addtext()
            pos = self.focused_index
            pos = f"focused pos : ({pos[0]},{pos[1]})"
            buf.addtext(pos)
            if isinstance(self.focused, textbox):
                tb: textbox = self.focused
                info = f"cursor pos = {tb.cursor}\ninput count= {tb.input_count}\nfull inputs = \"{tb.inputs}\""
                buf.addtext(info)

    @property
    def title(self) -> str:
        return i18n.trans("tabs.login_tab.name")


add_tabtype("login_tab", login_tab)


class tablist(notified):
    def __init__(self, win: "window"):
        super().__init__()
        self.tabs: List[tab] = []
        self._cur: Optional[tab] = None
        self.cur_index = 0
        self.win = win
        self.view_history = []
        self.max_view_history = 5
        self._on_curtab_changed = event()
        self._on_tablist_changed = event()

    def unite_like_tabs(self):
        no_duplicate = dict.fromkeys(self.tabs)
        self.tabs = list(no_duplicate)
        if self.cur:
            self.cur_index = self.tabs.index(self._cur)

    def newtab(self, tabtype: Type[T]) -> T:
        t = tabtype(self.win.client, self)
        self.add(t)
        return t

    def new_chat_tab(self) -> chat_tab:
        return self.newtab(chat_tab)

    def has_chat_tab(self) -> bool:
        for t in self.tabs:
            if isinstance(t, chat_tab):
                return True
        return False

    def match_chat_tab(self, predicate: Callable[["chat_tab"], bool]) -> Optional["chat_tab"]:
        for t in self.tabs:
            if isinstance(t, chat_tab) and predicate(t):
                return t
        return None

    def match_chat_tabs(self, predicate: Callable[["chat_tab"], bool]) -> Iterable["chat_tab"]:
        for t in self.tabs:
            if isinstance(t, chat_tab) and predicate(t):
                yield t

    @property
    def chat_tabs(self) -> List[chat_tab]:
        return [t for t in self.tabs if isinstance(t, chat_tab)]

    @property
    def chat_tabs_it(self) -> Iterable[chat_tab]:
        for t in self.tabs:
            if isinstance(t, chat_tab):
                yield t

    @property
    def tabs_count(self) -> int:
        return len(self.tabs)

    @property
    def on_curtab_changed(self) -> event:
        """
        Para 1:tablist object

        Para 2:index of current tab

        Para 3:current tab

        :return: event(tablist,int,tab)
        """
        return self._on_curtab_changed

    @property
    def on_tablist_changed(self) -> event:
        """
        Para 1:tablist object

        Para 2:change type: True->add ; False->remove

        Para 3:operated tab

        :return: event(tablist,bool,tab)
        """
        return self._on_tablist_changed

    def __len__(self) -> int:
        return len(self.tabs)

    @property
    def cur(self) -> Optional[tab]:
        return self._cur

    @cur.setter
    def cur(self, value: Optional[tab]):
        changed = self._cur is not value
        if changed:
            if self._cur:
                self._cur.on_lost_focus()
            self._cur = value
            if self._cur:
                self.cur_index = self.tabs.index(self._cur)
                self._cur.on_focused()
            self.on_curtab_changed(self, self.cur_index, tab)

    def add(self, tab: "tab"):
        self.tabs.append(tab)
        self.on_tablist_changed(self, True, tab)
        if self.cur is None:
            self.cur = tab
        tab.on_added()
        tab.on_content_changed.add(lambda _: self.on_content_changed(self))

    def replace(self, old_tab: Union[int, "tab"], new_tab: "tab"):
        if isinstance(old_tab, int):
            if 0 <= old_tab < len(self.tabs):
                removed = self.tabs[old_tab]
                del self.tabs[old_tab]
                pos = old_tab
            else:
                return
        elif isinstance(old_tab, tab):
            removed = old_tab
            try:
                pos = self.tabs.index(removed)
            except:
                return
            del self.tabs[pos]

        removed.on_removed()
        new_tab.on_added()
        self.tabs.insert(pos, new_tab)

        self.on_tablist_changed(self, False, removed)
        self.on_tablist_changed(self, True, new_tab)

        if self.cur is old_tab:
            self.cur = new_tab

    def insert(self, index: int, new_tab: "tab"):
        self.tabs.insert(index, new_tab)
        self.on_tablist_changed(self, True, new_tab)

    def remove(self, item: Union[int, "tab"]):
        if isinstance(item, int):
            if 0 <= item < len(self.tabs):
                removed = self.tabs[item]
                del self.tabs[item]
        elif isinstance(item, tab):
            removed = item
            try:
                self.tabs.remove(removed)
            except:
                return

        self.on_tablist_changed(self, False, removed)
        removed.on_removed()

        if len(self.tabs) == 0:
            self.cur = None
        else:
            self.goto(self.cur_index)

    def remove_cur(self):
        cur = self.cur
        if cur:
            self.tabs.remove(self.cur)
        self.on_tablist_changed(self, False, cur)
        cur.on_removed()

        if len(self.tabs) == 0:
            self.cur = None
        else:
            self.goto(self.cur_index)

    def switch(self):
        if len(self.view_history) >= 2:
            self.goto(self.view_history[-2])

    def goto(self, number: int):
        number = max(number, 0)
        number = min(number, len(self.tabs) - 1)
        origin = self.cur
        target = self.tabs[number]
        if origin == target:
            return
        self.cur = target
        self.add_view_history(number)

    def next(self):
        self.goto(self.cur_index + 1)

    def back(self):
        self.goto(self.cur_index - 1)

    def add_view_history(self, number: int):
        self.view_history.append(number)
        if len(self.view_history) > self.max_view_history:
            self.view_history = self.view_history[-self.max_view_history:]

    def draw_on(self, buf: buffer):
        tab_count = len(self.tabs)
        cur = self.cur
        with StringIO() as separator:
            for i, t in enumerate(self.tabs):
                bk = CmdBkColor.Yellow if t is cur else CmdBkColor.Green
                fg = CmdFgColor.Black if t is cur else CmdFgColor.Violet
                title = t.title
                displayed_title = f" {title} "
                buf.addtext(displayed_title, fgcolor=fg, bkcolor=bk, end='')
                repeated = " " if t is cur else "─"
                second_line = repeated * len(displayed_title)
                separator.write(second_line)
                if i + 1 < tab_count:
                    buf.addtext("│", end='')
                    if t is cur:
                        separator.write("└")
                    elif i + 1 < tab_count and self.tabs[i + 1] is cur:
                        separator.write("┘")
                    else:
                        separator.write("┴")
            buf.addtext()
            buf.addtext(separator.getvalue())


class window:
    def __init__(self, client: "client", displayer: output.i_display):
        self.client = client
        self.displayer: output.i_display = displayer
        self.tablist: tablist = tablist(self)
        self.screen_buffer: Optional[buffer] = None
        self.tablist.on_content_changed.add(lambda _: self.client.mark_dirty())
        self.tablist.on_curtab_changed.add(lambda li, n, t: self.client.mark_dirty())
        self.tablist.on_tablist_changed.add(lambda li, mode, t: self.client.mark_dirty())
        self.network: "i_network" = self.client.network

        def on_closed_last_tab(li: tablist, mode, t):
            if li.tabs_count == 0:
                self.client.stop()

        self.tablist.on_tablist_changed.add(on_closed_last_tab)

    def start(self):
        configs = settings()
        """
        t = self.newtab(test_tab)
        t = self.newtab(grid_tab)
        self.tablist.cur = t
        """
        if configs.RestoreTabWhenRestart:
            self.restore_last_time_tabs()

    def stop(self):
        configs = settings()
        if configs.RestoreTabWhenRestart:
            self.store_unclosed_tabs()

    def restore_last_time_tabs(self):
        configs = settings()
        last_opened: Dict[str, List[dict]] = configs.LastOpenedTabs
        for tab_name, li in last_opened.items():
            if tab_name in tab_name2type:
                tabtype = tab_name2type[tab_name]
                if tabtype.serializable():
                    for entity in li:
                        try:
                            tab = tabtype.deserialize(entity, self.client, self.tablist)
                        except:
                            continue
                        if tab:
                            self.tablist.add(tab)
        self.tablist.unite_like_tabs()

    def store_unclosed_tabs(self):
        self.tablist.unite_like_tabs()
        configs = settings()
        last_opened: Dict[str, List[dict]] = {}
        for tab in self.tablist.tabs:
            tabtype = type(tab)
            if tabtype in tab_type2name:
                if tabtype.serializable():
                    li = multiget(last_opened, tab_type2name[tabtype])
                    try:
                        dic = tabtype.serialize(tab)
                    except:
                        continue
                    if dic:
                        li.append(dic)
        configs.set("LastOpenedTabs", last_opened)

    def gen_default_tab(self):
        if self.tablist.tabs_count == 0:
            t = self.newtab(login_tab)

    def newtab(self, tabtype: Type[T]) -> T:
        return self.tablist.newtab(tabtype)

    def new_chat_tab(self) -> chat_tab:
        return self.tablist.new_chat_tab()

    def prepare(self):
        self.screen_buffer = self.displayer.gen_buffer()

    def update_screen(self):
        utils.clear_screen()
        self.prepare()
        self.tablist.draw_on(self.screen_buffer)
        curtab = self.tablist.cur
        if curtab:
            curtab.draw_on(self.screen_buffer)

        self.displayer.render(self.screen_buffer)

    def on_input(self, char):
        curtab = self.tablist.cur
        if curtab:
            curtab.on_input(char)

    def add_string(self, string: str):
        curtab = self.tablist.cur
        if curtab:
            curtab.add_string(string)


class context:
    pass


def gen_cmd_error_text(cmd_name: str, args: List[str], full_cmd: str, pos: int, msg: str,
                       is_quoted: bool = False) -> str:
    argslen = len(args) + 1
    with StringIO() as s:
        s.write(full_cmd)
        s.write('\n')
        if pos == -1:
            s.write(' ')
            for _ in range(len(cmd_name)):
                s.write('^')
            for arg in args:
                for _ in range(len(arg) + 1):
                    s.write(' ')
            s.write('\n')
        elif pos >= 0:
            for _ in range(len(cmd_name) + 2):
                s.write(' ')
            for i, arg in enumerate(args):
                if i == pos:
                    if is_quoted:
                        s.write(' ')
                    for _ in range(len(arg)):
                        s.write('^')
                else:
                    for _ in range(len(arg)):
                        s.write(' ')
                if i < argslen:
                    s.write(' ')
            s.write('\n')
        s.write(msg)
        return s.getvalue()


class _cmd_state(ui.states.state):
    mode: "cmd_mode"
    sm: "_cmd_smachine"

    def __init__(self, mode: "cmd_mode"):
        self.mode = mode

    def on_input(self, char: chars.char):
        pass


class _cmd_smachine(ui.states.smachine):
    def on_input(self, char: chars.char):
        if self.cur is not None:
            return self.cur.on_input(char)


class cmd_mode(ui_state):
    def __init__(self):
        super().__init__()
        self.cmd_history: List[str] = []
        self.cmd_history_index = 0
        self.last_cmd_history: Optional[str] = None

        def gen_state(statetype: type) -> _cmd_state:
            if issubclass(statetype, _cmd_state):
                s = statetype(self)
                return s
            else:
                return statetype()

        self.cmd_sm = _cmd_smachine(stype_pre=gen_state, allow_repeated_entry=False)

    @property
    def cmd_history_index(self) -> int:
        return self._cmd_history_index

    @cmd_history_index.setter
    def cmd_history_index(self, value: int):
        if value >= 0:
            self._cmd_history_index = 0
        else:
            value = max(value, -len(self.cmd_history))
            value = min(value, -1)
            self._cmd_history_index = value

    @property
    def cur_cmd_history(self) -> Optional[str]:
        if len(self.cmd_history) == 0 or self.cmd_history_index == 0:
            return None
        else:
            return self.cmd_history[self.cmd_history_index]

    def on_en(self):
        self.cmd_sm.enter(_cmd_hotkey_mode)
        self.client.mark_dirty()
        self.textbox.clear()
        self.cmd_manager: cmdmanager = self.client.cmd_manger

    def draw_on(self, buf: buffer):
        head_text = f"{i18n.trans('modes.command_mode.name')}:"
        if GLOBAL.DEBUG:
            head_text = f"{i18n.trans('modes.command_mode.name')}:{self.cmd_history_index} {self.cmd_sm.cur}"

        tip = utils.fillto(head_text, " ", 40)
        buf.addtext(text=tip, fgcolor=CmdFgColor.White,
                    bkcolor=CmdBkColor.Blue,
                    end='\n')

        if GLOBAL.DEBUG:
            buf.addtext(repr(self.cmd_history))

    @property
    def is_long_cmd_mode(self) -> bool:
        inputs = self.textbox.input_list
        return len(inputs) > 0 and inputs[0] == ':'

    def gen_context(self):
        contxt = context()
        contxt.client = self.client
        contxt.tablist = self.tablist
        contxt.network = self.client.network
        contxt.tab = self.tab
        contxt.cmd_manager = self.cmd_manager
        return contxt

    def _show_cmd_history(self):
        cur_his = self.cur_cmd_history
        if cur_his:
            if cur_his != self.last_cmd_history:
                # display history
                self.textbox.input_list = cur_his
                self.last_cmd_history = cur_his
                self.textbox.end()
        else:
            self.textbox.clear()

    def on_input(self, char: chars.char):
        c = self.client
        tb = self.textbox
        # press quit to clear textbox
        if c.key_quit_text_mode == char:
            self.textbox.clear()
            return

        # browser command using history
        if keys.k_up == char:
            up_or_down = -1
        elif keys.k_down == char:
            up_or_down = -1
        else:
            up_or_down = 0
            self.cmd_history_index = 0
        if up_or_down:
            saved = False
            if self.cmd_history_index == 0 and self.textbox.input_count > 0:
                # save current text
                input_list = self.textbox.input_list
                cur_content = utils.compose(input_list, connector='')
                saved = True
            self.cmd_history_index += up_or_down
            self._show_cmd_history()
            if saved:
                self.cmd_history.append(cur_content)
                self.cmd_history_index -= 1
            return
        # switch mode and input
        self.switch_mode()
        self.cmd_sm.on_input(char)
        self.switch_mode()

    def switch_mode(self):
        if self.is_long_cmd_mode:
            self.cmd_sm.enter(_cmd_long_mode)
        else:
            self.cmd_sm.enter(_cmd_hotkey_mode)


class _cmd_long_mode(_cmd_state):
    def __init__(self, mode: "cmd_mode"):
        super().__init__(mode)
        self.autofilling = False
        self.autofilling_it = None
        self.autofilling_cur = None
        self.autofilling_all = None

    def cmd_long_mode_execute_cmd(self):
        mode = self.mode
        tb = self.mode.textbox
        input_list = tb.input_list
        full_cmd = utils.compose(input_list, connector='')
        cmd_args, quoted_indexes = analyze_cmd_args(full_cmd)
        full_cmd = compose_full_cmd(cmd_args, quoted_indexes)
        args = cmd_args[1:]
        cmd_name = cmd_args[0][1:]
        contxt = mode.gen_context()
        try:
            mode.cmd_manager.execute(contxt, cmd_name, args)
        except WrongUsageError as wu:
            with StringIO() as s:
                s.write(output.tintedtxt(i18n.trans("modes.command_mode.cmd.wrong_usage"), fgcolor=CmdFgColor.Red))
                s.write(':\n')
                pos = wu.position
                is_pos_quoted = is_quoted(pos + 1, quoted_indexes)
                s.write(gen_cmd_error_text(cmd_name, args, full_cmd, pos, wu.msg, is_pos_quoted))
                mode.tab.add_string(s.getvalue())
        except CmdNotFound as cnt:
            error_output = gen_cmd_error_text(
                cmd_name, args, full_cmd, -1,
                i18n.trans("modes.command_mode.cmd.cannot_find", name=cmd_name))
            mode.tab.add_string(error_output)
        except CmdError as ce:
            with StringIO() as s:
                s.write(output.tintedtxt(i18n.trans("modes.command_mode.cmd.cmd_error"), fgcolor=CmdFgColor.Red))
                s.write(':\n')
                s.write(gen_cmd_error_text(cmd_name, args, full_cmd, -2, ce.msg))
                mode.tab.add_string(s.getvalue())
        except Exception as any_e:
            with StringIO() as s:
                s.write(output.tintedtxt(i18n.trans("modes.command_mode.cmd.unknown_error"), fgcolor=CmdFgColor.Red))
                s.write(':\n')
                s.write(gen_cmd_error_text(
                    cmd_name, args, full_cmd, -2,
                    i18n.trans("modes.command_mode.cmd.not_support", name=cmd_name)))
                mode.tab.add_string(s.getvalue())
                if GLOBAL.DEBUG:
                    mode.tab.logger.error(f"{any_e}\n{traceback.format_exc()}")

        mode.cmd_history.append(full_cmd)
        mode.cmd_history_index = 0
        tb.clear()

    def on_input(self, char: chars.char):
        mode = self.mode
        tb = mode.textbox

        # execute command
        if keys.k_enter == char:
            self.cmd_long_mode_execute_cmd()
        # auto filling
        elif chars.c_table == char:
            # TODO:Complete Autofilling
            if mode.autofilling:  # press tab and already entered auto-filling mode
                # to next candidate
                # cur_len = len(self.autofilling_cur)
                # tb.rmtext(cur_len)
                # self.autofilling_it = iter(self.autofilling_all)
                pass
            else:  # press tab but haven't enter auto-filling mode yet
                self.autofilling = True
                cmd_manager: cmdmanager = c.cmd_manager
                inputs = tb.inputs[1:]
                self.autofilling_all = cmd_manager.prompts(inputs)
                if len(all_prompts) == 0:
                    self.autofilling = False
                else:
                    self.autofilling_it = iter(autofilling_all)
                    self.autofilling_cur = next(self.autofilling_it)
                    tb.addtext(self.autofilling_cur)
        else:  # not enter and not tab
            tb.append(char)  # normally,add this char into textbox
            if self.autofilling:  # if already entered auto-filling
                # update candidate list
                self.autofilling_all = cmd_manager.prompts(inputs)
                if len(all_prompts) == 0:
                    self.autofilling = False
                else:
                    self.autofilling_it = iter(autofilling_all)
                    self.autofilling_cur = next(self.autofilling_it)
                    tb.addtext(self.autofilling_cur)
            else:
                pass


class _cmd_hotkey_mode(_cmd_state):
    def __init__(self, mode: "cmd_mode"):
        super().__init__(mode)

    def on_input(self, char: chars.char):
        mode = self.mode
        tb = mode.textbox

        if mode.client.key_enter_text == char:
            mode.sm.enter(text_mode)
        elif chars.c_colon == char:
            tb.append(chars.c_colon)
        else:
            not_consumed = common_hotkey(char, mode.tab, mode.client, mode.tablist)
            if not_consumed:
                pass


class text_mode(ui_state):

    def __init__(self):
        super().__init__()
        kbs = kbinding()
        self.kbs = kbs

        kbs.on_any = lambda c: self.textbox.append(c)
        kbs.bind(keys.k_enter, lambda c: self.tab.send_text())

    def on_en(self):
        self.client.mark_dirty()
        self.textbox.clear()

    def draw_on(self, buf: buffer):
        tip = utils.fillto(f"{i18n.trans('modes.text_mode.name')}:", " ", 40)
        buf.addtext(text=tip, fgcolor=CmdFgColor.White,
                    bkcolor=CmdBkColor.Blue,
                    end='\n')

    def on_input(self, char: chars.char):
        c = self.client
        if c.key_quit_text_mode == char:
            self.sm.enter(cmd_mode)
        elif True:
            self.kbs.trigger(char)