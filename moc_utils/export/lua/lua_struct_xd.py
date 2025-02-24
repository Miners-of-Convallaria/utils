import base64
from ctypes import c_uint8, c_uint64
from dataclasses import dataclass
from io import BytesIO
from typing import Self
from .lua_struct import *


class LuaXD(Lua):
    header: LuaHeader
    root: LuaChunk

    @classmethod
    def from_bytes(cls, raw: bytes):
        assert raw[:4] == b"\x01XFC", "Invalid LuaXD signature"
        data = luaZ_read_xd(raw)
        stream = BytesIO(data)
        header = LuaHeader.from_stream(stream)
        lua_stream = LuaStreamXD(stream, header)
        root = LuaChunk.from_stream(lua_stream)
        return cls(header, root)

    def to_bytes(self) -> bytes:
        stream = BytesIO()
        self.header.to_stream(stream)
        lua_stream = LuaStreamXD(stream, self.header)
        self.root.to_stream(lua_stream)
        return luaZ_read_xd(stream.getvalue())

    def to_normal(self) -> Lua:
        header = LuaHeader(
            signature=b"\x1bLua",
            version=0x51,
            format=self.header.format,
            endianness=self.header.endianness,
            int_size=self.header.int_size,
            size_t_size=self.header.size_t_size,
            instruction_size=self.header.instruction_size,
            lua_number_size=self.header.lua_number_size,
            integral_flag=self.header.integral_flag,
        )

        return Lua(header, self._decrypt_chunk(self.root))

    @classmethod
    def from_normal(cls, lua: Lua) -> Self:
        header = LuaHeader(
            signature=b"\x01XDI",
            version=1,
            format=lua.header.format,
            endianness=lua.header.endianness,
            int_size=lua.header.int_size,
            size_t_size=lua.header.size_t_size,
            instruction_size=lua.header.instruction_size,
            lua_number_size=lua.header.lua_number_size,
            integral_flag=lua.header.integral_flag,
        )

        return cls(header, cls._encrypt_chunk(lua.root))

    @classmethod
    def _decrypt_chunk(cls, chunck: LuaChunk) -> LuaChunk:
        return LuaChunk(
            name=chunck.name,
            linedefined=chunck.linedefined,
            lastlinedefined=chunck.lastlinedefined,
            nups=chunck.nups,
            numparams=chunck.numparams,
            is_vararg=chunck.is_vararg,
            maxstacksize=chunck.maxstacksize,
            instructions=[
                InstructionXD.decrypt(instr) for instr in chunck.instructions
            ],
            constants=chunck.constants,
            protos=[cls._decrypt_chunk(proto) for proto in chunck.protos],
            lineinfo=chunck.lineinfo,
            locvars=chunck.locvars,
            upvalues=chunck.upvalues,
        )

    def _encrypt_chunk(self, chunck: LuaChunk) -> LuaChunk:
        return LuaChunk(
            chunck.name,
            chunck.linedefined,
            chunck.lastlinedefined,
            chunck.nups,
            chunck.numparams,
            chunck.is_vararg,
            chunck.maxstacksize,
            [InstructionXD.encrypt(instr) for instr in chunck.instructions],
            constants=chunck.constants,
            protos=[self._encrypt_chunk(proto) for proto in chunck.protos],
            lineinfo=chunck.lineinfo,
            locvars=chunck.locvars,
            upvalues=chunck.upvalues,
        )


class LuaStreamXD(LuaStream):
    def read_string(self) -> str:
        length = self.read_size_t()
        if length == 0:
            return ""
        length -= 10
        raw = self.stream.read(length)
        assert raw[-1] == 0, "Invalid string"
        return DebugStringXD.try_decrypt(raw)

    def write_string(self, value: str):
        if not value:
            self.write_size_t(0)
            return
        raw = value.encode("utf8") + b"x\00"
        self.write_size_t(len(raw) + 10)
        self.stream.write(raw)


class DebugStringXD:
    @staticmethod
    def encrypt(src_str: str) -> bytes:
        encrypted_string = bytearray(src_str.encode("utf8"))
        for i, c in enumerate(encrypted_string):
            val = c_uint8(c)
            val.value += i
            val.value ^= 0xEE
            val.value -= i % 3
            encrypted_string[i] = val.value

        encoded = base64.b64encode(encrypted_string)

        return b"".join([b"\x41", encoded])

    @staticmethod
    def decrypt(enc_str: bytes) -> str:
        assert enc_str[0] == 0x41, "Invalid DebugString"
        decoded = base64.b64decode(enc_str[1:-1])

        if not decoded:
            return ""

        src_str = bytearray(len(decoded))
        for i, v in enumerate(decoded):
            val = c_uint8(v)
            val.value += i % 3
            val.value ^= 0xEE
            val.value -= i
            src_str[i] = val.value

        return src_str.strip(b"\x00").decode("utf8")

    @classmethod
    def try_decrypt(cls, enc_str: bytes) -> str:
        if len(enc_str) % 4 == 2 and enc_str[0] == 0x41:
            try:
                return cls.decrypt(enc_str)
            except:
                pass
        return enc_str[:-1].decode("utf8")


