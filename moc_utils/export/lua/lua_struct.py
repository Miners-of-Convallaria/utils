from dataclasses import dataclass, astuple
from enum import IntEnum
from io import BytesIO
from struct import unpack, pack
from typing import List, Union, BinaryIO, Literal, Self, Optional


@dataclass
class LuaHeader:
    signature: bytes
    version: int
    format: int
    endianness: bool  # 0 for big, 1 for little
    int_size: int
    size_t_size: int
    instruction_size: int
    lua_number_size: int
    integral_flag: bool  # 0 for integers, 1 for floats

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> Self:
        return cls(*unpack("<4sBB?BBBB?", stream.read(12)))

    def to_stream(self, stream: BinaryIO):
        stream.write(pack("<4sBB?BBBB?", *astuple(self)))


UINT_SYMBOL = Literal["H", "I", "Q"]
UINT_SYMBOL_MAP = {2: "H", 4: "I", 8: "Q"}
NUMBER_SYMBOL = Literal["f", "d"]
NUMBER_SYMBOL_MAP = {4: "f", 8: "d"}


class LuaStream:
    stream: BinaryIO
    endian: Literal["<", ">"]
    int_size: int
    int_symbol: UINT_SYMBOL
    size_t_size: int
    size_t_symbol: UINT_SYMBOL
    instr_size: int
    instr_symbol: UINT_SYMBOL
    number_size: int
    number_symbol: NUMBER_SYMBOL

    def __init__(self, stream: BinaryIO, header: LuaHeader):
        self.stream = stream
        self.endian = "<" if header.endianness else ">"
        self.int_size = header.int_size
        self.int_symbol = UINT_SYMBOL_MAP[header.int_size].lower()
        self.size_t_size = header.size_t_size
        self.size_t_symbol = UINT_SYMBOL_MAP[header.size_t_size]
        self.instr_size = header.instruction_size
        self.instr_symbol = UINT_SYMBOL_MAP[header.instruction_size]
        self.number_size = header.lua_number_size
        self.number_symbol = NUMBER_SYMBOL_MAP[header.lua_number_size]

    def read_byte(self) -> int:
        return self.stream.read(1)[0]

    def write_byte(self, value: int):
        self.stream.write(bytes([value]))

    def read_bool(self) -> bool:
        return self.read_byte() != 0

    def write_bool(self, value: bool):
        self.write_byte(1 if value else 0)

    def read_size_t(self) -> int:
        return unpack(
            f"{self.endian}{self.size_t_symbol}", self.stream.read(self.size_t_size)
        )[0]

    def write_size_t(self, value: int):
        self.stream.write(pack(f"{self.endian}{self.size_t_symbol}", value))

    def read_string(self) -> str:
        size = self.read_size_t()
        if size == 0:
            return ""
        raw = self.stream.read(size)
        assert raw[-1] == 0, "Not null-terminated string"
        return raw[:-1].decode("utf8")

    def write_string(self, value: str):
        data = value.encode("utf8") + b"\x00"
        self.write_size_t(len(data))
        self.stream.write(data)

    def read_int(self) -> int:
        return unpack(
            f"{self.endian}{self.int_symbol}", self.stream.read(self.int_size)
        )[0]

    def write_int(self, value: int):
        self.stream.write(pack(f"{self.endian}{self.int_symbol}", value))

    def read_number(self) -> float:
        return unpack(
            f"{self.endian}{self.number_symbol}", self.stream.read(self.number_size)
        )[0]

    def write_number(self, value: float):
        self.stream.write(pack(f"{self.endian}{self.number_symbol}", value))

    def read_ints(self) -> List[int]:
        count = self.read_int()
        return unpack(
            f"{self.endian}{count}{self.int_symbol}",
            self.stream.read(self.int_size * count),
        )

    def write_ints(self, values: List[int]):
        self.write_int(len(values))
        self.stream.write(pack(f"{self.endian}{len(values)}{self.int_symbol}", *values))

    def read_instructions(self) -> List[int]:
        count = self.read_int()
        return unpack(f"{self.endian}{count}I", self.stream.read(4 * count))

    def write_instructions(self, values: List[int]):
        self.write_int(len(values))
        self.stream.write(pack(f"{self.endian}{len(values)}I", *values))

    def read_constant(self) -> Union[None, bool, float, str]:
        type = self.read_byte()
        if type == 0:
            return None
        elif type == 1:
            return self.read_bool()
        elif type == 3:
            return self.read_number()
        elif type == 4:
            return self.read_string()
        else:
            raise Exception("Invalid constant type")

    def read_constants(self) -> List[Union[None, bool, float, str]]:
        count = self.read_int()
        return [self.read_constant() for _ in range(count)]

    def write_constant(self, value: Union[None, bool, float, str]):
        if value is None:
            self.write_byte(0)
        elif isinstance(value, bool):
            self.write_byte(1)
            self.write_bool(value)
        elif isinstance(value, float):
            self.write_byte(3)
            self.write_number(value)
        elif isinstance(value, str):
            self.write_byte(4)
            self.write_string(value)
        else:
            raise Exception("Invalid constant type")

    def write_constants(self, values: List[Union[None, bool, float, str]]):
        self.write_int(len(values))
        for value in values:
            self.write_constant(value)


