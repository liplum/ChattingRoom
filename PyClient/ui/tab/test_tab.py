import ui.panel.Stacks
from ui.control.xtbox import xtextbox
from ui.panel.Stacks import Stack
from ui.tab.shared import *
from ui.tabs import *


class test_tab(Tab):

    def __init__(self, client: "client", tablist: Tablist):
        super().__init__(client, tablist)
        self.stack = Stack()
        button_content = "Button"

        def button_content_getter() -> str:
            return button_content

        def _click_button():
            nonlocal button_content
            button_content = "Clicked"
            self.client.mark_dirty()

        self.stack.on_content_changed.Add(lambda _: self.on_content_changed(self))
        self.stack.add(Button(CGT(button_content_getter), _click_button))
        self.stack.add(Label("Label A"))
        self.account_tbox = xtextbox()
        self.account_tbox.space_placeholder = "_"
        account_stack = Stack()
        account_stack.add(Label("Account"))
        account_stack.add(self.account_tbox)
        account_stack.Orientation = ui.panel.Stacks.horizontal
        self.stack.add(account_stack)
        self.stack.add(Label("Test Label B"))
        self.stack.add(Label("Test"))
        self.input_box = xtextbox()
        self.input_box.space_placeholder = "_"
        self.stack.add(self.input_box)

        self.button = Button(CGT(button_content_getter), _click_button)
        self.button.margin = 2
        self.stack.add(self.button)
        self.stack.add(Button(CGT(button_content_getter), _click_button))
        self.stack.add(Button(CGT(button_content_getter), _click_button))
        self.stack.add(Button("Close", lambda: self.client.stop()))
        # self.Stack.Orientation = panels.Horizontal

        self.stack.elemt_interval = 1
        self._stack_focused = True

        def _on_stack_exit_focus(stak):
            self._stack_focused = False

        self.stack.on_exit_focus.Add(_on_stack_exit_focus)
        self.stack.switch_to_first_or_default_item()
        self.stack.left_margin = 10

    def paint_on(self, buf: buffer):
        self.stack.paint_on(buf)
        if GLOBAL.DEBUG:
            stak = self.stack
            c = stak.cur_focused
            info = f"focused index= {stak.cur_focused_index}\nfocused Control= {c}\n"
            buf.addtext(info)
            if c:
                pass

    @property
    def title(self) -> str:
        return "Test"

    def on_input(self, char: chars.char) -> Generator:
        consumed = self.stack.on_input(char)
        if not consumed:
            if keys.k_down == char:
                self.stack.switch_to_first_or_default_item()
        yield Finished
