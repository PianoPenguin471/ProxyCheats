from dataclasses import dataclass
from uuid import UUID
import uuid
from quarry.types.buffer import Buffer1_7
from quarry.net.proxy import Downstream, Upstream

from packet_util import PlayerPosition, PlayerPositionLook, PlayerLook


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
        Module.downstream.send_packet(
            "plugin_message",
            b'\x0elunarclient:pm\x0c\x04XRAY\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')


class No_Fall(Module):
    def __init__(self, downstream: Downstream, upstream: Upstream, enabled: bool = False) -> None:
        super().__init__("NoFall", downstream, upstream, enabled)


class Blink(Module):
    def __init__(self, downstream: Downstream, upstream: Upstream, enabled: bool = False) -> None:
        super().__init__("Blink", downstream, upstream, enabled)
        self.packet_list: list = []

    def on_enable(self) -> None:
        self.packet_list: list = []

    def on_disable(self) -> None:
        for packet in self.packet_list:
            if isinstance(packet, PlayerPosition):
                Module.upstream.send_packet("player_position", Buffer1_7.pack("ddd?", packet.x, packet.y, packet.z, packet.on_ground))
            elif isinstance(packet, PlayerPositionLook):
                Module.upstream.send_packet("player_position_look", Buffer1_7.pack("dddff?", packet.x, packet.y, packet.z, packet.pitch, packet.yaw, packet.on_ground))
            elif isinstance(packet, PlayerLook):
                Module.upstream.send_packet("player_look", Buffer1_7.pack("ff?", packet.pitch, packet.yaw, packet.on_ground))

class Scaffold(Module):
    def __init__(self, downstream: Downstream, upstream: Upstream, enabled: bool = False) -> None:
        super().__init__("Scaffold", downstream, upstream, enabled)

    def on_tick(self) -> None:
        Module.upstream.send_packet()
