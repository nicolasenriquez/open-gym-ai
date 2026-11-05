"""Private bounded TCP relay; only forwards to the run-owned synthetic PG."""

import asyncio
from contextlib import asynccontextmanager


class CommitRelay:
    def __init__(self, cut_reset=False):
        self.cut_reset = cut_reset
        self.reset_dropped = False
        self.held = asyncio.Event()
        self.release = asyncio.Event()
        self.commits = 0
        self.tasks = set()

    def accept(self, reader, writer):
        task = asyncio.create_task(self.forward(reader, writer))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def forward(self, reader, writer):
        upstream = None
        pipes = []
        committing = False
        try:
            remote, upstream = await asyncio.wait_for(
                asyncio.open_connection("platform-db", 5432), 5
            )
            size = await reader.readexactly(4)
            length = int.from_bytes(size, "big")
            if not 8 <= length <= 65536:
                return
            upstream.write(size + await reader.readexactly(length - 4))
            await upstream.drain()

            async def pipe(source, target, from_server):
                nonlocal committing
                while True:
                    kind = await source.readexactly(1)
                    header = await source.readexactly(4)
                    length = int.from_bytes(header, "big")
                    if not 4 <= length <= 65536:
                        return
                    body = await source.readexactly(length - 4)
                    if (
                        not from_server
                        and kind == b"Q"
                        and self.cut_reset
                        and not self.reset_dropped
                        and b"RESET ALL" in body
                    ):
                        self.reset_dropped = True
                        writer.close()
                        return
                    if (
                        not from_server
                        and kind == b"Q"
                        and body in (b"COMMIT;\0", b"COMMIT\0")
                    ):
                        committing = True
                        self.commits += 1
                    if (
                        from_server
                        and committing
                        and kind == b"C"
                        and body == b"COMMIT\0"
                        and not self.held.is_set()
                        and not self.cut_reset
                    ):
                        self.held.set()
                        await self.release.wait()
                        writer.close()
                        return
                    target.write(kind + header + body)
                    await target.drain()

            pipes = [
                asyncio.create_task(pipe(reader, upstream, False)),
                asyncio.create_task(pipe(remote, writer, True)),
            ]
            await asyncio.wait(pipes, return_when=asyncio.FIRST_COMPLETED)
        except (OSError, asyncio.IncompleteReadError, TimeoutError):
            pass
        finally:
            for task in pipes:
                task.cancel()
            await asyncio.gather(*pipes, return_exceptions=True)
            for stream in (writer, upstream):
                if stream is not None:
                    stream.close()
                    try:
                        await asyncio.wait_for(stream.wait_closed(), 5)
                    except (OSError, TimeoutError):
                        pass


@asynccontextmanager
async def commit_relay(*, cut_reset=False):
    relay = CommitRelay(cut_reset=cut_reset)
    server = await asyncio.start_server(relay.accept, "127.0.0.1", 0)
    relay.port = server.sockets[0].getsockname()[1]
    try:
        yield relay
    finally:
        server.close()
        await server.wait_closed()
        relay.release.set()
        for task in list(relay.tasks):
            task.cancel()
        await asyncio.wait_for(asyncio.gather(*relay.tasks, return_exceptions=True), 5)
