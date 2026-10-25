-- Stellar Eve outfit runtime part. Every Eve outfit replaces one default-look body part (OUTFITS below) with the whole
-- Eve outfit. For every character that wears one -- the master player AND the separate menu / equipment-preview model:
--  * joints: every joint's local position is set to that outfit's Eve proportions (its json, build_eve_outfit.py) at the
--    UpdateMotion entry, BEFORE the motion runs (method of LUA Bone System by VALIS); root / COG are left to the game
--    (riding the Seikret moves COG onto the saddle).
--  * face: the Player_Face mesh is swapped to Eve's head (stellar/eve27/face/eve27_face.mesh, build_eve_face.py), checked
--    every second and swapped again if the game put the hunter face back; the hunter hairstyle (ch01_*) is hidden; the
--    game's face material values that turned the face black are reset.
--  * slinger: the game's own (the drone slinger was dropped on 10-20: it needed UModel).
--  * body part: the game's equipment VFX blend (pink rim) is switched off.
--  * the same armour's other parts (head / arms / waist / legs) and other armours' arms / body / waist / legs: hidden, physics off (hide_parts).
-- Any other armour: original joints, face, hair and parts are restored.
-- REFramework panel: "Stellar Eve outfit" (on / off).

local OUTFITS = {
    ch03_002_1012 = "stellar-eve/ocean_maid_joints.json",     -- outfit beta type 2: Ocean Maid (CH_P_EVE_27)
    ch03_002_1002 = "stellar-eve/wave_bikini_joints.json",    -- outfit beta type 1: Wave Diver Bikini (CH_P_EVE_63)
    ch03_066_0012 = "stellar-eve/racers_high_joints.json",    -- Mizutsune beta body part: Racer's High (CH_P_EVE_41), split by part
    ch03_021_3012 = "stellar-eve/daily_mascot_joints.json",   -- Rey Dau gamma body part: Daily Mascot (CH_P_EVE_18), split by part
    ch03_027_3012 = "stellar-eve/moran_joints.json",          -- Nu Udra gamma body part: Moran with stockings (CH_P_EVE_34_body), split by part
}
-- night batch (10-18): more outfits from data/stellar-eve/outfits_auto.json, written by make_eve_auto.py:
-- {"outfits": {body_part: joints_json}, "chainFix": {body_part: chain2_path}, "hidePhys": [part names]}
local AUTO = json.load_file("stellar-eve/outfits_auto.json")
if type(AUTO) ~= "table" then AUTO = {} end
for part, file in pairs(AUTO.outfits or {}) do OUTFITS[part] = file end
local JOINTS = {}
for part, file in pairs(OUTFITS) do JOINTS[part] = json.load_file(file) end
-- only what is installed (10-20: each default look is its own download): without its joints file a part stays the
-- game's own and is not treated as an Eve outfit
for part in pairs(OUTFITS) do if type(JOINTS[part]) ~= "table" then OUTFITS[part] = nil; JOINTS[part] = nil end end
local FACE_MESH, FACE_MDF = "stellar/eve27/face/eve27_face.mesh", "stellar/eve27/face/eve27_face.mdf2"
local enabled = true
local PM = nil
local tick = 0
local targets = {}          -- key -> per-character state
local status = { loaded = next(OUTFITS) ~= nil, wearing = false, joints = 0, face = false, err = nil, targets = 0 }

local function holder(rtype, path)
    local r = sdk.create_resource(rtype, path)
    if not r then return nil end
    r = r:add_ref()
    return r:create_holder(rtype .. "Holder"):add_ref()
end
-- created once at script start (creating them during a load left parts without materials in earlier tests)
local eveMesh = holder("via.render.MeshResource", FACE_MESH)
local eveMdf = holder("via.render.MeshMaterialResource", FACE_MDF)
-- per-outfit faces (10-25, Scarlet: another Stellar Blade character with her own face): outfits_auto.json
-- "faces": {body part: {mesh = path, mdf = path}}; every other outfit gets Eve's face. Holders made here at start, too.
local FACE_HOLDERS = { [FACE_MESH] = { eveMesh, eveMdf } }
local FACES = {}
for part, f in pairs(AUTO.faces or {}) do
    if OUTFITS[part] and type(f) == "table" and f.mesh and f.mdf then
        FACES[part] = f.mesh
        if not FACE_HOLDERS[f.mesh] then FACE_HOLDERS[f.mesh] = { holder("via.render.MeshResource", f.mesh), holder("via.render.MeshMaterialResource", f.mdf) } end
    end
end
local function face_for(part) return FACES[part] or FACE_MESH end
local function is_mod_face(path) return path:find("stellar/", 1, true) ~= nil end   -- every face we ship lives under stellar/

local function comp(go, t) return go and go:call("getComponent(System.Type)", sdk.typeof(t)) end

local function master_transform()
    PM = PM or sdk.get_managed_singleton("app.PlayerManager")
    if not PM then return nil end
    local master = PM:getMasterPlayer()
    if not master then return nil end
    local info = master:get_field("<Character>k__BackingField")
    if not info or not info:get_IsSetUp() then return nil end
    local obj = master:get_Object()
    return obj and comp(obj, "via.Transform")
end

