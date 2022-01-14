from collections import defaultdict
from enum import Enum
from typing import Callable, Dict, Optional, NoReturn, Any, List, Type, Union

from Events import Event


class DpKey:
    def __init__(self, name: str, ownerType: type):
        self._name = name
        self._ownerType = ownerType
        self._hashCode = hash(name) ^ hash(ownerType)

    def __hash__(self) -> int:
        return self._hashCode

    def __eq__(self, o: object) -> bool:
        return isinstance(o, DpKey) and self._name == o._name and self._ownerType == o._ownerType


ValidateValueCallbackType = Callable[[Any], bool]
CoerceValueCallbackType = Callable[[Any, Any], Any]
PropChangedCallbackType = Callable[[Any, Any], NoReturn]


class DpPropMeta:
    def __init__(self, defaultValue: Union[Any, Callable[[], Any]],
                 allowSameValue=True,
                 validateValueCallback: Optional[ValidateValueCallbackType] = None,
                 propChangedCallback: Optional[PropChangedCallbackType] = None,
                 coerceValueCallback: Optional[CoerceValueCallbackType] = None):
        super().__init__()
        if isinstance(defaultValue, Callable):
            self._defaultValueGetter: Callable[[], Any] = defaultValue
        elif isinstance(defaultValue, type):
            self._defaultValueGetter: Callable[[], Any] = defaultValue
        else:
            self._defaultValueGetter: Callable[[], Any] = lambda: defaultValue
        self._allowSameValue = allowSameValue
        self._validateValueFunc: Optional[ValidateValueCallbackType] = validateValueCallback
        self._propChangedCallback: Optional[PropChangedCallbackType] = propChangedCallback
        self._coerceValueCallback: Optional[CoerceValueCallbackType] = coerceValueCallback

    @property
    def DefaultValueGetter(self) -> Callable[[], Any]:
        return self._defaultValueGetter

    @property
    def AllowSameValue(self):
        return self._allowSameValue

    @property
    def ValidateValueCallback(self) -> Optional[ValidateValueCallbackType]:
        return self._validateValueFunc

    @property
    def PropChangedCallback(self) -> Optional[PropChangedCallbackType]:
        return self._propChangedCallback

    @property
    def CoerceValueCallback(self) -> Optional[CoerceValueCallbackType]:
        return self._coerceValueCallback


class DpProp:
    _PropertyFromName: Dict[DpKey, "DpProp"] = {}

    @classmethod
    def Register(cls, name: str, propType: type,
                 ownerType: Type["DpObj"], meta: DpPropMeta) -> "DpProp":
        key = DpKey(name, ownerType)
        if key in cls._PropertyFromName:
            raise ExistedDpKeyError(f"{name} and {ownerType} already exist", name, ownerType)

        dp = DpProp(name, propType, ownerType, meta)
        cls._PropertyFromName[key] = dp
        return dp

    @classmethod
    def RegisterAttach(cls):
        pass

    def __init__(self, name: str, propType: type,
                 ownerType: Type["DpObj"], meta: DpPropMeta):
        """
        Private Constructor
        """
        super().__init__()
        self._name = name
        self._propType = propType
        self._ownerType: Type["DpObj"] = ownerType
        self._meta = meta

    @property
    def OwnerType(self) -> Type["DpObj"]:
        return self._ownerType

    @property
    def Meta(self) -> DpPropMeta:
        return self._meta


EventHandlerType = Callable[["DpObj", "RoutedEventArgs"], NoReturn]
EventHandlerMap = Dict["RoutedEventType", List[EventHandlerType]]


def _GenDpPropDefaultValue(prop: DpProp) -> Optional[object]:
    meta = prop.Meta
    return meta.DefaultValueGetter()


class DpObj:
    def __init__(self):
        super().__init__()
        self.DpPropValueEntries: Dict[DpProp, Optional[object]] = {}
        self._onDpPropChanged = Event(DpObj, DpProp, object, object)
        self._eventHandlers: EventHandlerMap = defaultdict(list)

    def Subscribe(self, eventType: "RoutedEventType", handler: EventHandlerType):
        handlers = self.EventHandlers[eventType]
        handlers.append(handler)

    def RemoveEventHandler(self, eventType: "RoutedEventType", handler: EventHandlerType) -> bool:
        handlers = self.EventHandlers[eventType]
        try:
            handlers.remove(handler)
            return True
        except:
            return False

    def ClearEventHandler(self, eventType: "RoutedEventType"):
        self.EventHandlers[eventType] = []

    @property
    def EventHandlers(self):
        return self._eventHandlers

    def SetValue(self, prop: DpProp, value):
        if not isinstance(self, prop.OwnerType):
            raise NotHasDependencyPropertyError(self, prop)
        meta = prop.Meta
        coerce = meta.CoerceValueCallback
        if coerce:
            value = coerce(self, value)
        validate = meta.ValidateValueCallback
        if meta.AllowSameValue or self.GetValue(prop) != value:
            if validate is None or validate(value):
                self.DpPropValueEntries[prop] = value
                callback = meta.PropChangedCallback
                if callback:
                    callback(self, value)

    def GetValue(self, prop: DpProp):
        if not isinstance(self, prop.OwnerType):
            raise NotHasDependencyPropertyError(self, prop)
        if prop in self.DpPropValueEntries:
            value = self.DpPropValueEntries[prop]
        else:
            value = _GenDpPropDefaultValue(prop)
            self.DpPropValueEntries[prop] = value
        return value

    def TryCatchEvent(self, eventType: "RoutedEventType", sender: "DpObj", args: "RoutedEventArgs"):
        handlers = self.EventHandlers[eventType]
        for handler in handlers:
            if args.Cancelable and args.IsHandled:
                break
            handler(sender, args)


class NotHasDependencyPropertyError(Exception):
    def __init__(self, *args: object):
        super().__init__(*args)


class ExistedDpKeyError(Exception):
    def __init__(self, *args: object):
        super().__init__(*args)


class RoutedStrategy(Enum):
    Bubble = 1
    Tunnel = 2
    Direct = 3


class RoutedEventType:
    _EventFromName: Dict[DpKey, "RoutedEventType"] = {}

    def __init__(self, name: str, ownerType: type
                 , argsType: Type["RoutedEventArgs"], strategy: RoutedStrategy):
        super().__init__()
        self._name = name
        self._ownerType = ownerType
        self._argsType: Type["RoutedEventArgs"] = argsType
        self._strategy = strategy

    @classmethod
    def Register(cls, name: str, ownerType: type
                 , argsType: Type["RoutedEventArgs"], strategy: RoutedStrategy) -> "RoutedEventType":
        key = DpKey(name, ownerType)
        if key in cls._EventFromName:
            raise ExistedDpKeyError(f"{name} and {ownerType} already exist", name, ownerType)
        e = RoutedEventType(name, ownerType, argsType, strategy)
        cls._EventFromName[key] = e
        return e

    @property
    def ArgsType(self) -> Type["RoutedEventArgs"]:
        return self._argsType

    @property
    def Strategy(self):
        return self._strategy


class RoutedEventArgs:
    def __init__(self, cancelable=True):
        super().__init__()
        self.IsHandled = False
        self.__cancelable = cancelable

    @property
    def Cancelable(self):
        return self.__cancelable


class EventTypeError(Exception):
    def __init__(self, *args: object):
        super().__init__(*args)