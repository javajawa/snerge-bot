import asyncio
import dataclasses
import functools
import itertools
import pathlib
import textwrap
import typing
import urllib.parse

import aiohttp
import epicstore_api


@dataclasses.dataclass
class GameInfo:
    name: str
    source: str
    description: str
    website: str
    purchase: str
    tags: list[str]
    platforms: list[str]
    prices: dict[str, float]


class GameList:
    games: list[GameInfo]

    def __init__(self, data: list[GameInfo]) -> None:
        self.games = data

    @property
    def name(self) -> str:
        return self.games[0].name

    @property
    def website(self) -> str:
        return self.games[0].website

    @property
    def description(self) -> str:
        return sorted([game.description for game in self.games], key=len, reverse=True)[0]

    @property
    def tags(self) -> set[str]:
        return set(itertools.chain(*[game.tags for game in self.games]))

    @property
    def platforms(self) -> set[str]:
        return set(itertools.chain(*[game.platforms for game in self.games]))

    @property
    def prices(self) -> dict[str, tuple[float, str]]:
        ret = {}

        for game in self.games:
            for currency, price in game.prices.items():
                if price > ret.get(currency, (100000, ""))[0]:
                    continue

                ret[currency] = (price, game.purchase)

        return ret


class Foo:
    file: pathlib.Path
    steam: dict[str, int] | None = None
    session: aiohttp.ClientSession | None = None
    epic_api: epicstore_api.EpicGamesStoreAPI | None = None

    def __init__(self, path: str) -> None:
        self.file = pathlib.Path(path)

    async def main(self):
        self.session = aiohttp.ClientSession()
        self.epic_api = epicstore_api.EpicGamesStoreAPI()

        try:
            with open("./games.md", "w") as out:
                with self.file.open("r", encoding="utf-8") as source:
                    for line in source.readlines():
                        if not line.strip():
                            continue

                        if not line.startswith("#"):
                            out.write(line)
                            continue

                        out.write("\n")
                        starred = "**" in line
                        game = line.strip().strip("*").strip("#").strip()
                        await self.get_game(game, out)
                        if starred:
                            out.write("> **Note**\n> Marked as exciting by Serge\n\n")

        finally:
            await self.session.close()

    async def steam_game(self, name: str) -> GameInfo | None:
        if not self.steam:
            response = await self.session.get(
                "https://api.steampowered.com/ISteamApps/GetAppList/v0002/?format=json"
            )
            self.steam = {
                x["name"].strip("™ "): x["appid"]
                for x in (await response.json())["applist"]["apps"]
            }

        if name not in self.steam:
            return None

        response = await self.session.get(
            "https://store.steampowered.com/api/appdetails?appids=" + str(self.steam[name])
        )
        json = await response.json()
        game = json[str(self.steam[name])]["data"]

        return GameInfo(
            source="Steam",
            name=game["name"],
            description=game["short_description"],
            website=game["website"],
            purchase=f"https://store.steampowered.com/app/{game['steam_appid']}/{game['name'].replace(' ', '_')}",
            tags=[x["description"].title() for x in game.get("genres", [])],
            platforms=[x for x in game["platforms"] if game["platforms"][x]],
            prices={game["price_overview"]["currency"]: game["price_overview"]["final"] / 100}
            if "price_overview" in game
            else {},
        )

    async def humble(self, name: str) -> GameInfo | None:
        response = await self.session.post(
            "https://ayszewdaz2-dsn.algolia.net/1/indexes/replica_product_query_site_search/query?x-algolia-agent=Algolia%20for%20vanilla%20JavaScript%203.24.5&x-algolia-application-id=AYSZEWDAZ2&x-algolia-api-key=5229f8b3dec4b8ad265ad17ead42cb7f",
            data=f'{{"params":"query={urllib.parse.quote(name)}&filters=NOT%20disallowed_countries%3A%22GB%22%20AND%20(exclusive_countries%3A%22n%2Fa%22%20OR%20exclusive_countries%3A%22GB%22)%20AND%20start_dt%20%3C%3D%201682890992%20AND%20end_dt%20%3E%201682890992&hitsPerPage=5&page=0"}}',
        )
        data = await response.json()
        humble = next((game for game in data["hits"] if name == game["human_name"]), None)

        if not humble:
            # if data["hits"]:
            #     print(name, "not found in humble, candidates", *[game["human_name"] for game in data["hits"]])
            return None

        return GameInfo(
            name=humble["human_name"],
            source="Humble",
            description=humble["description"],
            website="",
            purchase=f"https://www.humblebundle.com/store{humble['link']}?partner=SERGEYAGER",
            tags=[x.title() for x in humble.get("genres", [])],
            platforms=humble.get("platforms", []),
            prices={
                k: v["full_price"]
                for k, v in humble["localized_prices"].items()
                if k in ["EUR", "USD", "GBP", "CAD"]
            },
        )

    async def epic(self, name: str) -> GameInfo | None:
        games = await asyncio.get_running_loop().run_in_executor(
            None, functools.partial(self.epic_api.fetch_store_games, keywords=name)
        )

        for game in (
            games.get("data", {})
            .get("Catalog", {})
            .get("searchStore", {})
            .get("elements", [])
        ):
            if game.get("title").replace("Standard Edition", "").strip("™ ") != name:
                continue

            if not game["productSlug"]:
                continue

            data = self.epic_api.get_product(game["productSlug"])

            tags = set(
                itertools.chain.from_iterable(
                    page["data"]["meta"].get("tags", []) for page in data["pages"]
                )
            )
            platforms = set(
                itertools.chain.from_iterable(
                    page["data"]["meta"].get("platform", []) for page in data["pages"]
                )
            )

            return GameInfo(
                name=game["title"],
                source="Epic",
                description="",
                website="",
                purchase=f"https://store.epicgames.com/en-US/p/{game['productSlug']}",
                tags=[tag.replace("_", " ").title() for tag in tags],
                platforms=[platform.lower() for platform in platforms],
                prices={
                    game["price"]["totalPrice"]["currencyCode"]: game["price"]["totalPrice"][
                        "discountPrice"
                    ]
                    / 100
                },
            )

        # print(name, "not found in epic, candidates", *[game["title"] for game in games.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])])

        return None

    async def get_game(self, name: str, out: typing.TextIO) -> None:
        games = await asyncio.gather(
            self.steam_game(name),
            self.humble(name),
            self.epic(name),
        )

        game = GameList([game for game in games if game])

        if not game.games:
            print(name, "not in humble, epic, or steam -- typo?")
            out.write(f"### {name}\n")
            out.write("_No game metadata located._\n\n")
            return

        out.write(f"### [{game.name}]({game.website})\n")

        for currency, (price, link) in game.prices.items():
            out.write(f"[{price:.2f}{currency}]({link}) | ")

        for tag in game.tags:
            out.write(f"{tag} | ")

        for platform in game.platforms:
            out.write(
                f"![{platform}](https://img.shields.io/badge/platform-{platform}-blue) | "
            )

        out.write("\n\n")

        # if game.get("content_descriptors", {}).get("notes"):
        #     out.write("> **Warning**\n> ")
        #     out.write(game["content_descriptors"]["notes"])
        #     out.write("\n\n")

        out.write(textwrap.indent(game.description, "> "))
        out.write("\n\n")
