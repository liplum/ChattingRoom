from datetime import datetime
from threading import RLock
from typing import Tuple, List, Dict, Optional

import utils
from Events import Event
from core.filer import ifiler, sep, Directory, File
from core.shared import server_token, userid, roomid, StorageUnit
from ui.outputs import ilogger
from utils import compose, separate


class chatting_room:
    def __init__(self, _id: roomid):
        self.id = _id
        self._history = msgstorage(File(f"records{sep}{self.id}.rec"))

    @property
    def history(self) -> "msgstorage":
        return self._history


class msgstorage:
    def __init__(self, save_file: File = None):
        self._save_file: File = save_file
        self.__storage: List[StorageUnit] = []
        self._on_stored = Event(msgstorage, tuple)
        self.changed = False

    def store(self, msg_unit: StorageUnit):
        self.__storage.append(msg_unit)
        self.changed = True

    @property
    def on_stored(self) -> Event:
        """
        Para 1:msgstorage object

        Para 2:storage unit

        :return: Event(msgstorage,StorageUnit)
        """
        return self._on_stored

    def sort(self):
        if self.changed:
            self.__storage.sort(key=lambda i: i[0])
            self.changed = False

    def __iter__(self) -> [StorageUnit]:
        return iter(self.__storage[:])

    @property
    def save_file(self) -> File:
        return self._save_file

    @save_file.setter
    def save_file(self, value: File):
        self._save_file = value
        if not value.IsExisted:
            value.CreateOrTruncate()

    def serialize(self):
        if not self._save_file:
            raise ValueError("You should provide a save file path first.")
        self.sort()
        with open(self._save_file.FullPath, "w", encoding="utf-16") as save:
            for unit in self.__storage:
                unit_str = (str(unit[0]), str(unit[1]), unit[2])
                saved_line = compose(unit_str, '|', end='\n')
                save.write(saved_line)

    def deserialize(self):
        if not self._save_file:
            raise ValueError("You should provide a save file path first.")
        self.__storage = []
        with open(self._save_file.FullPath, "r", encoding="utf-16") as save:
            lines = save.readlines()
            for line in lines:
                line = line.rstrip()
                items = separate(line, '|', 2, allow_emptychar=True)
                if len(items) == 3:
                    time, uid, content = items
                    try:
                        time = datetime.fromisoformat(time)
                        uid = userid(uid)
                        self.__storage.append((time, uid, content))
                    except:
                        continue
                else:
                    continue
        self.sort()

    def retrieve(self, start: datetime, end: datetime, number_limit: Optional[int] = None,
                 reverse: bool = False) -> List[StorageUnit]:
        """

        :param start:the beginning time of message retrieval.
        :param end:the ending time of message retrieval.
        :param number_limit:the max number of message retrieval.If None,retrieves all.
        :param reverse:If true,retrieves msg starting from end datetime.Otherwise starting from start datetime.
        :return:
        """
        if len(self.__storage) == 0:
            return []

        start = min(start, end)
        end = max(start, end)

        snapshot = self.__storage[:]
        dt_snapshot = [unit[0] for unit in snapshot]
        _, start_pos = utils.find_range(dt_snapshot, start)
        end_pos, _ = utils.find_range(dt_snapshot, end)

        order = -1 if reverse else 1
        if number_limit:
            if number_limit >= len(snapshot):
                if reverse:
                    return snapshot[::order]
                else:
                    return snapshot
            return inrange[start_pos:end_pos + 1 - number_limit:order]
        else:
            return snapshot[start_pos:end_pos + 1:order]

    def retrieve_lasted(self, number_limit: int) -> List[StorageUnit]:
        """

        :param number_limit:the max number of message retrieval.
        :return:
        """
        if len(self.__storage) == 0:
            return []

        snapshot = self.__storage[:]
        if number_limit >= len(snapshot):
            return snapshot
        return snapshot[-number_limit:]

    def retrieve_until(self, end: datetime, number_limit: Optional[int] = None) -> List[StorageUnit]:
        if len(self.__storage) == 0:
            return []

        snapshot = self.__storage[:]
        dt_snapshot = [unit[0] for unit in snapshot]
        end_pos, _ = utils.find_range(dt_snapshot, end)
        if number_limit:
            if number_limit >= len(snapshot):
                return snapshot[:end_pos + 1]
            else:
                start_pos = max(end_pos - number_limit, 0)
                return snapshot[start_pos:end_pos + 1]
        else:
            return snapshot[:end_pos + 1]


