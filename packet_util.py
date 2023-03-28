from dataclasses import dataclass


@dataclass
class PlayerLook:
    pitch: float
    yaw: float
    on_ground: bool


@dataclass
class PlayerPosition:
    x: float
    y: float
    z: float
    on_ground: bool


@dataclass
class PlayerPositionLook:
    x: float
    y: float
    z: float
    pitch: float
    yaw: float
    on_ground: bool
