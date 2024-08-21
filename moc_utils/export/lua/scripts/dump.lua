require("patch")
require("export")

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

-- function coroutine.create(func)
--     print("Creating coroutine")
--     print("func", func)
--     return func
-- end

-- function coroutine.resume(func, ...)
--     print("Resuming coroutine")
--     print("func", func)
--     if func == nil then
--         return false, "cannot resume dead coroutine"
--     end
--     return true, false
-- end

-- function coroutine.yield(val)
--     print("Yielding coroutine")
--     return val
-- end

for i = 1, 100 do
    if not require("db/db_template" .. tostring(i)) then
        break
    end
end

require("common/DataUtil")
require("Game/GameTranslation")
require("db/DBLoader")
require("db/DBTemplateLua")
require("db/DBTemplateLuaExtra")

Database.DBTemplateLoader.loadLua2 = Database.DBTemplateLoader.loadLua

Database.db_loader.Global = {}
Database.db_loader.load(false, true)
Database.db_loader.post_load(true)

-- print(#Database.db_loader.Global)
for k, v in pairs(Database.db_loader.Global) do
    print(k, v)
    if k == "LuaCodes" or k == "LuaFuncs" or v == nil then
    else
        export_table("db", k, v)
        -- if pcall(export_table, "db", k, v) then
        --     print("Exported " .. k)
        -- else
        --     print("Failed to export " .. k)
        -- end
    end
end

-- for k, v in pairs(Database.db_loader.Global.trans_tables) do
--     print(k, v)
--     if k == "LuaCodes" or k == "LuaFuncs" or v == nil then
--     else
--         export_table("loc_" .. Localization, k, v)
--         --     print("Exported " .. k)
--         -- else
--         --     print("Failed to export " .. k)
--         -- end
--     end
-- end
