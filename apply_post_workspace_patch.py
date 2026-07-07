from pathlib import Path
import re

ROOT = Path.cwd()

INDEX_CANDIDATES = [
    ROOT / 'static' / 'index.html',
    ROOT / 'static' / 'index',
    ROOT / 'server' / 'static' / 'index.html',
    ROOT / 'server' / 'static' / 'index',
]
POSTS_CANDIDATES = [
    ROOT / 'routers' / 'posts.py',
    ROOT / 'server' / 'routers' / 'posts.py',
]


def existing(paths):
    return [p for p in paths if p.exists()]


def backup(p: Path):
    b = p.with_suffix(p.suffix + '.bak_post_workspace_v34') if p.suffix else Path(str(p) + '.bak_post_workspace_v34')
    if not b.exists():
        b.write_text(p.read_text(encoding='utf-8'), encoding='utf-8')


def patch_index(p: Path):
    txt = p.read_text(encoding='utf-8')
    backup(p)

    css = r'''

/* Admin Post Workspace v34 */
.post-workspace-header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}
.post-workspace-title{font-size:20px;font-weight:900;color:var(--text-pri)}
.post-workspace-sub{font-size:12px;color:var(--text-sec);margin-top:4px}
.post-workspace-grid{display:grid;grid-template-columns:360px 1fr;gap:14px;align-items:start}
.post-workspace-card{background:var(--bg-1);border:1px solid var(--border);border-radius:var(--radius);padding:14px}
.post-workspace-card-title{font-size:12px;font-weight:900;color:var(--green);text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;gap:8px}
.post-workspace-form{display:grid;gap:10px}
.post-workspace-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:12px}
.post-mode-note{font-size:11px;color:var(--text-sec);border:1px solid var(--border);background:var(--bg-2);border-radius:var(--radius);padding:10px;margin-top:12px;line-height:1.45}
.admin-dev-table{display:grid;gap:8px}
.admin-dev-card{border:1px solid var(--border);background:var(--bg-2);border-radius:var(--radius);padding:12px}
.admin-dev-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.admin-dev-name{font-size:14px;font-weight:900;color:var(--text-pri)}
.admin-dev-meta{font-family:var(--font-mono);font-size:11px;color:var(--text-sec);margin-top:3px}
.admin-dev-toolbar{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}
.admin-dev-settings{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:10px;font-size:11px;color:var(--text-sec)}
.admin-th-list{border-top:1px solid var(--border);margin-top:10px;padding-top:8px;display:grid;gap:6px}
.admin-th-row{display:grid;grid-template-columns:1fr auto auto;gap:8px;align-items:center;font-size:11px}
.admin-th-param{font-weight:800;color:var(--text-pri)}
.admin-th-values{font-family:var(--font-mono);color:var(--text-sec)}
.admin-th-actions{display:flex;gap:5px;justify-content:flex-end}
@media(max-width:1100px){.post-workspace-grid{grid-template-columns:1fr}.admin-dev-settings{grid-template-columns:1fr}}
'''
    if 'Admin Post Workspace v34' not in txt:
        txt = txt.replace('</style>', css + '\n</style>', 1)

    page = r'''

      <!-- POST WORKSPACE -->
      <div class="page" id="page-post-detail">
        <div class="post-workspace-header">
          <div>
            <div class="post-workspace-title" id="pw-title">Пост</div>
            <div class="post-workspace-sub" id="pw-sub">Картка адміністрування поста, приладів і порогів</div>
          </div>
          <div style="display:flex;gap:8px;align-items:center">
            <button class="btn-sm" onclick="showPage('posts')">← До списку постів</button>
            <button class="btn-add" onclick="addDeviceFromWorkspace()">+ Прилад</button>
          </div>
        </div>

        <div class="post-workspace-grid">
          <div class="post-workspace-card">
            <div class="post-workspace-card-title">Дані поста</div>
            <div class="post-workspace-form">
              <div class="fg"><label>Назва</label><input class="fi" style="width:100%" id="pw-name"/></div>
              <div class="fg"><label>Регіон</label><input class="fi" style="width:100%" id="pw-region"/></div>
              <div class="fg"><label>Локація</label><input class="fi" style="width:100%" id="pw-location"/></div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
                <div class="fg"><label>Широта</label><input class="fi" style="width:100%" id="pw-lat" type="number" step="0.000001"/></div>
                <div class="fg"><label>Довгота</label><input class="fi" style="width:100%" id="pw-lng" type="number" step="0.000001"/></div>
              </div>
              <label style="display:flex;gap:8px;align-items:center;font-size:12px;color:var(--text-sec)">
                <input type="checkbox" id="pw-active"/> Активний пост
              </label>
            </div>
            <div class="post-workspace-actions">
              <button class="btn-save" onclick="savePostWorkspace()">Зберегти</button>
            </div>
            <div class="post-mode-note" id="pw-mode-note">
              Режим <b>Центральний</b> показує та редагує дані Railway. Режим <b>Локальний</b> працює з локальною БД робочого місця. Зміни передаються між ними через Sync Engine.
            </div>
          </div>

          <div class="post-workspace-card">
            <div class="post-workspace-card-title">
              <span>Прилади та налаштування</span>
              <button class="btn-sm" onclick="refreshPostWorkspace()">Оновити</button>
            </div>
            <div id="pw-devices" class="admin-dev-table"><div class="empty-state"><div class="spinner"></div></div></div>
          </div>
        </div>
      </div>
'''
    if 'id="page-post-detail"' not in txt:
        marker = '      <!-- USERS -->'
        if marker in txt:
            txt = txt.replace(marker, page + '\n' + marker, 1)
        else:
            txt = txt.replace('</main>', page + '\n</main>', 1)

    # Replace edit button in post list, whether original or previous patch.
    txt = re.sub(
        r"<button class=\"btn-sm\" onclick=\"event\.stopPropagation\(\);(?:openPostModal|openPostAdminModal)\('\$\{p\.id\}'[^\"]*\"[^>]*>Редагувати</button>",
        '<button class="btn-sm" onclick="event.stopPropagation();openPostWorkspace(\'${p.id}\')">Редагувати</button>',
        txt,
        flags=re.S,
    )

    js = r'''

// ── POST WORKSPACE v34: адміністрування поста ───────────────
let postWorkspaceId=null;
let postWorkspacePost=null;
let postWorkspaceDevices=[];
let postWorkspaceThresholds={};

async function openPostWorkspace(postId){
  if(!me || me.role!=='admin') { toast('Доступ лише для адміністратора','error'); return; }
  postWorkspaceId=postId;
  showPage('post-detail');
  await refreshPostWorkspace();
}

async function refreshPostWorkspace(){
  if(!postWorkspaceId) return;
  const post=await api('/api/posts/'+postWorkspaceId);
  if(!post) return;
  postWorkspacePost=post;
  document.getElementById('pw-title').textContent='Пост: '+(post.name||'—');
  document.getElementById('pw-sub').textContent=(post.location||'—')+' · '+(post.region||'—')+' · '+(currentServer==='central'?'Центральний сервер':'Локальний сервер');
  document.getElementById('pw-name').value=post.name||'';
  document.getElementById('pw-region').value=post.region||'';
  document.getElementById('pw-location').value=post.location||'';
  document.getElementById('pw-lat').value=post.latitude??'';
  document.getElementById('pw-lng').value=post.longitude??'';
  document.getElementById('pw-active').checked=!!post.is_active;
  const note=document.getElementById('pw-mode-note');
  if(note) note.innerHTML=currentServer==='central'
    ? 'Ви редагуєте <b>центральну Railway БД</b>. Локальні пости отримають ці зміни після запуску/циклу Sync Engine.'
    : 'Ви редагуєте <b>локальну БД</b> цього робочого місця. Зміни будуть передані на Railway через Sync Engine, якщо таблиця дозволяє push.';
  await loadWorkspaceDevices();
}

async function savePostWorkspace(){
  if(!postWorkspaceId) return;
  const body={
    name:document.getElementById('pw-name').value.trim(),
    region:document.getElementById('pw-region').value.trim(),
    location:document.getElementById('pw-location').value.trim(),
    latitude:document.getElementById('pw-lat').value===''?null:parseFloat(document.getElementById('pw-lat').value),
    longitude:document.getElementById('pw-lng').value===''?null:parseFloat(document.getElementById('pw-lng').value),
    is_active:document.getElementById('pw-active').checked
  };
  if(!body.name){toast('Введіть назву поста','error');return;}
  const r=await api('/api/posts/'+postWorkspaceId,'PATCH',body);
  if(r?.ok){toast('Пост збережено','success'); await loadPosts(); await refreshPostWorkspace();}
}

async function loadWorkspaceDevices(){
  const box=document.getElementById('pw-devices');
  box.innerHTML='<div class="empty-state"><div class="spinner"></div></div>';
  const devs=await api(`/api/posts/${postWorkspaceId}/devices`);
  if(!devs) return;
  postWorkspaceDevices=devs;
  postWorkspaceThresholds={};
  for(const d of devs){
    postWorkspaceThresholds[d.id]=await api(`/api/thresholds/for-device?device_id=${d.id}&device_type=${d.type}&post_id=${postWorkspaceId}`)||[];
  }
  renderWorkspaceDevices();
}

function renderWorkspaceDevices(){
  const box=document.getElementById('pw-devices');
  if(!postWorkspaceDevices.length){
    box.innerHTML='<div class="empty-state"><div class="icon">◈</div><p>На цьому посту ще немає приладів</p></div>';
    return;
  }
  box.innerHTML=postWorkspaceDevices.map(d=>{
    const th=postWorkspaceThresholds[d.id]||[];
    return `<div class="admin-dev-card">
      <div class="admin-dev-top">
        <div>
          <div class="admin-dev-name">${esc(d.name)}</div>
          <div class="admin-dev-meta">${esc(d.id)}</div>
        </div>
        <div class="admin-dev-toolbar">
          <span class="sb ${d.is_online?'s-RESOLVED':'s-IGNORED'}">${d.is_online?'Online':'Offline'}</span>
          <button class="btn-sm" onclick="editDeviceFromWorkspace('${d.id}')">Налаштувати</button>
          <button class="btn-sm" onclick="openThreshModal('${d.type}','${d.id}','${postWorkspaceId}',null,'','','','')">+ Поріг</button>
          <button class="btn-sm red" onclick="deleteDeviceFromWorkspace('${d.id}','${String(d.name||'').replace(/'/g,'`')}')">Видалити</button>
        </div>
      </div>
      <div class="admin-dev-settings">
        <div><b>Тип:</b> ${esc(d.type||'—')}</div>
        <div><b>IP:</b> ${esc(d.host||'—')}</div>
        <div><b>TCP:</b> ${d.port||'—'}</div>
      </div>
      <div class="admin-th-list">
        ${th.length?th.map(t=>`<div class="admin-th-row">
          <div><div class="admin-th-param">${esc(t.parameter)}</div><div class="admin-th-values">⚠ ${t.warn_value} / 🔴 ${t.crit_value} ${esc(t.unit||'')}</div></div>
          <div class="admin-th-values">${esc(t.device_type||'')}</div>
          <div class="admin-th-actions">
            <button class="btn-sm" onclick="openThreshModal('${d.type}','${d.id}','${postWorkspaceId}','${t.id}','${escAttr(t.parameter)}','${escAttr(t.unit||'')}',${t.warn_value},${t.crit_value})">✎</button>
            <button class="btn-sm red" onclick="deleteThresh('${t.id}')">✕</button>
          </div>
        </div>`).join(''):'<div style="font-size:11px;color:var(--text-dim)">Порогів для цього приладу ще немає</div>'}
      </div>
    </div>`;
  }).join('');
}

function addDeviceFromWorkspace(){
  if(!postWorkspaceId) return;
  openDevModal(postWorkspaceId,'','','','',0);
}
function editDeviceFromWorkspace(deviceId){
  const d=postWorkspaceDevices.find(x=>x.id===deviceId);
  if(!d) return;
  openDevModal(postWorkspaceId,d.id,d.type,d.name,d.host,d.port||0);
}
async function deleteDeviceFromWorkspace(deviceId,name){
  if(!confirm(`Видалити прилад "${name}"?`)) return;
  const r=await api(`/api/posts/${postWorkspaceId}/devices/${deviceId}`,'DELETE');
  if(r?.ok){toast('Прилад видалено','success');await loadWorkspaceDevices();await loadPosts();await loadDevices();}
}
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function escAttr(s){return String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
'''
    if 'POST WORKSPACE v34' not in txt:
        marker = '// ── POSTS ─'
        if marker in txt:
            txt = txt.replace(marker, js + '\n' + marker, 1)
        else:
            txt = txt.replace('// ── HELPERS', js + '\n// ── HELPERS', 1)

    # Make server switch refresh current workspace when mode changes.
    if "if(document.getElementById('page-post-detail')?.classList.contains('active'))" not in txt:
        txt = txt.replace(
            "loadDevices();\n  loadAlarms();\n  initCharts();",
            "loadDevices();\n  loadAlarms();\n  initCharts();\n  if(document.getElementById('page-post-detail')?.classList.contains('active')) refreshPostWorkspace();",
            1
        )

    # Refresh workspace after device save/delete and threshold save/delete.
    txt = txt.replace(
        "if(r?.ok){closeDevModal();loadDevices();toast(devId?'Оновлено':'Додано','success');}",
        "if(r?.ok){closeDevModal();loadDevices();if(postWorkspaceId){await loadWorkspaceDevices();await loadPosts();}toast(devId?'Оновлено':'Додано','success');}"
    )
    txt = txt.replace(
        "if(r?.ok){loadDevices();toast('Видалено','success');}",
        "if(r?.ok){loadDevices();if(postWorkspaceId){await loadWorkspaceDevices();await loadPosts();}toast('Видалено','success');}"
    )
    txt = txt.replace(
        "if(r?.ok){closeThreshModal();loadDevices();toast(threshEditId?'Поріг оновлено':'Поріг створено','success');}",
        "if(r?.ok){closeThreshModal();loadDevices();if(postWorkspaceId){await loadWorkspaceDevices();}toast(threshEditId?'Поріг оновлено':'Поріг створено','success');}"
    )
    txt = txt.replace(
        "if(r?.ok){loadDevices();toast('Поріг видалено','success');}",
        "if(r?.ok){loadDevices();if(postWorkspaceId){await loadWorkspaceDevices();}toast('Поріг видалено','success');}"
    )

    p.write_text(txt, encoding='utf-8')
    print('OK patched UI:', p)


