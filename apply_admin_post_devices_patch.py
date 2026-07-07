from pathlib import Path
import re

ROOT = Path.cwd()

CANDIDATES_INDEX = [
    ROOT / "static" / "index.html",
    ROOT / "server" / "static" / "index.html",
    ROOT / "server" / "static" / "index",
]
CANDIDATES_POSTS = [
    ROOT / "routers" / "posts.py",
    ROOT / "server" / "routers" / "posts.py",
]


def find_existing(paths):
    return [p for p in paths if p.exists()]


def backup(p: Path):
    b = p.with_suffix(p.suffix + ".bak_admin_devices") if p.suffix else Path(str(p) + ".bak_admin_devices")
    if not b.exists():
        b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")


def patch_index(path: Path):
    txt = path.read_text(encoding="utf-8")
    backup(path)

    # 1) CSS
    css_marker = "</style>"
    css_block = r'''

/* Admin post/devices management */
.admin-post-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.admin-device-row{display:grid;grid-template-columns:1fr 120px 150px 90px 150px;gap:8px;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)}
.admin-device-row:last-child{border-bottom:none}
.admin-device-head{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.04em}
.admin-device-name{font-weight:700;color:var(--text-main)}
.admin-device-meta{font-size:11px;color:var(--text-sec);font-family:var(--font-mono)}
.admin-device-actions{display:flex;gap:6px;justify-content:flex-end}
.admin-box{background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);padding:12px;margin-top:12px}
.admin-box-title{font-size:12px;font-weight:800;color:var(--green);margin-bottom:10px;text-transform:uppercase;letter-spacing:.05em}
'''
    if "admin-post-grid" not in txt:
        txt = txt.replace(css_marker, css_block + "\n" + css_marker, 1)

    # 2) Insert modal after device modal block
    modal_block = r'''

<!-- MODAL: Адміністрування поста та приладів -->
<div class="modal-overlay" id="post-admin-modal">
  <div class="modal" style="width:min(920px,96vw)">
    <div class="modal-header">
      <span id="pam-title">Адміністрування поста</span>
      <span class="modal-close" onclick="closePostAdminModal()">×</span>
    </div>
    <div class="modal-body">
      <div class="modal-section">Дані поста</div>
      <div class="admin-post-grid">
        <div class="fg"><label>Назва</label><input class="fi" style="width:100%" id="pam-name"/></div>
        <div class="fg"><label>Регіон</label><input class="fi" style="width:100%" id="pam-region"/></div>
        <div class="fg"><label>Локація</label><input class="fi" style="width:100%" id="pam-loc"/></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div class="fg"><label>Широта</label><input class="fi" style="width:100%" id="pam-lat" type="number" step="0.0001"/></div>
          <div class="fg"><label>Довгота</label><input class="fi" style="width:100%" id="pam-lng" type="number" step="0.0001"/></div>
        </div>
      </div>
      <div style="display:flex;gap:8px;margin-top:10px;justify-content:flex-end">
        <button class="btn-sm" onclick="savePostFromAdmin()">Зберегти дані поста</button>
      </div>

      <div class="admin-box">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
          <div class="admin-box-title">Прилади цього поста</div>
          <button class="btn-sm" onclick="addDeviceFromPostAdmin()">+ Додати прилад</button>
        </div>
        <div class="admin-device-row admin-device-head">
          <div>Прилад</div><div>Тип</div><div>Адреса</div><div>Статус</div><div></div>
        </div>
        <div id="pam-devices"><div class="empty-state"><div class="spinner"></div></div></div>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn-cancel" onclick="closePostAdminModal()">Закрити</button>
    </div>
  </div>
</div>
'''
    if 'id="post-admin-modal"' not in txt:
        marker = '<!-- MODAL: Користувач -->'
        if marker in txt:
            txt = txt.replace(marker, modal_block + "\n" + marker, 1)
        else:
            txt = txt.replace('</body>', modal_block + "\n</body>", 1)

    # 3) Change edit button in post cards to open admin modal
    txt = re.sub(
        r"<button class=\"btn-sm\" onclick=\"event\.stopPropagation\(\);openPostModal\('\$\{p\.id\}'.*?</button>",
        '<button class="btn-sm" onclick="event.stopPropagation();openPostAdminModal(\'${p.id}\')">Редагувати</button>',
        txt,
        count=1,
        flags=re.S,
    )

    # 4) Insert JS functions before DEVICE MODAL section
    js_block = r'''

// ── POST ADMIN MODAL: пост + прилади ────────────────────────
let adminPostId=null, adminPostData=null, adminPostDevices=[];

async function openPostAdminModal(postId){
  if(me.role!=='admin'){toast('Доступ лише для адміністратора','error');return;}
  adminPostId=postId;
  const post=await api('/api/posts/'+postId);
  if(!post) return;
  adminPostData=post;
  document.getElementById('pam-title').textContent='Адміністрування: '+post.name;
  document.getElementById('pam-name').value=post.name||'';
  document.getElementById('pam-loc').value=post.location||'';
  document.getElementById('pam-region').value=post.region||'';
  document.getElementById('pam-lat').value=post.latitude||'';
  document.getElementById('pam-lng').value=post.longitude||'';
  document.getElementById('post-admin-modal').classList.add('open');
  await loadPostAdminDevices();
}

function closePostAdminModal(){
  document.getElementById('post-admin-modal')?.classList.remove('open');
}

async function savePostFromAdmin(){
  if(!adminPostId) return;
  const body={
    name:document.getElementById('pam-name').value.trim(),
    location:document.getElementById('pam-loc').value.trim(),
    region:document.getElementById('pam-region').value.trim(),
    latitude:parseFloat(document.getElementById('pam-lat').value)||null,
    longitude:parseFloat(document.getElementById('pam-lng').value)||null,
  };
  if(!body.name){toast('Введіть назву поста','error');return;}
  const r=await api('/api/posts/'+adminPostId,'PATCH',body);
  if(r?.ok){toast('Пост оновлено','success');await loadPosts();await openPostAdminModal(adminPostId);}
}

async function loadPostAdminDevices(){
  if(!adminPostId) return;
  const box=document.getElementById('pam-devices');
  box.innerHTML='<div class="empty-state"><div class="spinner"></div></div>';
  const devs=await api(`/api/posts/${adminPostId}/devices`);
  if(!devs) return;
  adminPostDevices=devs;
  if(!devs.length){
    box.innerHTML='<div class="empty-state"><div class="icon">◈</div><p>На цьому посту ще немає приладів</p></div>';
    return;
  }
  box.innerHTML=devs.map(d=>`
    <div class="admin-device-row">
      <div><div class="admin-device-name">${d.name}</div><div class="admin-device-meta">${d.id}</div></div>
      <div><span class="chip">${d.type}</span></div>
      <div class="admin-device-meta">${d.host||'—'}:${d.port||'—'}</div>
      <div><span class="sb ${d.is_online?'s-RESOLVED':'s-IGNORED'}">${d.is_online?'Online':'Offline'}</span></div>
      <div class="admin-device-actions">
        <button class="btn-sm" onclick="editDeviceFromPostAdmin('${d.id}')">Налаштувати</button>
        <button class="btn-sm red" onclick="deleteDeviceFromPostAdmin('${d.id}','${(d.name||'').replace(/'/g,'`')}')">Видалити</button>
      </div>
    </div>`).join('');
}

function addDeviceFromPostAdmin(){
  if(!adminPostId) return;
  openDevModal(adminPostId,'','','','',0);
}

function editDeviceFromPostAdmin(deviceId){
  const d=adminPostDevices.find(x=>x.id===deviceId);
  if(!d) return;
  openDevModal(adminPostId,d.id,d.type,d.name,d.host,d.port||0);
}

async function deleteDeviceFromPostAdmin(deviceId,name){
  if(!confirm(`Видалити прилад "${name}"?`)) return;
  const r=await api(`/api/posts/${adminPostId}/devices/${deviceId}`,'DELETE');
  if(r?.ok){toast('Прилад видалено','success');await loadPostAdminDevices();await loadPosts();await loadDevices();}
}
'''
    if "POST ADMIN MODAL: пост + прилади" not in txt:
        marker = "// ── DEVICE MODAL"
        txt = txt.replace(marker, js_block + "\n" + marker, 1)

    # 5) after saveDev success refresh admin modal
    old = "if(r?.ok){closeDevModal();loadDevices();toast(devId?'Оновлено':'Додано','success');}"
    new = "if(r?.ok){closeDevModal();loadDevices();if(adminPostId){await loadPostAdminDevices();await loadPosts();}toast(devId?'Оновлено':'Додано','success');}"
    if old in txt:
        txt = txt.replace(old, new, 1)

    # 6) after deleteDev success refresh admin modal
    old = "if(r?.ok){loadDevices();toast('Видалено','success');}"
    new = "if(r?.ok){loadDevices();if(adminPostId){await loadPostAdminDevices();await loadPosts();}toast('Видалено','success');}"
    if old in txt:
        txt = txt.replace(old, new, 1)

    path.write_text(txt, encoding="utf-8")
    print(f"OK patched UI: {path}")


