from quarry.types.buffer import Buffer1_7
from quarry.net.proxy import Downstream, Upstream


class Module:
    def __init__(self, name: str, downstream: Downstream, upstream: Upstream, enabled: bool = False):
        self.name: str = name
        self.downstream: Downstream = downstream
        self.upstream: Upstream = upstream
        self.enabled: bool = enabled

    def on_tick(self) -> None:
        pass

    def on_game_event(self, buff: Buffer1_7, event) -> bool:
        pass

    def on_enable(self) -> None:
        pass

    def on_disable(self) -> None:
        pass

    def toggle(self) -> None:
        self.enabled = not self.enabled
        if self.enabled:
            self.on_enable()
        else:
            self.on_disable()


class NoWeather(Module):
    def __init__(self, downstream: Downstream, upstream: Upstream, enabled: bool = False) -> None:
        super().__init__("NoWeather", downstream, upstream, enabled)  # TODO: Fix super call

    def on_game_event(self, buff: Buffer1_7, event) -> bool:
        return event == 2  # Cancel packet if event is to start raining


class Xray(Module):
    def __init__(self, downstream: Downstream, upstream: Upstream, enabled: bool = False) -> None:
        super().__init__("Xray", downstream, upstream, enabled)

    def on_enable(self) -> None:
        self.downstream.send_packet(
            "plugin_message",
            b'\x0elunarclient:pm\x0c\x04XRAY\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')


class Packet:
    def __init__(self, type: str, data: bytes, direction):
        self.type = type
        self.data = data
        self.direction = direction


class Blink(Module):
    def __init__(self, downstream: Downstream, upstream: Upstream, enabled: bool = False) -> None:
        super().__init__("Blink", downstream, upstream, enabled)
        self.packet_list: list = []

    def on_enable(self) -> None:
        self.packet_list: list[Packet] = []

    def on_disable(self) -> None:
        for packet in self.packet_list:
            print(packet.type)
            if "down" in packet.direction:
                self.downstream.send_packet(packet.type, packet.data)
            elif "up" in packet.direction:
                self.upstream.send_packet(packet.type, packet.data)