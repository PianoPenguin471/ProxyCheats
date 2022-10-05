from dataclasses import dataclass
from quarry.types.buffer import Buffer1_7

@dataclass
class Module:
    name: str
    enabled: bool = False
    def on_tick(self) ->None:
        pass
    def on_game_event(self, buff: Buffer1_7, event) -> bool:
        pass
    def on_downstream_plugin_message(self, buff: Buffer1_7, channel) -> bool:
        pass

@dataclass
class NoWeather(Module):
    def __init__(self) -> None:
        super().__init__("NoWeather")# TODO: Fix super call
    def on_game_event(self, buff: Buffer1_7, event) -> bool:
        return event == 2 # Cancel packet if event is to start raining

@dataclass
class Xray(Module):
    def __init__(self) -> None:
        super().__init__("Xray")
    def on_downstream_plugin_message(self, buff: Buffer1_7, channel) -> bool:
        print(channel)
        return False