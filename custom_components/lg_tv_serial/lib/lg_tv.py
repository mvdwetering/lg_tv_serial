import asyncio
from dataclasses import dataclass
import logging
import sys

import serial_asyncio

from constants import Encoding3D, Mode3D, RemoteKeyCode, Input
from protocol import LgTvProtocol, Response

logger = logging.getLogger(__name__)

@dataclass
class Config3D:
    mode:Mode3D
    encoding:Encoding3D
    right_to_left:bool
    depth:int


class LgTv:
    """Control an LG TV with serial port."""

    def __init__(
        self,
        serial_url,
        set_id=0
    ) -> None:
        self._serial_url = serial_url
        self._set_id = set_id

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def connect(self):
        loop = asyncio.get_event_loop()
        transport, protocol = await serial_asyncio.create_serial_connection(loop, LgTvProtocol, self._serial_url, baudrate=9600)
    
        await protocol.wait_for_connection_made()
        self._protocol:LgTvProtocol = protocol
        self._transport = transport

    async def close(self):
        if self._transport:
            self._transport.close()


    async def _do_command(self, command1, command2, data0:int, data1:int|None = None, data2:int|None = None, data3:int|None = None, data4:int|None = None, data5:int|None = None) -> Response|bool:
        return await self._protocol.do_command(command1, command2, self._set_id, data0, data1, data2, data3, data4, data5)


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