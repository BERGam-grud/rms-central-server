from pathlib import Path
import shutil
import re

ROOT = Path.cwd()
INDEX = ROOT / 'server' / 'static' / 'index'
if not INDEX.exists():
    raise SystemExit('Не знайдено server/static/index. Запусти скрипт з кореня проєкту C:\\PROG або C:\\rms-central-server')

text = INDEX.read_text(encoding='utf-8')
backup = INDEX.with_suffix('.backup_v38')
if not backup.exists():
    shutil.copy2(INDEX, backup)

MARK_CSS = '/* RMS_V2_UI_ARCHITECTURE_PATCH_V38_CSS */'
MARK_JS = '// RMS_V2_UI_ARCHITECTURE_PATCH_V38_JS'

css = r'''
/* RMS_V2_UI_ARCHITECTURE_PATCH_V38_CSS */
.mode-pill{padding:3px 9px;border:1px solid var(--border);border-radius:999px;font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--text-sec)}
.mode-pill.central{border-color:rgba(167,139,250,.45);color:var(--purple);background:rgba(167,139,250,.09)}
.mode-pill.local{border-color:rgba(0,229,160,.35);color:var(--green);background:rgba(0,229,160,.08)}
.srv-btn.locked{opacity:.35;cursor:not-allowed}
.rms-v2-toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
.rms-v2-filter{padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius);background:var(--bg-2);color:var(--text-sec);font-size:11px}
.rms-v2-filter.active{border-color:var(--green-dim);color:var(--green);background:rgba(0,229,160,.08)}
.rms-v2-search{min-width:220px;padding:7px 10px;background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);color:var(--text-pri);font-size:12px}
.workspace-grid{display:grid;grid-template-columns:1.2fr .8fr;gap:16px;margin-bottom:16px}
.workspace-card{background:var(--bg-1);border:1px solid var(--border);border-radius:var(--radius);padding:16px}
.workspace-card h3{font-size:14px;margin-bottom:10px}.workspace-muted{color:var(--text-sec);font-size:12px}
.info-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}.info-box{background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);padding:10px}.info-label{font-size:10px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.08em}.info-value{font-family:var(--font-mono);font-size:13px;margin-top:3px}
.device-card .device-card-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.device-card.clickable{cursor:pointer}.device-card.clickable:hover{border-color:var(--green-dim)}
.device-detail-hero{display:grid;grid-template-columns:240px 1fr;gap:16px;margin-bottom:16px}.big-value{font-family:var(--font-mono);font-size:34px;font-weight:700;color:var(--green)}.big-unit{font-size:12px;color:var(--text-sec)}
.post-device-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}.mini-device{background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);padding:12px}.mini-title{font-weight:700;margin-bottom:3px}.mini-meta{font-size:11px;color:var(--text-sec);font-family:var(--font-mono)}
@media(max-width:1000px){.workspace-grid,.device-detail-hero{grid-template-columns:1fr}}
'''

