# blender -b -P chain_empty.py -- <in.chain2.14> <out.chain2.14> : same file, no chain groups (no physics on a hidden part)
import sys, importlib, addon_utils
a = sys.argv[sys.argv.index('--') + 1:]
addon_utils.enable('RE_Chain_Editor', default_set=True, handle_error=None)
fc2 = importlib.import_module('RE_Chain_Editor.modules.file_re_chain2')
c2 = fc2.Chain2File(); f = open(a[0], 'rb'); c2.read(f); f.close()
print('GROUPS before', len(c2.ChainGroupList), 'settings', len(c2.ChainSettingsList) if hasattr(c2, 'ChainSettingsList') else '?')
c2.ChainGroupList = []; c2.Header.chainGroupCount = 0
for k in ('ChainLinkList', 'chainLinkList'):
    if hasattr(c2, k): setattr(c2, k, [])
if hasattr(c2.Header, 'chainLinkCount'): c2.Header.chainLinkCount = 0
fc2.writeREChain2(c2, a[1])
nb = bytearray(open(a[1], 'rb').read()); nb[112:128] = open(a[0], 'rb').read()[112:128]; open(a[1], 'wb').write(nb)
chk = fc2.Chain2File(); f = open(a[1], 'rb'); chk.read(f); f.close(); print('GROUPS after', len(chk.ChainGroupList))