@dataclass
class LocVar:
    name: str
    startpc: int
    endpc: int

    @classmethod
    def from_stream(cls, lua_stream: LuaStream):
        return cls(
            name=lua_stream.read_string(),
            startpc=lua_stream.read_int(),
            endpc=lua_stream.read_int(),
        )

    def to_stream(self, lua_stream: LuaStream):
        lua_stream.write_string(self.name)
        lua_stream.write_int(self.startpc)
        lua_stream.write_int(self.endpc)


@dataclass
class LuaChunk:
    name: str
    linedefined: int
    lastlinedefined: int
    nups: int
    numparams: int
    is_vararg: int
    maxstacksize: int
    instructions: List[int]
    constants: List[Union[None, bool, float, str]]
    protos: List["LuaChunk"]
    # debug info
    lineinfo: List[int]
    locvars: List[LocVar]
    upvalues: List[str]

    @classmethod
    def from_stream(cls, lua_stream: LuaStream) -> Self:
        return cls(
            name=lua_stream.read_string(),
            linedefined=lua_stream.read_int(),
            lastlinedefined=lua_stream.read_int(),
            nups=lua_stream.read_byte(),
            numparams=lua_stream.read_byte(),
            is_vararg=lua_stream.read_byte(),
            maxstacksize=lua_stream.read_byte(),
            instructions=lua_stream.read_instructions(),
            constants=lua_stream.read_constants(),
            protos=[
                LuaChunk.from_stream(lua_stream) for _ in range(lua_stream.read_int())
            ],
            lineinfo=lua_stream.read_ints(),
            locvars=[
                LocVar.from_stream(lua_stream) for _ in range(lua_stream.read_int())
            ],
            upvalues=[lua_stream.read_string() for _ in range(lua_stream.read_int())],
        )

    def to_stream(self, lua_stream: LuaStream):
        lua_stream.write_string(self.name)
        lua_stream.write_int(self.linedefined)
        lua_stream.write_int(self.lastlinedefined)
        lua_stream.write_byte(self.nups)
        lua_stream.write_byte(self.numparams)
        lua_stream.write_byte(self.is_vararg)
        lua_stream.write_byte(self.maxstacksize)
        lua_stream.write_instructions(self.instructions)
        lua_stream.write_constants(self.constants)
        lua_stream.write_int(len(self.protos))
        for proto in self.protos:
            proto.to_stream(lua_stream)
        lua_stream.write_ints(self.lineinfo)
        lua_stream.write_int(len(self.locvars))
        for locvar in self.locvars:
            locvar.to_stream(lua_stream)
        lua_stream.write_int(len(self.upvalues))
        for upvalue in self.upvalues:
            lua_stream.write_string(upvalue)


@dataclass
class Lua:
    header: LuaHeader
    root: LuaChunk

    @classmethod
    def from_bytes(cls, raw: bytes) -> Self:
        stream = BytesIO(raw)
        header = LuaHeader.from_stream(stream)
        lua_stream = LuaStream(stream, header)
        root = LuaChunk.from_stream(lua_stream)
        return cls(header, root)

    def to_bytes(self) -> bytes:
        stream = BytesIO()
        self.header.to_stream(stream)
        lua_stream = LuaStream(stream, self.header)
        self.root.to_stream(lua_stream)
        return stream.getvalue()


LUAP_OPNAMES = [
    "MOVE",
    "LOADK",
    "LOADBOOL",
    "LOADNIL",
    "GETUPVAL",
    "GETGLOBAL",
    "GETTABLE",
    "SETGLOBAL",
    "SETUPVAL",
    "SETTABLE",
    "NEWTABLE",
    "SELF",
    "ADD",
    "SUB",
    "MUL",
    "DIV",
    "MOD",
    "POW",
    "UNM",
    "NOT",
    "LEN",
    "CONCAT",
    "JMP",
    "EQ",
    "LT",
    "LE",
    "TEST",
    "TESTSET",
    "CALL",
    "TAILCALL",
    "RETURN",
    "FORLOOP",
    "FORPREP",
    "TFORLOOP",
    "SETLIST",
    "CLOSE",
    "CLOSURE",
    "VARARG",
]


class OpMode(IntEnum):
    ABC = 0
    ABx = 1
    AsBx = 2


LUAP_OPMODES = [
    OpMode.ABC,
    OpMode.ABx,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABx,
    OpMode.ABC,
    OpMode.ABx,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.AsBx,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.AsBx,
    OpMode.AsBx,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABC,
    OpMode.ABx,
    OpMode.ABC,
]
