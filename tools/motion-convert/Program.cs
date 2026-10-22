using Assimp;
using ReeLib;
using ContentEditor.App.FileLoaders;
using System.Text.Json;
using System.Security.Cryptography;
using System.Buffers.Binary;
static string MhwDir() => Environment.GetEnvironmentVariable("MHW_DIR") ?? @"C:\Program Files (x86)\Steam\steamapps\common\MonsterHunterWilds";
static string WorkDir() => Path.GetFullPath(Environment.GetEnvironmentVariable("WORK_DIR") ?? Path.Combine(AppContext.BaseDirectory, "../../../work")).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

if (args.Length == 3 && args[0] == "--extract-mesh") {
    var outputPath=Path.GetFullPath(args[2]);
    var project=WorkDir();
    if (!outputPath.StartsWith(project.TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Output must stay inside the work folder (WORK_DIR)");
    using var ws=new Workspace(new GameConfig("mhwilds") {
        GamePath=MhwDir()
    });
    using var stream=ws.FindSingleFile(args[1],out var resolvedMeshPath) ?? throw new Exception("Native mesh not found");
    var resolvedExtension=Path.GetExtension(resolvedMeshPath);
    if (!int.TryParse(resolvedExtension.AsSpan(1),out var resolvedMeshVersion))
        throw new Exception("Resolved native mesh lacks format version: "+resolvedMeshPath);
    if (!outputPath.EndsWith(resolvedExtension,StringComparison.Ordinal)) outputPath+=resolvedExtension;
    using (var extracted=File.Create(outputPath)) stream.CopyTo(extracted);
    using var mesh=new MeshFile(new FileHandler(outputPath));
    if (!mesh.Read()) throw new Exception("Native mesh read failed");
    if (mesh.RequiresStreamingData) {
        using var buffer=ws.FindSingleFile("streaming/"+args[1]) ?? throw new Exception("Native mesh streaming data not found");
        using var cached=File.Create(outputPath+".streaming");
        buffer.CopyTo(cached); cached.Flush(); cached.Position=0;
        mesh.LoadStreamingData(new FileHandler(cached));
    }
    var meshReference=new CommonMeshResource(Path.GetFileNameWithoutExtension(outputPath),ws) {NativeMesh=mesh,GameVersion=GameName.mhwilds};
    meshReference.ExportToFile(outputPath+".glb",false,false);
    Console.WriteLine(JsonSerializer.Serialize(new {source=args[1],resolvedMeshPath,resolvedMeshVersion,output=outputPath+".glb",meshReference.VertexCount,meshReference.BoneCount,
        limit="Private reference geometry, no original game files modified"}));
    return;
}

if (args.Length == 2 && args[0] == "--check-mesh") {
    // Parse a built .mesh with REE-Lib (independent of RE Mesh Editor) and report the key header facts.
    using var mesh=new MeshFile(new FileHandler(Path.GetFullPath(args[1])));
    var ok=mesh.Read();
    Console.WriteLine(JsonSerializer.Serialize(new {file=args[1],ok,mesh.RequiresStreamingData,
        bones=mesh.BoneData?.Bones.Count, materials=mesh.MaterialNames?.ToArray(),
        lods=mesh.MeshData?.LODs.Count, groups=mesh.MeshData?.LODs.FirstOrDefault()?.MeshGroups.Select(g=>new {g.groupId,subs=g.Submeshes.Count,verts=g.vertexCount}).ToArray()},
        new JsonSerializerOptions{WriteIndented=true}));
    return;
}

if (args.Length == 4 && args[0] == "--rest-offsets") {
    // <wilds rig mesh> <eve rig mesh> <out json>: per mapped bone, O = inv(R_hunter) * R_eve (game space, rest),
    // so at runtime W_eve = W_hunter * O. Also the Eve pelvis offset expressed in the hunter Hip frame.
    using var wm=new MeshFile(new FileHandler(Path.GetFullPath(args[1])));
    using var em=new MeshFile(new FileHandler(Path.GetFullPath(args[2])));
    if (!wm.Read() || !em.Read()) throw new Exception("Mesh read failed");
    System.Numerics.Matrix4x4 M(ReeLib.via.mat4 m)=>new(m.m00,m.m01,m.m02,m.m03,m.m10,m.m11,m.m12,m.m13,m.m20,m.m21,m.m22,m.m23,m.m30,m.m31,m.m32,m.m33);
    (System.Numerics.Quaternion q,System.Numerics.Vector3 t) G(MeshFile f,string n){
        var b=f.BoneData!.GetByName(n) ?? throw new Exception("missing bone "+n);
        System.Numerics.Matrix4x4.Decompose(M(b.globalTransform),out _,out var q,out var t); return (System.Numerics.Quaternion.Normalize(q),t);
    }
    var map=new Dictionary<string,string>{{"COG","Bip001"},{"Hip","Bip001-Pelvis"},{"Spine_0","Bip001-Spine"},{"Spine_1","Bip001-Spine1"},
        {"Spine_2","Bip001-Spine2"},{"Neck_0","Bip001-Neck"},{"Head","Bip001-Head"}};
    foreach (var s in new[]{"L","R"}) {
        foreach (var (t,e) in new[]{("Shoulder","Clavicle"),("UpperArm","UpperArm"),("Forearm","Forearm"),("Hand","Hand"),
                                     ("Thigh","Thigh"),("Knee","Calf"),("Foot","Foot"),("Toe","Toe0")}) map[$"{s}_{t}"]=$"Bip001-{s}-{e}";
        foreach (var (f,i) in new[]{("Thumb",0),("IndexF",1),("MiddleF",2),("RingF",3),("PinkyF",4)})
            foreach (var (j,suf) in new[]{(1,""),(2,"1"),(3,"2")}) map[$"{s}_{f}{j}"]=$"Bip001-{s}-Finger{i}{suf}";
    }
    var pairs=new List<object>();
    foreach (var (h,e) in map) {
        if (wm.BoneData!.GetByName(h)==null || em.BoneData!.GetByName(e)==null) continue;
        var (qh,_)=G(wm,h); var (qe,_)=G(em,e);
        var o=System.Numerics.Quaternion.Inverse(qh)*qe;
        pairs.Add(new {h,e,o=new[]{o.X,o.Y,o.Z,o.W}});
    }
    var (hipQ,hipT)=G(wm,"COG"); var (pelQ,pelT)=G(em,"Bip001");
    var d=System.Numerics.Vector3.Transform(pelT-hipT,System.Numerics.Quaternion.Inverse(hipQ));
    // Parent-first order for the runtime driver (Eve hierarchy order).
    var order=em.BoneData!.Bones.Select(b=>b.name).ToList();
    var sorted=pairs.OrderBy(p=>order.IndexOf((string)p.GetType().GetProperty("e")!.GetValue(p)!)).ToArray();
    File.WriteAllText(Path.GetFullPath(args[3]),JsonSerializer.Serialize(new {pairs=sorted,cog=new {h="COG",e="Bip001",d=new[]{d.X,d.Y,d.Z}},
        hunterCogRest=new[]{hipT.X,hipT.Y,hipT.Z},eveCogRest=new[]{pelT.X,pelT.Y,pelT.Z}},new JsonSerializerOptions{WriteIndented=true}));
    Console.WriteLine($"pairs={pairs.Count} cogOffset={d}");
    return;
}

if ((args.Length == 4 || args.Length == 5) && args[0] == "--rest-drive") {
    // Optional 5th arg: text file with the driven bone names (one per line). Each bone then gets as parent its
    // nearest DRIVEN ancestor and v relative to it: the hunter skeleton has extra joints (Neck_1, L_Shin,
    // L_Instep, L_Palm) between driven ones, which are never re-posed, so a child hung on them followed the
    // hunter chain instead of Eve's bone (head sank forward, feet/toes/fingers off).
    var driven=args.Length==5 ? new HashSet<string>(File.ReadAllLines(Path.GetFullPath(args[4])).Select(l=>l.Trim()).Where(l=>l.Length>0)) : null;
    // <wilds rig mesh> <eve mesh using Wilds bone names> <out json>. For each Eve bone (parent-first):
    // o = inv(R_hunter) * R_eve, and v = Eve rest translation from its Eve parent, in the parent's frame.
    // Runtime: W = W_hunter * o; P = P_parent' + W_parent' * v (COG: hunter COG + W_hunterCOG * d).
    using var wm=new MeshFile(new FileHandler(Path.GetFullPath(args[1])));
    using var em=new MeshFile(new FileHandler(Path.GetFullPath(args[2])));
    if (!wm.Read() || !em.Read()) throw new Exception("Mesh read failed");
    System.Numerics.Matrix4x4 M(ReeLib.via.mat4 m)=>new(m.m00,m.m01,m.m02,m.m03,m.m10,m.m11,m.m12,m.m13,m.m20,m.m21,m.m22,m.m23,m.m30,m.m31,m.m32,m.m33);
    (System.Numerics.Quaternion q,System.Numerics.Vector3 t) G(ReeLib.Mesh.MeshBone b){
        System.Numerics.Matrix4x4.Decompose(M(b.globalTransform),out _,out var q,out var t); return (System.Numerics.Quaternion.Normalize(q),t);
    }
    var bones=new List<object>();
    foreach (var eb in em.BoneData!.Bones) {
        if (eb.name=="root") continue;
        var hb=wm.BoneData!.GetByName(eb.name) ?? throw new Exception("hunter lacks "+eb.name);
        var (qe,te)=G(eb); var (qh,th)=G(hb);
        var o=System.Numerics.Quaternion.Inverse(qh)*qe;
        var pb=eb.Parent;
        if (driven!=null) { if (!driven.Contains(eb.name)) continue; while (pb!=null && pb.name!="root" && !driven.Contains(pb.name)) pb=pb.Parent; }
        var parent=pb?.name;
        float[] v=new float[3];
        if (parent!=null && parent!="root") { var (qp,tp)=G(pb!); var lv=System.Numerics.Vector3.Transform(te-tp,System.Numerics.Quaternion.Inverse(qp)); v=new[]{lv.X,lv.Y,lv.Z}; }
        float[] d=new float[3];
        if (eb.name=="COG") { var lv=System.Numerics.Vector3.Transform(te-th,System.Numerics.Quaternion.Inverse(qh)); d=new[]{lv.X,lv.Y,lv.Z}; }
        // qe: Eve rest world rotation (x,y,z,w) -- lets the runtime rebuild rest-relative rotations (twist extraction).
        bones.Add(new {name=eb.name,parent,o=new[]{o.X,o.Y,o.Z,o.W},v,d,qe=new[]{qe.X,qe.Y,qe.Z,qe.W},te=new[]{te.X,te.Y,te.Z}});
    }
    File.WriteAllText(Path.GetFullPath(args[3]),JsonSerializer.Serialize(new {bones},new JsonSerializerOptions{WriteIndented=true}));
    Console.WriteLine($"bones={bones.Count}");
    return;
}

if (args.Length == 3 && args[0] == "--skel-vs-mesh") {
    // Compare runtime skeleton rest (fbxskel, composed to global) with a mesh's bind globals for key bones.
    using var sk=new FbxSkelFile(new FileHandler(Path.GetFullPath(args[1])));
    using var me=new MeshFile(new FileHandler(Path.GetFullPath(args[2])));
    if (!sk.Read() || !me.Read()) throw new Exception("read failed");
    var gq=new System.Numerics.Quaternion[sk.Bones.Count]; var gt=new System.Numerics.Vector3[sk.Bones.Count];
    for (int i=0;i<sk.Bones.Count;i++){ var b=sk.Bones[i]; var lq=new System.Numerics.Quaternion(b.rotation.X,b.rotation.Y,b.rotation.Z,b.rotation.W); var lt=new System.Numerics.Vector3(b.position.X,b.position.Y,b.position.Z);
        if (b.parentIndex<0){gq[i]=lq;gt[i]=lt;} else {var p=b.parentIndex; gq[i]=gq[p]*lq; gt[i]=gt[p]+System.Numerics.Vector3.Transform(lt,gq[p]);} }
    System.Numerics.Matrix4x4 M(ReeLib.via.mat4 m)=>new(m.m00,m.m01,m.m02,m.m03,m.m10,m.m11,m.m12,m.m13,m.m20,m.m21,m.m22,m.m23,m.m30,m.m31,m.m32,m.m33);
    foreach (var n in new[]{"root","COG","Hip","Spine_0","L_Thigh","L_Knee","L_UpperArm","L_Hand","Head"}) {
        var i=sk.Bones.FindIndex(b=>b.name==n); var mb=me.BoneData!.GetByName(n);
        if (i<0||mb==null){Console.WriteLine(n+" missing");continue;}
        System.Numerics.Matrix4x4.Decompose(M(mb.globalTransform),out _,out var mq,out var mt);
        Console.WriteLine($"{n,-10} skel q={gq[i]:F3} t={gt[i]:F3} | mesh q={mq:F3} t={mt:F3}");
    }
    return;
}

if (args.Length == 2 && args[0] == "--check-bones") {
    using var me=new MeshFile(new FileHandler(Path.GetFullPath(args[1])));
    if (!me.Read()) throw new Exception("read failed");
    System.Numerics.Matrix4x4 M(ReeLib.via.mat4 m)=>new(m.m00,m.m01,m.m02,m.m03,m.m10,m.m11,m.m12,m.m13,m.m20,m.m21,m.m22,m.m23,m.m30,m.m31,m.m32,m.m33);
    int bad=0; float worst=0; string worstName="";
    foreach (var b in me.BoneData!.Bones) {
        var g=M(b.globalTransform); var l=M(b.localTransform); var ig=M(b.inverseGlobalTransform);
        var expect=b.Parent==null ? l : l*M(b.Parent.globalTransform);
        float err=0; for (int r=0;r<4;r++) for (int c=0;c<4;c++) err=Math.Max(err,Math.Abs(expect[r,c]-g[r,c]));
        var id=g*ig; float ierr=0; for (int r=0;r<4;r++) for (int c=0;c<4;c++) ierr=Math.Max(ierr,Math.Abs(id[r,c]-(r==c?1:0)));
        System.Numerics.Matrix4x4.Decompose(g,out var sc,out _,out _);
        var e=Math.Max(err,ierr); if (e>worst){worst=e;worstName=b.name+$" chain={err:F4} inv={ierr:F4} scale={sc:F3}";}
        if (e>1e-3) bad++;
    }
    Console.WriteLine($"bones={me.BoneData.Bones.Count} inconsistent={bad} worst={worstName} deform={me.BoneData.DeformBones.Count}");
    return;
}

if (args.Length == 2 && args[0] == "--dump-mesh") {
    // Flat dump of scalar fields of the mesh header and top-level sub-objects (for diffing a loading vs failing mesh).
    using var me=new MeshFile(new FileHandler(Path.GetFullPath(args[1])));
    if (!me.Read()) throw new Exception("read failed");
    var seen=new HashSet<object>(ReferenceEqualityComparer.Instance);
    void Dump(string prefix, object? o, int depth) {
        if (o==null) { Console.WriteLine($"{prefix} = null"); return; }
        var t=o.GetType();
        if (t.IsPrimitive || t.IsEnum || o is string || o is decimal) { Console.WriteLine($"{prefix} = {o}"); return; }
        if (depth>3 || !seen.Add(o)) return;
        if (o is System.Collections.IEnumerable en) { int n=0; foreach (var x in en) { if (n<3) Dump($"{prefix}[{n}]",x,depth+1); n++; } Console.WriteLine($"{prefix}.Count = {n}"); return; }
        foreach (var f in t.GetFields(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Instance)) Dump($"{prefix}.{f.Name}",f.GetValue(o),depth+1);
        foreach (var p in t.GetProperties(System.Reflection.BindingFlags.Public|System.Reflection.BindingFlags.Instance)) {
            if (p.GetIndexParameters().Length>0) continue; object? v; try { v=p.GetValue(o); } catch { continue; }
            Dump($"{prefix}.{p.Name}",v,depth+1);
        }
    }
    Dump("Header",me.Header,0);
    Dump("MeshData",me.MeshData,0);
    Dump("BoneData.Count",me.BoneData?.Bones.Count,0);
    Console.WriteLine($"FileSize = {new FileInfo(Path.GetFullPath(args[1])).Length}");
    return;
}

if (args.Length == 2 && args[0] == "--check-verts") {
    using var me=new MeshFile(new FileHandler(Path.GetFullPath(args[1])));
    if (!me.Read()) throw new Exception("read failed");
    var buf=me.MeshBuffer!;
    int nan=0; var lo=new System.Numerics.Vector3(1e9f); var hi=new System.Numerics.Vector3(-1e9f);
    foreach (var p in buf.Positions){ if (float.IsNaN(p.X)||float.IsNaN(p.Y)||float.IsNaN(p.Z)||float.IsInfinity(p.X)) nan++; else { lo=System.Numerics.Vector3.Min(lo,p); hi=System.Numerics.Vector3.Max(hi,p);} }
    int badSum=0, zero=0; uint maxIdx=0; var sums=new Dictionary<int,int>();
    foreach (var w in buf.Weights){ int s=0; for (int i=0;i<8;i++) s+=w.boneWeights[i]; if (s==0) zero++; if (Math.Abs(s-255)>3) badSum++; sums[s]=sums.GetValueOrDefault(s)+1;
        foreach (var bi in w.boneIndices) { for (int k=0;k<3;k++){ var idx=(bi>>(10*k))&0x3ff; if (idx>maxIdx) maxIdx=idx; } } }
    var uvNan=0;
    Console.WriteLine(JsonSerializer.Serialize(new {file=Path.GetFileName(args[1]),verts=buf.Positions.Length,nanPos=nan,lo=new[]{lo.X,lo.Y,lo.Z},hi=new[]{hi.X,hi.Y,hi.Z},
        weightsZero=zero,weightSumOff=badSum,topSums=sums.OrderByDescending(k=>k.Value).Take(4).Select(k=>$"{k.Key}:{k.Value}"),maxBoneIndex=maxIdx,
        deform=me.BoneData!.DeformBones.Count,uvNan,uv1=buf.UV1.Length,colors=buf.Colors.Length,faces=buf.IndicesCount,extraWeights=buf.ExtraWeights?.Length,
        vbSize=buf.vertexBufferSize,total=buf.totalBufferSize,elements=buf.elementCount}));
    return;
}

if (args.Length == 2 && args[0] == "--check-mdf") {
    using var mdf=new MdfFile(new FileHandler(Path.GetFullPath(args[1])));
    var ok=mdf.Read();
    Console.WriteLine(JsonSerializer.Serialize(new {file=args[1],ok,materials=mdf.Materials.Select(m=>new {
        name=m.Header.matName, mmtr=m.Header.mmtrPath, textures=m.Textures.Count, parameters=m.Parameters.Count,
        shader=m.Header.shaderType.ToString(),
        albd=m.Textures.FirstOrDefault(t=>t.texType=="BaseDielectricMap")?.texPath}).ToArray()},
        new JsonSerializerOptions{WriteIndented=true}));
    return;
}

if (args.Length == 3 && args[0] == "--dump-user") {
    // --dump-user <native path of a .user> <out json under assets>: the RSZ object tree as JSON (field name -> value),
    // e.g. the long sword action id list / behaviour table / action guide names.
    var project=WorkDir();
    var outPath=Path.GetFullPath(args[2]);
    if (!outPath.StartsWith(project.TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Output must stay inside the work folder (WORK_DIR)");
    using var ws=new Workspace(new GameConfig("mhwilds") { GamePath=MhwDir() });
    using var stream=ws.FindSingleFile(args[1],out var resolved) ?? throw new Exception("Native file not found: "+args[1]);
    var ms=new MemoryStream(); stream.CopyTo(ms); ms.Position=0;
    var uf=new UserFile(ws.RszFileOption,new FileHandler(ms,resolved));
    if (!uf.Read()) throw new Exception("user read failed");
    var seen=new HashSet<object>(ReferenceEqualityComparer.Instance);
    object? Dump(object? v,int depth) {
        if (v==null) return null;
        if (depth>40) return "...";
        if (v is RszInstance inst) {
            if (!seen.Add(inst)) return "@"+inst.Name;
            var d=new Dictionary<string,object?>{["$type"]=inst.RszClass.name};
            for (int i=0;i<inst.Fields.Length && i<inst.Values.Length;i++) d[inst.Fields[i].name]=Dump(inst.Values[i],depth+1);
            return d;
        }
        if (v is string str) return str;
        if (v is System.Collections.IEnumerable en) { var l=new List<object?>(); foreach (var x in en) l.Add(Dump(x,depth+1)); return l; }
        if (v.GetType().IsPrimitive || v is decimal) return v;
        return v.ToString();
    }
    var dumpRoot=uf.RSZ.ObjectList.Select(o=>Dump(o,0)).ToList();
    File.WriteAllText(outPath,JsonSerializer.Serialize(dumpRoot,new JsonSerializerOptions{WriteIndented=true}));
    Console.WriteLine(JsonSerializer.Serialize(new {resolved,objects=uf.RSZ.ObjectList.Count,output=outPath}));
    return;
}

if (args.Length == 3 && args[0] == "--extract-file") {
    // Generic private copy of one native file (version suffix resolved by REE-Lib), e.g. a weapon .mdf2 or .tex.
    var outputDir=Path.GetFullPath(args[2]);
    var project=WorkDir();
    if (!outputDir.StartsWith(project.TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Output must stay inside the work folder (WORK_DIR)");
    using var ws=new Workspace(new GameConfig("mhwilds") {
        GamePath=MhwDir()
    });
    using var stream=ws.FindSingleFile(args[1],out var resolved) ?? throw new Exception("Native file not found: "+args[1]);
    Directory.CreateDirectory(outputDir);
    var target=Path.Combine(outputDir,Path.GetFileName(resolved));
    using (var f=File.Create(target)) stream.CopyTo(f);
    Console.WriteLine(JsonSerializer.Serialize(new {source=args[1],resolved,output=target,bytes=new FileInfo(target).Length}));
    return;
}

if (args.Length == 3 && args[0] == "--extract-bank") {
    var outputPath=Path.GetFullPath(args[2]);
    var project=WorkDir();
    if (!outputPath.StartsWith(project.TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Output must stay inside the work folder (WORK_DIR)");
    using var ws=new Workspace(new GameConfig("mhwilds") {
        GamePath=MhwDir()
    });
    using var stream=ws.FindSingleFile(args[1]) ?? throw new Exception("Native bank not found");
    using (var extracted=File.Create(outputPath)) stream.CopyTo(extracted);
    using var bank=new MotbankFile(new FileHandler(outputPath));
    if (!bank.Read()) throw new Exception("Native bank read failed");
    Console.WriteLine(JsonSerializer.Serialize(new {bank.version,bank.JmapPath,bank.UvarPath,
        entries=bank.MotlistItems.Select(x=>new {x.BankID,x.BankType,x.BankTypeMaskBits,x.Path}).ToArray()},
        new JsonSerializerOptions{WriteIndented=true}));
    return;
}

if (args.Length == 5 && args[0] == "--stage-bank") {
    var project=WorkDir();
    var outputPath=Path.GetFullPath(args[4]);
    if (!outputPath.StartsWith(project.TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Output must stay inside the work folder (WORK_DIR)");
    using var original=new MotbankFile(new FileHandler(Path.GetFullPath(args[1])));
    if (!original.Read()) throw new Exception("Native bank read failed");
    var entry=original.MotlistItems.Single(x=>x.BankID==long.Parse(args[3]));
    using var bank=new MotbankFile(new FileHandler(outputPath)) { version=original.version,
        JmapPath=original.JmapPath,UvarPath=original.UvarPath };
    bank.MotlistItems.Add(new ReeLib.Motbank.MotbankEntry(original.version) {
        BankID=entry.BankID,BankType=entry.BankType,BankTypeMaskBits=entry.BankTypeMaskBits,Path=args[2]
    });
    if (!bank.SaveAs(outputPath)) throw new Exception("Motbank writer failed");
    using var check=new MotbankFile(new FileHandler(outputPath));
    if (!check.Read() || check.MotlistItems.Count!=1 || check.MotlistItems[0].Path!=args[2])
        throw new Exception("Motbank readback failed");
    Console.WriteLine(JsonSerializer.Serialize(new {check.version,check.JmapPath,check.UvarPath,
        entries=check.MotlistItems.Select(x=>new {x.BankID,x.BankType,x.BankTypeMaskBits,x.Path}).ToArray(),
        status="Private wrapper only; runtime selection unverified"},new JsonSerializerOptions{WriteIndented=true}));
    return;
}

if (args.Length == 4 && args[0] == "--compare-stage") {
    using var baseline=new MotlistFile(new FileHandler(Path.GetFullPath(args[1])));
    using var staged=new MotlistFile(new FileHandler(Path.GetFullPath(args[2])));
    if (!baseline.Read() || !staged.Read()) throw new Exception("Bank read failed");
    var selected=ushort.Parse(args[3]);
    string MotionHash(BaseFile motion) {
        using var handler=new FileHandler();
        if (!motion.WriteTo(handler,false)) throw new Exception("Canonical motion serialization failed");
        return Convert.ToHexString(SHA256.HashData(((MemoryStream)handler.Stream).ToArray()));
    }
    string EventHash(MotFile motion) {
        using var handler=new FileHandler();
        foreach (var clip in motion.Clips) clip.Write(handler);
        return Convert.ToHexString(SHA256.HashData(((MemoryStream)handler.Stream).ToArray()));
    }
    var differences=new List<object>(); int unchanged=0;
    if (baseline.Motions.Count!=staged.Motions.Count) throw new Exception("Motion count changed");
    foreach (var entry in baseline.Motions) {
        var peer=staged.Motions.Single(x=>x.motNumber==entry.motNumber && x.Switch==entry.Switch);
        if (entry.motNumber==selected && entry.Switch==0) continue;
        if (MotionHash(entry.MotFile!)!=MotionHash(peer.MotFile!)) differences.Add(new {entry.motNumber,entry.Switch});
        else unchanged++;
    }
    var oldMotion=(MotFile)baseline.Motions.Single(x=>x.motNumber==selected && x.Switch==0).MotFile!;
    var newMotion=(MotFile)staged.Motions.Single(x=>x.motNumber==selected && x.Switch==0).MotFile!;
    var eventsIdentical=EventHash(oldMotion)==EventHash(newMotion);
    Console.WriteLine(JsonSerializer.Serialize(new {selected,unchangedOtherMotions=unchanged,differences,eventsIdentical,
        oldFrames=oldMotion.Header.frameCount,newFrames=newMotion.Header.frameCount,
        limit="Canonical serialization comparison; does not establish runtime action mapping or hit alignment"},new JsonSerializerOptions{WriteIndented=true}));
    if (differences.Count>0 || !eventsIdentical) throw new Exception("Staging changed unrelated motion or behavior content");
    return;
}

if (args.Length == 3 && args[0] == "--events") {
    using var file=new MotlistFile(new FileHandler(Path.GetFullPath(args[1])));
    if (!file.Read()) throw new Exception("Motion read failed");
    var motion=(MotFile)file.Motions.Single(x=>x.motNumber==ushort.Parse(args[2]) && x.Switch==0).MotFile!;
    object Property(ReeLib.Clip.Property p) => new {name=p.Info.FunctionName,start=p.Info.startFrame,end=p.Info.endFrame,
        type=p.Info.DataType.ToString(),keys=p.Keys?.Select(k=>new {frame=k.frame,value=k.ToString()}).ToArray(),
        extraKeys=p.ExtraKeys?.Select(k=>new {frame=k.frame,value=k.ToString()}).ToArray(),
        children=p.ChildProperties?.Select(Property).ToArray()};
    Console.WriteLine(JsonSerializer.Serialize(new {motion.Name,frames=motion.Header.frameCount,fps=motion.Header.FrameRate,
        clips=motion.Clips.Select(c=>new {c.MainTrackName,properties=c.ClipEntry.Properties.Select(Property).ToArray()}).ToArray()},
        new JsonSerializerOptions{WriteIndented=true}));
    return;
}

if (args.Length == 3 && args[0] == "--msg") {
    // --msg <msg file> <out json>: every entry (name, guid, text per language) of a message file
    var msg=new MsgFile(new FileHandler(Path.GetFullPath(args[1])));
    msg.Read();
    var langs=msg.Languages?.Select(l=>l.ToString()).ToList() ?? new List<string>();
    var outList=new List<Dictionary<string,object?>>();
    foreach (var e in msg.Entries) {
        var d=new Dictionary<string,object?>();
        foreach (var pr in e.GetType().GetProperties()) {
            var v=pr.GetValue(e);
            if (v is string || v is Guid || v is int || v is uint) d[pr.Name]=v?.ToString();
            else if (v is System.Collections.IEnumerable en && v is not string) {
                var arr=en.Cast<object?>().Select(x=>x?.ToString()).ToList();
                if (arr.Count==langs.Count && langs.Count>0) d[pr.Name]=langs.Zip(arr).Where(z=>z.First is "Japanese" or "English" or "Korean").ToDictionary(z=>z.First,z=>(object?)z.Second);
                else if (arr.Count<8) d[pr.Name]=arr;
            }
        }
        outList.Add(d);
    }
    File.WriteAllText(Path.GetFullPath(args[2]), JsonSerializer.Serialize(new {langs, entries=outList}, new JsonSerializerOptions{WriteIndented=true, Encoder=System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping}));
    Console.WriteLine($"entries {outList.Count} langs {langs.Count}");
    return;
}

if (args.Length >= 2 && args[0] == "--msg-members") {
    // reflection dump of ReeLib.MsgFile (to learn the API)
    foreach (var t in typeof(MsgFile).Assembly.GetTypes().Where(t=>t.Name.StartsWith("Msg")))
        Console.WriteLine(t.FullName+": "+string.Join(", ", t.GetMembers().Where(m=>m.MemberType is System.Reflection.MemberTypes.Property or System.Reflection.MemberTypes.Field or System.Reflection.MemberTypes.Method).Select(m=>m.Name).Distinct()));
    return;
}

if (args.Length == 2 && args[0] == "--soundtriggers") {
    // --soundtriggers <motlist>: per motion, every sound trigger id (SoundRegisteredContainerTriggerTracks) with the frame
    // it fires on (the sibling Trigger key frame), to find which Wwise events are the attack swings.
    using var file=new MotlistFile(new FileHandler(Path.GetFullPath(args[1])));
    if (!file.Read()) throw new Exception("Motion read failed");
    var outList=new List<object>();
    foreach (var m in file.Motions) {
        if (m.Switch!=0 || m.MotFile is not MotFile mf) continue;
        var trig=new List<object>();
        foreach (var c in mf.Clips) {
            if (c.MainTrackName==null || !c.MainTrackName.Contains("Sound")) continue;
            var props=c.ClipEntry.Properties.ToList();
            for (int i=0;i<props.Count;i++) {
                if (props[i].Info.FunctionName!="TriggerId" || props[i].Keys==null || props[i].Keys.Count==0) continue;
                var id=props[i].Keys[0].ToString().Split(':').Last().Trim();
                int frame=-1;
                if (i+1<props.Count && props[i+1].Info.FunctionName=="Trigger") frame=(int)props[i+1].Info.startFrame;
                trig.Add(new {track=c.MainTrackName,id,frame});
            }
        }
        outList.Add(new {id=m.motNumber,name=mf.Name,frames=mf.Header.frameCount,triggers=trig});
    }
    Console.WriteLine(JsonSerializer.Serialize(outList));
    return;
}

if (args.Length == 2 && args[0] == "--hitwindows") {
    // --hitwindows <motlist>: per motion, frame count and every attack-collision window (_IsInRange start-end) plus the
    // first dodge / combo cancel frames, so the runtime can time-warp the hunter motion onto Eve's hit moments.
    using var file=new MotlistFile(new FileHandler(Path.GetFullPath(args[1])));
    if (!file.Read()) throw new Exception("Motion read failed");
    var outList=new List<object>();
    foreach (var m in file.Motions) {
        if (m.Switch!=0 || m.MotFile is not MotFile mf) continue;
        var hits=new List<int[]>(); int dodge=-1, combo=-1;
        foreach (var c in mf.Clips) {
            if (c.MainTrackName!="app.motion_track.AttackCollision_PlWp") continue;
            void Walk(ReeLib.Clip.Property p) {
                var n=p.Info.FunctionName;
                if (n=="_IsInRange") hits.Add(new[]{(int)p.Info.startFrame,(int)p.Info.endFrame});
                if (n=="_Dodge" && (dodge<0 || p.Info.startFrame<dodge)) dodge=(int)p.Info.startFrame;
                if (n.StartsWith("_ATTACK_") && n.EndsWith("_COMBO") && (combo<0 || p.Info.startFrame<combo)) combo=(int)p.Info.startFrame;
                if (p.ChildProperties!=null) foreach (var ch in p.ChildProperties) Walk(ch);
            }
            foreach (var p in c.ClipEntry.Properties) Walk(p);
        }
        outList.Add(new {id=m.motNumber,name=mf.Name,frames=mf.Header.frameCount,hits=hits.Distinct(new IntArrCmp()).OrderBy(h=>h[0]).ToArray(),dodge,combo});
    }
    Console.WriteLine(JsonSerializer.Serialize(outList));
    return;
}

if (args.Length == 2 && args[0] == "--sig") {
    // Debug: list public method signatures of a REE-Lib type (e.g. ReeLib.MotFile).
    var ty=typeof(MotFile).Assembly.GetType(args[1]) ?? throw new Exception("type?");
    foreach (var mi in ty.GetMethods()) Console.WriteLine(mi.Name+"("+string.Join(", ",mi.GetParameters().Select(p=>p.ParameterType.Name+" "+p.Name+(p.HasDefaultValue?"="+p.DefaultValue:"")))+")");
    return;
}

if ((args.Length == 5 || args.Length == 6) && args[0] == "--stage-motion") {
    // Optional 6th arg "keep-root": keep the native root channel so the character still
    // travels like the native motion (retargeted Eve clips carry no root motion, e.g. dodge).
    var keepRoot=args.Length==6 && args[5]=="keep-root";
    var project=WorkDir();
    var outputPath=Path.GetFullPath(args[4]);
    if (!outputPath.StartsWith(project.TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Output must stay inside the work folder (WORK_DIR)");
    using var original=new MotlistFile(new FileHandler(Path.GetFullPath(args[1])));
    using var imported=new MotlistFile(new FileHandler(Path.GetFullPath(args[2])));
    if (!original.Read() || !imported.Read()) throw new Exception("Input motion read failed");
    var id=ushort.Parse(args[3]);
    var entry=original.Motions.Single(x=>x.motNumber==id && x.Switch==0);
    var targetMotion=entry.MotFile as MotFile ?? throw new Exception("Target is not a normal motion");
    var sourceMotion=imported.MotFiles.Single() as MotFile ?? throw new Exception("Expected one normal imported motion");
    var nativeName=targetMotion.Name;
    var before=targetMotion.Clips.Select(c=>c.MainTrackName).ToArray();
    // Attack motions (collision track), basic actions such as dodge 61 (HunterBasic) and idle/locomotion loops
    // (cancel/visual tracks only) are all staged the same way; native event tracks are kept as they are.
    if (!before.Contains("app.motion_track.AttackCollision_PlWp") && !before.Contains("app.motion_track.HunterBasic"))
        Console.Error.WriteLine("Note: reference has no attack/HunterBasic track (idle/locomotion loop): "+string.Join(",",before));
    // Common/female motions use a 197-bone subset (no weapon HJ extras, but bust HJ the retarget rig lacks):
    // take the converted channels for bones the native motion has, keep native channels for the rest.
    var targetHashes=targetMotion.BoneClips.Select(c=>c.ClipHeader.boneHash).ToHashSet();
    // KEEP_NATIVE_WEAPON=1: weapon joints keep the native channels (sword on the back / attach data) instead of the
    // retarget's identity tracks, so no separate --restore-native-weapon pass is needed.
    string[] nativeOnly=Environment.GetEnvironmentVariable("KEEP_NATIVE_WEAPON")=="1" ? new[]{"R_Wep","R_Wep_Sub","L_Wep","L_Wep_Sub"} : Array.Empty<string>();
    var usable=sourceMotion.BoneClips.Where(c=>targetMotion.GetBoneByHash(c.ClipHeader.boneHash) is {} nb && !nativeOnly.Contains(nb.boneName)).ToList();
    var keptNative=targetMotion.BoneClips.Where(c=>!usable.Any(u=>u.ClipHeader.boneHash==c.ClipHeader.boneHash)).ToList();
    if (usable.Count<100) throw new Exception($"Only {usable.Count} converted channels match the native rig; do not stage");
    Console.Error.WriteLine($"Channels: converted {usable.Count}, native kept {keptNative.Count} ({string.Join(",",keptNative.Select(c=>c.ClipHeader.boneName).Take(12))}), dropped {sourceMotion.BoneClips.Count-usable.Count}");
    var nativeRoot=keepRoot ? targetMotion.BoneClips.Where(c=>c.ClipHeader.boneName=="root").ToList() : new();
    if (keepRoot && nativeRoot.Count!=1) throw new Exception("Native motion has no single root channel");
    targetMotion.BoneClips.Clear();targetMotion.BoneClips.AddRange(usable);targetMotion.BoneClips.AddRange(keptNative);
    if (keepRoot) {
        targetMotion.BoneClips.RemoveAll(c=>c.ClipHeader.boneName=="root");
        targetMotion.BoneClips.Add(nativeRoot[0]);
    }
    // Native motions can share the same Bones/RootBones lists. Keep those lists intact.
    // Follow upstream CopyValuesFrom's channel remapping without replacing native metadata/end clips.
    foreach (var channel in targetMotion.BoneClips) {
        if (keptNative.Contains(channel) || nativeRoot.Contains(channel)) continue;   // native channels are already mapped
        var nativeBone=targetMotion.GetBoneByHash(channel.ClipHeader.boneHash)
            ?? throw new Exception("Imported channel has no matching native bone hash");
        channel.ClipHeader.boneIndex=(ushort)nativeBone.Index;
        channel.ClipHeader.boneName=nativeBone.boneName;
    }
    targetMotion.Header.frameCount=sourceMotion.Header.frameCount;
    targetMotion.Header.endFrame=sourceMotion.Header.endFrame;
    targetMotion.Header.FrameRate=sourceMotion.Header.FrameRate;
    if (original.Motions.IndexOf(entry)==0 || Environment.GetEnvironmentVariable("STAGE_REPACK")=="1") {
        // The first motion owns the bone list the others share; a single-motion block cannot carry it, so this one
        // case re-serializes the whole list (other motions are re-encoded too; check them in game).
        if (!original.WriteTo(outputPath)) throw new Exception("Whole-list serialization failed");
        using var verify0=new MotlistFile(new FileHandler(outputPath));
        if (!verify0.Read()) throw new Exception("Repacked file read failed");
        var r0=(MotFile)verify0.Motions.Single(x=>x.motNumber==id && x.Switch==0).MotFile!;
        Console.WriteLine(JsonSerializer.Serialize(new {referenceId=id,referenceName=r0.Name,convertedFrames=r0.Header.frameCount,
            bankEntries=verify0.Motions.Count,strategy="Whole motlist re-serialized (first motion owns shared bones)",
            limit="Other motions re-encoded; verify in game"},new JsonSerializerOptions{WriteIndented=true}));
        return;
    }
    // Use the upstream single-motion writer, then append that block to an unchanged bank.
    // Rewriting the whole bank reserializes unrelated compressed tracks.
    if ((int)original.Header.version!=992) throw new Exception("Append staging is scoped to the inspected Wilds 992 layout");
    using var block=new FileHandler(new MemoryStream(),Path.GetFullPath(args[1]));
    if (!targetMotion.WriteTo(block,false)) throw new Exception("Single motion serialization failed");
    var originalBytes=File.ReadAllBytes(args[1]);
    var blockBytes=((MemoryStream)block.Stream).ToArray();
    var appendOffset=(originalBytes.Length+15L)&~15L;
    var outputBytes=new byte[checked((int)appendOffset+blockBytes.Length)];
    originalBytes.CopyTo(outputBytes,0);blockBytes.CopyTo(outputBytes,(int)appendOffset);
    var pointerOffset=checked((int)(original.Header.pointersOffset+original.Motions.IndexOf(entry)*8L));
    BinaryPrimitives.WriteInt64LittleEndian(outputBytes.AsSpan(pointerOffset,8),appendOffset);
    for (int i=0;i<originalBytes.Length;i++)
        if ((i<pointerOffset || i>=pointerOffset+8) && originalBytes[i]!=outputBytes[i])
            throw new Exception("Unexpected original-bank byte change");
    File.WriteAllBytes(outputPath,outputBytes);
    using var verify=new MotlistFile(new FileHandler(outputPath));
    if (!verify.Read()) throw new Exception("Staged file read failed");
    var result=(MotFile)verify.Motions.Single(x=>x.motNumber==id && x.Switch==0).MotFile!;
    if (result.Name!=nativeName || !before.SequenceEqual(result.Clips.Select(c=>c.MainTrackName)))
        throw new Exception("Native motion identity or event track names changed");
    Console.WriteLine(JsonSerializer.Serialize(new {referenceId=id,referenceName=nativeName,
        convertedFrames=result.Header.frameCount,fps=result.Header.FrameRate,bones=result.Bones.Count,
        boneTracks=result.BoneClips.Count,eventTracks=before,bankEntries=verify.Motions.Count,
        strategy="Original bank bytes retained except selected 8-byte pointer; upstream-serialized motion appended",
        pointerOffset,appendOffset,appendedBytes=blockBytes.Length,
        limit="Reference candidate only; native event times preserved, swing alignment/input mapping/gameplay unverified"},
        new JsonSerializerOptions{WriteIndented=true}));
    return;
}

// Weapon joints carry native attach/visibility data (e.g. L_Wep scale Y=2); retargeted
// Eve clips reset them to identity and the equipped sword disappears during playback.
if (args.Length >= 5 && args[0] == "--restore-native-weapon") {
    var project=WorkDir();
    var outputPath=Path.GetFullPath(args[3]);
    if (!outputPath.StartsWith(project.TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Output must stay inside the work folder (WORK_DIR)");
    string[] weaponBones={"R_Wep","R_Wep_Sub","L_Wep","L_Wep_Sub"};
    // Optional "grip=<id>": take R_Wep/R_Wep_Sub from that native motion instead of the same id.
    // Same-id native grip tracks follow the native swing timing (195 moves the sword ~0.44m off the hand).
    var gripArg=args.Skip(4).FirstOrDefault(a=>a.StartsWith("grip="));
    ushort? gripId=gripArg==null ? null : ushort.Parse(gripArg[5..]);
    var ids=args.Skip(4).Where(a=>!a.StartsWith("grip=")).Select(ushort.Parse).ToArray();
    using var native=new MotlistFile(new FileHandler(Path.GetFullPath(args[1])));
    using var current=new MotlistFile(new FileHandler(Path.GetFullPath(args[2])));
    if (!native.Read() || !current.Read()) throw new Exception("Bank read failed");
    if ((int)current.Header.version!=992) throw new Exception("Append staging is scoped to the inspected Wilds 992 layout");
    var bytes=File.ReadAllBytes(args[2]).ToList();
    var originalLength=bytes.Count;
    var pointers=new List<int>(); var report=new List<object>();
    foreach (var id in ids) {
        var entry=current.Motions.Single(x=>x.motNumber==id && x.Switch==0);
        var motion=(MotFile)entry.MotFile!;
        var nativeMotion=(MotFile)native.Motions.Single(x=>x.motNumber==id && x.Switch==0).MotFile!;
        var replaced=new List<string>();
        for (int i=0;i<motion.BoneClips.Count;i++) {
            var name=motion.BoneClips[i].ClipHeader.boneName;
            if (!weaponBones.Contains(name)) continue;
            var hash=motion.BoneClips[i].ClipHeader.boneHash;
            var donor=gripId!=null && name.StartsWith("R_Wep")
                ? (MotFile)native.Motions.Single(x=>x.motNumber==gripId && x.Switch==0).MotFile!
                : nativeMotion;
            var source=donor.BoneClips.SingleOrDefault(c=>c.ClipHeader.boneHash==hash)
                ?? throw new Exception("Native motion lacks weapon track "+name);
            source.ClipHeader.boneIndex=motion.BoneClips[i].ClipHeader.boneIndex;
            motion.BoneClips[i]=source; replaced.Add(name);
        }
        if (replaced.Count!=weaponBones.Length) throw new Exception($"Motion {id}: replaced {replaced.Count}/{weaponBones.Length} weapon tracks");
        using var block=new FileHandler(new MemoryStream(),Path.GetFullPath(args[2]));
        if (!motion.WriteTo(block,false)) throw new Exception("Single motion serialization failed");
        while (bytes.Count%16!=0) bytes.Add(0);
        var appendOffset=bytes.Count;
        bytes.AddRange(((MemoryStream)block.Stream).ToArray());
        var pointerOffset=checked((int)(current.Header.pointersOffset+current.Motions.IndexOf(entry)*8L));
        var patched=bytes.ToArray();
        BinaryPrimitives.WriteInt64LittleEndian(patched.AsSpan(pointerOffset,8),appendOffset);
        bytes=patched.ToList(); pointers.Add(pointerOffset);
        report.Add(new {id,replaced,appendOffset,frames=motion.Header.frameCount,nativeFrames=nativeMotion.Header.frameCount});
    }
    var original=File.ReadAllBytes(args[2]); var result=bytes.ToArray();
    for (int i=0;i<originalLength;i++)
        if (!pointers.Any(p=>i>=p && i<p+8) && original[i]!=result[i]) throw new Exception("Unexpected original-bank byte change");
    File.WriteAllBytes(outputPath,result);
    using var verify=new MotlistFile(new FileHandler(outputPath));
    if (!verify.Read()) throw new Exception("Output read failed");
    foreach (var id in ids) {
        var m=(MotFile)verify.Motions.Single(x=>x.motNumber==id && x.Switch==0).MotFile!;
        var before=(MotFile)current.Motions.Single(x=>x.motNumber==id && x.Switch==0).MotFile!;
        if (m.Name!=before.Name || m.Header.frameCount!=before.Header.frameCount) throw new Exception("Motion identity changed "+id);
    }
    Console.WriteLine(JsonSerializer.Serialize(new {motions=report,outputBytes=result.Length,
        limit="Only weapon joint tracks swapped to native; body pose unchanged; visibility in game unverified"},
        new JsonSerializerOptions{WriteIndented=true}));
    return;
}

if ((args.Length >= 2 && args.Length <= 4) && args[0] == "--roundtrip") {
    var project=WorkDir();
    var input=Path.GetFullPath(args[1]);
    if (!input.StartsWith(project.TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Input/output must remain in project assets");
    var reference=Path.GetDirectoryName(input)!;
    using var ws=new Workspace(new GameConfig("mhwilds") {
        GamePath=MhwDir()
    });
    using var animation=new MotlistFile(new FileHandler(input));
    using var mesh=new MeshFile(new FileHandler(Path.Combine(reference,"ch03_000_0001.mesh.241111606")));
    using var skeleton=new FbxSkelFile(new FileHandler(args.Length>=3 ? Path.GetFullPath(args[2]) : Path.Combine(reference,"ch03_000_9000.fbxskel.7")));
    if (!animation.Read() || !mesh.Read() || !skeleton.Read()) throw new Exception("Reference resource read failed");
    if (mesh.RequiresStreamingData) {
        const string streamPath="streaming/art/model/character/ch03/000/000/1/ch03_000_0001.mesh.241111606";
        using var buffer=ws.FindSingleFile(streamPath) ?? throw new Exception("Required native mesh streaming buffer not found");
        using var cached=File.Create(Path.Combine(reference,"ch03_000_0001.streaming.mesh.241111606"));
        buffer.CopyTo(cached);
        cached.Flush();
        cached.Position=0;
        mesh.LoadStreamingData(new FileHandler(cached));
        Console.WriteLine("Loaded required original mesh streaming buffer: "+cached.Length+" bytes");
    }
    var roundtripResource=new CommonMeshResource("Wilds_Roundtrip",ws){NativeMesh=mesh,GameVersion=GameName.mhwilds};
    var selected=args.Length==4 ? new[]{(MotFile)animation.Motions.Single(x=>x.motNumber==ushort.Parse(args[3]) && x.Switch==0).MotFile!}
        : animation.MotFiles.OfType<MotFile>();
    var exportPath=input+(args.Length==4 ? ".motion"+args[3] : "")+".glb";
    roundtripResource.ExportToFile(exportPath,false,false,skeleton,selected);
    Console.WriteLine("Exported actual MOTLIST data to "+exportPath);
    return;
}

if ((args.Length == 2 || args.Length == 3) && args[0] == "--inspect") {
    using var file = new MotlistFile(new FileHandler(Path.GetFullPath(args[1])));
    if (!file.Read()) throw new Exception("Native MOTLIST read failed");
    Console.WriteLine(JsonSerializer.Serialize(file.Motions.Where(index=>args.Length==2 || index.motNumber==ushort.Parse(args[2])).Select(index => new {
        id=index.motNumber, name=index.MotFile?.Name, switchId=index.Switch,
        overrides=index.OverrideClips.Count,
        frames=(index.MotFile as MotFile)?.Header.frameCount,
        fps=(index.MotFile as MotFile)?.Header.FrameRate,
        bones=(index.MotFile as MotFile)?.Bones.Count,
        clips=(index.MotFile as MotFile)?.Clips.Count,
        clipTypes=(index.MotFile as MotFile)?.Clips.Select(c=>c.GetType().Name).ToArray(),
        clipNames=(index.MotFile as MotFile)?.Clips.Select(c=>c.MainTrackName).ToArray(),
        boneNames=(index.MotFile as MotFile)?.Bones.Select(b=>b.boneName).ToArray(),
        boneRest=args.Length==3 ? (index.MotFile as MotFile)?.Bones.Select(b=>new {
            name=b.boneName,parent=b.Parent?.boneName,index=b.Index,
            translation=new[]{b.translation.X,b.translation.Y,b.translation.Z},
            quaternion=new[]{b.quaternion.W,b.quaternion.X,b.quaternion.Y,b.quaternion.Z}
        }).ToArray() : null
    }),new JsonSerializerOptions{WriteIndented=true}));
    return;
}

if (args.Length == 5 && args[0] == "--dump-pose") {
    // --dump-pose <motlist> <motion id> <frames, e.g. 0,20,40> <out json>: local rotation (w,x,y,z) and, where animated,
    // local translation of every animated bone at the given frames (linear / nlerp between keys), plus the motion's rest.
    using var file = new MotlistFile(new FileHandler(Path.GetFullPath(args[1])));
    if (!file.Read()) throw new Exception("Native MOTLIST read failed");
    var mot = file.Motions.First(i => i.motNumber == ushort.Parse(args[2])).MotFile as MotFile ?? throw new Exception("motion not found");
    var frames = args[3].Split(',').Select(float.Parse).ToArray();
    int[] idx(ReeLib.Mot.Track tr, int n) => tr.frameIndexes is { Length: > 0 } fi && fi.Length == n ? fi : Enumerable.Range(0, n).ToArray();
    (int, int, float) seg(int[] fi, float f) {
        if (f <= fi[0]) return (0, 0, 0); if (f >= fi[^1]) return (fi.Length - 1, fi.Length - 1, 0);
        int k = 0; while (k < fi.Length - 1 && fi[k + 1] <= f) k++;
        return (k, k + 1, (f - fi[k]) / Math.Max(1, fi[k + 1] - fi[k]));
    }
    var bones = new Dictionary<string, object>();
    foreach (var c in mot.BoneClips) {
        var name = c.ClipHeader.boneName ?? c.ClipHeader.boneHash.ToString();
        List<float[]>? rs = null, ts = null;
        if (c.HasRotation && c.Rotation!.rotations is { Length: > 0 } rq) {
            var fi = idx(c.Rotation, rq.Length); rs = new();
            foreach (var f in frames) { var (a, b, u) = seg(fi, f); var q = System.Numerics.Quaternion.Slerp(rq[a], rq[b], u); rs.Add(new[] { q.W, q.X, q.Y, q.Z }); }
        }
        if (c.HasTranslation && c.Translation!.translations is { Length: > 0 } tv) {
            var fi = idx(c.Translation, tv.Length); ts = new();
            foreach (var f in frames) { var (a, b, u) = seg(fi, f); var p = System.Numerics.Vector3.Lerp(tv[a], tv[b], u); ts.Add(new[] { p.X, p.Y, p.Z }); }
        }
        bones[name] = new { r = rs, t = ts };
    }
    var restOut = mot.Bones.Select(b => new { name = b.boneName, parent = b.Parent?.boneName, t = new[] { b.translation.X, b.translation.Y, b.translation.Z },
                                               q = new[] { b.quaternion.W, b.quaternion.X, b.quaternion.Y, b.quaternion.Z } }).ToArray();
    File.WriteAllText(Path.GetFullPath(args[4]), JsonSerializer.Serialize(new { motion = mot.Name, frameCount = mot.Header.frameCount, frames, bones, rest = restOut }));
    Console.WriteLine($"pose: {mot.Name} {bones.Count} animated bones, {frames.Length} frames");
    return;
}

if (args.Length == 3 && args[0] == "--channels") {
    // --channels <motlist> <out json>: what each motion animates per bone (rotation / translation / scale keys) and,
    // for translation tracks, how far the local offset moves from the bone's rest offset (length change = the motion
    // sets the bone length itself, so a body with other proportions would be overridden by the motion).
    using var file = new MotlistFile(new FileHandler(Path.GetFullPath(args[1])));
    if (!file.Read()) throw new Exception("Native MOTLIST read failed");
    var perBone = new Dictionary<string, Dictionary<string, double>>();
    var chMotions = new List<object>();
    ReeLib.Mot.MotBone? rest(MotFile m, uint hash) { try { return m.GetBoneByHash(hash); } catch { return null; } }
    foreach (var index in file.Motions) {
        if (index.MotFile is not MotFile mot) continue;
        var bones = new List<object>();
        foreach (var c in mot.BoneClips) {
            var name = c.ClipHeader.boneName ?? c.ClipHeader.boneHash.ToString();
            var rb = rest(mot, c.ClipHeader.boneHash);
            double tMove = 0, tLen = 0, rAng = 0, sDev = 0;
            if (c.HasTranslation && c.Translation!.translations is { Length: > 0 } ts) {
                var r0 = rb?.translation ?? ts[0];
                tMove = ts.Max(t => (double)(t - r0).Length());
                tLen = ts.Max(t => Math.Abs((double)t.Length() - r0.Length()));
            }
            if (c.HasRotation && c.Rotation!.rotations is { Length: > 0 } rs) {
                var q0 = rb?.quaternion ?? rs[0];
                rAng = rs.Max(q => 2 * Math.Acos(Math.Min(1.0, Math.Abs((double)System.Numerics.Quaternion.Dot(q, q0))))) * 180 / Math.PI;
            }
            if (c.HasScale && c.Scale!.translations is { Length: > 0 } ss) sDev = ss.Max(s => (double)(s - System.Numerics.Vector3.One).Length());
            bones.Add(new { bone = name, T = c.HasTranslation ? c.Translation!.keyCount : 0, R = c.HasRotation ? c.Rotation!.keyCount : 0,
                            S = c.HasScale ? c.Scale!.keyCount : 0, tMove = Math.Round(tMove, 4), tLenChange = Math.Round(tLen, 4),
                            rMaxDeg = Math.Round(rAng, 1), sDev = Math.Round(sDev, 4) });
            if (!perBone.TryGetValue(name, out var agg)) perBone[name] = agg = new() { ["motions"] = 0, ["withT"] = 0, ["withR"] = 0, ["withS"] = 0, ["maxTMove"] = 0, ["maxTLenChange"] = 0, ["maxRDeg"] = 0, ["maxSDev"] = 0, ["tLenOver1cm"] = 0 };
            agg["motions"]++; if (c.HasTranslation) agg["withT"]++; if (c.HasRotation) agg["withR"]++; if (c.HasScale) agg["withS"]++;
            agg["maxTMove"] = Math.Max(agg["maxTMove"], Math.Round(tMove, 4)); agg["maxTLenChange"] = Math.Max(agg["maxTLenChange"], Math.Round(tLen, 4));
            agg["maxRDeg"] = Math.Max(agg["maxRDeg"], Math.Round(rAng, 1)); agg["maxSDev"] = Math.Max(agg["maxSDev"], Math.Round(sDev, 4));
            if (tLen > 0.01) agg["tLenOver1cm"]++;
        }
        chMotions.Add(new { id = index.motNumber, name = mot.Name, frames = mot.Header.frameCount, skeletonBones = mot.Bones.Count, tracks = mot.BoneClips.Count, bones });
    }
    var restOut = file.Motions.Select(i => i.MotFile as MotFile).FirstOrDefault(m => m != null && m.Bones.Count > 0)?.Bones
        .Select(b => new { name = b.boneName, parent = b.Parent?.boneName, t = new[] { b.translation.X, b.translation.Y, b.translation.Z }, len = b.translation.Length() }).ToArray();
    File.WriteAllText(Path.GetFullPath(args[2]), JsonSerializer.Serialize(new { file = Path.GetFileName(args[1]), motionCount = chMotions.Count, perBone, rest = restOut, motions = chMotions },
        new JsonSerializerOptions { WriteIndented = true }));
    Console.WriteLine($"channels: {chMotions.Count} motions, {perBone.Count} bones");
    return;
}

if (args.Length != 2) throw new ArgumentException("Input GLB and project output MOTLIST required");
var root=Path.GetFullPath(Path.Combine(AppContext.BaseDirectory,"../../../../"));
var output=Path.GetFullPath(args[1]);
if (!output.StartsWith(Path.Combine(root,"assets")+Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
    throw new ArgumentException("Output must stay inside the work folder (WORK_DIR)");
using var workspace=new Workspace(new GameConfig("mhwilds"));
using var assimp=new AssimpContext();
var scene=assimp.ImportFile(Path.GetFullPath(args[0]));
if (scene.AnimationCount != 1) throw new Exception($"Expected one source animation, got {scene.AnimationCount}");
var resource=new CommonMeshResource("eve_attack01_candidate",workspace){Scene=scene,GameVersion=GameName.mhwilds};
var motions=resource.Motlist;
if (motions.MotFiles.Count != 1) throw new Exception("Converter did not produce one motion");
// Upstream rounds key indexes but floors the header duration. A glTF float
// just below an exact 60fps boundary can otherwise hide its final keyed frame.
var sourceAnimation=scene.Animations.Single();
var sourceRate=sourceAnimation.TicksPerSecond==0 ? 60 : sourceAnimation.TicksPerSecond;
var sourceEndFrames=sourceAnimation.DurationInTicks/sourceRate*60;
var roundedEnd=Math.Round(sourceEndFrames);
var convertedMotion=(MotFile)motions.MotFiles.Single();
if (Math.Abs(sourceEndFrames-roundedEnd)<0.001 && convertedMotion.Header.endFrame==roundedEnd-1) {
    Console.WriteLine($"Normalized near-integer header end {convertedMotion.Header.endFrame} -> {roundedEnd}; source={sourceEndFrames:R}, keyed poses unchanged");
    convertedMotion.Header.frameCount=(float)roundedEnd;
    convertedMotion.Header.endFrame=(float)roundedEnd;
}
if (!motions.SaveAs(output)) throw new Exception("MOTLIST serializer returned false");
using var reread=new MotlistFile(new FileHandler(output));
if (!reread.Read()) throw new Exception("Output MOTLIST read failed");
Console.WriteLine($"MOTLIST conversion and readback: version={reread.Header.version}, clips={reread.MotFiles.Count}, bytes={new FileInfo(output).Length}");
Console.WriteLine("Conversion candidate only. Native action, collision events, weapon offsets and gameplay remain unverified.");

class IntArrCmp : IEqualityComparer<int[]> {
    public bool Equals(int[]? a, int[]? b) => a!=null && b!=null && a.SequenceEqual(b);
    public int GetHashCode(int[] a) => a.Aggregate(17,(h,x)=>h*31+x);
}

