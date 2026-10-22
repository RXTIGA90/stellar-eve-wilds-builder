# Patched files for the Blender add-ons (GPL-3.0)

The installer downloads the upstream add-ons (NSACloud, GPL-3.0) at the commits in deps.json, then copies these files over them:

- RE_Chain_Editor/ : changes needed to run RE Chain Editor (commit 54ed5d4) on Blender 5.2.
- RE_Mesh_Editor/ : RE Mesh Editor (commit 622daa7), console toggle skipped in background mode.

Modified files stay under GPL-3.0 (license copies included). Upstream: https://github.com/NSACloud
