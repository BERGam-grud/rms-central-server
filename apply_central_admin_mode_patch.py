from pathlib import Path
from datetime import datetime
import re
import sys

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
ROUTERS = ROOT / 'routers'
STATIC = ROOT / 'static' / 'index.html'

def backup(p: Path):
    if p.exists():
        b = p.with_name(p.name + '.backup_central_mode_v36_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
        b.write_text(p.read_text(encoding='utf-8'), encoding='utf-8')
        return b

def patch_posts():
    p = ROUTERS / 'posts.py'
    if not p.exists():
        print('SKIP posts.py'); return
    text = p.read_text(encoding='utf-8')
    backup(p)
    # Central dispatcher posts list must require admin.
    text = text.replace('def get_posts(user: dict = Depends(any_role)):', 'def get_posts(user: dict = Depends(admin_only)):')
    text = text.replace('def get_post(post_id: str, user: dict = Depends(any_role)):', 'def get_post(post_id: str, user: dict = Depends(admin_only)):')
    text = text.replace('def get_devices(post_id: str, user: dict = Depends(any_role)):', 'def get_devices(post_id: str, user: dict = Depends(admin_only)):')
    text = text.replace('def post_summary(post_id: str, user: dict = Depends(any_role)):', 'def post_summary(post_id: str, user: dict = Depends(admin_only)):')
    p.write_text(text, encoding='utf-8')
    print('OK central posts.py')

def patch_users():
    p = ROUTERS / 'users.py'
    if not p.exists():
        print('SKIP users.py'); return
    text = p.read_text(encoding='utf-8')
    backup(p)
    # Hide soft-deleted users if query exists.
    text = text.replace('ORDER  BY u.created_at DESC', 'WHERE  COALESCE(u.deleted_at IS NULL, TRUE)\n        ORDER  BY u.created_at DESC') if 'WHERE  COALESCE(u.deleted_at IS NULL' not in text else text
    p.write_text(text, encoding='utf-8')
    print('OK central users.py')

def patch_measurements():
    p = ROUTERS / 'measurements.py'
    if not p.exists():
        print('SKIP measurements.py'); return
    text = p.read_text(encoding='utf-8')
    backup(p)
    # In central dispatcher mode, global measurements are admin-only. Operators should use local server.
    text = text.replace('user: dict = Depends(any_role)', 'user: dict = Depends(admin_only)')
    if 'from core.auth import any_role' in text and 'admin_only' not in text.split('from core.auth import',1)[1].split('\n',1)[0]:
        text = text.replace('from core.auth import any_role', 'from core.auth import any_role, admin_only')
    p.write_text(text, encoding='utf-8')
    print('OK central measurements.py')

def patch_alarms():
    candidates = [ROUTERS / 'alarms.py', ROUTERS / 'alarms']
    p = next((x for x in candidates if x.exists()), None)
    if not p:
        print('SKIP alarms'); return
    text = p.read_text(encoding='utf-8')
    backup(p)
    text = text.replace('user: dict = Depends(any_role)', 'user: dict = Depends(admin_only)')
    if 'from core.auth import any_role, operator_only' in text:
        text = text.replace('from core.auth import any_role, operator_only', 'from core.auth import any_role, operator_only, admin_only')
    elif 'from core.auth import any_role' in text and 'admin_only' not in text:
        text = text.replace('from core.auth import any_role', 'from core.auth import any_role, admin_only')
    p.write_text(text, encoding='utf-8')
    print('OK central alarms')

def patch_thresholds():
    p = ROUTERS / 'thresholds.py'
    if not p.exists():
        print('SKIP thresholds.py'); return
    text = p.read_text(encoding='utf-8')
    backup(p)
    text = text.replace('def list_thresholds(user: dict = Depends(any_role)):', 'def list_thresholds(user: dict = Depends(admin_only)):')
    p.write_text(text, encoding='utf-8')
    print('OK central thresholds.py')

def patch_frontend():
    p = STATIC
    if not p.exists():
        print('SKIP static/index.html'); return
    text = p.read_text(encoding='utf-8')
    backup(p)
    if 'RMS_CENTRAL_ADMIN_ONLY_V36' not in text:
        text = text.replace('<script>', '<script>\n// RMS_CENTRAL_ADMIN_ONLY_V36: Railway UI is dispatcher/admin-only')
    # if app has switch buttons, hide local on Railway; exact DOM may vary, so use runtime guard.
    guard = r'''
(function(){
  const oldFetch = window.fetch;
  window.fetch = function(input, init){
    try{
      const token = localStorage.getItem('rms_token');
      const role  = (window.me && window.me.role) || localStorage.getItem('rms_role');
      if(role && role !== 'admin') console.warn('Central mode is admin-only; non-admin should use local server.');
    }catch(e){}
    return oldFetch(input, init);
  };
})();
'''
    if 'Central mode is admin-only' not in text:
        text = text.replace('</script>', guard + '\n</script>', 1)
    p.write_text(text, encoding='utf-8')
    print('OK central frontend')

patch_posts(); patch_users(); patch_measurements(); patch_alarms(); patch_thresholds(); patch_frontend()
print('\nГотово. Зроби git add/commit/push і дочекайся деплою Railway.')
