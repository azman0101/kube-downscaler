import importlib


class CalendarFactory:
    _provider = None

    def __init__(self, provider: str) -> None:
        self._provider = provider
        super().__init__()

    def create(self):
        if isinstance(self._provider, str):
            module = importlib.import_module('.' + self._provider + 'calendar', package=__package__)
            class_ = getattr(module, self._provider.capitalize() + 'Calendar')
            return class_()
        else:
            return self._provider
