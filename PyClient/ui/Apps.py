import traceback
from collections import deque
from typing import Deque

from core.settings import entity as settings
from ui.coroutines import Suspend
from ui.tab.chat import chat_tab
from ui.tab.main_menu import main_menu_tab
from ui.tabs import *
from utils import get

Focusable = Union[base_popup, Tab]
CallStackItem = Tuple[Generator, Focusable]

NeedRemoveCurFrame = bool


class Frame:

    def __init__(self, t: Tab, co: Optional[Generator]):
        self.tab: Tab = t
        self.coroutine: Optional[Generator] = co

    def __repr__(self):
        return f"{self.tab}:{'Coroutine' if self.coroutine else None}"

    def __iter__(self):
        return iter((self.tab, self.coroutine))


class App(IApp):

    def __init__(self, client: IClient):
        super().__init__(client)
        self.logger: "ilogger" = self.client.logger
        self.network: "inetwork" = self.client.network
        self._tablist: Tablist = Tablist()
        self.screen_buffer: Optional[buffer] = None
        self.tablist.on_content_changed.Add(lambda _: self.client.mark_dirty())
        self.tablist.on_tablist_changed.Add(lambda li, mode, t: self.client.mark_dirty())
        self.popup_return_values: Dict[base_popup, Any] = {}
        self.call_stack: Deque[Frame] = deque()

        def on_curtab_changed(tablist, index, curtab):
            if curtab is None:
                self.call_stack = deque()
            else:
                new_frame = Frame(curtab, None)
                if len(self.call_stack) == 0:
                    self.call_stack = deque((new_frame,))
                else:
                    self.call_stack[0] = new_frame
                self.client.mark_dirty()

        self.tablist.on_curtab_changed.Add(on_curtab_changed)

    @property
    def cur_frame(self) -> Optional[Frame]:
        if len(self.call_stack) > 0:
            return self.call_stack[-1]
        return None

    @property
    def accept_input(self) -> bool:
        return (frame := self.cur_frame) and frame.coroutine is None

    def start(self):
        configs = settings()
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
                        except CannotRestoreTab:
                            continue
                        except Exception as e:
                            self.client.logger.warn(f"[App]{e}\n{traceback.format_exc()}")
                            continue
                        if tab is not None:
                            self.tablist.add(tab)
        self.tablist.unite_like_tabs()

    def store_unclosed_tabs(self):
        self.tablist.unite_like_tabs()
        configs = settings()
        last_opened: Dict[str, List[dict]] = defaultdict(list)
        for tab in self.tablist.tabs:
            tabtype = type(tab)
            if tabtype in tab_type2name:
                if tabtype.serializable():
                    li = last_opened[tab_type2name[tabtype]]
                    try:
                        dic = tabtype.serialize(tab)
                    except CannotStoreTab:
                        continue
                    except Exception as e:
                        self.client.logger.warn(f"[App]{e}\n{traceback.format_exc()}")
                        continue
                    if dic is not None:
                        li.append(dic)
        configs.LastOpenedTabs = last_opened

    def gen_default_tab(self):
        if self.tablist.tabs_count == 0:
            t = self.newtab(main_menu_tab)
            self.tablist.add(t)

    def newtab(self, tabtype: Union[Type[T], str, Any]) -> T:
        if isinstance(tabtype, str):
            ttype = get(tab_name2type, tabtype)
            if ttype:
                t = ttype(self.client, self.tablist)
            else:
                raise TabTypeNotFound(tab_name=tabtype)
        elif isinstance(tabtype, type):
            t = tabtype(self.client, self.tablist)
        else:
            raise TypeError(tabtype, type(tabtype))
        return t

    def new_chat_tab(self) -> chat_tab:
        return self.newtab(chat_tab)

    def prepare(self):
        self.screen_buffer = self.displayer.gen_buffer()

    def render_debug_info(self, buf):
        if GLOBAL.DEBUG:
            buf.addtext(str(self.tablist.tabs))
            buf.addtext(f"Focused={self.tablist.cur}")

    def OnTick(self):
        pass

    def update_screen(self):
        self.prepare()
        self.tablist.paint_on(self.screen_buffer)
        cur_painter = self.cur_painter
        if cur_painter:
            cur_painter.paint_on(self.screen_buffer)
        self.render_debug_info(self.screen_buffer)
        utils.clear_screen()
        self.displayer.render(self.screen_buffer)

    def run_coroutine(self):
        if len(self.call_stack) > 0:
            frame = self.call_stack[-1]
            if frame.coroutine:
                need_remove = self.step(frame)
                if need_remove:
                    len(self.call_stack)
                    if len(self.call_stack) == 1:
                        frame.coroutine = None
                    elif len(self.call_stack) > 1:
                        self.call_stack.pop()

    def step(self, frame: Frame) -> NeedRemoveCurFrame:
        t = frame.tab
        co = frame.coroutine
        while True:
            try:
                rv = next(co)
            except StopIteration:
                return True
            except Exception as e:
                raise e
            if rv == Suspend:
                return False
            elif rv == Finished:
                return True
            elif isinstance(rv, base_popup):
                self.call_stack.append(Frame(rv, None))
                rv.on_content_changed.Add(lambda _: self.client.mark_dirty())
                rv.on_returned.Add(self._on_popup_returned)
                rv.on_added()
                return False
            elif isinstance(rv, Generator):
                self.call_stack.append(Frame(t, rv))
                return False
            else:
                return self.step(frame)

    def on_input(self, char):
        frame = self.cur_frame
        if frame:
            co = frame.tab.on_input(char)
            frame.coroutine = co

    def _on_popup_returned(self, popup: base_popup):
        self.popup_return_values[popup] = popup.return_value
        popup.on_lost_focus()
        popup.on_removed()
        if popup.need_refresh_instant:
            self.call_stack.pop()
        else:
            self.client.mark_dirty()

    @property
    def cur_painter(self) -> Optional[painter]:
        frame = self.cur_frame
        if frame:
            return frame.tab
        return None

    def add_string(self, string: str):
        curtab = self.tablist.cur
        if curtab:
            curtab.add_string(string)

    def reload(self):
        for t in self.tablist:
            t.reload()
        self.client.mark_dirty()

    def retrieve_popup(self, popup: "base_popup") -> Optional[Any]:
        if popup in self.popup_return_values:
            value = self.popup_return_values[popup]
            del self.popup_return_values[popup]
            return value
        else:
            return None

    @property
    def tablist(self) -> "Tablist":
        return self._tablist

    def find_first_popup(self, predicate: Callable[["base_popup"], bool]) -> Optional["base_popup"]:
        for t, co in self.call_stack:
            if isinstance(t, base_popup):
                try:
                    if predicate(t):
                        return t
                except:
                    pass
        return None
