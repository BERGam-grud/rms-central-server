from pathlib import Path

ROOT = Path.cwd()


def find_file(*candidates):
    for c in candidates:
        p = ROOT / c
        if p.exists():
            return p
    raise FileNotFoundError(f"Не знайдено жоден файл із: {candidates}")


def backup(p: Path):
    b = p.with_suffix(p.suffix + ".bak_v37")
    if not b.exists():
        b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")


POST_USER_ENDPOINTS = r'''

# ── КОРИСТУВАЧІ ПОСТА ───────────────────────────────────────

@router.get("/{post_id}/users")
def get_post_users(post_id: str, user: dict = Depends(admin_only)):
    """Адмін: користувачі, прив'язані до конкретного поста, та доступні для прив'язки."""
    post = fetchone("SELECT id, name FROM posts WHERE id=%s AND deleted_at IS NULL", (post_id,))
    if not post:
        raise HTTPException(404, "Пост не знайдено")

    assigned = fetchall("""
        SELECT id, username, email, role, post_id, is_active, last_login, created_at
        FROM users
        WHERE post_id=%s
          AND deleted_at IS NULL
        ORDER BY role, username
    """, (post_id,))

    available = fetchall("""
        SELECT id, username, email, role, post_id, is_active, last_login, created_at
        FROM users
        WHERE deleted_at IS NULL
          AND is_active=TRUE
          AND (post_id IS NULL OR post_id<>%s)
        ORDER BY role, username
    """, (post_id,))

    return {
        "ok": True,
        "post": _fmt_post(post),
        "assigned": [_fmt_post_user(u) for u in assigned],
        "available": [_fmt_post_user(u) for u in available],
    }


@router.post("/{post_id}/users/{user_id}")
def bind_user_to_post(post_id: str, user_id: str, user: dict = Depends(admin_only)):
    """Адмін: прив'язати користувача до поста."""
    post = fetchone("SELECT id FROM posts WHERE id=%s AND deleted_at IS NULL", (post_id,))
    if not post:
        raise HTTPException(404, "Пост не знайдено")

    target = fetchone("SELECT id, username, role FROM users WHERE id=%s AND deleted_at IS NULL", (user_id,))
    if not target:
        raise HTTPException(404, "Користувача не знайдено")

    execute("""
        UPDATE users
        SET post_id=%s,
            updated_at=NOW()
        WHERE id=%s
    """, (post_id, user_id))
    return {"ok": True}


@router.delete("/{post_id}/users/{user_id}")
def unbind_user_from_post(post_id: str, user_id: str, user: dict = Depends(admin_only)):
    """Адмін: відв'язати користувача від поста."""
    target = fetchone("SELECT id FROM users WHERE id=%s AND post_id=%s AND deleted_at IS NULL", (user_id, post_id))
    if not target:
        raise HTTPException(404, "Користувача не знайдено у цьому пості")

    execute("""
        UPDATE users
        SET post_id=NULL,
            updated_at=NOW()
        WHERE id=%s
    """, (user_id,))
    return {"ok": True}
'''


FMT_USER_FUNC = r'''

def _fmt_post_user(r):
    return {
        "id": str(r["id"]),
        "username": r.get("username"),
        "email": r.get("email"),
        "role": r.get("role"),
        "post_id": str(r["post_id"]) if r.get("post_id") else None,
        "is_active": r.get("is_active"),
        "last_login": r["last_login"].isoformat() if r.get("last_login") else None,
        "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
    }
'''


POST_USERS_MODAL = r'''

<!-- MODAL: Користувачі поста -->
<div class="modal-overlay" id="post-users-modal">
  <div class="modal" style="width:760px;max-width:95vw">
    <div class="modal-header">
      <span id="post-users-title">Користувачі поста</span>
      <span class="modal-close" onclick="closePostUsersModal()">×</span>
    </div>
    <div class="modal-body">
      <div class="modal-section">Прив'язані користувачі</div>
      <div class="table-card" style="max-height:280px;overflow:auto;margin-bottom:12px">
        <table>
          <thead><tr><th>Логін</th><th>Email</th><th>Роль</th><th>Статус</th><th></th></tr></thead>
          <tbody id="post-users-assigned">
            <tr><td colspan="5" class="empty-state">Завантаження...</td></tr>
          </tbody>
        </table>
      </div>

      <div class="modal-section">Додати користувача до поста</div>
      <div style="display:grid;grid-template-columns:1fr auto;gap:10px;align-items:end">
        <div class="fg">
          <label>Користувач</label>
          <select class="fi" style="width:100%" id="post-users-select"></select>
        </div>
        <button class="btn-save" onclick="assignSelectedUserToPost()">Прив'язати</button>
      </div>
      <div style="background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;font-size:11px;color:var(--text-sec);margin-top:10px">
        Оператор або гість із прив'язкою до поста у локальному режимі бачитиме тільки цей пост. Адміністратор у центральному режимі бачить усю систему.
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn-cancel" onclick="closePostUsersModal()">Закрити</button>
    </div>
  </div>
</div>
'''


