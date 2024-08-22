Global = _G

-- implement String.Split used by DBTemplateLua
String = {
    Split = function(inputstr, sep)
        if sep == nil then
            sep = "%s"
        end
        local t = {}
        for str in string.gmatch(inputstr, "([^" .. sep .. "]+)") do
            table.insert(t, str)
        end
        return t
    end

}

-- implement DataUtil.MakePath used by DBLoader for db_lua.bytes
Util = {
    MakePath = function(path)
        return ASSET_DIR .. "\\" .. path
    end
}

-- implement printerror used in metatables
function printerror(err)
    print("Error: " .. err)
end

-- implement various globals
UnityEngine = {
    Application = {
        platform = "None",
    },
    RuntimePlatform = {
        WindowsPlayer = nil,
        WindowsEditor = nil,
        OSXPlayer = nil,
        Android = nil,
        IPhonePlayer = nil,
    },
    Debug = {
        Log = function(msg)
            print("Debug: " .. msg)
        end,
        LogError = function(msg)
            print("Error: " .. msg)
        end,
        LogWarning = function(msg)
            print("Warning: " .. msg)
        end,
    }
}

Global._USE_DEBUG = true
Global.Translation = "none" -- id
Database = Database or {}
protos = protos or {}
battle = battle or {}
Game = {
    BATTLE_SERVER = false,
    DataUtil = {
        getText = function(v)
            return tostring(v)
        end,
        global_params = {}
    },
    HandlerBase = {
        TipTexts = {}
    },
    OPERATING_AREA = OperatingArea
}
Online = Online or {}
Battle = Battle or {}
Model = {
    Skill = {
        AttackMethod = {

        }
    }
}
Handler = Handler or {}
Editor = Editor or {}
Debug = Debug or {}
Logger = {
    Log = function(msg)
        print("Log: " .. msg)
    end,
}

-- patch loadfile to fix the lua path
-- implemented in the lua_handler
-- local _loadfile = loadfile
-- function loadfile(path)
--     local split = String.Split(path, "/")

--     if #split > 1 then
--         split[1] = split[1]:lower()

--         path = table.concat(split, "\\")
--         if path == "dbtemplat\\b_loader" then
--             path = "db\\DBLoader"
--         end
--         if path == "dbtemplate/BTemplateLoader" then
--             path = "db\\DBTemplateLoader"
--         end
--     end

--     return _loadfile(path)
-- end

-- patch require to fix the lua path
-- local _require = require
-- function require(str)
--     local split = String.Split(str, "/")

--     if #split == 1 then
--         return _require(str)
--     end

--     split[1] = split[1]:lower()

--     local path = table.concat(split, "\\")
--     if path == "dbtemplate/b_loader" then
--         path = "db/DBLoader"
--     end
--     if path == "dbtemplate/BTemplateLoader" then
--         path = "db/DBTemplateLoader"
--     end
--     return _require(path)
-- end


require("util/async")
require("util/base64")
-- class = require("util/cs_cs_class")
function class(name)
    return setmetatable({}, {
        __index = function(t, k)
            local raw = rawget(t, k)
            if raw then
                return raw
            end
            local v = {}
            rawset(t, k, v)
            return v
        end,
    })
end

Util2 = {
    SetGlobalTextsAndQuotes = function(_ids, _texts, _tips)
        print("TODO: Util2.SetGlobalTextsAndQuotes")
    end,
    SetGlobalScenarioTexts = function(_ids, _texts)
        print("TODO: Util2.SetGlobalScenarioTexts")
    end
}

require("util/cs_cs_dump")
require("util/cs_cs_index")
require("util/cs_cs_newindex")
require("util/cs_cs_pcall")
require("util/cs_cs_resume")
require("util/cs2lua__lualib")
require("util/TimeUtil")

require("battle/Logic_Speciality")


function TimeUtil.SocketGetTimeFunc()
    return os.time
end