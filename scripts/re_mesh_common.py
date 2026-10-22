"""Shared helper: enable the local RE Mesh Editor copy inside background Blender.
Run Blender with BLENDER_USER_SCRIPTS=<builder folder>\\tools\\blender\\user-scripts
(install.ps1 puts RE Mesh Editor commit 622daa7 + patches/ into user-scripts/addons/RE_Mesh_Editor)."""
import addon_utils


def register_re_mesh_editor():
    loaded, enabled = addon_utils.check('RE_Mesh_Editor')
    if not enabled:
        addon_utils.enable('RE_Mesh_Editor', default_set=True, handle_error=None)
    loaded, enabled = addon_utils.check('RE_Mesh_Editor')
    if not enabled:
        raise RuntimeError('RE Mesh Editor failed to enable; check BLENDER_USER_SCRIPTS')