def patch_posts_router(path: Path):
    txt = path.read_text(encoding="utf-8")
    backup(path)

    # Filter deleted posts/devices when deleted_at exists.
    txt = txt.replace(
        "SELECT * FROM posts WHERE id=%s", 
        "SELECT * FROM posts WHERE id=%s AND deleted_at IS NULL"
    )
    txt = txt.replace(
        "SELECT * FROM posts ORDER BY name", 
        "SELECT * FROM posts WHERE deleted_at IS NULL ORDER BY name"
    )
    txt = txt.replace(
        "SELECT * FROM devices WHERE post_id=%s ORDER BY type", 
        "SELECT * FROM devices WHERE post_id=%s AND deleted_at IS NULL ORDER BY type"
    )
    txt = txt.replace(
        "SELECT * FROM devices WHERE id=%s AND post_id=%s", 
        "SELECT * FROM devices WHERE id=%s AND post_id=%s AND deleted_at IS NULL"
    )
    txt = txt.replace(
        "SELECT * FROM devices WHERE post_id=%s", 
        "SELECT * FROM devices WHERE post_id=%s AND deleted_at IS NULL"
    )

    # Soft delete posts if still physical DELETE.
    txt = txt.replace(
        'execute("DELETE FROM posts WHERE id=%s", (post_id,))',
        'execute("""\n        UPDATE posts\n        SET deleted_at=NOW(), updated_at=NOW(), is_active=FALSE\n        WHERE id=%s\n    """, (post_id,))'
    )

    # Update devices should touch updated_at.
    txt = txt.replace(
        "UPDATE devices SET {set_clause} WHERE id=%s AND post_id=%s",
        "UPDATE devices SET {set_clause}, updated_at=NOW() WHERE id=%s AND post_id=%s"
    )

    # Soft delete devices if still physical DELETE.
    txt = txt.replace(
        'execute("DELETE FROM devices WHERE id=%s AND post_id=%s", (device_id, post_id))',
        'execute("""\n        UPDATE devices\n        SET deleted_at=NOW(), updated_at=NOW(), is_online=FALSE\n        WHERE id=%s AND post_id=%s\n    """, (device_id, post_id))'
    )

    path.write_text(txt, encoding="utf-8")
    print(f"OK patched API: {path}")


def main():
    indexes = find_existing(CANDIDATES_INDEX)
    routers = find_existing(CANDIDATES_POSTS)
    if not indexes:
        raise SystemExit("Не знайдено static/index.html або server/static/index")
    if not routers:
        print("Увага: routers/posts.py не знайдено, патчу API не буде")
    for p in indexes:
        patch_index(p)
    for p in routers:
        patch_posts_router(p)
    print("\nГотово. Перезапусти сервер і зроби git add/commit/push для Railway.")

if __name__ == "__main__":
    main()
