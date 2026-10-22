// Private, local extraction of Stellar Blade assets (owned copy) via CUE4Parse.
// Reads the user's own installed copy (SB_PAKS); outputs stay under the local work folder (WORK_DIR), never redistributed.
using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Versions;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Assets.Exports.Texture;
using CUE4Parse.UE4.Assets.Exports.SkeletalMesh;
using CUE4Parse.UE4.Assets.Exports.StaticMesh;
using CUE4Parse.UE4.Assets.Exports.Material;
using CUE4Parse_Conversion;
using CUE4Parse_Conversion.Options;

using System.Text.Json;

var Game = Environment.GetEnvironmentVariable("SB_PAKS") ?? @"C:\Program Files (x86)\Steam\steamapps\common\StellarBlade\SB\Content\Paks";
var project = Path.GetFullPath(Environment.GetEnvironmentVariable("WORK_DIR") ?? Path.Combine(AppContext.BaseDirectory, "../../../work")).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
var usmap = Environment.GetEnvironmentVariable("SB_USMAP") ?? Path.Combine(AppContext.BaseDirectory, "4.26.2-0+++UE4+Release-4.26-SB-v1.4.1.usmap");

var provider = new DefaultFileProvider(Game, SearchOption.TopDirectoryOnly, new VersionContainer(EGame.GAME_UE4_26));
provider.MappingsContainer = new FileUsmapTypeMappingsProvider(usmap);
provider.Initialize();
provider.Mount();
Console.Error.WriteLine($"mounted files: {provider.Files.Count}");

if (args[0] == "--opts") {
    // print the ExportOptions constructor parameters (to find the morph-target switch)
    foreach (var c in typeof(ExportOptions).GetConstructors())
        Console.WriteLine(string.Join(", ", c.GetParameters().Select(p => p.ParameterType.Name + " " + p.Name + (p.HasDefaultValue ? "=" + p.DefaultValue : ""))));
    return;
}

