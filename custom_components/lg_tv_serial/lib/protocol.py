import asyncio
from dataclasses import dataclass
import logging
import re
import sys
from typing import Callable

import serial_asyncio

END = ord('x')
WEIRD_VALUE = 0xFF

@dataclass
class Response:
    command2: str
    set_id:int
    status_ok:bool
    data0:int
    data1:int|None = None
    data2:int|None = None
    data3:int|None = None
    data4:int|None = None
    data5:int|None = None    

class LgTvProtocol(asyncio.Protocol):

    def __init__(self) -> None:
        super().__init__()
        self._receive_buffer:bytearray = bytearray()
        self.connected_flag = asyncio.Event()
        self._response:asyncio.Future|None = None

    def connection_made(self, transport):
        self.transport = transport
        logging.debug('port opened - %s' , transport)
        self.connected_flag.set()

    async def wait_for_connection_made(self, timeout=1):
        async with asyncio.timeout(timeout):
            await self.connected_flag.wait()

    def data_received(self, data:bytes):
        logging.debug('data received: %s', repr(data))

        for d in data:
            logging.debug('d=: %s', d)
            if d == END:
                logging.debug("received command: %s", self._receive_buffer)
                self._parse_response(self._receive_buffer)
                self._receive_buffer = bytearray()
            elif d == WEIRD_VALUE:
                logging.debug("received weird value: %d", WEIRD_VALUE)
                self._receive_buffer = bytearray()
                assert self._response is not None
                self._response.set_result(False)
            else:
                self._receive_buffer.append(d)
    
    def _parse_response(self, reponse:bytearray):
        match = re.match(r"(?P<cmd2>.) (?P<set_id>\d\d) (?P<status>..)(?P<data>.+)", reponse.decode("ascii"))

        if match is None:
            logging.error("Could not match %s", reponse)
            return

        try:
            logging.debug("DEBUG MATCH DATA: %s, %s, %s, %s", match.group("cmd2"), match.group("set_id"), match.group("status"), match.group("data"))
            cmd2 = match.group("cmd2")
            set_id = int(match.group("set_id"), 16)
            status_ok = match.group("status") == "OK"
            data0 = int(match.group("data"), 16)

            assert self._response is not None
            self._response.set_result(Response(cmd2, set_id, status_ok, data0))

        except Exception as e:
            logging.error("Could not parse data from %s", reponse)
            raise e


    def connection_lost(self, exc):
        logging.debug('port closed')
        self.transport.loop.stop()

    def send(self, command1, command2, set_id:int, data0:int, data1:int|None = None, data2:int|None = None, data3:int|None = None, data4:int|None = None, data5:int|None = None):
        arguments = locals()
        print(arguments)
        command_string = f"{command1}{command2} {set_id:02X}"
        data_index = 0
        while arguments[f"data{data_index}"] is not None:
            data = arguments[f"data{data_index}"]
            print(data_index, data)
            command_string += f" {data:02X}"
            data_index += 1
        command_string += "\r"  # CR
        command = command_string.encode("ascii")

        logging.debug("send string: %s", command_string)
        logging.debug("send bytes: %s", command)

        self.transport.write(command)

    async def do_command(self, command1, command2, set_id:int, data0:int, data1:int|None = None, data2:int|None = None, data3:int|None = None, data4:int|None = None, data5:int|None = None):
        self._response = asyncio.get_running_loop().create_future()
        self._receive_buffer = bytearray()

        print("before send")
        self.send(command1, command2, set_id, data0, data1, data2, data3, data4, data5)

        print("before await")
        try:
            async with asyncio.timeout(1):
                await self._response
        except TimeoutError:
            pass

        print("after await")

        return self._response.result() if not self._response.cancelled() else False



async def main(serial_url:str):
    loop = asyncio.get_event_loop()

    # loop = asyncio.new_event_loop()
    transport, protocol = await serial_asyncio.create_serial_connection(loop, LgTvProtocol, serial_url, baudrate=9600)
    # transport, protocol = loop.run_until_complete(coro)
    # loop.run_forever()

    # transport, protocol = await serial_asyncio.create_serial_connection(loop, LgTvProtocol, serial_url, baudrate=9600)
    # await asyncio.sleep(1)
    await protocol.wait_for_connection_made()

    response = await protocol.do_command("k", "a", 0, 1)
    print(f"{response=}")
    await asyncio.sleep(2)

    response = await protocol.do_command("k", "a", 0, 0xFF)
    print(f"{response=}")
    await asyncio.sleep(2)

    response = await protocol.do_command("k", "e", 0, 1)
    print(f"{response=}")
    await asyncio.sleep(2)

    response = await protocol.do_command("k", "e", 0, 0)
    print(f"{response=}")
    await asyncio.sleep(2)

    response = await protocol.do_command("k", "a", 0, 0)
    print(f"{response=}")
    await asyncio.sleep(2)

    response = await protocol.do_command("k", "a", 0, 0xFF)
    print(f"{response=}")
    await asyncio.sleep(1)

    response = await protocol.do_command("k", "a", 0, 3)
    print(f"{response=}")
    await asyncio.sleep(1)

    # protocol.send("k", "a", 0, 1)
    # await asyncio.sleep(1)
    # protocol.send("k", "a", 0, 0xFF)
    # await asyncio.sleep(1)
    # protocol.send("k", "a", 0, 0)
    # await asyncio.sleep(2)
    # protocol.send("k", "a", 0, 0xFF)
    # protocol.send("k", "a", 0, 1)
    # await asyncio.sleep(1)
    # await asyncio.sleep(1)
    # loop.close()


if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print("Must provide a serial_url parameter like:")
        print("  COM3")
        print("  /dev/ttyUSB0")
        print("  socket://192.168.178.53:11113")
        exit(1)

    logging.basicConfig(level="DEBUG")

    asyncio.run(main(sys.argv[1]))