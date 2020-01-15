import importlib


class CalendarFactory:
    _provider = None

    def __init__(self, provider: str) -> None:
        self._provider = provider
        super().__init__()

    def create(self):
        module = importlib.import_module(self._provider + 'calendar')

        class_ = getattr(module, self._provider.capitalize() + 'Calendar')

        return class_