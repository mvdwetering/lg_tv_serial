import asyncio
from dataclasses import dataclass
import logging
import re
import sys
from serial import SerialException

import serial_asyncio

from .constants import Encoding3D, Mode3D, RemoteKeyCode, Input
from .protocol import LgTvProtocol, Response

logger = logging.getLogger(__name__)

END_MARKER = b'x'
WEIRD_VALUE = 0xFF

@dataclass
class Config3D:
    mode:Mode3D
    encoding:Encoding3D
    right_to_left:bool
    depth:int


def build_command(command1, command2, set_id:int, data0:int, data1:int|None = None, data2:int|None = None, data3:int|None = None, data4:int|None = None, data5:int|None = None) -> bytes:
    arguments = locals()
    # print(arguments)

    command_string = f"{command1}{command2} {set_id:02X}"
    data_index = 0
    while arguments[f"data{data_index}"] is not None:
        data = arguments[f"data{data_index}"]
        # print(data_index, data)
        command_string += f" {data:02X}"
        data_index += 1
    command_string += "\r"  # CR
    command = command_string.encode("ascii")

    logging.debug("build_command string: %s", command_string)
    logging.debug("build_command bytes: %s", command)

    return command

def parse_response(reponse:bytearray) -> Response | None:
    try:
        match = re.match(r"(?P<cmd2>.) (?P<set_id>\d\d) (?P<status>..)(?P<data>.+)", reponse.decode("ascii"))
        if match is None:
            logging.error("Could not match %s", reponse)
            return None

        logging.debug("DEBUG MATCH DATA: %s, %s, %s, %s", match.group("cmd2"), match.group("set_id"), match.group("status"), match.group("data"))
        cmd2 = match.group("cmd2")
        set_id = int(match.group("set_id"), 16)
        status_ok = match.group("status") == "OK"
        data0 = int(match.group("data"), 16)

        return Response(cmd2, set_id, status_ok, data0)
    except Exception as e:
        logging.error("Could not parse data from %s", reponse)
        raise e


