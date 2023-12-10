from enum import IntEnum, unique


@unique
class RemoteKeyCode(IntEnum):
    CH_PLUS = 0x00
    CH_MINUX = 0x01
    VOLUME_PLUS = 0x02
    VOLUME_MINUS = 0x03
    ARROW_RIGHT = 0x06
    ARROW_LEFT = 0x07
    POWER = 0x08
    MUTE = 0x09
    INPUT = 0x0B
    SLEEP = 0x0E
    TV_RADIO = 0x0F
    NUMBER_0 = 0x10
    NUMBER_1 = 0x11
    NUMBER_2 = 0x12
    NUMBER_3 = 0x13
    NUMBER_4 = 0x14
    NUMBER_5 = 0x15
    NUMBER_6 = 0x16
    NUMBER_7 = 0x17
    NUMBER_8 = 0x18
    NUMBER_9 = 0x19
    Q_VIEW_FLASHBACK = 0x1A
    FAV = 0x1E
    TELETEXT = 0x20
    TELETEXT_OPTIONS = 0x21
    RETURN_BACK = 0x28
    AV_MODE = 0x30
    CAPTION_SUBTITLE = 0x39
    ARROW_UP = 0x40
    ARROW_DOWNMUTE = 0x41
    MY_APPS = 0x42
    MENU_SETTINGS = 0x43
    OK_ENTER = 0x44
    Q_MENU = 0x45
    LIST_MINUS = 0x4C
    PICTURE = 0x4D
    SOUND = 0x52
    LIST = 0x53
    EXIT = 0x5B
    PIP = 0x60
    BLUE = 0x61
    YELLOW = 0x63
    GREEN = 0x71
    RED = 0x72
    ASPECT_RATIO = 0x79
    AUDIO_DESCRIPTION = 0x91
    LIVE_MENU = 0x9E
    USER_GUIDE = 0x7A
    SMART_HOME = 0x7C
    SIMPLINK = 0x7E
    FORWARD = 0x8E
    REWIND = 0x8F
    INFO = 0xAA
    PROGRAM_GUIDE = 0xAB
    PLAY = 0xB0
    STOP_FILELIST = 0xB1
    RECENT = 0xB5
    FREEZE_SLOWPLAY_PAUSE = 0xBA
    SOCCER = 0xBB
    REC = 0xBD
    THREE_D = 0xDC
    AUTOCONFIG = 0x99
    APP = 0x9F
    TV_PC = 0x9B

@unique
class Input(IntEnum):
    DTV = 0x00
    CADTV = 0x01
    SATELLITE_DTV__ISDB_BS_JAPAN = 0x02
    ISDB_CS1_JAPAN = 0x03
    ISDB_CS2_JAPAN = 0x04
    CATV = 0x11
    AV1= 0x20
    AV2 = 0x21
    COMPONENT1 = 0x40
    COMPONENT2 = 0x41
    RGB = 0x60
    HDMI1 = 0x90
    HDMI2 = 0x91
    HDMI3 = 0x92
    HDMI4 = 0x93

@unique
class Mode3D(IntEnum):
    ON = 0x00
    OFF = 0x01
    TO_2D = 0x02
    TO_3D = 0x03
    UNKNOWN = 0xFF

@unique
class Encoding3D(IntEnum):
    TOP_BOTTOM = 0x00
    SIDE_BY_SIDE = 0x01
    CHECKERBOARD = 0x02
    FRAME_SEQUENTIAL = 0x03
    COLUMN_INTERLEAVING = 0x04
    ROW_INTERLEAVING = 0x05
    UNKNOWN = 0xFF
