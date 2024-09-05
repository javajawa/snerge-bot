import asyncio

from . import Foo


if __name__ == "__main__":
    asyncio.run(Foo("serge.md").main())
