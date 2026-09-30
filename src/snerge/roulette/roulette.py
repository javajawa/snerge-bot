from dataclasses import dataclass


@dataclass
class RouletteGame:
    id: str
    label: str
    aliases: list[str]

@dataclass
class RouletteGameWeight:
    roulette_game_id: str
    weight: int

@dataclass
class ChatEvent:
    chatter_user_id: str
    chatter_user_name: str
    message: str
    total_weight: int
    game_weights: list[RouletteGameWeight]