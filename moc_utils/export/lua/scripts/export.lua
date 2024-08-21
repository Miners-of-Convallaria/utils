local escape_char_map = {
    ["\\"] = "\\",
    ["\""] = "\"",
    ["\b"] = "b",
    ["\f"] = "f",
    ["\n"] = "n",
    ["\r"] = "r",
    ["\t"] = "t",
}

local function escape_char(c)
    return "\\" .. (escape_char_map[c] or string.format("u%04x", c:byte()))
end

local function is_array(t)
    local i = 0
    for _ in pairs(t) do
        i = i + 1
        if t[i] == nil then return false end
    end
    return true
end


local function value_to_string(v)
    if type(v) == "string" then
        return '\"' .. v:gsub('[%z\1-\31\\"]', escape_char) .. '\"'
    end
    if (type(v) == "number") then
        return tostring(v)
    end
    if (type(v) == "boolean") then
        return v and "true" or "false"
    end
    if type(v) == "nil" then
        return "null"
    end
    if type(v) == "table" then
        if is_array(v) then
            local table_values = {}
            for i, tv in ipairs(v) do
                if type(tv) == "table" then
                    table.insert(table_values, i, value_to_string(tv.id or tv))
                else
                    table.insert(table_values, i, value_to_string(tv))
                end
            end
            return "[" .. table.concat(table_values, ", ") .. "]"
        else
            local ret = {}
            for k, vv in pairs(v) do
                if type(vv) == "table" then
                    table.insert(ret, value_to_string(k) .. ": " .. value_to_string(vv.id or vv))
                else
                    table.insert(ret, value_to_string(k) .. ": " .. value_to_string(vv))
                end
            end
            return "{" .. table.concat(ret, ", ") .. "}"
        end
    end
    return "\"unimplemented type" .. type(v) .. "\""
end

function export_table(ttype, name, data)
    local fp = EXPORT_DIR .. "\\" .. "\\" .. name .. ".json"
    print("Exporting to " .. fp)
    local file = io.open(fp, "w")
    if not file then
        print("Failed to open file")
        return
    end

    print("Exporting " .. name)
    if not Database["_" .. name] then
        file:write("{")
        for dk, dv in pairs(data) do
            file:write("\n  \"" .. tostring(dk) .. "\": ")
            file:write(value_to_string(dv))
            if next(data, dk) then
                file:write(",")
            end
        end
        file:write("\n}")
    else
        local structure = {}
        for k, v in pairs(Database["_" .. name].param_index) do
            structure[v] = k
        end

        file:write("[")
        for dk, dv in pairs(data) do
            -- print(dk)
            file:write("\n  {")
            for ek, ev in pairs(dv) do
                local key = type(ek) == "number" and ek <= #structure and structure[ek] or ek
                file:write("\n    \"" .. key .. "\": ")
                file:write(value_to_string(ev))
                if next(dv, ek) then
                    file:write(",")
                end
            end
            file:write("\n  }")
            if next(data.datas, dk) then
                file:write(",")
            end
            file:flush()
        end
        file:write("\n]")
    end
    file:close()
end
