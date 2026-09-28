# SPDX-FileCopyrightText: 2026 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
#
# SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations as _future_annotations

from typing import Any, Literal, NotRequired, TypedDict

import enum


class TwitchEvent(TypedDict):
    metadata: TwitchEventMetadata
    payload: dict[str, Any]


class TwitchEventMetadata(TypedDict):
    message_id: str
    message_type: str
    message_timestamp: str


class TwitchNotificationPayload(TypedDict):
    subscription: TwitchSubscriptionMetadata
    event: TwitchNotificationEvent


class TwitchChatPayload(TypedDict):
    subscription: TwitchSubscriptionMetadata
    event: TwitchChatEvent


class TwitchSubscriptionMetadata(TypedDict):
    id: str
    status: Literal["enabled"]
    type: str
    condition: dict[str, str]
    transport: dict[str, str]
    created_at: str
    cost: int


class TwitchBadgeFragment(TypedDict):
    set_id: str
    id: str
    info: str


class TwitchChatEvent(TypedDict):
    broadcaster_user_id: str
    broadcaster_user_login: str
    broadcaster_user_name: str

    chatter_user_id: str
    chatter_user_login: str
    chatter_user_name: str

    color: str
    badges: list[TwitchBadgeFragment]

    message_id: str
    message_type: Literal["text"]

    message: TwitchChatMessage
    cheer: None
    reply: None

    source_broadcaster_user_id: str
    source_broadcaster_user_login: str
    source_broadcaster_user_name: str
    source_message_id: str
    source_badges: list[TwitchBadgeFragment] | None


class TwitchNotificationEvent(TypedDict):
    broadcaster_user_id: str
    broadcaster_user_login: str
    broadcaster_user_name: str

    chatter_user_id: str
    chatter_user_login: str
    chatter_user_name: str
    chatter_is_anonymous: bool

    color: str
    badges: list[TwitchBadgeFragment]

    message_id: str
    system_message: str
    notice_type: Literal[
        "sub",
        "resub",
        "sub_gift",
        "community_sub_gift",
        "gift_paid_upgrade",
        "prime_paid_upgrade",
    ]
    message: TwitchChatMessage

    sub: dict[str, str] | None
    resub: dict[str, str] | None
    sub_gift: dict[str, str] | None
    community_sub_gift: dict[str, str] | None
    gift_paid_upgrade: dict[str, str] | None
    prime_paid_upgrade: dict[str, str] | None
    pay_it_forward: dict[str, str] | None
    raid: dict[str, str] | None
    unraid: dict[str, str] | None
    announcement: dict[str, str] | None
    bits_badge_tier: dict[str, str] | None
    charity_donation: dict[str, str] | None
    watch_streak: dict[str, str] | None
    shared_chat_sub: dict[str, str] | None
    shared_chat_resub: dict[str, str] | None
    shared_chat_sub_gift: dict[str, str] | None
    shared_chat_community_sub_gift: dict[str, str] | None
    shared_chat_gift_paid_upgrade: dict[str, str] | None
    shared_chat_prime_paid_upgrade: dict[str, str] | None
    shared_chat_pay_it_forward: dict[str, str] | None
    shared_chat_raid: dict[str, str] | None
    shared_chat_announcement: dict[str, str] | None


class TwitchRewardRedemptionEvent(TypedDict):
    id: str
    broadcaster_user_id: str
    broadcaster_user_login: str
    broadcaster_user_name: str

    user_id: str
    user_login: str
    user_name: str

    user_input: str
    status: str
    redeemed_at: str

    reward: TwitchReward


class TwitchReward(TypedDict):
    id: str
    title: str
    cost: int
    prompt: str


class TwitchChatMessage(TypedDict):
    text: str
    fragments: list[TwitchMessageFragment]


class TwitchMessageFragment(TypedDict):
    type: str
    text: str
    cheermote: TwitchCheermoteFragment | None
    emote: TwitchEmoteFragment | None


class TwitchCheermoteFragment(TypedDict):
    prefix: str
    bits: int
    tier: int


class TwitchEmoteFragment(TypedDict):
    id: str
    emote_set_id: NotRequired[str]


class KnownBadges(enum.Enum):
    BOT = "bot-badge", "1"
    MOD = "moderator", "1"
    STREAMER = "broadcaster", "1"

    set_id: str
    id: str

    __slots__ = "id", "set_id"

    def __init__(self, set_id: str, _id: str) -> None:
        self.set_id = set_id
        self.id = _id

    def __eq__(self, other: object, /) -> bool:
        if not isinstance(other, dict):
            return super().__eq__(other)

        if other.keys() != {"set_id", "id", "info"}:
            return super().__eq__(other)

        return bool(self.set_id == other["set_id"]) and bool(self.id == other["id"])

    def __hash__(self) -> int:
        return hash((self.set_id, self.id))