class InstructionXD:
    # normal:
    # bits: 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31
    # ABC:  OPCODE           | A                     | C                        | B
    # ABx:  OPCODE           | A                     | B
    # AsBx: OPCODE           | A                     | sBx

    # xd:
    # bits: 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31
    # ABC:  A                      | C                        | B                        | OPCODE
    # ABx:  A                      | B                                                   | OPCODE
    # AsBx: A                      | sBx                                                 | OPCODE

    @staticmethod
    def encrypt(instr: int) -> int:
        opcode = instr & 0x6
        # opmode = LUAP_OPMODES[opcode]
        opcode_xd = OPCODE_NORMAL_TO_XD[opcode]

        instr_xd = opcode_xd << 26 | (instr >> 6) & 0x3FFFFFF

        # a = (instr >> 6) & 0xFF
        # instr_xd |= a

        # if opmode == OpMode.ABC:  # iABC
        #     c = (instr >> 14) & 0x1FF
        #     b = (instr >> 23) & 0x1FF
        #     instr_xd |= c << 8 | b << 17
        # elif opmode == OpMode.ABx:  # iABx
        #     b = (instr >> 14) & 0x3FFFF
        #     instr_xd |= b << 8
        # elif opmode == OpMode.AsBx:  # iAsBx
        #     b = (instr >> 14) & 0x3FFFF
        #     instr_xd |= (b + 0x1FFFF) << 8

        return instr_xd

    @staticmethod
    def decrypt(instr_xd: int) -> int:
        opcode_xd = instr_xd >> 26
        opcode = OPCODE_XD_TO_NORMAL[opcode_xd]
        # opmode = LUAP_OPMODES[opcode]

        instr = opcode | (instr_xd & 0x3FFFFFF) << 6
        # a = instr_xd & 0xFF
        # instr |= a << 6

        # if opmode == OpMode.ABC:  # iABC
        #     c = (instr_xd >> 8) & 0x1FF
        #     b = (instr_xd >> 17) & 0x1FF
        #     instr |= c << 14 | b << 23
        # elif opmode == OpMode.ABx:  # iABx
        #     b = (instr_xd >> 8) & 0x3FFFF
        #     instr |= b << 14
        # elif opmode == OpMode.AsBx:  # iAsBx
        #     b = ((instr_xd >> 8) & 0x3FFFF) - 0x1FFFF
        #     instr |= (b + 0x1FFF) << 14

        return instr


def luaZ_read_xd(src_data: bytes, offset: int = 0, count: int = -1) -> bytes:
    if count == -1:
        count = len(src_data) - offset

    dst_data = bytearray(count)
    remaining = len(src_data) - offset
    if remaining < count:
        count = remaining

    if count == 0:
        return b""

    src_off = offset
    dst_off = 0

    xor_val1 = c_uint64(539034887 * src_off)
    xor_val2 = 0
    for dst_off, (src_off, val) in zip(
        range(count), enumerate(src_data[offset:], offset)
    ):
        if src_off < 2:
            dst_data[dst_off] = val
            src_off += 1
            dst_off += 1
            xor_val1.value += 539034887
            continue

        xor_val_opt = src_off % 3

        if xor_val_opt == 1:
            xor = ((xor_val1.value >> 16 & 0xFF) - src_off) & 0xFF
        elif xor_val_opt == 2:
            xor_val2 = xor_val2 & 0xFFFFFF00 | (
                ((xor_val1.value >> 21) | src_off) & 0xFF
            )
            xor = xor_val2 & 0xFF
        else:
            xor_val2 = (xor_val1.value >> 28) + (xor_val1.value & 1) + src_off
            xor = xor_val2 & 0xFF

        dst_data[dst_off] = xor ^ val

        src_off += 1
        dst_off += 1
        xor_val1.value += 539034887

    return dst_data


LUAP_OPNAMES_XD = [
    "LOADNIL",
    "MUL",
    "SETTABLE",
    "LE",
    "CLOSE",
    "NEWTABLE",
    "LOADK",
    "POW",
    "GETTABLE",
    "TESTSET",
    "LT",
    "EQ",
    "MOVE",
    "SETGLOBAL",
    "GETUPVAL",
    "LOADBOOL",
    "DIV",
    "RETURN",
    "ADD",
    "GETGLOBAL",
    "CONCAT",
    "CALL",
    "TFORLOOP",
    "CLOSURE",
    "FORPREP",
    "SETLIST",
    "TAILCALL",
    "FORLOOP",
    "SETUPVAL",
    "JMP",
    "MOD",
    "NOT",
    "SELF",
    "UNM",
    "TEST",
    "LEN",
    "SUB",
    "VARARG",
]

OPCODE_XD_TO_NORMAL = {
    i: LUAP_OPNAMES.index(name) for i, name in enumerate(LUAP_OPNAMES_XD)
}
OPCODE_NORMAL_TO_XD = {v: k for k, v in OPCODE_XD_TO_NORMAL.items()}