local function children(tr)
    local out, child = {}, tr:get_Child()
    while child do out[#out + 1] = child; child = child:get_Next() end
    return out
end

local function wearing(tr)      -- the Eve outfit body part this character wears, or nil
    -- two Eve parts at once (an Eve body + the Diver waist, which is a whole Eve too): the body slot wins, the other one
    -- is hidden like any other armour part (hide_parts)
    local found = nil
    for _, c in ipairs(children(tr)) do
        local go = c:get_GameObject()
        local nm = go and go:get_Name() or ""
        for part in pairs(OUTFITS) do
            if nm:find(part, 1, true) then
                if part:sub(13, 13) == "2" then return part end
                found = found or part
            end
        end
    end
    return found
end

-- weapon joints stay at the hunter's values (10-20, game test with the great sword: overriding R_Wep / L_Wep / *_Wep_Sub with
-- Eve's positions dropped the drawn-weapon arm pose -- hands hung at the hips, the sword hilt between the legs; with them
-- left alone the hold matches the hunter's)
local SKIP = { root = true, COG = true, R_Wep = true, L_Wep = true, R_Wep_Sub = true, L_Wep_Sub = true }
local WEP_OFFSET = { 0.0, 0.0, 0.0 }
local WEP_JOINTS = { R_Wep = true, R_Wep_Sub = true }
-- test switch (10-18, user: the great sword sat right in the hand while the hunter proportions were on): keep the HUNTER's
-- arm chain (shoulder, upper arm, forearm, hand) so the hands -- and the weapon -- land where the hunter animations expect
local ARM_JOINTS = { "L_Shoulder", "L_UpperArm", "L_Forearm", "L_Hand", "R_Shoulder", "R_UpperArm", "R_Forearm", "R_Hand" }
local hunter_arms = false
local SKIP_PAT = {}   -- diagnostics (10-20): control.json skipJoints = name substrings left at the hunter's value
local function skip(name)
    if SKIP[name] then return true end
    for _, pat in ipairs(SKIP_PAT) do if name:find(pat, 1, true) then return true end end
    if hunter_arms then for _, a in ipairs(ARM_JOINTS) do if a == name then return true end end end
    return false
end

local function build_list(tr, joints)
    local list, original = {}, {}
    for name, p in pairs(joints or {}) do
        local j = (not skip(name)) and tr:getJointByName(name) or nil
        if j then
            list[#list + 1] = { j = j, v = Vector3f.new(p.x, p.y, p.z) }
            original[#original + 1] = { j = j, v = j:get_LocalPosition(), name = name }
        end
    end
    return list, original
end

local function restore_joints(st)
    if st.original then
        for _, e in ipairs(st.original) do pcall(function() e.j:set_LocalPosition(e.v) end) end
    end
    st.applied = false
end

local function face_mesh_component(tr)
    local f = tr:find("Player_Face")
    return f and comp(f:get_GameObject(), "via.render.Mesh")
end

-- the hairstyle object (ch01_*) hangs below the character transform at some depth: search the tree.
-- The hair mesh's Enabled belongs to the GAME (it sets it per helm when the armour changes): we never write it.
-- 10-20 (user): forcing it on gave helms with built-in hair a second hair; putting back a value read under the Eve
-- outfit's helm (hair off) left every later headpiece bald. Under Eve the hair objects are hidden with DrawSelf, which
-- the game does not touch, and shown again the same way. Helm _DispOffHear* params: remembered per param object before
-- we change them and put back after.
local HELM_ORIG = {}
local function set_hair(st, visible)
    local found = {}
    st.hairMeshes = {}
    local function walk(t, depth)
        local child = t:get_Child()
        while child do
            local go = child:get_GameObject()
            local name = go and go:get_Name() or ""
            if name:sub(1, 5) == "ch01_" then
                go:set_DrawSelf(visible)
                if not visible then st.hairMeshes[#st.hairMeshes + 1] = go end
                found[#found + 1] = name
            elseif depth < 6 then
                local hac = comp(go, "app.HairAdjustController")
                if hac then pcall(function()
                    local hp = hac:get_field("_HelmParam")
                    if hp then
                        local key = tostring(hp)
                        if not visible then
                            if HELM_ORIG[key] == nil then HELM_ORIG[key] = { hp:get_field("_DispOffHear"), hp:get_field("_DispOffHearOtherParts0"), hp } end
                            hp:set_field("_DispOffHear", true); hp:set_field("_DispOffHearOtherParts0", true)
                        elseif HELM_ORIG[key] ~= nil then
                            hp:set_field("_DispOffHear", HELM_ORIG[key][1]); hp:set_field("_DispOffHearOtherParts0", HELM_ORIG[key][2])
                            HELM_ORIG[key] = nil
                        end
                        found[#found + 1] = "HAC:" .. name
                    end
                end) end
                walk(child, depth + 1)
            end
            child = child:get_Next()
        end
    end
    walk(st.tr, 0)
    if visible then
        -- helm params of parts already taken off (the armour change replaces the parts before we notice): put them back
        -- too, the param object can be shared by every later use of that helm
        for key, o in pairs(HELM_ORIG) do
            pcall(function() o[3]:set_field("_DispOffHear", o[1]); o[3]:set_field("_DispOffHearOtherParts0", o[2]) end)
            HELM_ORIG[key] = nil
        end
    end
    if st.master then status.hair = found end
end

local ONE3 = Vector3f.new(1, 1, 1)
local FX_FAR, FX_TINY = Vector3f.new(0, -500, 0), Vector3f.new(0.0001, 0.0001, 0.0001)
local function fix_head_scale(st)
    if not st.swapped then return end
    local f = st.tr:find("Player_Face")
    if f ~= st.hsTr then st.hsTr = f; st.hsJ = f and f:getJointByName("HeadAll_SCL") or nil end
    -- the joint goes stale when the face mesh is rebuilt (armour change): every failed read is an error line in the
    -- REFramework log (10-20 reinstall test: 60+ per second), so drop it and look it up again a second later
    if st.hsJ and (st.hsWait or 0) <= tick then
        local ok, sc = pcall(function() return st.hsJ:get_LocalScale() end)
        if not ok then st.hsTr, st.hsJ, st.hsWait = nil, nil, tick + 60; return end
        if math.abs(sc.x - 1) > 1e-3 or math.abs(sc.y - 1) > 1e-3 or math.abs(sc.z - 1) > 1e-3 then
            st.hsJ:set_LocalScale(ONE3)
            if st.master then status.headScaleFixed = sc.x end
        end
    end
end


local function face_still_eve(st)
    local m = face_mesh_component(st.tr)
    if m == nil or m ~= st.mesh then return false end
    local ok, path = pcall(function() return m:call("getMesh"):call("get_ResourcePath") end)
    if ok and type(path) == "string" and path ~= "" then return path:find((st.faceKey or FACE_MESH):match("([^/]+)%.mesh$"), 1, true) ~= nil end
    return true
end

-- 10-20 (user: after an Eve outfit, NORMAL armour showed a different, plain face): putting the base face mesh / mdf back
-- by path loses what character creation set on the hunter's face -- the Player_Face joints (face shape, HeadAll_SCL head
-- size, which fix_head_scale forces to 1 under Eve) and the face material values (skin, make-up colours). Read them
-- once while the hunter face is still on, keep them per character (master also in a file, for Reset Scripts), and
-- write them back for a while after the hunter mesh is restored (the joint set is rebuilt a frame later).
-- Where the hunter face comes from (game test 10-20): NOT from the moment of the swap -- while a save loads, the character
-- gets Eve's face before the game has put the customization on (the read gave the mdf defaults: brown eyes, no make-up,
-- FaceBlend 0). Instead the master's face is snapshot while the game alone has set it: hunter mesh on, at least 10 s
-- after the character appeared, and that face component never swapped / restored by us (TOUCHED). Kept in memory and in
-- data/stellar-eve/hunter_face_state.json, so a session that starts in an Eve outfit uses the last good snapshot.
local HUNTER_FACE = nil
local TOUCHED = setmetatable({}, { __mode = "k" })
local function v3t(v) return { v.x, v.y, v.z } end
local function v4t(v) return { v.x, v.y, v.z, v.w } end
local function read_face_state(m, ftr)
    local s = { joints = {}, mats = {} }
    pcall(function()
        for _, j in ipairs(ftr:call("get_Joints"):get_elements()) do
            local n = j:call("get_Name")
            if n then s.joints[n] = { p = v3t(j:get_LocalPosition()), r = v4t(j:get_LocalRotation()), s = v3t(j:get_LocalScale()) } end
        end
    end)
    pcall(function()
        for mi = 0, (m:call("get_MaterialNum") or 0) - 1 do
            local vars = {}
            for vi = 0, (m:call("getMaterialVariableNum", mi) or 0) - 1 do
                pcall(function()
                    local t = m:call("getMaterialVariableType", mi, vi)
                    local name = tostring(m:call("getMaterialVariableName", mi, vi))
                    if t == 1 then vars[name] = m:call("getMaterialFloat", mi, vi)
                    elseif t == 2 or t == 3 or t == 4 then vars[name] = v4t(m:call("getMaterialFloat4", mi, vi)) end
                end)
            end
            s.mats[tostring(m:call("getMaterialName", mi))] = vars
        end
    end)
    return s
end

local function write_face_state(st)
    local s, m = HUNTER_FACE, st.restoreMesh
    if not s or not m then return end
    local ftr = st.tr:find("Player_Face")
    if ftr then
        for name, e in pairs(s.joints) do
            local j = ftr:getJointByName(name)
            if j then pcall(function()
                local p = j:get_LocalPosition(); p.x, p.y, p.z = e.p[1], e.p[2], e.p[3]; j:set_LocalPosition(p)
                local r = j:get_LocalRotation(); r.x, r.y, r.z, r.w = e.r[1], e.r[2], e.r[3], e.r[4]; j:set_LocalRotation(r)
                local sc = j:get_LocalScale(); sc.x, sc.y, sc.z = e.s[1], e.s[2], e.s[3]; j:set_LocalScale(sc)
            end) end
        end
    end
    pcall(function()
        for mi = 0, (m:call("get_MaterialNum") or 0) - 1 do
            local vars = s.mats[tostring(m:call("getMaterialName", mi))]
            if vars then
                for vi = 0, (m:call("getMaterialVariableNum", mi) or 0) - 1 do
                    local want = vars[tostring(m:call("getMaterialVariableName", mi, vi))]
                    if type(want) == "table" then pcall(function() m:call("setMaterialFloat4", mi, vi, Vector4f.new(want[1], want[2], want[3], want[4])) end)
                    elseif want ~= nil then pcall(function() m:call("setMaterialFloat", mi, vi, want) end) end
                end
            end
        end
    end)
end

local function snapshot_face(st)
    if not st.master or tick - (st.born or tick) < 600 then return end
    local m = face_mesh_component(st.tr)
    if not m or TOUCHED[m] then return end
    local path = nil
    pcall(function() path = m:call("getMesh"):call("get_ResourcePath") end)
    if not path or is_mod_face(path) then return end
    local ftr = st.tr:find("Player_Face")
    if not ftr then return end
    local s = read_face_state(m, ftr)
    if next(s.mats) == nil or next(s.joints) == nil then return end
    HUNTER_FACE = s
    if not st.snapSaved or tick - st.snapSaved > 18000 then
        json.dump_file("stellar-eve/hunter_face_state.json", s); st.snapSaved = tick
    end
    status.faceSnap = tick
end

local function swap_face(st)
    local m = face_mesh_component(st.tr)
    local key = face_for(st.wearing)
    local h = FACE_HOLDERS[key]
    if not h or not h[1] or not h[2] then key = FACE_MESH; h = FACE_HOLDERS[FACE_MESH] end
    if not m or not h[1] or not h[2] then return false end
    if not HUNTER_FACE then
        local f = json.load_file("stellar-eve/hunter_face_state.json")
        if type(f) == "table" and type(f.joints) == "table" and type(f.mats) == "table" then HUNTER_FACE = f; status.faceStateFromFile = true end
    end
    TOUCHED[m] = true
    -- remember the hunter face by resource PATH and make our own referenced holders for it: keeping the raw getMesh()
    -- object and handing it back later crashed the game (10-18, access violation in Mesh.setMesh when switching Eve off)
    if not st.origMeshPath then
        pcall(function() st.origMeshPath = m:call("getMesh"):call("get_ResourcePath") end)
        pcall(function() st.origMdfPath = m:call("get_Material"):call("get_ResourcePath") end)
        if st.origMeshPath and is_mod_face(st.origMeshPath) then st.origMeshPath = nil end
        if st.origMdfPath and is_mod_face(st.origMdfPath) then st.origMdfPath = nil end
        -- 10-18: after Reset Scripts with an Eve outfit on, the face read here is already Eve's, so the hunter face could
        -- not be restored later (Eve's face stayed on normal armour). Keep the hunter face paths in a file: saved
        -- whenever they are read cleanly, used when they are not.
        if st.origMeshPath and st.origMdfPath then
            json.dump_file("stellar-eve/hunter_face.json", { mesh = st.origMeshPath, mdf = st.origMdfPath })
        else
            local f = json.load_file("stellar-eve/hunter_face.json")
            if type(f) == "table" and f.mesh and f.mdf then st.origMeshPath, st.origMdfPath = f.mesh, f.mdf; status.faceFromFile = true end
        end
    end
    m:setMesh(h[1]); m:set_Material(h[2]); m:set_Enabled(true)
    set_hair(st, false)
    st.mesh = m; st.swapped = true; st.faceKey = key
    return true
end

local function restore_face(st)
    if st.mesh and st.origMeshPath and st.origMdfPath then
        pcall(function()
            local hm = holder("via.render.MeshResource", st.origMeshPath)
            local hd = holder("via.render.MeshMaterialResource", st.origMdfPath)
            if hm and hd then st.mesh:setMesh(hm); st.mesh:set_Material(hd); st.keep = { hm, hd } end
        end)
        st.restoreMesh = st.mesh; st.restoreUntil = tick + 120
    end
    set_hair(st, true)
    st.swapped = false; st.mesh = nil
end

-- the game turns on an equipment-only VFX material blend for the body part (pink rim on hair strands, lace, outline)
local function vfx_off(st)
    for _, c in ipairs(children(st.tr)) do
        local go = c:get_GameObject()
        if go and st.wearing and go:get_Name():find(st.wearing, 1, true) then
            local m = comp(go, "via.render.Mesh")
            if m then pcall(function()
                for mi = 0, (m:call("get_MaterialNum") or 0) - 1 do
                    for vi = 0, (m:call("getMaterialVariableNum", mi) or 0) - 1 do
                        if m:call("getMaterialVariableName", mi, vi) == "Enable_VFXMaterialBlend"
                            and (m:call("getMaterialFloat", mi, vi) or 0) ~= 0 then m:call("setMaterialFloat", mi, vi, 0.0) end
                    end
                end
            end) end
        end
    end
end

-- the game writes the hunter's face material values into Eve's face (ColorParam 0.15 grey ...) -> black face: reset them
local FACE_KEEP = { ColorParam = { 1.0, 1.0, 1.0, 1.0 }, ObjectOffset = { 0.0, 0.0, 0.0, 0.0 }, Wet_Roughness = 0.25 }
local function face_fix(st)
    local m = st.mesh
    if not m then return end
    pcall(function()
        for mi = 0, (m:call("get_MaterialNum") or 0) - 1 do
            for vi = 0, (m:call("getMaterialVariableNum", mi) or 0) - 1 do
                local want = FACE_KEEP[tostring(m:call("getMaterialVariableName", mi, vi))]
                if type(want) == "table" then
                    local f = m:call("getMaterialFloat4", mi, vi)
                    if f and (math.abs(f.x - want[1]) + math.abs(f.y - want[2]) + math.abs(f.z - want[3]) + math.abs(f.w - want[4])) > 1e-3 then
                        m:call("setMaterialFloat4", mi, vi, Vector4f.new(want[1], want[2], want[3], want[4]))
                        status.faceFix = (status.faceFix or 0) + 1; status.faceFixLast = tick
                    end
                elseif want then
                    local v = m:call("getMaterialFloat", mi, vi)
                    if v and math.abs(v - want) > 1e-3 then
                        m:call("setMaterialFloat", mi, vi, want)
                        status.faceFix = (status.faceFix or 0) + 1; status.faceFixLast = tick
                    end
                end
            end
        end
    end)
end

local function new_state(tr, master)
    return { tr = tr, master = master, born = tick, list = nil, original = nil, applied = false, wearing = nil, swapped = false,
             mesh = nil, origMesh = nil, origMdf = nil, waitUntil = 0, hairMeshes = {} }
end

-- other characters wearing the outfit (menu / equipment preview model): found through their body part mesh
local function scan_others(mt)
    local found = {}
    local scene = sdk.call_native_func(sdk.get_native_singleton("via.SceneManager"), sdk.find_type_definition("via.SceneManager"), "get_CurrentScene")
    local list = scene and scene:call("findComponents(System.Type)", sdk.typeof("via.render.Mesh"))
    for _, m in ipairs(list and list:get_elements() or {}) do
        local go = m:get_GameObject()
        local name = go and go:get_Name() or ""
        local hit = false
        for part in pairs(OUTFITS) do if name:find(part, 1, true) then hit = true end end
        if hit then
            local p = go:get_Transform():get_Parent()
            -- only real characters (they have a Player_Face child): the equipment-change effect (11_pl_equipchange_*, armour
            -- pieces flying onto the hunter, 10-18 with Racer's High on Mizutsune beta) carries copies of the part meshes;
            -- treating those as characters left big armour pieces / sparkles floating round Eve
            local real = false
            if p and p ~= mt then
                for _, c in ipairs(children(p)) do
                    local g = c:get_GameObject()
                    if g and g:get_Name() == "Player_Face" then real = true; break end
                end
            end
            if real then found[#found + 1] = p end
        end
    end
    return found
end

-- chain fix (10-18): armour parts whose original has no chain2 file (Rey Dau gamma body) get a Chain2 component without our
-- chain2 (ponytail / bust / butt jiggle) -- the game only loads a part's chain2 when the original has one. Point that
-- component at our file once per character (status.chainFix records before / after / error).
local CHAIN_FIX = {
    ch03_021_3012 = "Art/Model/Character/ch03/021/301/2/ch03_021_3012.chain2",
    ch03_027_3012 = "Art/Model/Character/ch03/027/301/2/ch03_027_3012.chain2",
}
for part, path in pairs(AUTO.chainFix or {}) do CHAIN_FIX[part] = path end
local function chain_fix(st)
    local path = CHAIN_FIX[st.wearing]
    if not path then return end
    local rec = { part = st.wearing }
    local ok, err = pcall(function()
        local go = nil
        for _, c in ipairs(children(st.tr)) do
            local g = c:get_GameObject()
            if g and g:get_Name() == st.wearing then go = g end
        end
        if not go then rec.e = "no part"; return end
        local ch = go:call("getComponent(System.Type)", sdk.typeof("via.motion.Chain2"))
        if not ch then
            -- 10-19 (Diver alpha): parts with no chain at all have no Chain2 component -> add one
            pcall(function() ch = go:call("createComponent(System.Type)", sdk.typeof("via.motion.Chain2")) end)
            rec.created = ch ~= nil
            if not ch then rec.e = "no Chain2"; return end
        end
        local a = ch:call("get_ChainAsset")
        if a then pcall(function() rec.before = a:call("get_ResourcePath") end); rec.beforeType = a:get_type_definition():get_full_name() end
        if rec.before and rec.before:lower():find(path:lower(), 1, true) then rec.already = true; st.chainDone = true; return end
        local res = sdk.create_resource("via.motion.Chain2Resource", path)
        if not res then rec.e = "create_resource nil"; return end
        res:add_ref()
        local holder = res:create_holder(rec.beforeType or "via.motion.Chain2ResourceHolder")
        if not holder then rec.e = "create_holder nil"; return end
        holder:add_ref()
        ch:call("set_ChainAsset", holder)
        pcall(function() ch:call("restart") end)
        local a2 = ch:call("get_ChainAsset")
        if a2 then pcall(function() rec.after = a2:call("get_ResourcePath") end) end
        rec.groups = ch:call("getGroupCount")
        pcall(function() ch:call("set_Enabled", false) end)
        st.chainReenable = ch
        local cs = go:call("getComponent(System.Type)", sdk.typeof("app.ChainSetting"))
        if cs then
            local names = {}
            for _, m in ipairs(cs:get_type_definition():get_methods()) do names[#names + 1] = m:get_name() end
            rec.chainSettingMethods = names
            pcall(function()
                local f = {}
                for _, fd in ipairs(cs:get_type_definition():get_fields()) do f[#f + 1] = fd:get_name() end
                rec.chainSettingFields = f
            end)
        end
        st.chainDone = true
    end)
    if not ok then rec.e = tostring(err); st.chainDone = true end
    if st.master then status.chainFix = rec end
end

-- The other parts of an Eve outfit's armour (10-20, user): they used to be installed as one-triangle hidden meshes, so the
-- same helm / arms / waist / legs worn WITHOUT the Eve part were invisible (a helm also hid the hunter's hair: bald).
-- Now the game keeps its own files and, only while a character wears an Eve part, the parts of that same armour
-- (same "ch03_XXX_YYY" prefix: parts 1 3 4 5 and the waist extras _0 / _9) are hidden here and their cloth / chain /
-- joint-constraint physics switched off. Part 6 (slinger) stays; other armours: see part_to_hide. What we
-- switch off is remembered and switched back when the Eve part comes off.
local KEEP = {}                                  -- parts of an Eve armour that carry Eve pieces (drapes) besides the body
for _, n in ipairs(AUTO.keep or {}) do KEEP[n] = true end
local function phys_comp(t)
    return (t:find("Cloth", 1, true) or t:find("Chain", 1, true) or t:find("JointConstraints", 1, true)) and not t:find("Setting", 1, true)
end
-- 10-20 (user): an Eve outfit is a whole outfit, so OTHER armours' arms / body / waist / legs go too -- Cypurrpunk has no
-- waist part and the hunter's other waist armour showed over Eve; mixing parts of two Eve armours showed both. Other
-- armours' helms (user wants them on Eve) and every slinger stay. The default looks (innerwear, ch03_002) keep the old rule:
-- only their own innerwear parts are hidden, armour pieces worn with them stay.
local function part_to_hide(nm, st)
    if nm == st.wearing then return false end
    -- waist extras come as "ch02_XXX_YYY5_0" / "_9" (game test 10-20); they go with any armour waist
    if nm:match("^ch02_%d%d%d_%d%d%d5_") then return st.wearing:sub(1, 8) ~= "ch03_002" end
    local slot = nm:match("^ch03_%d%d%d_%d%d%d(%d)")
    if not slot or slot == "6" then return false end
    if nm:sub(1, 12) == st.wearing:sub(1, 12) then return not KEEP[nm] end
    return slot ~= "3" and st.wearing:sub(1, 8) ~= "ch03_002"
end
local function hide_parts(st)
    st.hiddenParts = st.hiddenParts or {}
    local n = 0
    for _, c in ipairs(children(st.tr)) do
        local g = c:get_GameObject()
        local nm = g and g:get_Name() or ""
        if nm == st.wearing then
            -- 10-20 (user: Ceremonial -> Harvest set swap, the whole hunter invisible): while a set changes, the new Eve
            -- body can be hidden as "another armour's body" before the next wearing() check; whatever we switched off on
            -- the part now worn goes back on
            for key, e in pairs(st.hiddenParts) do
                if e[3] == nm then
                    pcall(function()
                        if e[1]:get_type_definition():get_full_name() == "via.render.Mesh" then e[1]:set_Enabled(true) else e[1]:call("set_Enabled", true) end
                    end)
                    st.hiddenParts[key] = nil
                end
            end
            if st.physSeen then st.physSeen[nm] = nil end
        elseif part_to_hide(nm, st) then
            n = n + 1
            local m = comp(g, "via.render.Mesh")
            if m then
                local key = tostring(m)
                if st.hiddenParts[key] == nil then st.hiddenParts[key] = { m, m:get_Enabled(), nm } end
                if m:get_Enabled() then m:set_Enabled(false) end
            end
            if tick % 30 == 0 or not st.physSeen or not st.physSeen[nm] then   -- new part objects at once, then twice a second
                st.physSeen = st.physSeen or {}
                st.physSeen[nm] = true
                pcall(function()
                    for _, cp in ipairs(g:call("get_Components"):get_elements()) do
                        if phys_comp(cp:get_type_definition():get_full_name()) then pcall(function()
                            local key = tostring(cp)
                            if st.hiddenParts[key] == nil then st.hiddenParts[key] = { cp, cp:call("get_Enabled"), nm } end
                            cp:call("set_Enabled", false)
                        end) end
                    end
                end)
            end
        end
    end
    if st.master then status.partsHidden = n end
end
local function show_parts(st)
    if not st.hiddenParts then return end
    for _, e in pairs(st.hiddenParts) do
        pcall(function()
            -- always back ON: right after a load the game has the part meshes (and their physics) off for a moment, and
            -- that read was taken for the original (10-20 game test: the player's Dahaad parts stayed invisible)
            if e[1]:get_type_definition():get_full_name() == "via.render.Mesh" then e[1]:set_Enabled(true) else e[1]:call("set_Enabled", true) end
        end)
    end
    st.hiddenParts = nil; st.physSeen = nil
end

local function update(st)
    local tr = st.tr
    if tick % 120 == 61 and not st.swapped then pcall(snapshot_face, st) end
    if tick % 30 == 1 then
        local w = wearing(tr)
        if w and not st.wearing then st.waitUntil = tick + (st.master and 300 or 30) end    -- player: ~5 s after the outfit appears
        if w ~= st.wearing and st.applied then restore_joints(st); st.list = nil; st.gripJ = nil end
        if w ~= st.wearing then st.chainDone = nil; pcall(show_parts, st) end   -- outfit changed: new joint set, parts back
        st.wearing = w
    end
    if enabled and st.wearing and tick % 3 == 0 then pcall(hide_parts, st) end
    if not enabled or not st.wearing then
        if st.hiddenParts then pcall(show_parts, st) end
        if st.applied then restore_joints(st) end
        if st.swapped then restore_face(st) end
        if st.restoreUntil then
            if tick <= st.restoreUntil then pcall(write_face_state, st) else st.restoreUntil = nil; st.restoreMesh = nil end
        end
        if not st.hairShown and tick % 30 == 3 then pcall(set_hair, st, true); st.hairShown = true end
        st.epvOff = nil
        return
    end
    st.hairShown = nil
    -- armour effects (EPV) on the Eve parts (user 10-19: Afi's white flames by the head): switched off
    if tick % 30 == 11 then
        pcall(function()
            for _, c in ipairs(children(tr)) do
                local g = c:get_GameObject(); local nm = g and g:get_Name() or ""
                if nm:sub(1, 5) == "ch03_" then
                    pcall(function() for _, comp in ipairs(g:call("get_Components"):get_elements()) do
                        local t = comp:get_type_definition():get_full_name()
                        if t:find("EPVStandard", 1, true) or t:find("EPVExpert", 1, true) then pcall(function() comp:call("set_Enabled", false) end) end
                    end end)   -- own pcall: one odd component must not stop the effect children below (10-19)
                    for _, fx in ipairs(children(c)) do
                        local fg = fx:get_GameObject(); local fn = fg and fg:get_Name() or ""
                        if fn:sub(1, 3) == "11_" then
                            pcall(function() fg:set_DrawSelf(false) end)
                            local okm, em = pcall(function() local ft = fg:get_Transform(); ft:set_LocalPosition(FX_FAR); ft:set_LocalScale(FX_TINY) end)
                            if st.master then status.fxMoved = (status.fxMoved or 0) + 1; status.fxErr = (not okm) and tostring(em) or nil; status.fxLast = fn end
                            for _, comp in ipairs(fg:call("get_Components"):get_elements()) do
                                local t = comp:get_type_definition():get_full_name()
                                if t == "via.effect.EffectPlayer" then pcall(function() comp:call("set_Enabled", false) end) end
                                if t == "app.AppEffectController" then pcall(function() comp:call("forceDrawOff") end) end
                            end
                        end
                    end
                end
            end
        end)
        st.epvOff = true
    end
    local eve = true
    if JOINTS[st.wearing] then
        if not st.list then st.list, st.original = build_list(tr, JOINTS[st.wearing]); if st.master then status.joints = #st.list end end
        for _, e in ipairs(st.list) do e.j:set_LocalPosition(e.v) end
        if WEP_OFFSET[1] ~= 0 or WEP_OFFSET[2] ~= 0 or WEP_OFFSET[3] ~= 0 then
            st.wepJ = st.wepJ or { tr:getJointByName("R_Wep"), tr:getJointByName("R_Wep_Sub") }
            st.wepBase = st.wepBase or {}
            for i, j in ipairs(st.wepJ) do
                if j then
                    if not st.wepBase[i] then
                        local b = j:get_LocalPosition(); st.wepBase[i] = { b.x, b.y, b.z }
                        for _, e in ipairs(st.list) do if e.j == j then st.wepBase[i] = { e.v.x, e.v.y, e.v.z } end end
                    end
                    local v = j:get_LocalPosition()
                    v.x = st.wepBase[i][1] + WEP_OFFSET[1]; v.y = st.wepBase[i][2] + WEP_OFFSET[2]; v.z = st.wepBase[i][3] + WEP_OFFSET[3]
                    j:set_LocalPosition(v)
                end
            end
        end
        st.applied = true
    end
    if not st.chainDone and tick >= (st.waitUntil or 0) and tick % 30 == 9 then chain_fix(st) end
    if st.chainReenable and tick % 30 == 19 then
        local ch = st.chainReenable; st.chainReenable = nil
        local ok2 = pcall(function() ch:call("set_Enabled", true); ch:call("restart") end)
        if st.master and status.chainFix then status.chainFix.reenabled = ok2; pcall(function() status.chainFix.groupsAfter = ch:call("getGroupCount") end) end
    end
    if st.swapped and tick % 60 == 11 and not face_still_eve(st) then
        st.swapped = false; status.faceReswap = (status.faceReswap or 0) + 1
    end
    -- straight from one outfit to another with a different face (Eve outfit <-> Scarlet): swap again
    if st.swapped and st.faceKey ~= face_for(st.wearing) then st.swapped = false end
    if eve and st.swapped and tick >= st.waitUntil + 120 and tick % 30 == 5 then vfx_off(st) end
    if st.swapped and tick % 15 == 7 then face_fix(st) end
    if not st.swapped and tick >= st.waitUntil then
        local ok = swap_face(st)
        if st.master then status.face = ok end
    end
    if st.swapped and tick % 120 == 0 then set_hair(st, false) end
    if st.swapped then for _, go in ipairs(st.hairMeshes) do go:set_DrawSelf(false) end end
    pcall(fix_head_scale, st)
end

re.on_application_entry("UpdateMotion", function()
    local ok, err = pcall(function()
        tick = tick + 1
        local mt = master_transform()
        -- master player (a new transform after loading resets its state)
        if mt then
            local st = targets.master
            if not st or st.tr ~= mt then targets.master = new_state(mt, true) end
        else
            targets.master = nil
        end
        if tick % 180 == 90 then
            local seen = {}
            for _, p in ipairs(scan_others(mt)) do
                local key = tostring(p)
                seen[key] = true
                if not targets[key] then targets[key] = new_state(p, false) end
            end
            for key, st in pairs(targets) do
                -- a preview / menu model that took the Eve part off is kept until its parts, joints, face and hair are
                -- back (10-20: dropping it at once left the tent preview bald, with the outfit's other parts invisible)
                local busy = st.wearing or st.applied or st.swapped or st.hiddenParts or st.restoreUntil or not st.hairShown
                if key ~= "master" and not seen[key] and (not busy or (st.fails or 0) > 3) then targets[key] = nil end
            end
        end
        local n = 0
        for key, st in pairs(targets) do
            n = n + 1
            local ok2, err2 = pcall(update, st)
            if not ok2 then status.err = key .. ": " .. tostring(err2); st.list = nil; st.fails = (st.fails or 0) + 1 else st.fails = 0 end
        end
        status.targets = n
        status.wearing = targets.master and targets.master.wearing or false
        if tick % 300 == 2 then
            if mt then
                status.parts = {}
                status.partMesh = {}
                for _, c in ipairs(children(mt)) do
                    local go = c:get_GameObject()
                    if go then
                        local nm = go:get_Name(); status.parts[#status.parts + 1] = nm
                        if nm:sub(1, 5) == "ch03_" then pcall(function()
                            local m = comp(go, "via.render.Mesh")
                            status.partMesh[nm] = m and { m:get_Enabled(), go:get_DrawSelf(), m:call("getMesh"):call("get_ResourcePath") } or "no mesh"
                        end) end
                    end
                end
            end
            status.tick = tick
            json.dump_file("stellar-eve/status.json", status)
        end
    end)
    if not ok then status.err = tostring(err) end
end)

-- ---------------- two-handed grip (user 10-18: great sword, long sword, charge / switch axe -- the left hand missed the
-- handle). The hunter animations put both hands on the handle with the HUNTER's arm lengths; on Eve's shorter, narrower
-- arms the same rotations leave the left hand off the grip. After the motion (LateUpdateBehavior) the hunter's left-hand
-- pose relative to the right hand is rebuilt by FK with the hunter's own bone offsets, and Eve's left arm is solved
-- (2-bone IK, elbow kept on its current side) so her left hand takes that relative pose. Weight fades in when the
-- hunter's hands are closer than GRIP_NEAR..GRIP_FAR (hands apart = not a two-handed hold = untouched).
local grip_fix = false   -- off by default: measured 10-18, the hunter itself does not hold the great sword two-handed in its drawn idle
local GRIP_NEAR, GRIP_FAR = 0.45, 0.65
local CHAIN_L = { "L_Shoulder", "L_UpperArm", "L_Forearm", "L_Hand" }
local CHAIN_R = { "R_Shoulder", "R_UpperArm", "R_Forearm", "R_Hand" }

local function Q(e) return { w = e.w, x = e.x, y = e.y, z = e.z } end
local function V(e) return { e.x, e.y, e.z } end
local function qmul(a, b)
    return { w = a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z, x = a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
             y = a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x, z = a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w }
end
local function qinv(a) return { w = a.w, x = -a.x, y = -a.y, z = -a.z } end
local function qnorm(a) local l = math.sqrt(a.w * a.w + a.x * a.x + a.y * a.y + a.z * a.z); return { w = a.w / l, x = a.x / l, y = a.y / l, z = a.z / l } end
local function qrot(q, v)
    local r = qmul(qmul(q, { w = 0, x = v[1], y = v[2], z = v[3] }), qinv(q)); return { r.x, r.y, r.z }
end
local function vadd(a, b) return { a[1] + b[1], a[2] + b[2], a[3] + b[3] } end
local function vsub(a, b) return { a[1] - b[1], a[2] - b[2], a[3] - b[3] } end
local function vmul(a, k) return { a[1] * k, a[2] * k, a[3] * k } end
local function vdot(a, b) return a[1] * b[1] + a[2] * b[2] + a[3] * b[3] end
local function vcross(a, b) return { a[2] * b[3] - a[3] * b[2], a[3] * b[1] - a[1] * b[3], a[1] * b[2] - a[2] * b[1] } end
local function vlen(a) return math.sqrt(vdot(a, a)) end
local function vnorm(a) local l = vlen(a); if l < 1e-8 then return { 0, 0, 0 } end; return vmul(a, 1 / l) end
local function from_to(u, v)
    u = vnorm(u); v = vnorm(v); local d = vdot(u, v)
    if d < -0.9999 then
        local ax = vcross({ 1, 0, 0 }, u); if vlen(ax) < 1e-4 then ax = vcross({ 0, 1, 0 }, u) end; ax = vnorm(ax)
        return { w = 0, x = ax[1], y = ax[2], z = ax[3] }
    end
    local c = vcross(u, v); return qnorm({ w = 1 + d, x = c[1], y = c[2], z = c[3] })
end
local function nlerp(a, b, t)
    if a.w * b.w + a.x * b.x + a.y * b.y + a.z * b.z < 0 then b = { w = -b.w, x = -b.x, y = -b.y, z = -b.z } end
    return qnorm({ w = a.w + (b.w - a.w) * t, x = a.x + (b.x - a.x) * t, y = a.y + (b.y - a.y) * t, z = a.z + (b.z - a.z) * t })
end
local function set_local_rot(j, q)
    local e = j:get_LocalRotation(); e.w = q.w; e.x = q.x; e.y = q.y; e.z = q.z; j:set_LocalRotation(e)
end

-- FK of a chain from its parent frame (identity) with given local positions: position / rotation of the last joint
local function fk(joints_, hpos)
    local p, q = { 0, 0, 0 }, { w = 1, x = 0, y = 0, z = 0 }
    for _, j in ipairs(joints_) do
        p = vadd(p, qrot(q, hpos[j])); q = qmul(q, Q(j:get_LocalRotation()))
    end
    return p, q
end

local function grip(st)
    if not st.gripJ then
        st.gripJ = {}
        for _, n in ipairs(CHAIN_L) do st.gripJ[n] = st.tr:getJointByName(n) end
        for _, n in ipairs(CHAIN_R) do st.gripJ[n] = st.tr:getJointByName(n) end
        st.hunterPos = {}
        for _, e in ipairs(st.original or {}) do if e.name then st.hunterPos[e.name] = e.v end end
    end
    local J = st.gripJ
    for _, n in ipairs(CHAIN_L) do if not J[n] then return end end
    for _, n in ipairs(CHAIN_R) do if not J[n] then return end end
    -- hunter hands, both from the Spine_2 frame (L/R_Shoulder parent): hunter bone offsets + current rotations
    local hp, lj, rj = {}, {}, {}
    for _, n in ipairs(CHAIN_L) do hp[J[n]] = V(st.hunterPos[n] or J[n]:get_LocalPosition()); lj[#lj + 1] = J[n] end
    for _, n in ipairs(CHAIN_R) do hp[J[n]] = V(st.hunterPos[n] or J[n]:get_LocalPosition()); rj[#rj + 1] = J[n] end
    local hlp, hlq = fk(lj, hp)
    local hrp, hrq = fk(rj, hp)
    local dist = vlen(vsub(hlp, hrp))
    local w = math.max(0, math.min(1, (GRIP_FAR - dist) / (GRIP_FAR - GRIP_NEAR)))
    if st.master then status.gripDist = math.floor(dist * 1000 + 0.5) / 1000; status.gripW = math.floor(w * 100 + 0.5) / 100 end
    if w <= 0 then return end
    local relP = qrot(qinv(hrq), vsub(hlp, hrp)); local relQ = qmul(qinv(hrq), hlq)
    -- Eve, current world
    local R = J.R_Hand; local rq = Q(R:get_Rotation()); local rp = V(R:get_Position())
    local tgtP = vadd(rp, qrot(rq, relP)); local tgtQ = qmul(rq, relQ)
    local U, F, H = J.L_UpperArm, J.L_Forearm, J.L_Hand
    local S, E, W = V(U:get_Position()), V(F:get_Position()), V(H:get_Position())
    local qU, qF, qH = Q(U:get_Rotation()), Q(F:get_Rotation()), Q(H:get_Rotation())
    local qP = Q(J.L_Shoulder:get_Rotation())
    tgtP = vadd(W, vmul(vsub(tgtP, W), w)); tgtQ = nlerp(qH, tgtQ, w)
    local a, b = vlen(vsub(E, S)), vlen(vsub(W, E))
    local d = math.max(math.abs(a - b) + 1e-3, math.min(a + b - 1e-3, vlen(vsub(tgtP, S))))
    local u = vnorm(vsub(tgtP, S))
    local ca = math.max(-1, math.min(1, (a * a + d * d - b * b) / (2 * a * d)))
    local se = vsub(E, S); local v = vnorm(vsub(se, vmul(u, vdot(se, u))))
    if vlen(v) < 1e-6 then v = vnorm(vcross(u, { 0, 1, 0 })) end
    local E2 = vadd(S, vmul(vadd(vmul(u, ca), vmul(v, math.sqrt(1 - ca * ca))), a))
    local d1 = from_to(se, vsub(E2, S))
    local nqU = qmul(d1, qU)
    local we = qrot(d1, vsub(W, E))
    local d2 = from_to(we, vsub(vadd(S, vmul(u, d)), E2))
    local nqF = qmul(qmul(d2, d1), qF)
    set_local_rot(U, qmul(qinv(qP), nqU))
    set_local_rot(F, qmul(qinv(nqU), nqF))
    set_local_rot(H, qmul(qinv(nqF), tgtQ))
end

-- 2-bone IK of one arm (side "L" / "R") so its hand reaches tgtP with world rotation tgtQ; elbow stays on its current side
local function solve_arm(J, side, tgtP, tgtQ)
    local U, F, H = J[side .. "_UpperArm"], J[side .. "_Forearm"], J[side .. "_Hand"]
    local S, E, W = V(U:get_Position()), V(F:get_Position()), V(H:get_Position())
    local qU, qF = Q(U:get_Rotation()), Q(F:get_Rotation())
    local qP = Q(J[side .. "_Shoulder"]:get_Rotation())
    local a, b = vlen(vsub(E, S)), vlen(vsub(W, E))
    local d = math.max(math.abs(a - b) + 1e-3, math.min(a + b - 1e-3, vlen(vsub(tgtP, S))))
    local u = vnorm(vsub(tgtP, S))
    local ca = math.max(-1, math.min(1, (a * a + d * d - b * b) / (2 * a * d)))
    local se = vsub(E, S); local v = vnorm(vsub(se, vmul(u, vdot(se, u))))
    if vlen(v) < 1e-6 then v = vnorm(vcross(u, { 0, 1, 0 })) end
    local E2 = vadd(S, vmul(vadd(vmul(u, ca), vmul(v, math.sqrt(1 - ca * ca))), a))
    local d1 = from_to(se, vsub(E2, S))
    local nqU = qmul(d1, qU)
    local we = qrot(d1, vsub(W, E))
    local d2 = from_to(we, vsub(vadd(S, vmul(u, d)), E2))
    local nqF = qmul(qmul(d2, d1), qF)
    set_local_rot(U, qmul(qinv(qP), nqU))
    set_local_rot(F, qmul(qinv(nqU), nqF))
    set_local_rot(H, qmul(qinv(nqF), tgtQ))
    return vadd(S, vmul(u, d))
end

-- hand retarget (user 10-18: with Eve's narrow shoulders / short arms the great-sword hand sat INSIDE her hip and thigh):
-- the right hand is put where the HUNTER's right hand is relative to the pelvis (FK Hip -> spine -> arm with the hunter's
-- bone offsets and the current animation rotations), so a held weapon sits outside the body like on the hunter; the left
-- hand keeps the hunter's pose relative to the right hand. Weight = hand_fix (0..1).
local hand_fix = 0.0
local SPINE_R = { "Spine_0", "Spine_1", "Spine_2", "R_Shoulder", "R_UpperArm", "R_Forearm", "R_Hand" }
local SPINE_L = { "Spine_0", "Spine_1", "Spine_2", "L_Shoulder", "L_UpperArm", "L_Forearm", "L_Hand" }
local function handfix(st)
    if not st.hfJ then
        st.hfJ = {}
        for _, n in ipairs({ "Hip", "Spine_0", "Spine_1", "Spine_2", "L_Shoulder", "L_UpperArm", "L_Forearm", "L_Hand",
                             "R_Shoulder", "R_UpperArm", "R_Forearm", "R_Hand" }) do st.hfJ[n] = st.tr:getJointByName(n) end
        st.hunterPos = {}
        for _, e in ipairs(st.original or {}) do if e.name then st.hunterPos[e.name] = e.v end end
    end
    local J = st.hfJ
    for _, j in pairs(J) do if not j then return end end
    local hp, rj, lj = {}, {}, {}
    for _, n in ipairs(SPINE_R) do hp[J[n]] = V(st.hunterPos[n] or J[n]:get_LocalPosition()); rj[#rj + 1] = J[n] end
    for _, n in ipairs(SPINE_L) do hp[J[n]] = V(st.hunterPos[n] or J[n]:get_LocalPosition()); lj[#lj + 1] = J[n] end
    local hrp, hrq = fk(rj, hp)            -- in the Hip frame
    local hlp, hlq = fk(lj, hp)
    local hipP, hipQ = V(J.Hip:get_Position()), Q(J.Hip:get_Rotation())
    local w = hand_fix
    local Rnow, RnowQ = V(J.R_Hand:get_Position()), Q(J.R_Hand:get_Rotation())
    local rT = vadd(hipP, qrot(hipQ, hrp)); local rTQ = qmul(hipQ, hrq)
    rT = vadd(Rnow, vmul(vsub(rT, Rnow), w)); rTQ = nlerp(RnowQ, rTQ, w)
    local rReached = solve_arm(J, "R", rT, rTQ)
    if st.master then status.handFixMove = math.floor(vlen(vsub(rReached, Rnow)) * 1000 + 0.5) / 1000 end
    -- left hand: the hunter's pose relative to the right hand, attached to where the right hand now is
    local relP = qrot(qinv(hrq), vsub(hlp, hrp)); local relQ = qmul(qinv(hrq), hlq)
    local Lnow, LnowQ = V(J.L_Hand:get_Position()), Q(J.L_Hand:get_Rotation())
    local lT = vadd(rReached, qrot(rTQ, relP)); local lTQ = qmul(rTQ, relQ)
    lT = vadd(Lnow, vmul(vsub(lT, Lnow), w)); lTQ = nlerp(LnowQ, lTQ, w)
    solve_arm(J, "L", lT, lTQ)
end

-- diagnostics (10-18): data/stellar-eve/control.json {"enabled": bool, "grip": bool} switches from outside (re-read every
-- second), and every frame the master's FINAL hand poses (after the game's own hand IK) are recorded: left hand relative to
-- the right hand, in the right hand's frame -> status.handRel (latest) / handRelHunter (latest with the Eve outfit off).
local ctl_tick = 0
-- moving R_Wep did nothing in game (10-18): the weapon follows its own Wp_Parent / WpSub_Parent objects. Move those instead,
-- after the motion, by WP_MOVE = {right, up, forward} metres in the character's own frame.
local WP_MOVE = { 0.0, 0.0, 0.0 }   -- local: a global assignment silently failed in REFramework (10-18)
local function move_weapon(st)
    if WP_MOVE[1] == 0 and WP_MOVE[2] == 0 and WP_MOVE[3] == 0 then return end
    local rq = Q(st.tr:get_Rotation())
    local off = qrot(rq, { WP_MOVE[1], WP_MOVE[2], WP_MOVE[3] })
    for _, n in ipairs({ "Wp_Parent", "WpSub_Parent" }) do
        local t = st.tr:find(n)
        if t then
            local p = t:get_Position(); p.x = p.x + off[1]; p.y = p.y + off[2]; p.z = p.z + off[3]; t:set_Position(p)
        end
    end
end
-- hand + weapon move (10-18): moving only the weapon left the hands behind, and moving only the hands (handFix) left the
-- weapon. HAND_MOVE = {right, up, forward} metres in the character's frame moves BOTH hands by 2-bone IK (rotations kept)
-- and the weapon objects by the same offset, so the grip stays together but comes out of the body. Only while a weapon is
-- in the hand (Wp_Parent within 0.35 m of R_Hand or L_Hand), so a sheathed weapon on the back is left alone.
local HAND_MOVE = { 0.0, 0.0, 0.0 }
local function move_hands(st)
    if HAND_MOVE[1] == 0 and HAND_MOVE[2] == 0 and HAND_MOVE[3] == 0 then return end
    if not st.hmJ then
        st.hmJ = {}
        for _, n in ipairs({ "L_Shoulder", "L_UpperArm", "L_Forearm", "L_Hand", "R_Shoulder", "R_UpperArm", "R_Forearm", "R_Hand" }) do
            st.hmJ[n] = st.tr:getJointByName(n)
        end
    end
    local J = st.hmJ
    for _, j in pairs(J) do if not j then return end end
    local wp = st.tr:find("Wp_Parent")
    if not wp then return end
    -- Wp_Parent itself sits at the world origin; the weapon is its first child (e.g. it0000_0012_0), which is in the hand when drawn
    local kid = wp:get_Child()
    if not kid then if st.master then status.handMoveOn = false end; return end
    local wpp = V(kid:get_Position())
    local R, L = V(J.R_Hand:get_Position()), V(J.L_Hand:get_Position())
    local held = math.min(vlen(vsub(wpp, R)), vlen(vsub(wpp, L)))
    if st.master then status.wpHandDist = math.floor(held * 1000 + 0.5) / 1000 end
    if held > 0.35 then if st.master then status.handMoveOn = false end; return end
    if st.master and ctl_tick % 60 == 7 then
        local info = { R = R }
        for _, n in ipairs({ "Wp_Parent", "WpSub_Parent", "Wp_ReserveParent", "WpSub_ReserveParent" }) do
            local t = st.tr:find(n)
            if t then
                local e = { p = V(t:get_Position()), lp = V(t:get_LocalPosition()), kids = {} }
                local c = t:get_Child(); local k = 0
                while c and k < 8 do
                    local go = c:get_GameObject()
                    e.kids[#e.kids + 1] = { n = go and go:get_Name() or "?", p = V(c:get_Position()) }
                    c = c:get_Next(); k = k + 1
                end
                info[n] = e
            end
        end
        status.wpInfo = info
    end
    local off = qrot(Q(st.tr:get_Rotation()), { HAND_MOVE[1], HAND_MOVE[2], HAND_MOVE[3] })
    local RQ, LQ = Q(J.R_Hand:get_Rotation()), Q(J.L_Hand:get_Rotation())
    local rr = solve_arm(J, "R", vadd(R, off), RQ)
    solve_arm(J, "L", vadd(L, off), LQ)
    for _, n in ipairs({ "Wp_Parent", "WpSub_Parent" }) do
        local t = st.tr:find(n)
        if t then local q = t:get_Position(); q.x = q.x + off[1]; q.y = q.y + off[2]; q.z = q.z + off[3]; t:set_Position(q) end
    end
    if st.master then status.handMoveOn = true; status.handMoveReached = math.floor(vlen(vsub(rr, R)) * 1000 + 0.5) / 1000 end
end
-- Afi flames (verified 10-19): armour effect objects (11_ch02_*) under the Eve outfit's parts are moved 500 m down and
-- shrunk; set_Enabled / DrawSelf / forceDrawOff / killEffectAll left the smoke visible. Only parts of the worn Eve outfit.
local FX_CACHE = {}
FX_SER = {}
LIGHT_CACHE = {}
local function fx_away()
    local ser, found = {}, {}
    for _, st in pairs(targets) do
        if st.wearing and st.swapped then
            ser["11_ch02_" .. st.wearing:sub(6, 8) .. "_"] = true
            -- EPV standard / expert off on the worn Eve parts (killEffectAll / DisableRequestEffect made the game re-create
            -- the effect detached under NoParentEffects -> worse, 10-19; not used)
            local p = st.wearing:sub(1, 12)
            for _, c in ipairs(children(st.tr)) do
                local g = c:get_GameObject(); local nm = g and g:get_Name() or ""
                if nm:sub(1, 12) == p then pcall(function()
                    for _, comp in ipairs(g:call("get_Components"):get_elements()) do
                        local t = comp:get_type_definition():get_full_name()
                        if t:find("EPVExpert", 1, true) or t:find("EPVStandard", 1, true) then pcall(function() comp:call("set_Enabled", false) end) end
                    end
                end) end
            end
        end
    end
    FX_SER = ser
    LIGHT_CACHE = {}
    -- armour lights (user 10-19, Afi: a white glow stayed behind after the sparks were gone = CageLight_Master_PointLight
    -- under the hidden waist part ch03_081_0015): every light component below the worn Eve outfit's parts is switched off
    for _, st in pairs(targets) do
        if st.wearing and st.swapped then
            local p = st.wearing:sub(1, 12)
            local function walk(t, d)
                local c = t:get_Child()
                while c do
                    local g = c:get_GameObject()
                    if g then pcall(function()
                        for _, comp in ipairs(g:call("get_Components"):get_elements()) do
                            local tn = comp:get_type_definition():get_full_name()
                            if tn:find("via.render.", 1, true) and tn:find("Light", 1, true) then
                                -- the game switches it back on every frame: keep it dark and far away every frame (fx_hold)
                                LIGHT_CACHE[#LIGHT_CACHE + 1] = { comp, g:get_Transform() }; status.lightOff = #LIGHT_CACHE
                            end
                        end
                    end) end
                    if d < 4 then walk(c, d + 1) end
                    c = c:get_Next()
                end
            end
            for _, c in ipairs(children(st.tr)) do
                local g = c:get_GameObject(); local nm = g and g:get_Name() or ""
                if nm:sub(1, 12) == p then walk(c, 0) end
            end
        end
    end
    if next(ser) == nil then FX_CACHE = {}; return end
    -- by name wherever the effect object hangs (under the part, or detached under NoParentEffects: 10-19 dozens of
    -- detached copies kept flickering): "11_ch02_<series>_" of the worn Eve outfit
    local scene = sdk.call_native_func(sdk.get_native_singleton("via.SceneManager"), sdk.find_type_definition("via.SceneManager"), "get_CurrentScene")
    local l = scene:call("findComponents(System.Type)", sdk.typeof("app.AppEffectController"))
    for _, c in ipairs(l:get_elements()) do
        local go = c:get_GameObject(); local nm = go and go:get_Name() or ""
        if ser[nm:sub(1, 12)] then
            found[#found + 1] = go:get_Transform()
            -- also stop drawing / updating the effect object and its EffectPlayer (user 10-19: sparks still flickered)
            pcall(function() go:set_DrawSelf(false) end)
        end
    end
    FX_CACHE = found
    status.fxMoved = #found
end
-- every frame (user 10-19: moved only every 30 frames the white sparks still flickered back for a moment)
local function fx_hold()
    for _, tr in ipairs(FX_CACHE) do pcall(function() tr:set_LocalPosition(FX_FAR); tr:set_LocalScale(FX_TINY) end) end
    for _, e in ipairs(LIGHT_CACHE) do pcall(function()
        e[1]:call("set_Enabled", false); pcall(function() e[1]:call("set_Intensity", 0.0) end); e[2]:set_LocalPosition(FX_FAR)
    end) end
end

re.on_application_entry("LateUpdateBehavior", function()
    ctl_tick = ctl_tick + 1
    for _, st in pairs(targets) do pcall(fix_head_scale, st) end
    if ctl_tick % 10 == 5 then local okf, ef = pcall(fx_away); if not okf then status.fxErr = tostring(ef) end end   -- every frame cost 60 -> 13 fps (10-19); controller off keeps them quiet
    fx_hold()
    if ctl_tick % 60 == 13 then
        -- the file normally does not exist; load_file on a missing file writes an error line to the log every time
        local c = nil
        local okg, found = pcall(fs.glob, [[.*stellar-eve\\control\.json]])
        if okg and type(found) == "table" and #found > 0 then c = json.load_file("stellar-eve/control.json") end
        if type(c) == "table" then
            if c.enabled ~= nil then enabled = c.enabled end
            if c.grip ~= nil then grip_fix = c.grip end
            if type(c.handFix) == 'number' then hand_fix = c.handFix end
            if type(c.wepOffset) == 'table' then for i = 1, 3 do WEP_OFFSET[i] = tonumber(c.wepOffset[i]) or 0 end end
            status.wepOffset = WEP_OFFSET
            if type(c.wpMove) == 'table' then for i = 1, 3 do WP_MOVE[i] = tonumber(c.wpMove[i]) or 0 end end
            status.wpMove = WP_MOVE
            if type(c.handMove) == 'table' then for i = 1, 3 do HAND_MOVE[i] = tonumber(c.handMove[i]) or 0 end end
            status.handMove = HAND_MOVE
            status.handFix = hand_fix
            if c.hunterArms ~= nil and c.hunterArms ~= hunter_arms then
                hunter_arms = c.hunterArms
                for _, st in pairs(targets) do if st.applied then restore_joints(st) end; st.list = nil end   -- rebuild the joint set
            end
            status.hunterArms = hunter_arms
            local sj = type(c.skipJoints) == 'table' and table.concat(c.skipJoints, ',') or ''
            if sj ~= (status.skipJoints or '') then
                SKIP_PAT = {}; for _, x in ipairs(c.skipJoints or {}) do SKIP_PAT[#SKIP_PAT + 1] = tostring(x) end
                for _, st in pairs(targets) do if st.applied then restore_joints(st) end; st.list = nil end
                status.skipJoints = sj
            end
        end
    end
    local m = targets.master
    if m and m.tr and ctl_tick % 10 == 0 then pcall(function()
        local L, Rj = m.tr:getJointByName("L_Hand"), m.tr:getJointByName("R_Hand")
        local rq = Q(Rj:get_Rotation())
        local rel = qrot(qinv(rq), vsub(V(L:get_Position()), V(Rj:get_Position())))
        local rr = qmul(qinv(rq), Q(L:get_Rotation()))
        local rec = { p = { math.floor(rel[1] * 1000 + 0.5) / 1000, math.floor(rel[2] * 1000 + 0.5) / 1000, math.floor(rel[3] * 1000 + 0.5) / 1000 },
                      q = { rr.w, rr.x, rr.y, rr.z }, d = math.floor(vlen(rel) * 1000 + 0.5) / 1000, eve = enabled and m.applied or false, t = ctl_tick }
        -- weapon (first child of Wp_Parent) in each hand's frame: does the weapon keep the hunter's grip offset on Eve?
        local wp = m.tr:find("Wp_Parent"); local kid = wp and wp:get_Child()
        if kid then
            local kp, kq = V(kid:get_Position()), Q(kid:get_Rotation())
            local function r3(v) return { math.floor(v[1] * 1000 + 0.5) / 1000, math.floor(v[2] * 1000 + 0.5) / 1000, math.floor(v[3] * 1000 + 0.5) / 1000 } end
            local lq = Q(L:get_Rotation())
            local wr = qrot(qinv(rq), vsub(kp, V(Rj:get_Position())))
            local wl = qrot(qinv(lq), vsub(kp, V(L:get_Position())))
            rec.wpR = r3(wr); rec.wpL = r3(wl); rec.wpRd = math.floor(vlen(wr) * 1000 + 0.5) / 1000; rec.wpLd = math.floor(vlen(wl) * 1000 + 0.5) / 1000
            local qq = qmul(qinv(rq), kq); rec.wpRq = { qq.w, qq.x, qq.y, qq.z }
        end
        -- shoulder helpers (10-18): how far each helper turns relative to R_Shoulder, vs the upper arm itself (degrees)
        local sj = m.tr:getJointByName("R_Shoulder")
        if sj then
            local sq = Q(sj:get_Rotation()); local sh = {}
            for _, n in ipairs({ "R_UpperArm", "R_Deltoid_HJ_00", "R_Deltoid_HJ_01", "R_Deltoid_HJ_02", "R_Shoulder_HJ_00", "R_UpperArmDouble_HJ_00", "R_UpperArmTwist_HJ_00" }) do
                local j = m.tr:getJointByName(n)
                if j then
                    local r = qmul(qinv(sq), Q(j:get_Rotation()))
                    sh[n] = math.floor(math.deg(2 * math.acos(math.min(1, math.abs(r.w)))) * 10 + 0.5) / 10
                end
            end
            rec.sh = sh
        end
        status.handRel = rec
        if not rec.eve then status.handRelHunter = rec end
        status.handLog = status.handLog or {}
        status.handLog[#status.handLog + 1] = rec
        if #status.handLog > 60 then table.remove(status.handLog, 1) end
    end) end
    if enabled then
        for _, st in pairs(targets) do
            if st.applied then
                local ok, err = pcall(move_weapon, st)
                if not ok then status.wpErr = tostring(err) end
                ok, err = pcall(move_hands, st)
                if not ok then status.handMoveErr = tostring(err) end
            end
        end
    end
    if enabled and hand_fix > 0 then
        for _, st in pairs(targets) do
            if st.applied then
                local ok, err = pcall(handfix, st)
                if not ok then status.handFixErr = tostring(err) end
            end
        end
    end
    if not grip_fix or not enabled then return end
    for _, st in pairs(targets) do
        if st.applied then
            local ok, err = pcall(grip, st)
            if not ok then status.gripErr = tostring(err) end
        end
    end
end)

re.on_draw_ui(function()
    if imgui.tree_node("Stellar Eve outfit") then
        local changed
        changed, enabled = imgui.checkbox("Enabled", enabled)
        imgui.text(string.format("data %s | wearing %s | joints %d | face %s | characters %d", tostring(status.loaded),
            tostring(status.wearing), status.joints, tostring(status.face), status.targets or 0))
        if status.err then imgui.text("error: " .. status.err) end
        changed, grip_fix = imgui.checkbox("Two-handed grip fix", grip_fix)
        imgui.text(string.format("hunter hand distance %s | grip weight %s", tostring(status.gripDist), tostring(status.gripW)))
        if status.gripErr then imgui.text("grip error: " .. status.gripErr) end
        imgui.tree_pop()
    end
end)

-- the effect system may move its objects back after LateUpdateBehavior: hold them away again just before rendering
re.on_application_entry("BeginRendering", function() pcall(fx_hold) end)

-- catch the armour effect the moment it starts (user 10-19: between two scans new sparks still flashed for a few frames):
-- hook app.AppEffectController.start; an Eve outfit's own effect object (11_ch02_<series>_) is hidden and moved away there
pcall(function()
    local td = sdk.find_type_definition("app.AppEffectController")
    local m = td and (td:get_method("start") or td:get_method("awake"))
    if not m then status.fxHook = "no method"; return end
    sdk.hook(m, function(args)
        pcall(function()
            if next(FX_SER) == nil then return end
            local o = sdk.to_managed_object(args[2])
            local go = o and o:call("get_GameObject"); if not go then return end
            local nm = go:get_Name() or ""
            if FX_SER[nm:sub(1, 12)] then
                go:set_DrawSelf(false)
                local tr = go:get_Transform(); tr:set_LocalPosition(FX_FAR); tr:set_LocalScale(FX_TINY)
                FX_CACHE[#FX_CACHE + 1] = tr
                status.fxHooked = (status.fxHooked or 0) + 1
            end
        end)
    end, function(r) return r end)
    status.fxHook = m:get_name()
end)
