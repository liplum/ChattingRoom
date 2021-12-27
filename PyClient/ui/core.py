from abc import abstractmethod, ABC
from typing import Callable
from typing import Union, Type, Any, Optional

from cmds import cmdmanager
from ioc import container
from ui.k import cmdkey
from ui.shared import *


class iclient(ABC):
    def __init__(self):
        self._on_service_register = Event(iclient, container)
        self._on_cmd_register = Event(iclient, cmdmanager)
        self._on_keymapping = Event(iclient, cmdkey)

    @property
    @abstractmethod
    def win(self) -> "iwindow":
        raise NotImplementedError()

    @property
    def on_service_register(self) -> Event:
        """
        Para 1:client object


        Para 2:container

        :return: Event(iclient,container)
        """
        return self._on_service_register

    @property
    def on_cmd_register(self) -> Event:
        """
        Para 1:the manager of cmd

        :return: Event(iclient,cmdmanager)
        """
        return self._on_cmd_register

    @property
    def on_keymapping(self) -> Event:
        """
        Para 1: client object


        Para 1: key map

        :return: Event(iclient,cmdkey)
        """
        return self._on_keymapping

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def connect(self, ip: str, port: int):
        pass

    @abstractmethod
    def mark_dirty(self):
        pass

    @abstractmethod
    def init(self) -> None:
        pass

    @abstractmethod
    def add_task(self, task: Callable):
        pass

    @property
    @abstractmethod
    def container(self) -> "container":
        raise NotImplementedError()

    @property
    @abstractmethod
    def network(self) -> "inetwork":
        raise NotImplementedError()

    @property
    @abstractmethod
    def logger(self) -> "ilogger":
        raise NotImplementedError()

    @property
    @abstractmethod
    def displayer(self) -> "idisplay":
        raise NotImplementedError()

    @property
    @abstractmethod
    def msg_manager(self) -> "imsgmager":
        raise NotImplementedError()


class iwindow(inputable, reloadable):
    def __init__(self, client: iclient):
        self.client = client
        self.displayer = self.client.displayer

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def newtab(self, tabtype: Union[Type[T], str, Any]) -> T:
        pass

    @abstractmethod
    def new_chat_tab(self) -> "chat_tab":
        pass

    @abstractmethod
    def update_screen(self):
        pass

    @abstractmethod
    def gen_default_tab(self):
        pass

    @property
    @abstractmethod
    def accept_input(self) -> bool:
        pass

    @abstractmethod
    def retrieve_popup(self, popup: "base_popup") -> Optional[Any]:
        pass

    @property
    @abstractmethod
    def tablist(self) -> "tablist":
        pass

    def add_string(self, string: str):
        pass

    @abstractmethod
    def find_first_popup(self, predicate: Callable[["base_popup"], bool]) -> Optional["base_popup"]:
        pass

    @abstractmethod
    def run_coroutine(self):
        pass