POST_USERS_JS = r'''

// ── POST USERS BINDING ─────────────────────────────────────
let postUsersCurrentPostId = null;
let postUsersCurrentPostName = '';

function escHtml(s){
  return String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

async function openPostUsers(postId, postName){
  if(me.role !== 'admin'){
    toast('Доступно тільки адміністратору', 'error');
    return;
  }
  postUsersCurrentPostId = postId;
  postUsersCurrentPostName = postName || '';
  document.getElementById('post-users-title').textContent = `Користувачі поста: ${postUsersCurrentPostName}`;
  document.getElementById('post-users-modal').classList.add('open');
  await loadPostUsers();
}

function closePostUsersModal(){
  document.getElementById('post-users-modal').classList.remove('open');
  postUsersCurrentPostId = null;
}

async function loadPostUsers(){
  if(!postUsersCurrentPostId) return;
  const data = await api(`/api/posts/${postUsersCurrentPostId}/users`);
  if(!data) return;

  const tbody = document.getElementById('post-users-assigned');
  if(!data.assigned?.length){
    tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-dim);padding:14px">До цього поста ще не прив’язано користувачів</td></tr>';
  }else{
    tbody.innerHTML = data.assigned.map(u => `<tr>
      <td class="val">${escHtml(u.username)}</td>
      <td>${escHtml(u.email)}</td>
      <td><span class="role-badge role-${escHtml(u.role)}">${escHtml(u.role)}</span></td>
      <td><span class="sb ${u.is_active?'s-RESOLVED':'s-IGNORED'}">${u.is_active?'Активний':'Заблокований'}</span></td>
      <td style="text-align:right">
        ${u.id!==me.id?`<button class="btn-sm red" onclick="unassignUserFromPost('${u.id}')">Відв'язати</button>`:'<span style="font-size:11px;color:var(--text-dim)">це ви</span>'}
      </td>
    </tr>`).join('');
  }

  const sel = document.getElementById('post-users-select');
  sel.innerHTML = '<option value="">— оберіть користувача —</option>';
  (data.available || []).forEach(u => {
    const opt = document.createElement('option');
    opt.value = u.id;
    opt.textContent = `${u.username} · ${u.email} · ${u.role}`;
    sel.appendChild(opt);
  });
}

async function assignSelectedUserToPost(){
  const userId = document.getElementById('post-users-select').value;
  if(!userId){toast('Оберіть користувача', 'error'); return;}
  const r = await api(`/api/posts/${postUsersCurrentPostId}/users/${userId}`, 'POST', {});
  if(r?.ok){
    toast('Користувача прив’язано до поста', 'success');
    await loadPostUsers();
    if(typeof loadUsers === 'function') loadUsers();
  }
}

async function unassignUserFromPost(userId){
  if(!confirm('Відв’язати користувача від цього поста?')) return;
  const r = await api(`/api/posts/${postUsersCurrentPostId}/users/${userId}`, 'DELETE');
  if(r?.ok){
    toast('Користувача відв’язано', 'success');
    await loadPostUsers();
    if(typeof loadUsers === 'function') loadUsers();
  }
}
'''


def patch_posts_router():
    p = find_file("routers/posts.py", "server/routers/posts.py")
    backup(p)
    s = p.read_text(encoding="utf-8")

    if "@router.get(\"/{post_id}/users\")" not in s:
        marker = "# ── ПРИЛАДИ"
        if marker in s:
            s = s.replace(marker, POST_USER_ENDPOINTS + "\n\n" + marker, 1)
        else:
            s += POST_USER_ENDPOINTS

    if "def _fmt_post_user" not in s:
        # Insert before _fmt_meas or append at the end.
        marker = "def _fmt_meas"
        if marker in s:
            s = s.replace(marker, FMT_USER_FUNC + "\n" + marker, 1)
        else:
            s += FMT_USER_FUNC

    p.write_text(s, encoding="utf-8")
    print(f"OK: patched {p}")


def patch_index():
    p = find_file("static/index.html", "server/static/index", "server/static/index.html")
    backup(p)
    s = p.read_text(encoding="utf-8")

    # Add users button to post cards.
    if "openPostUsers(" not in s:
        needle = "<button class=\"btn-sm\" onclick=\"event.stopPropagation();openDevModal('${p.id}','','','','',0)\">+ Прилад</button>"
        repl = needle + "\n        <button class=\"btn-sm\" onclick=\"event.stopPropagation();openPostUsers('${p.id}','${(p.name||'').replace(/'/g,'`')}')\">👥 Користувачі</button>"
        if needle in s:
            s = s.replace(needle, repl, 1)
        else:
            # Fallback: insert after any + Прилад button in admin post card.
            s = s.replace("+ Прилад</button>", "+ Прилад</button>\n        <button class=\"btn-sm\" onclick=\"event.stopPropagation();openPostUsers('${p.id}','${(p.name||'').replace(/'/g,'`')}')\">👥 Користувачі</button>", 1)

    # Add modal before toast container.
    if "id=\"post-users-modal\"" not in s:
        marker = '<div id="toast-container"></div>'
        if marker in s:
            s = s.replace(marker, POST_USERS_MODAL + "\n" + marker, 1)
        else:
            s = s.replace("<script>", POST_USERS_MODAL + "\n<script>", 1)

    # Add JS before USERS section.
    if "postUsersCurrentPostId" not in s:
        marker = "// ── USERS"
        if marker in s:
            s = s.replace(marker, POST_USERS_JS + "\n" + marker, 1)
        else:
            s = s.replace("// ── NAV", POST_USERS_JS + "\n// ── NAV", 1)

    p.write_text(s, encoding="utf-8")
    print(f"OK: patched {p}")


if __name__ == "__main__":
    patch_posts_router()
    patch_index()
    print("\nГотово. Перезапусти сервер і зроби Ctrl+F5 у браузері.")
