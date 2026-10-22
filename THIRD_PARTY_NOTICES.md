# Third-party notices

The builder does not ship these tools (except the patched add-on files in `patches/`). `install.ps1` downloads them
from the sources in `deps.json` and checks their hashes.

| Tool | Author | License | Use |
|---|---|---|---|
| Blender 5.2.2 | Blender Foundation | GPL-2.0-or-later | runs every build script |
| RE Mesh Editor (622daa7) | NSACloud | GPL-3.0 | RE Engine mesh / mdf2 / tex import-export; `patches/RE_Mesh_Editor` modifies 2 files |
| RE Chain Editor (54ed5d4) | NSACloud | GPL-3.0 | chain2 physics files; `patches/RE_Chain_Editor` modifies 4 files for Blender 5 |
| .NET 10 SDK | .NET Foundation | MIT | builds `tools/sb-extract` and `tools/motion-convert` |
| CUE4Parse / CUE4Parse-Conversion | FabianFG and contributors | Apache-2.0 | reads Stellar Blade packages (NuGet; `dotnet build` also restores their own dependencies, each under its own license) |
| REE Content Editor / REE-Lib v0.7.22 | shadowcookie (kagenocookie) | MIT | reads Monster Hunter Wilds paks |
| MHWS_STM file list | REasy (seifhassine) | MIT | names of files inside the Wilds paks |
| Stellar Blade usmap | Stellar Blade Modding Team | community resource | type mappings for Stellar Blade packages |
| REFramework | praydog | MIT | required mod; runs the Eve Lua script in game |

Stellar Blade © SHIFT UP Corporation / Sony Interactive Entertainment. Monster Hunter Wilds © CAPCOM.
This is an unofficial fan project; no game assets are included in this repository.