if (args[0] == "--sound") {
    // --sound <package path prefix> <out dir under assets>: decoded USoundWave data (OGG etc.) as files
    var outDir = Path.GetFullPath(args[2]);
    if (!outDir.StartsWith(project + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Output must remain in project assets");
    Directory.CreateDirectory(outDir);
    foreach (var file in provider.Files.Keys.Where(k => k.StartsWith(args[1], StringComparison.OrdinalIgnoreCase) && k.EndsWith(".uasset")).Order()) {
        foreach (var obj in provider.LoadPackage(file).GetExports()) {
            if (obj is not CUE4Parse.UE4.Assets.Exports.Sound.USoundWave sw) continue;
            CUE4Parse_Conversion.Sounds.SoundDecoder.Decode(sw, true, out var fmt, out var data);
            if (data == null) { Console.WriteLine($"{sw.Name}: no data"); continue; }
            var o = Path.Combine(outDir, sw.Name + "." + (fmt ?? "bin").ToLowerInvariant());
            File.WriteAllBytes(o, data); Console.WriteLine($"{o} {data.Length}");
        }
    }
    return;
}

if (args[0] == "--list") {
    foreach (var f in provider.Files.Keys.Where(k => k.Contains(args[1], StringComparison.OrdinalIgnoreCase)).Order())
        Console.WriteLine(f);
    return;
}

if (args[0] == "--json-prefix") {
    // --json-prefix <package path prefix> <out dir> : one JSON per package under the prefix (single mount).
    var outDir = Path.GetFullPath(args[2]); Directory.CreateDirectory(outDir);
    foreach (var f in provider.Files.Keys.Where(k => k.StartsWith(args[1], StringComparison.OrdinalIgnoreCase) && k.EndsWith(".uasset")).Order()) {
        try {
            var pkg = provider.LoadPackage(f);
            File.WriteAllText(Path.Combine(outDir, Path.GetFileNameWithoutExtension(f) + ".json"),
                Newtonsoft.Json.JsonConvert.SerializeObject(pkg.GetExports(), Newtonsoft.Json.Formatting.None));
        } catch (Exception e) { Console.Error.WriteLine($"fail {f}: {e.Message}"); }
    }
    return;
}

if (args[0] == "--json") {
    // --json <package path> : dump the package exports (properties, object references) to stdout.
    var pkg = provider.LoadPackage(args[1]);
    Console.WriteLine(Newtonsoft.Json.JsonConvert.SerializeObject(pkg.GetExports(), Newtonsoft.Json.Formatting.Indented));
    return;
}

if (args[0] == "--locres") {
    // --locres <language, e.g. ko> : dump every localized string of the game (namespace \t key \t text) to stdout.
    var path = $"SB/Content/Localization/Game/{args[1]}/Game.locres";
    var bytes = provider.SaveAsset(path);
    if (args.Length > 2) { File.WriteAllBytes(Path.GetFullPath(args[2]), bytes); return; }   // raw copy for an own parser
    var res = new CUE4Parse.UE4.Localization.FTextLocalizationResource(new CUE4Parse.UE4.Readers.FByteArchive(path, bytes));
    Console.OutputEncoding = System.Text.Encoding.UTF8;
    foreach (var ns in res.Entries)
        foreach (var kv in ns.Value)
            Console.WriteLine($"{ns.Key.Str}\t{kv.Key.Str}\t{kv.Value.LocalizedString.Replace("\r", " ").Replace("\n", " ")}");
    return;
}

if (args[0] == "--export-actorx") {
    // --export-actorx <package path prefix> <out dir>: skeletal meshes as ActorX (.pskx) and animation sequences as .psa
    // (the drone slinger is posed from a Stellar Blade drone animation)
    var outDir = Path.GetFullPath(args[2]);
    if (!outDir.StartsWith(project + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Output must remain in the work folder");
    Directory.CreateDirectory(outDir);
    var options = new ExportOptions(EMeshFormat.ActorX, default, default, default, ETextureFormat.Png, 100, false, false,
        default, false, false, ESocketFormat.None, default);
    var session = new ExportSession(null!);
    var report = new List<object>();
    foreach (var file in provider.Files.Keys.Where(k => k.StartsWith(args[1], StringComparison.OrdinalIgnoreCase) && k.EndsWith(".uasset")).Order()) {
        IEnumerable<UObject> exports;
        try { exports = provider.LoadPackage(file).GetExports(); }
        catch (Exception e) { report.Add(new { file, error = e.Message }); continue; }
        foreach (var obj in exports) {
            if (obj is not (USkeletalMesh or CUE4Parse.UE4.Assets.Exports.Animation.UAnimSequence)) continue;
            session.Add(obj); report.Add(new { file, type = obj.ExportType, name = obj.Name });
        }
    }
    var results = await session.RunAsync(outDir, options, null!, CancellationToken.None);
    foreach (var r in results) report.Add(new { r.Success, r.ObjectPath, r.DiskFilePaths, error = r.Error?.Message });
    File.WriteAllText(Path.Combine(outDir, "export-report.json"), JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
    Console.WriteLine($"exported entries: {report.Count}");
    return;
}

if (args[0] == "--export") {
    // --export <package path prefix, e.g. SB/Content/Art/Character/PC/CH_P_EVE_09> <out dir under assets>
    var outDir = Path.GetFullPath(args[2]);
    if (!outDir.StartsWith(project + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
        throw new ArgumentException("Output must remain in project assets");
    Directory.CreateDirectory(outDir);
    var options = new ExportOptions(EMeshFormat.Gltf2, default, default, default, ETextureFormat.Png, 100, false, false,
        default, true, Environment.GetEnvironmentVariable("SB_MORPHS") == "1", Environment.GetEnvironmentVariable("SB_SOCKETS") == "1" ? ESocketFormat.Bone : ESocketFormat.None, default);   // SB_SOCKETS=1: sockets as bones (attach points)   // SB_MORPHS=1: keep morph targets (face expressions)
    var session = new ExportSession(null!);
    var report = new List<object>();
    foreach (var file in provider.Files.Keys.Where(k => k.StartsWith(args[1], StringComparison.OrdinalIgnoreCase) && k.EndsWith(".uasset")).Order()) {
        IEnumerable<UObject> exports;
        try { exports = provider.LoadPackage(file).GetExports(); }
        catch (Exception e) { report.Add(new { file, error = e.Message }); continue; }
        foreach (var obj in exports) {
            if (obj is not (USkeletalMesh or UStaticMesh or UMaterialInstanceConstant or UTexture2D)) continue;
            try {
                if (obj is UMaterialInstanceConstant mic) {
                    var dump = Path.Combine(outDir, mic.Name + ".material.json");
                    File.WriteAllText(dump, JsonSerializer.Serialize(new {
                        mic.Name, parent = mic.Parent?.Name,
                        textures = mic.TextureParameterValues.Select(t => new { name = t.ParameterInfo.Name.Text, value = t.ParameterValue.ResolvedObject?.GetPathName() }),
                        scalars = mic.ScalarParameterValues.Select(s => new { name = s.ParameterInfo.Name.Text, s.ParameterValue }),
                        vectors = mic.VectorParameterValues.Select(v => new { name = v.ParameterInfo.Name.Text, value = v.ParameterValue?.ToString() })
                    }, new JsonSerializerOptions { WriteIndented = true }));
                    report.Add(new { file, type = "material", output = dump });
                    continue;
                }
                session.Add(obj);
                report.Add(new { file, type = obj.ExportType, name = obj.Name, queued = true });
            } catch (Exception e) { report.Add(new { file, name = obj.Name, error = e.Message }); }
        }
    }
    var results = await session.RunAsync(outDir, options, null!, CancellationToken.None);
    foreach (var r in results) report.Add(new { r.Success, r.ObjectPath, r.DiskFilePaths, error = r.Error?.Message });
    File.WriteAllText(Path.Combine(outDir, "export-report.json"), JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
    Console.WriteLine($"exported entries: {report.Count}");
}


