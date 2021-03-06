import io
import sys

import GLOBAL
import utils
from debugs import FakeStringIO
from utils import get_at

TestLOGO = (
    "████████╗███████╗███████╗████████╗",
    "╚══██╔══╝██╔════╝██╔════╝╚══██╔══╝",
    "   ██║   █████╗  ███████╗   ██║   ",
    "   ██║   ██╔══╝  ╚════██║   ██║   ",
    "   ██║   ███████╗███████║   ██║   ",
    "   ╚═╝   ╚══════╝╚══════╝   ╚═╝   ",
)

GLOBAL.LOGO = TestLOGO
GLOBAL.StringIO = io.StringIO
IDE = False
args = sys.argv
finalarg: str = arg if (arg := get_at(args, -1)) is not None else ""
extra = []


def match_arg(para: str):
    matched = finalarg.startswith(para)
    if matched:
        global extra
        extra = finalarg.replace(para, "")
    return matched


if match_arg("-debug"):
    GLOBAL.DEBUG = True
elif match_arg("-ide"):
    GLOBAL.DEBUG = True
    IDE = True
elif match_arg(""):
    pass

GLOBAL.USE_NEW_RENDER = True

if "M" in extra:
    GLOBAL.MONITOR = True
if "S" in extra:
    GLOBAL.StringIO = FakeStringIO

if IDE:
    utils.clear_screen = lambda: None

import platform

system_type = platform.system()


def detect_debug_attach():
    input("Attach the process and enter any text to start:")


import i18n

i18n.load("en_us")


def main():
    if GLOBAL.DEBUG:
        detect_debug_attach()
    from Test.Clients import TestClient
    _client = TestClient()
    _client.on_service_register.Add(init_plugin)
    _client.init()
    if GLOBAL.MONITOR:
        from pef.monitor import pef_monitor
        _client.container.resolve(pef_monitor)
    _client.start()


from ioc import container


def init_plugin(client, registry: container):
    from ui.inputs import iinput
    from ui.Renders import IRender
    if IDE:
        from ui.cmds.cmdprompt import cmd_input
        registry.register_singleton(iinput, cmd_input)
        from ui.cmds.Renders import CmdRender
        registry.register_singleton(IRender, CmdRender)
    else:
        if system_type == "Windows":
            from ui.wins import nonblocks
            from ui.wins.Renders import WinRender
            registry.register_singleton(iinput, nonblocks.nbinput)
            registry.register_singleton(IRender, WinRender)
        elif system_type == "Linux":
            from ui.linuxs.nonblocks import nbinput
            from ui.linuxs.Renders import LinuxColoredRender
            registry.register_singleton(iinput, nbinput)
            registry.register_singleton(IRender, LinuxColoredRender)
        else:
            from ui.cmds.cmdprompt import cmd_input
            from ui.cmds.Renders import CmdRender
            registry.register_singleton(iinput, cmd_input)
            registry.register_singleton(IRender, CmdRender)

    if GLOBAL.MONITOR:
        from pef.monitor import pef_monitor
        registry.register_instance(pef_monitor, pef_monitor(interval=0.5))


if __name__ == '__main__':
    main()