def patch_posts_router(p: Path):
    txt = p.read_text(encoding='utf-8')
    backup(p)

    # DeviceUpdate must allow type settings.
    txt = txt.replace(
        "class DeviceUpdate(BaseModel):\n    name:  Optional[str] = None\n    host:  Optional[str] = None\n    port:  Optional[int] = None",
        "class DeviceUpdate(BaseModel):\n    type:  Optional[str] = None\n    name:  Optional[str] = None\n    host:  Optional[str] = None\n    port:  Optional[int] = None"
    )
    if 'if body.type:' not in txt and 'fields = {}\n    if body.name:' in txt:
        txt = txt.replace("fields = {}\n    if body.name: fields[\"name\"] = body.name", "fields = {}\n    if body.type: fields[\"type\"] = body.type\n    if body.name: fields[\"name\"] = body.name", 1)

    # Touch updated_at on device update.
    txt = txt.replace(
        "execute(f\"UPDATE devices SET {set_clause} WHERE id=%s AND post_id=%s\",\n            (*fields.values(), device_id, post_id))",
        "execute(f\"UPDATE devices SET {set_clause}, updated_at=NOW() WHERE id=%s AND post_id=%s\",\n            (*fields.values(), device_id, post_id))"
    )

    # Make deletes soft when schema has deleted_at.
    txt = txt.replace(
        'execute("DELETE FROM posts WHERE id=%s", (post_id,))',
        'execute("""\n        UPDATE posts\n        SET deleted_at=NOW(), updated_at=NOW(), is_active=FALSE\n        WHERE id=%s\n    """, (post_id,))'
    )
    txt = txt.replace(
        'execute("DELETE FROM devices WHERE id=%s AND post_id=%s", (device_id, post_id))',
        'execute("""\n        UPDATE devices\n        SET deleted_at=NOW(), updated_at=NOW(), is_online=FALSE\n        WHERE id=%s AND post_id=%s\n    """, (device_id, post_id))'
    )

    # Hide soft-deleted records, if not already.
    txt = txt.replace('SELECT * FROM posts WHERE id=%s", (str(user["post_id"]),)', 'SELECT * FROM posts WHERE id=%s AND deleted_at IS NULL", (str(user["post_id"]),)')
    txt = txt.replace('SELECT * FROM posts ORDER BY name', 'SELECT * FROM posts WHERE deleted_at IS NULL ORDER BY name')
    txt = txt.replace('SELECT * FROM posts WHERE id=%s", (post_id,)', 'SELECT * FROM posts WHERE id=%s AND deleted_at IS NULL", (post_id,)')
    txt = txt.replace('SELECT * FROM devices WHERE post_id=%s ORDER BY type', 'SELECT * FROM devices WHERE post_id=%s AND deleted_at IS NULL ORDER BY type')
    txt = txt.replace('SELECT * FROM devices WHERE id=%s AND post_id=%s",', 'SELECT * FROM devices WHERE id=%s AND post_id=%s AND deleted_at IS NULL",')
    txt = txt.replace('SELECT * FROM devices WHERE post_id=%s", (post_id,)', 'SELECT * FROM devices WHERE post_id=%s AND deleted_at IS NULL", (post_id,)')

    # Include updated/deleted in formatted output for admin/debug/sync clarity.
    if '"updated_at":r["updated_at"].isoformat()' not in txt:
        txt = txt.replace(
            '"created_at":r["created_at"].isoformat() if r.get("created_at") else None}',
            '"created_at":r["created_at"].isoformat() if r.get("created_at") else None,\n            "updated_at":r["updated_at"].isoformat() if r.get("updated_at") else None,\n            "deleted_at":r["deleted_at"].isoformat() if r.get("deleted_at") else None}'
        )
    if '"deleted_at":r["deleted_at"].isoformat() if r.get("deleted_at") else None' not in txt and 'def _fmt_device' in txt:
        txt = txt.replace(
            '"last_seen":r["last_seen"].isoformat() if r.get("last_seen") else None}',
            '"last_seen":r["last_seen"].isoformat() if r.get("last_seen") else None,\n            "updated_at":r["updated_at"].isoformat() if r.get("updated_at") else None,\n            "deleted_at":r["deleted_at"].isoformat() if r.get("deleted_at") else None}'
        )

    p.write_text(txt, encoding='utf-8')
    print('OK patched posts router:', p)


def main():
    idxs = existing(INDEX_CANDIDATES)
    posts = existing(POSTS_CANDIDATES)
    if not idxs:
        print('WARN: static index file not found')
    if not posts:
        print('WARN: routers/posts.py not found')
    for p in idxs:
        patch_index(p)
    for p in posts:
        patch_posts_router(p)
    print('\nDONE. Restart server / commit and push if this is Railway repo.')

if __name__ == '__main__':
    main()