class imsgmager:

    def __init__(self) -> None:
        super().__init__()
        self._on_received = Event(imsgmager, server_token, roomid, tuple)

    def load_lasted(self, server: server_token, room_id: roomid,
                    amount: int) -> List[StorageUnit]:
        pass

    def retrieve(self, server: server_token, room_id: roomid, amount: int, start: datetime,
                 end: datetime) -> List[StorageUnit]:
        pass

    def receive(self, server: server_token, room_id: roomid, msg_unit: StorageUnit):
        pass

    def load_until_today(self, server: server_token, room_id: roomid,
                         number_limit: Optional[int] = None) -> List[StorageUnit]:
        pass

    def save_all(self):
        pass

    @property
    def on_received(self) -> Event:
        """
        Para 1:imsgmager object

        Para 2:server

        Para 3:room id

        Para 4:storage unit

        :return: Event(imsgmager,server_token,roomid,StorageUnit)
        """
        return self._on_received


class imsgfiler:
    def save(self, server: server_token, room_id: roomid, storage: msgstorage):
        pass

    def get(self, server: server_token, room_id: roomid) -> File:
        pass


class msgfiler(imsgfiler):

    def init(self, container):
        self.logger: ilogger = container.resolve(ilogger)
        self.filer: ifiler = container.resolve(ifiler)
        self.data_folder: Directory = self.filer.get_dir("data")

    def __init__(self):
        pass

    def save(self, server: server_token, room_id: roomid, storage: msgstorage):
        try:
            file = self.data_folder.SubFile(f"{server.ip}-{server.port}{sep}{room_id}.rec")
            storage.save_file = file
            storage.serialize()
        except:
            self.logger.error(f'[MsgFiler]Cannot save msg into "{storage.save_file}"')

    def get(self, server: server_token, room_id: roomid) -> File:
        return self.data_folder.SubFile(f"{server.ip}-{server.port}{sep}{room_id}.rec")


class msgmager(imsgmager):
    def __init__(self):
        super().__init__()
        self.cache: Dict[Tuple[server_token, roomid], msgstorage] = {}
        self._lock = RLock()

    def init(self, container):
        self.filer: imsgfiler = container.resolve(imsgfiler)
        self.logger: ilogger = container.resolve(ilogger)

    def get_storage(self, server: server_token, room_id: roomid) -> Optional[msgstorage]:
        if (server, room_id) in self.cache:
            return self.cache[server, room_id]
        else:
            msgs_file = self.filer.get(server, room_id)
            if msgs_file:
                storage = msgstorage(msgs_file)
                storage.deserialize()
                self.cache[server, room_id] = storage
                return storage
            else:
                return None

    def load_lasted(self, server: server_token, room_id: roomid, amount: int) -> List[StorageUnit]:
        with self._lock:
            storage = self.get_storage(server, room_id)
            if storage:
                return storage.retrieve_lasted(amount)
            else:
                self.logger.error(f"[MsgManager]Cannot load msg storage from {room_id}")

    def retrieve(self, server: server_token, room_id: roomid, amount: int, start: datetime,
                 end: datetime) -> List[StorageUnit]:
        with self._lock:
            storage = self.get_storage(server, room_id)
            if storage:
                return storage.retrieve(start=start, end=end, number_limit=amount)
            else:
                self.logger.error(f"[MsgManager]Cannot load msg storage from {room_id}")

    def receive(self, server: server_token, room_id: roomid, msg_unit: StorageUnit):
        with self._lock:
            if (server, room_id) in self.cache:
                storage = self.cache[server, room_id]
            else:
                msgs_file = self.filer.get(server, room_id)
                storage = msgstorage(msgs_file)
                self.cache[server, room_id] = storage
            storage.store(msg_unit)
        self.on_received(self, server, room_id, msg_unit)

    def load_until_today(self, server: server_token, room_id: roomid,
                         number_limit: Optional[int] = None) -> List[StorageUnit]:
        with self._lock:
            storage = self.get_storage(server, room_id)
            if storage:
                return storage.retrieve_until(end=datetime.now(), number_limit=number_limit)
            else:
                self.logger.error(f"[MsgManager]Cannot load msg storage from {room_id}")

    def save_all(self):
        for strg in self.cache.values():
            strg.serialize()