class LgTv:
    """Control an LG TV with serial port."""

    def __init__(
        self,
        serial_url,
        set_id=0
    ) -> None:
        self._serial_url = serial_url
        self._set_id = set_id
        self._lock = asyncio.Lock()
        self._reader:asyncio.StreamReader
        self._writer:asyncio.StreamWriter
        self._on_disconnect = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def connect(self, on_disconnect=None):
        try:
            (self._reader, self._writer) = await serial_asyncio.open_serial_connection(url=self._serial_url, baudrate=9600)
            self._on_disconnect = on_disconnect
        except SerialException:
            raise ConnectionError("Could not connect to LG TV")

    async def close(self):
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()


    async def _do_command(self, command1, command2, data0:int, data1:int|None = None, data2:int|None = None, data3:int|None = None, data4:int|None = None, data5:int|None = None) -> Response|bool:
        async with self._lock:
            command = build_command(command1, command2, self._set_id, data0, data1, data2, data3, data4, data5)
            print("before send", command)
            self._writer.write(command)

            print("before await")
            try:
                async with asyncio.timeout(5):
                    command = bytearray()
                    while True:
                        data = await self._reader.read(1)
                        if data == END_MARKER:
                            print("parsing data:", command)
                            result = parse_response(command)
                            return result
                        if data == WEIRD_VALUE:
                            # Sometimes the TV returns 0xFF, it is unclear why
                            # and the value is not documented
                            # I think it means something like "busy"
                            return False
                        if data == b'':
                            # Connection closed
                            raise ConnectionError("Connection closed")
                        command.extend(data)
            except TimeoutError:
                logger.debug("TimeoutError")
            except ConnectionError:
                if self._on_disconnect:
                    await self._on_disconnect()

            print("_do_command failed")
            return False
            # return await self._protocol.do_command(command1, command2, self._set_id, data0, data1, data2, data3, data4, data5)


    async def set_power_on(self, value:bool) -> None:
        await self._do_command("k", "a", 1 if value else 0)

    async def get_power_on(self) -> bool|None:
        response = await self._do_command("k", "a", 0xFF)
        if isinstance(response, Response) and response.status_ok:
            return response.data0 == 1
        return None


    async def set_mute(self, mute:bool) -> None:
        await self._do_command("k", "e", 1 if mute else 0)

    async def get_mute(self) -> bool|None:
        response = await self._do_command("k", "e", 0, 0xFF)
        if isinstance(response, Response) and response.status_ok:
            return response.data0 == 1
        return None
    

    async def set_volume(self, value:int) -> None:
        assert value >= 0
        assert value <= 100
        response = await self._do_command("k", "f", value)

    async def get_volume(self) -> int|None:
        response = await self._do_command("k", "f", 0xFF)
        if isinstance(response, Response) and response.status_ok:
            return response.data0
        return None

    async def volume_up(self) -> None:
        response = await self._do_command("m", "c", 2)

    async def volume_down(self) -> None:
        response = await self._do_command("m", "c", 3)


    async def channel_up(self) -> None:
        response = await self._do_command("m", "c", 0)

    async def channel_down(self) -> None:
        response = await self._do_command("m", "c", 1)


    async def remote_key(self, code:RemoteKeyCode) -> None:
        """Allows sending remote key codes, note that some key codes already have methods like `volume_up`"""
        await self._do_command("m", "c", code)


    async def set_contrast(self, value:int) -> None:
        assert value >= 0
        assert value <= 100
        response = await self._do_command("k", "g", value)

    async def get_contrast(self) -> int|None:
        response = await self._do_command("k", "g", 0xFF)
        if isinstance(response, Response) and response.status_ok:
            return response.data0
        return None


    async def set_brightness(self, value:int) -> None:
        assert value >= 0
        assert value <= 100
        response = await self._do_command("k", "h", value)

    async def get_brightness(self) -> int|None:
        response = await self._do_command("k", "h", 0xFF)
        if isinstance(response, Response) and response.status_ok:
            return response.data0
        return None


    async def set_color(self, value:int) -> None:
        assert value >= 0
        assert value <= 100
        response = await self._do_command("k", "i", value)

    async def get_color(self) -> int|None:
        response = await self._do_command("k", "i", 0xFF)
        if isinstance(response, Response) and response.status_ok:
            return response.data0
        return None


    async def set_sharpness(self, value:int) -> None:
        assert value >= 0
        assert value <= 100
        response = await self._do_command("k", "k", value)

    async def get_sharpness(self) -> int|None:
        response = await self._do_command("k", "k", 0xFF)
        if isinstance(response, Response) and response.status_ok:
            return response.data0
        return None


    async def set_remote_control_lock(self, value:bool) -> None:
        response = await self._do_command("k", "m", 1 if value else 0)

    async def get_remote_control_lock(self) -> bool|None:
        response = await self._do_command("k", "m", 0xFF)
        if isinstance(response, Response) and response.status_ok:
            return response.data0 == 1
        return None


    async def set_treble(self, value:int) -> None:
        assert value >= 0
        assert value <= 100
        response = await self._do_command("k", "r", value)

    async def get_treble(self) -> int|None:
        response = await self._do_command("k", "r", 0xFF)
        if isinstance(response, Response) and response.status_ok:
            return response.data0
        return None


    async def set_bass(self, value:int) -> None:
        assert value >= 0
        assert value <= 100
        response = await self._do_command("k", "s", value)

    async def get_bass(self) -> int|None:
        response = await self._do_command("k", "s", 0xFF)
        if isinstance(response, Response) and response.status_ok:
            return response.data0
        return None


    async def set_balance(self, value:int) -> None:
        assert value >= 0
        assert value <= 100
        response = await self._do_command("k", "t", value)

    async def get_balance(self) -> int|None:
        response = await self._do_command("k", "t", 0xFF)
        if isinstance(response, Response) and response.status_ok:
            return response.data0
        return None


    async def set_color_temperature(self, value:int) -> None:
        assert value >= 0
        assert value <= 100
        response = await self._do_command("x", "u", value)

    async def get_color_temperature(self) -> int|None:
        response = await self._do_command("x", "u", 0xFF)
        if isinstance(response, Response) and response.status_ok:
            return response.data0
        return None


    async def set_input(self, value:Input) -> None:
        await self._do_command("x", "b", value)

    async def get_input(self) -> Input|None:
        response = await self._do_command("x", "b", 0xFF)
        if isinstance(response, Response) and response.status_ok:
            return Input(response.data0)
        return None

    async def set_3d(self, mode:Mode3D, encoding:Encoding3D, right_to_left:bool, depth:int) -> None:
        response = await self._do_command("x", "t", mode, encoding, 1 if right_to_left else 0, depth)

    # Does not seem to work even though my TV supports 3D
    # async def get_3d(self) -> Config3D:
    #     response = await self._do_command("x", "t", 0xFF)
    #     return Config3D(Mode3D(response.data0), Encoding3D(response.data1), response.data2==1, response.data3)


async def main(serial_url:str):
    async with LgTv(serial_url) as tv:
        await tv.connect()

        print("Current settings")
        print(f"{await tv.get_power_on()=}")
        await tv.set_power_on(True)
        await asyncio.sleep(2)
        print(f"{await tv.get_power_on()=}")
        print(f"{await tv.get_input()=}")
        print(f"{await tv.get_volume()=}")
        print(f"{await tv.get_mute()=}")
        print(f"{await tv.get_treble()=}")
        print(f"{await tv.get_bass()=}")
        print(f"{await tv.get_balance()=}")
        print(f"{await tv.get_brightness()=}")
        print(f"{await tv.get_contrast()=}")
        print(f"{await tv.get_color()=}")
        print(f"{await tv.get_color_temperature()=}")
        print(f"{await tv.get_sharpness()=}")
        print(f"{await tv.get_remote_control_lock()=}")

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        print("Must provide a serial_url parameter like:")
        print("  COM3")
        print("  /dev/ttyUSB0")
        print("  socket://192.168.178.53:11113")
        exit(1)

    logging.basicConfig(level="INFO")
    # logging.basicConfig(level="DEBUG")

    asyncio.run(main(sys.argv[1]))