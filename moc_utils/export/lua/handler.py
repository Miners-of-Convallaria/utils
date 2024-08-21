import _ctypes
import ctypes
import os
from typing import Callable

lua_CFunction = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)  # noqa: N816


class luaL_Reg(ctypes.Structure):  # noqa: N801
    _fields_ = [  # noqa: RUF012
        ("name", ctypes.c_char_p),
        ("func", lua_CFunction),
    ]


class LuaHandler:
    fp: str
    lua: ctypes.CDLL
    state: ctypes.c_void_p

    def __init__(self, fp: str) -> None:
        self.fp = fp
        if os.name == "nt":
            self.lua = ctypes.WinDLL(fp)
        else:
            raise NotImplementedError("TODO: compile slua with necessary modifications for non-windows")
        register_lua_functions(self.lua)
        self.newstate()
        self.openlibs()

    def __del__(self) -> None:
        if os.name == "nt":
            _ctypes.FreeLibrary(self.lua._handle)
        else:
            _ctypes.dlclose(self.lua._handle)

    def check_error(self, err: int) -> None:
        if err:
            err_msg = self.tolstring(-1)
            print(f"Error {err} executing Lua script:", err_msg)
            raise Exception("Failed to load string")

    def newstate(self) -> None:
        self.state = self.lua.luaL_newstate()
        assert self.state is not None, "Failed to create Lua state"

    def openlibs(self) -> None:
        assert self.lua.luaL_openlibs(self.state) != 0, "Failed to open Lua libs"

    def loadstring(self, s: str) -> None:
        err = self.lua.luaL_loadstring(self.state, s.encode("utf-8") + b"\x00")
        self.check_error(err)

    def loadbuffer(self, buff: str | bytes, name: str) -> None:
        if isinstance(buff, str):
            buff = buff.encode("utf-8")
        err = self.lua.luaLS_loadbuffer(self.state, buff, len(buff), name.encode("utf-8"))
        self.check_error(err)

    def pcall(self, nargs: int, nresults: int, errfunc: int) -> None:
        err = self.lua.lua_pcall(self.state, nargs, nresults, errfunc)
        self.check_error(err)

    def register(self, libs: list[luaL_Reg], libname: str | None = None) -> None:
        libname_c = libname.encode("utf-8") + b"\x00" if libname else 0

        libs.append(
            luaL_Reg(
                name=0,
                func=ctypes.cast(0, lua_CFunction),
            )
        )

        libs_ptr = (luaL_Reg * len(libs))(*libs)

        return self.lua.luaL_register(self.state, libname_c, ctypes.cast(libs_ptr, ctypes.POINTER(luaL_Reg)))

    def tolstring(self, idx: int) -> str:
        c_size_t = ctypes.c_size_t()
        value = self.lua.lua_tolstring(self.state, idx, ctypes.byref(c_size_t))
        if value is None:
            return ""
        return value.decode("utf-8")

    def register_package_loader(self, loader: Callable[[str], bytes]) -> None:
        @lua_CFunction
        def loader_handler(l_state: ctypes.c_void_p) -> int:
            c_size_t = ctypes.c_size_t()
            value = self.lua.lua_tolstring(l_state, 1, ctypes.byref(c_size_t))
            filename = value.decode("utf-8")
            raw = loader(filename)
            if raw:
                self.lua.lua_pushlstring(l_state, raw, len(raw))
            return 1

        # Register the loader handler function
        functions = [
            luaL_Reg(
                name="loader".encode("utf-8") + b"\x00",
                func=loader_handler,
            )
        ]
        self.register(functions, "python")

        # Insert the custom loader into package.loaders or package.searchers table
        self.loadstring(
            """
            loadfile = function(modulename)
                print("Loading module", modulename)
                -- call python
                local result = python.loader(modulename)
                if type(result) == "string" and #result > 0 then
                    -- Compile and return the module
                    return assert(loadstring(result, modulename))
                end
                return "Failed to load module " .. modulename .. " from Python"
            end
            -- Install the loader so that it's called just before the normal Lua loader
            table.insert(package.loaders, 2, loadfile)
            """
        )
        self.pcall(0, 0, 0)

    # def register_io_handler(self, handler):
    #     # io:open(filename, mode) -> file
    #     # io.open(Util.MakePath(name), "rb", "r"
    #     # file:read(*all, *a) -> string?
    #     # file:close
    #     # file:lines() -> string[]
    #     # file:gsub
    #     # file:find
    #     # file:write(str)
    #     self.loadstring(
    #         """
    #     io:open = function(filename, mode)
    #         ref = python.io_open(filename, mode)
    #         if ref == nil then
    #             return nil
    #         end
    #         local file = {}
    #         file.ref = ref
    #         file.read = function(self, ...)
    #             return python.io_read(self.ref, ...)
    #         end
    #         file.close = function(self)
    #             python.io_close(self.ref)
    #         end
    #         file.lines = function(self)
    #             return python.io_lines(self.ref)
    #         end
    #         file.write = function(self, str)
    #             python.io_write(self.ref, str)
    #         end
    #         file.gsub = function(self, ...)
    #             return python.io_gsub(self.ref, ...)
    #         end
    #         file.find = function(self, ...)
    #             return python.io_find(self.ref, ...)
    #         end
    #         return file
    #     end
    #     """
    #     )


def register_lua_functions(lua: ctypes.CDLL) -> None:
    # lua_State *luaL_newstate (void);
    lua.luaL_newstate.argtypes = []
    lua.luaL_newstate.restype = ctypes.c_void_p

    # void luaL_openlibs (lua_State *L);
    lua.luaL_openlibs.argtypes = [ctypes.c_void_p]
    lua.luaL_openlibs.argtypes = [ctypes.c_void_p]

    # int luaL_loadstring (lua_State *L, const char *s);
    lua.luaL_loadstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lua.luaL_loadstring.restype = ctypes.c_int

    lua.luaL_loadfile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lua.luaL_loadfile.restype = ctypes.c_int

    # luaLS_loadbuffer(lua_State *L, const char *buff, int sz, const char *name)
    lua.luaLS_loadbuffer.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
    ]
    lua.luaLS_loadbuffer.restype = ctypes.c_int

    # int lua_pcall (lua_State *L, int nargs, int nresults, int errfunc);
    lua.lua_pcall.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
    ]

    # int lua_dump (lua_State *L, lua_Writer writer, void *data)
    # lua.lua_dump.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    # lua.lua_dump.restype = ctypes.c_int

    # lua.luaZ_read.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
    # lua.luaZ_read.restype = ctypes.c_size_t

    # Define luaL_register prototype
    lua.luaL_register.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.POINTER(luaL_Reg),
    ]
    lua.luaL_register.restype = None

    lua.lua_tolstring.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    lua.lua_tolstring.restype = ctypes.c_char_p

    lua.lua_getfield.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p]
    lua.lua_getfield.restype = ctypes.c_int

    lua.lua_remove.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lua.lua_remove.restype = None

    lua.lua_pushinteger.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lua.lua_pushinteger.restype = None

    lua.lua_pushstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lua.lua_pushstring.restype = None

    lua.lua_pushlstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
    lua.lua_pushlstring.restype = None

    # lua.lua_pushcfunction.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    # lua.lua_pushcfunction.restype = None

    lua.lua_rawset.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lua.lua_rawset.restype = None

    # lua.lua_pop.argtypes = [ctypes.c_void_p, ctypes.c_int]
    # lua.lua_pop.restype = None

    lua.lua_remove.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lua.lua_remove.restype = None

    lua.luaL_error.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lua.luaL_error.restype = ctypes.c_int
