require("patch")
require("export")

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

function convertMetaParamIndexToNormalTable(key, data)
    local structure = {}
    for k, v in pairs(Database["_" .. key].param_index) do
        structure[v] = k
    end
    local new_data = {}
    for i, v in pairs(data) do
        local new_v = {}
        for dk, dv in pairs(v) do
            -- if key is a number, then try to get the key from the structure
            local dkey = type(dk) == "number" and dk <= #structure and structure[dk] or dk
            -- if value is a table, then only keep the ids
            local dvalue = dv
            if type(dvalue) == "table" then
                for vk, vv in pairs(dvalue) do
                    if type(vv) == "table" then
                        dvalue[vk] = vv.id or vv
                    end
                end
            end 
            new_v[dkey] = dvalue
        end
        new_data[new_v.id or i] = new_v
    end
    return new_data
end


local neatjson = require("neatjson")
local json_options = {{
    wrap = true,
    sort = function(k) return tonumber(k) or k end,
}}

for k, v in pairs(Database.db_loader.Global) do
    print(k, v)
    if k == "LuaCodes" or k == "LuaFuncs" or v == nil then
    else
        print("Dumping " .. k)
        local string = ""
        if Database["_" .. k] then
            string = neatjson(convertMetaParamIndexToNormalTable(k, v),  json_options)
        else
            string=neatjson(v, json_options)
        end
        local fp = EXPORT_DIR .. "/" .. k .. ".json"
        local file = io.open(fp, "w")
        file:write(string)
        file:close()
    end
end