js = r'''
// RMS_V2_UI_ARCHITECTURE_PATCH_V38_JS
(function(){
  const V2 = { deviceCache: [], postDeviceCache: {}, selectedDevice: null, selectedPost: null, deviceFilter: 'ALL', deviceSearch: '' };

  function htmlEscape(v){return String(v ?? '').replace(/[&<>'"]/g, s=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[s]));}
  function localApi(){ return IS_RAILWAY ? '' : 'http://localhost:8000'; }
  function centralApi(){ return API_CENTRAL; }
  function isAdmin(){ return me && me.role === 'admin'; }
  function isCentral(){ return currentServer === 'central'; }

  function ensurePages(){
    const content = document.querySelector('.content');
    if(!content) return;
    if(!document.getElementById('page-post-workspace')){
      content.insertAdjacentHTML('beforeend', `
      <div class="page" id="page-post-workspace">
        <div class="page-header">
          <div><div class="page-title" id="post-ws-title">Картка поста</div><div class="page-sub" id="post-ws-sub">Керування постом, приладами, користувачами і налаштуваннями</div></div>
          <div class="page-actions"><button class="btn-action" onclick="showPage('posts')">← До постів</button><button class="btn-action green" id="post-ws-add-device">+ Прилад</button></div>
        </div>
        <div id="post-workspace-body"><div class="empty-state"><div class="spinner"></div></div></div>
      </div>`);
    }
    if(!document.getElementById('page-device-workspace')){
      content.insertAdjacentHTML('beforeend', `
      <div class="page" id="page-device-workspace">
        <div class="page-header">
          <div><div class="page-title" id="device-ws-title">Картка приладу</div><div class="page-sub" id="device-ws-sub">Поточні значення, пороги, TCP/RS485, журнал</div></div>
          <div class="page-actions"><button class="btn-action" onclick="showPage('devices')">← До приладів</button><button class="btn-action green" id="device-ws-edit">Редагувати</button></div>
        </div>
        <div id="device-workspace-body"><div class="empty-state"><div class="spinner"></div></div></div>
      </div>`);
    }
  }

  function ensureModePill(){
    let p = document.getElementById('mode-pill');
    if(!p){
      p = document.createElement('span');
      p.id='mode-pill';
      p.className='mode-pill local';
      const brand=document.querySelector('.topbar-brand');
      if(brand) brand.insertAdjacentElement('afterend', p);
    }
    p.className='mode-pill '+(isCentral()?'central':'local');
    p.textContent=isCentral()?'Диспетчерський центр':'Локальний пост';
  }

  function applyAccess(){
    ensurePages(); ensureModePill();
    const sw=document.getElementById('server-switch');
    const centralBtn=document.getElementById('btn-central');
    const adminSec=document.getElementById('admin-section');
    if(sw) sw.style.display = isAdmin() ? 'flex' : 'none';
    if(centralBtn) centralBtn.classList.toggle('locked', !isAdmin());
    if(!isAdmin()){
      currentServer='local'; API=localApi();
    }
    if(adminSec) adminSec.style.display = (isAdmin() && isCentral()) ? '' : 'none';
    const banner=document.getElementById('central-banner');
    if(banner){
      banner.classList.toggle('show', isCentral());
      banner.textContent = isCentral() ? '◎ Центральний режим — диспетчерський центр, всі пости, всі прилади, всі аварії' : '◉ Локальний режим — робоче місце конкретного поста';
    }
    const dashTitle=document.querySelector('#page-dashboard .page-title');
    if(dashTitle) dashTitle.textContent = isCentral() ? 'Центральна панель' : 'Головна поста';
    const devSub=document.querySelector('#page-devices .page-sub');
    if(devSub) devSub.textContent = isCentral() ? 'Усі прилади по всіх постах' : 'Прилади локального поста';
    const readSub=document.querySelector('#page-readings .page-sub');
    if(readSub) readSub.textContent = isCentral() ? 'Останні вимірювання з усієї системи' : 'Останні вимірювання локального поста';
  }

  window.switchServer = function(type){
    if(type==='central' && !isAdmin()){
      currentServer='local'; API=localApi(); applyAccess(); toast('Центральний режим доступний тільки адміністратору','error'); return;
    }
    currentServer = type;
    API = type==='central' ? centralApi() : localApi();
    document.getElementById('btn-local')?.classList.toggle('active', type==='local');
    document.getElementById('btn-central')?.classList.toggle('active', type==='central');
    applyAccess();
    if(ws) ws.close();
    chartHist = {};
    Object.values(chartInst).forEach(ch=>{ if(ch){ ch.data.labels=[]; ch.data.datasets[0].data=[]; ch.update('none'); }});
    loadDevices(); loadAlarms(); initCharts();
    toast(type==='central'?'◎ Центральний режим':'◉ Локальний режим','success');
  };

  const oldBoot = window.boot;
  window.boot = function(){
    if(!isAdmin()){ currentServer='local'; API=localApi(); }
    else { currentServer = currentServer || 'local'; API = currentServer==='central' ? centralApi() : localApi(); }
    if(oldBoot) oldBoot();
    applyAccess();
  };

  const oldShowPage = window.showPage;
  window.showPage = function(name){
    applyAccess();
    if((name==='posts' || name==='users') && (!isAdmin() || !isCentral())){
      toast('Адміністрування доступне тільки адміністратору у центральному режимі','error');
      name='dashboard';
    }
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
    document.getElementById('page-'+name)?.classList.add('active');
    document.getElementById('nav-'+name)?.classList.add('active');
    if(name==='alarms')  loadAlarms();
    if(name==='users')   loadUsers();
    if(name==='readings')renderReadings();
    if(name==='posts')   {loadPosts();setTimeout(()=>leafMap&&leafMap.invalidateSize(),300);}
    if(name==='devices') loadDevices();
  };

  window.renderPostsList = async function(posts){
    const list=document.getElementById('posts-list');
    if(!posts.length){list.innerHTML='<div class="empty-state"><div class="icon">◎</div><p>Немає постів</p></div>';return;}
    list.innerHTML=posts.map(p=>`
      <div class="post-card" id="pc-${p.id}" onclick="selectPost('${p.id}')">
        <div class="post-card-header"><div class="post-card-name">${htmlEscape(p.name)}</div><span class="sb ${p.is_active?'s-RESOLVED':'s-IGNORED'}">${p.is_active?'Активний':'Вимкнений'}</span></div>
        <div class="post-card-meta">${htmlEscape(p.location||'—')} · ${htmlEscape(p.region||'—')}</div>
        ${p.latitude?`<div class="post-card-meta" style="font-family:var(--font-mono);font-size:10px;margin-top:2px">${p.latitude}, ${p.longitude}</div>`:''}
        <div class="post-stats" id="ps-stats-${p.id}"><span class="post-stat ps-ok">Завантаження...</span></div>
        ${isAdmin()&&isCentral()?`<div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap">
          <button class="btn-sm" onclick="event.stopPropagation();openPostWorkspace('${p.id}')">Картка</button>
          <button class="btn-sm" onclick="event.stopPropagation();openDevModal('${p.id}','','','','',0)">+ Прилад</button>
          <button class="btn-sm" onclick="event.stopPropagation();openPostModal('${p.id}','${htmlEscape(p.name)}','${htmlEscape(p.location||'')}','${htmlEscape(p.region||'')}',${p.latitude||''},${p.longitude||''})">Редагувати</button>
          <button class="btn-sm red" onclick="event.stopPropagation();deletePost('${p.id}','${htmlEscape(p.name)}')">Видалити</button>
        </div>`:''}
      </div>`).join('');
    for(const p of posts) loadPostStats(p.id);
  };

  window.loadDevices = async function(){
    const posts=await api('/api/posts/');
    const grid=document.getElementById('devices-grid');
    if(!grid) return;
    if(!posts?.length){grid.innerHTML='<div class="empty-state"><div class="icon">◈</div><p>Немає постів</p></div>';return;}
    V2.deviceCache=[];
    for(const post of posts){
      const devs=await api(`/api/posts/${post.id}/devices`);
      if(!devs?.length) continue;
      for(const d of devs){ V2.deviceCache.push({...d, post_name: post.name, post_id: post.id}); }
    }
    renderDeviceDirectory();
  };

  window.renderDeviceDirectory = async function(){
    const grid=document.getElementById('devices-grid');
    if(!grid) return;
    const types=['ALL',...Array.from(new Set(V2.deviceCache.map(d=>d.type).filter(Boolean)))];
    const q=V2.deviceSearch.toLowerCase();
    const data=V2.deviceCache.filter(d=>(V2.deviceFilter==='ALL'||d.type===V2.deviceFilter) && (!q || (d.name||'').toLowerCase().includes(q) || (d.post_name||'').toLowerCase().includes(q) || (d.type||'').toLowerCase().includes(q)));
    grid.innerHTML = `<div style="grid-column:1/-1" class="rms-v2-toolbar">
      ${types.map(t=>`<button class="rms-v2-filter ${V2.deviceFilter===t?'active':''}" onclick="setDeviceFilter('${t}')">${t==='ALL'?'Всі':htmlEscape(t)}</button>`).join('')}
      <button class="rms-v2-filter ${V2.deviceFilter==='OFFLINE'?'active':''}" onclick="setDeviceFilter('OFFLINE')">Offline</button>
      <input class="rms-v2-search" placeholder="🔍 Знайти прилад або пост..." value="${htmlEscape(V2.deviceSearch)}" oninput="setDeviceSearch(this.value)"/>
    </div>`;
    const list = V2.deviceFilter==='OFFLINE' ? V2.deviceCache.filter(d=>!d.is_online) : data;
    if(!list.length){grid.insertAdjacentHTML('beforeend','<div class="empty-state"><div class="icon">◈</div><p>Немає приладів за фільтром</p></div>');return;}
    for(const d of list){
      const icons={PAED_GAMMA:'☢',SPECTROMETER:'◈',PFU:'⬡'};
      const el=document.createElement('div'); el.className='device-card clickable';
      el.onclick=()=>openDeviceWorkspace(d.id);
      el.innerHTML=`<div class="device-header">
        <div class="device-icon">${icons[d.type]||'○'}</div><div style="flex:1"><div class="device-name">${htmlEscape(d.name)}</div><div class="device-type">${htmlEscape(d.type)} · ${htmlEscape(d.post_name)}</div><div class="device-conn">${htmlEscape(d.host||'—')}:${htmlEscape(d.port||'—')}</div></div><div class="online-dot ${d.is_online?'online':'offline'}"></div></div>
        <div class="readings-list" id="dr-${d.id}"><div style="font-size:11px;color:var(--text-dim);padding:4px 0">Натисніть для картки приладу</div></div>
        <div class="device-card-actions"><button class="btn-sm" onclick="event.stopPropagation();openDeviceWorkspace('${d.id}')">Картка</button>${isAdmin()?`<button class="btn-sm" onclick="event.stopPropagation();openDevModal('${d.post_id}','${d.id}','${d.type}','${htmlEscape(d.name)}','${htmlEscape(d.host||'')}',${d.port||0})">Налаштування</button>`:''}</div>`;
      grid.appendChild(el);
    }
    updateDevCards();
  };
  window.setDeviceFilter=function(t){V2.deviceFilter=t;renderDeviceDirectory();};
  window.setDeviceSearch=function(v){V2.deviceSearch=v;renderDeviceDirectory();};

  window.openPostWorkspace = async function(postId){
    if(!isAdmin() || !isCentral()){toast('Картка поста доступна адміністратору у центральному режимі','error');return;}
    V2.selectedPost=postId; showPage('post-workspace'); await loadPostWorkspace(postId);
  };
  async function loadPostWorkspace(postId){
    const post = (allPosts||[]).find(p=>p.id===postId) || await api('/api/posts/'+postId);
    const devs = await api(`/api/posts/${postId}/devices`) || [];
    const users = await api('/api/users/') || [];
    const body=document.getElementById('post-workspace-body');
    document.getElementById('post-ws-title').textContent = post ? `Пост: ${post.name}` : 'Картка поста';
    document.getElementById('post-ws-add-device').onclick=()=>openDevModal(postId,'','','','',0);
    body.innerHTML=`<div class="workspace-grid"><div class="workspace-card"><h3>Інформація</h3><div class="info-grid">
      <div class="info-box"><div class="info-label">Назва</div><div class="info-value">${htmlEscape(post?.name||'—')}</div></div>
      <div class="info-box"><div class="info-label">Регіон</div><div class="info-value">${htmlEscape(post?.region||'—')}</div></div>
      <div class="info-box"><div class="info-label">Локація</div><div class="info-value">${htmlEscape(post?.location||'—')}</div></div>
      <div class="info-box"><div class="info-label">GPS</div><div class="info-value">${post?.latitude||'—'} / ${post?.longitude||'—'}</div></div>
      <div class="info-box"><div class="info-label">Статус</div><div class="info-value">${post?.is_active?'Активний':'Вимкнений'}</div></div>
    </div><div style="margin-top:12px"><button class="btn-action green" onclick="openPostModal('${postId}','${htmlEscape(post?.name||'')}','${htmlEscape(post?.location||'')}','${htmlEscape(post?.region||'')}',${post?.latitude||''},${post?.longitude||''})">Редагувати інформацію</button></div></div>
    <div class="workspace-card"><h3>Користувачі поста</h3>${users.filter(u=>u.post_id===postId).map(u=>`<div class="mini-device"><div class="mini-title">${htmlEscape(u.username)} <span class="role-badge role-${u.role}">${u.role}</span></div><div class="mini-meta">${htmlEscape(u.email||'')}</div></div>`).join('') || '<div class="workspace-muted">Користувачів не прив’язано</div>'}</div></div>
    <div class="workspace-card"><h3>Прилади поста</h3><div class="post-device-list">${devs.map(d=>`<div class="mini-device"><div class="mini-title">${htmlEscape(d.name)}</div><div class="mini-meta">${htmlEscape(d.type)} · ${htmlEscape(d.host||'—')}:${htmlEscape(d.port||'—')}</div><div style="display:flex;gap:6px;margin-top:8px"><button class="btn-sm" onclick="openDeviceWorkspace('${d.id}')">Картка</button><button class="btn-sm" onclick="openDevModal('${postId}','${d.id}','${d.type}','${htmlEscape(d.name)}','${htmlEscape(d.host||'')}',${d.port||0})">Налаштування</button></div></div>`).join('') || '<div class="workspace-muted">Приладів немає</div>'}</div></div>`;
  }

  window.openDeviceWorkspace = async function(deviceId){
    if(!V2.deviceCache.length) await loadDevices();
    const d=V2.deviceCache.find(x=>x.id===deviceId);
    if(!d){toast('Прилад не знайдено','error');return;}
    V2.selectedDevice=d; showPage('device-workspace'); renderDeviceWorkspace(d);
  };
  function renderDeviceWorkspace(d){
    document.getElementById('device-ws-title').textContent = d.name;
    document.getElementById('device-ws-sub').textContent = `${d.type} · ${d.post_name}`;
    document.getElementById('device-ws-edit').onclick=()=>openDevModal(d.post_id,d.id,d.type,d.name,d.host,d.port||0);
    const latest = liveData.filter(r=>r.device_id===d.id).sort((a,b)=>new Date(b.recorded_at)-new Date(a.recorded_at));
    const main = latest[0];
    document.getElementById('device-workspace-body').innerHTML=`<div class="device-detail-hero"><div class="workspace-card"><h3>Поточне значення</h3><div class="big-value">${main?parseFloat(main.value).toFixed(4):'—'}</div><div class="big-unit">${htmlEscape(main?.unit||'очікування даних')}</div><div class="workspace-muted" style="margin-top:8px">${main?fmt(main.recorded_at):'—'}</div></div><div class="workspace-card"><h3>Зв’язок і налаштування</h3><div class="info-grid"><div class="info-box"><div class="info-label">Статус</div><div class="info-value">${d.is_online?'Online':'Offline'}</div></div><div class="info-box"><div class="info-label">IP</div><div class="info-value">${htmlEscape(d.host||'—')}</div></div><div class="info-box"><div class="info-label">TCP Port</div><div class="info-value">${htmlEscape(d.port||'—')}</div></div><div class="info-box"><div class="info-label">Пост</div><div class="info-value">${htmlEscape(d.post_name)}</div></div></div></div></div><div class="workspace-card"><h3>Останні параметри</h3><div class="table-card"><table><thead><tr><th>Параметр</th><th>Значення</th><th>Одиниця</th><th>Час</th></tr></thead><tbody>${latest.length?latest.map(r=>`<tr><td class="val">${htmlEscape(r.parameter)}</td><td class="val">${parseFloat(r.value).toFixed(4)}</td><td>${htmlEscape(r.unit)}</td><td style="font-family:var(--font-mono);font-size:11px">${fmt(r.recorded_at)}</td></tr>`).join(''):'<tr><td colspan="4"><div class="empty-state"><p>Немає даних</p></div></td></tr>'}</tbody></table></div></div>`;
  }

  // First-run UI preparation when patch is loaded after the original script.
  window.addEventListener('load',()=>setTimeout(applyAccess,300));
})();
'''

if MARK_CSS not in text:
    text = text.replace('</style>', css + '\n</style>')
if MARK_JS not in text:
    text = text.replace('</script>\n</body>', js + '\n</script>\n</body>')

INDEX.write_text(text, encoding='utf-8')
print('OK: RMS v2 UI architecture patch applied')
print(f'Backup: {backup}')
