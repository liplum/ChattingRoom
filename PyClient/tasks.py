from collections import deque
from typing import Deque, Callable, Optional

Total = int
Count = int
StepMode = Callable[[Total], Count]


def byPercent(percent: float) -> StepMode:
    def func(total: Total) -> Count:
        return round(percent * total + 0.5)

    return func


def byCount(max_count: int) -> StepMode:
    def func(total: Total) -> Count:
        return max_count if total > max_count else total

    return func


DefaultStepMode = byCount(1)

WhetherHandled = bool


class task_runner:
    def __init__(self, *, step_mode: StepMode = DefaultStepMode, safe_mode: bool = True):
        self.tasks: Deque = deque()
        self._step: StepMode = step_mode
        self.exceptions: Deque[Exception] = deque()
        self.on_catch: Optional[Callable[[Exception], WhetherHandled]] = None
        self._safe_mode = safe_mode

    @property
    def safe_mode(self) -> bool:
        return self._safe_mode

    @safe_mode.setter
    def safe_mode(self, value: bool):
        if self._safe_mode != value:
            self._safe_mode = value

    @property
    def step_mode(self) -> StepMode:
        return self._step

    @step_mode.setter
    def step_mode(self, value: StepMode):
        self._step = value

    def add(self, task: Callable):
        self.tasks.append(task)

    def run_all(self):
        if self.safe_mode:
            tasks = self.tasks
            while len(tasks) > 0:
                task = tasks.popleft()
                try:
                    task()
                except Exception as e:
                    on_catch = self.on_catch
                    if on_catch is None or on_catch(e) is False:
                        self.exceptions.append(e)
        else:
            tasks = self.tasks
            while len(tasks) > 0:
                task = tasks.popleft()
                task()

    def run_step(self):
        if self.safe_mode:
            tasks = self.tasks
            count = self.step_mode(len(tasks))
            while count > 0 and len(tasks) > 0:
                task = self.tasks.popleft()
                try:
                    task()
                except Exception as e:
                    on_catch = self.on_catch
                    if on_catch is None or on_catch(e) is False:
                        self.exceptions.append(e)
                count -= 1
        else:
            tasks = self.tasks
            count = self.step_mode(len(tasks))
            while count > 0 and len(tasks) > 0:
                task = self.tasks.popleft()
                task()
                count -= 1
