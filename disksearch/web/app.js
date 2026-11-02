(function () {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => Array.from(document.querySelectorAll(selector));
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
  const eur = (value) => value == null || value === '' ? '—' : Number(value).toLocaleString('es-ES', { style: 'currency', currency: 'EUR' });
  const fmtDate = (value) => {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString('es-ES');
  };
  const fmtCap = (gb) => {
    const n = Number(gb || 0);
    if (!n) return '—';
    return n >= 1000 ? `${(n / 1000).toLocaleString('es-ES', { maximumFractionDigits: 2 })} TB` : `${n} GB`;
  };

  const EMPTY = { meta: { time: '—', pages: 0, raw: 0, unique: 0, shown: 0, sources: [] }, items: [], highlights: {} };
  let D = DATA || EMPTY;
  let BOOTDATA = BOOT || {};
  let FAV = new Set((D && D.favorites) || BOOTDATA.favorites || []);

  const state = { brand: '', sortKey: 'ppt', sortDir: 'asc', page: 1, pageSize: 25, tab: 'search' };
  const hstate = {
    q: '', status: '', favorites: false, sort: 'last_seen', dir: 'desc',
    page: 1, pageSize: 25, total: 0, items: [], stats: {}, notifications: [],
    expanded: null, details: {}, loaded: false,
  };

  // ── utilidades de render ──────────────────────────────────────────────
  function setOptions(selector, values) {
    const select = $(selector);
    if (!select) return;
    const current = select.value;
    const first = select.options[0];
    select.innerHTML = '';
    if (first) select.appendChild(first);
    values.forEach((value) => {
      if (!value) return;
      const option = document.createElement('option');
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    });
    if (values.includes(current)) select.value = current;
  }

  function renderStats() {
    const meta = D.meta || {};
    $('#stats').innerHTML = [
      ['Hora de búsqueda', meta.time || '—'],
      ['Páginas encontradas', meta.pages || 0],
      ['Discos distintos', meta.unique || 0],
      ['Mostrados', meta.shown || 0],
    ].map(([label, value]) => `<div class="stat"><small>${label}</small><b>${esc(value)}</b></div>`).join('');
  }

  function renderSources() {
    const sources = (D.meta && D.meta.sources) || [];
    $('#srcs').innerHTML = sources.map((source) => {
      const bad = source.note ? ' class="bad"' : '';
      const note = source.note ? ' — ' + esc(source.note) : '';
      return `<span${bad}>${esc(source.name)}: ${source.items || 0} productos${note}</span>`;
    }).join('');
  }

  function card(title, color, item, why) {
    if (!item) return `<div class="card" style="--c:${color}"><h3>${title}</h3><div class="meta">Sin datos suficientes (${esc(why || '')}).</div></div>`;
    return `<div class="card" style="--c:${color}"><h3>${title}</h3>
      <div class="m">${esc(item.brand)} ${esc(item.model)}</div>
      <div class="p">${eur(item.price)}</div>
      <div class="meta">${fmtCap(item.capacity_gb)} · ${item.cache ? item.cache + ' MB' : 'caché n/d'} · ${item.ppt == null ? '—' : eur(item.ppt) + '/TB'}${item.rating ? ` · ★ ${item.rating} (${item.reviews})` : ''} · ${esc(item.store)}</div>
      <a href="${esc(item.url)}" target="_blank" rel="noopener">Ver producto</a></div>`;
  }

  function renderHighlights() {
    const h = D.highlights || {};
    $('#hl').innerHTML = card('El más barato', 'var(--cheap)', h.cheapest, '')
      + card('El más valorado', 'var(--rate)', h.rated, 'las tiendas no publican valoraciones')
      + card('El mejor', 'var(--best)', h.best, '');
  }

  function renderChips() {
    const brands = [...new Set((D.items || []).map((item) => item.brand).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'es'));
    if (state.brand && !brands.includes(state.brand)) state.brand = '';
    $('#chips').innerHTML = ['', ...brands].map((brand) =>
      `<button type="button" class="chip" aria-pressed="${brand === state.brand}" data-brand="${esc(brand)}">${brand ? esc(brand) : 'Todas'}</button>`
    ).join('');
  }

  function fillFilters() {
    setOptions('#form', [...new Set((D.items || []).map((item) => item.form_factor).filter(Boolean))].sort());
    setOptions('#iface', [...new Set((D.items || []).map((item) => item.interface).filter((value) => value && value !== '—'))].sort());
    setOptions('#store', [...new Set((D.items || []).map((item) => item.store).filter(Boolean))].sort());
  }

  // ── resultados ────────────────────────────────────────────────────────
  function itemValue(item, key) {
    if (key === 'tb') return item.capacity_gb;
    if (key === 'rating') return item.rating;
    if (key === 'cache') return item.cache;
    return item[key];
  }

  function filteredItems() {
    const query = ($('#q').value || '').toLowerCase().trim();
    const form = $('#form').value;
    const iface = $('#iface').value;
    const nas = $('#nas').value;
    const store = $('#store').value;
    const favOnly = $('#favonly').checked;
    const min = parseFloat($('#capmin').value);
    const max = parseFloat($('#capmax').value);
    return (D.items || []).filter((item) => {
      if (state.brand && item.brand !== state.brand) return false;
      if (form && item.form_factor !== form) return false;
      if (iface && item.interface !== iface) return false;
      if (nas === 'yes' && !item.nas) return false;
      if (nas === 'no' && item.nas) return false;
      if (store && item.store !== store) return false;
      if (favOnly && !FAV.has(item.key)) return false;
      if (!Number.isNaN(min) && item.capacity_gb / 1000 < min) return false;
      if (!Number.isNaN(max) && item.capacity_gb / 1000 > max) return false;
      if (query && !`${item.brand} ${item.model} ${item.store} ${item.title}`.toLowerCase().includes(query)) return false;
      return true;
    });
  }

  function compareItems(a, b) {
    const key = state.sortKey;
    let va = itemValue(a, key);
    let vb = itemValue(b, key);
    if (va == null || va === '') {
      if (vb == null || vb === '') return String(a.key).localeCompare(String(b.key));
      return 1;
    }
    if (vb == null || vb === '') return -1;
    let result;
    if (typeof va === 'number' && typeof vb === 'number') result = va - vb;
    else result = String(va).localeCompare(String(vb), 'es', { numeric: true, sensitivity: 'base' });
    if (result === 0) result = String(a.key).localeCompare(String(b.key));
    return state.sortDir === 'asc' ? result : -result;
  }

  function setSort(key) {
    if (state.sortKey === key) state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
    else {
      state.sortKey = key;
      state.sortDir = ['capacity_gb', 'tb', 'cache', 'rating'].includes(key) ? 'desc' : 'asc';
    }
    state.page = 1;
    renderRows();
  }

  function renderSortState() {
    $$('th[data-key]').forEach((th) => {
      if (th.dataset.key === state.sortKey) {
        th.setAttribute('aria-sort', state.sortDir === 'asc' ? 'ascending' : 'descending');
      } else {
        th.removeAttribute('aria-sort');
      }
    });
  }

  function tagHtml(item) {
    const h = D.highlights || {};
    const tags = [];
    if (h.cheapest && h.cheapest.key === item.key) tags.push(['Barato', 'var(--cheap)']);
    if (h.rated && h.rated.key === item.key) tags.push(['Valorado', 'var(--rate)']);
    if (h.best && h.best.key === item.key) tags.push(['Mejor', 'var(--best)']);
    return tags.map(([name, color]) => `<span class="tag" style="--c:${color}">${name}</span>`).join('');
  }

  function rowHtml(item, maxCapacity) {
    const favorite = FAV.has(item.key);
    const width = Math.max(3, Math.min(100, (item.capacity_gb / Math.max(maxCapacity, 1)) * 100));
    return `<tr>
      <td class="favcol"><button type="button" class="fav" data-fav="${esc(item.key)}" aria-pressed="${favorite}" aria-label="${favorite ? 'Quitar de favoritos' : 'Añadir a favoritos'}" title="${favorite ? 'Quitar de favoritos' : 'Añadir a favoritos'}">${favorite ? '★' : '☆'}</button></td>
      <td>${esc(item.brand)}</td>
      <td><span class="model" title="${esc(item.title)}">${esc(item.model)}</span>${tagHtml(item)}</td>
      <td><div class="cap"><b>${fmtCap(item.capacity_gb)}</b><i><u style="width:${width}%"></u></i></div></td>
      <td class="num">${item.cache ? item.cache + ' MB' : '—'}</td>
      <td>${item.form_factor ? esc(item.form_factor) + '"' : '—'}</td>
      <td class="num"><b>${eur(item.price)}</b>${item.offers > 1 ? `<div class="foot">${item.offers} ofertas</div>` : ''}</td>
      <td class="num">${item.ppt == null ? '—' : eur(item.ppt)}</td>
      <td title="${esc(item.title)}">${esc(item.store)}</td>
      <td><a href="${esc(item.url)}" target="_blank" rel="noopener">Abrir</a></td>
    </tr>`;
  }

  function pagerHtml(total, page, pageSize, attribute) {
    const pages = Math.max(1, Math.ceil(total / pageSize));
    const current = Math.min(Math.max(1, page), pages);
    const numbers = [];
    const start = Math.max(1, current - 2);
    const end = Math.min(pages, current + 2);
    for (let n = start; n <= end; n += 1) numbers.push(n);
    const buttons = [
      `<button type="button" data-${attribute}="${current - 1}" ${current <= 1 ? 'disabled' : ''}>‹ Anterior</button>`,
      ...numbers.map((n) => `<button type="button" data-${attribute}="${n}" ${n === current ? 'aria-current="page"' : ''}>${n}</button>`),
      `<button type="button" data-${attribute}="${current + 1}" ${current >= pages ? 'disabled' : ''}>Siguiente ›</button>`,
    ].join('');
    const sizes = [25, 50, 100].map((n) => `<option value="${n}" ${n === pageSize ? 'selected' : ''}>${n}</option>`).join('');
    return `${buttons}<span class="spacer"></span><label>Por página <select data-pagesize="${attribute}">${sizes}</select></label>`;
  }

  function renderRows() {
    const all = filteredItems();
    all.sort(compareItems);
    const pages = Math.max(1, Math.ceil(all.length / state.pageSize));
    state.page = Math.min(Math.max(1, state.page), pages);
    const start = (state.page - 1) * state.pageSize;
    const visible = all.slice(start, start + state.pageSize);
    const maxCapacity = Math.max(1, ...(D.items || []).map((item) => item.capacity_gb || 0));
    $('#rows').innerHTML = visible.length
      ? visible.map((item) => rowHtml(item, maxCapacity)).join('')
      : '<tr><td colspan="10" class="empty">Sin resultados. Prueba con otro filtro o pulsa «Buscar de nuevo».</td></tr>';
    $('#pager').innerHTML = pagerHtml(all.length, state.page, state.pageSize, 'page');
    $('#foot').textContent = `${all.length} discos en pantalla. «Mejor» pondera €/TB (50%), valoración (25%), gama NAS (15%) y caché (10%).`;
    renderSortState();
  }

  function render() {
    renderStats();
    renderSources();
    renderHighlights();
    renderChips();
    fillFilters();
    renderRows();
  }

  // ── histórico ─────────────────────────────────────────────────────────
  function initHistoryFromBoot() {
    const boot = BOOTDATA || {};
    hstate.items = boot.items || [];
    hstate.total = boot.total || hstate.items.length;
    hstate.stats = boot.stats || {};
    hstate.notifications = boot.notifications || [];
    if (boot.favorites) FAV = new Set(boot.favorites);
    hstate.loaded = Boolean(boot.items);
  }

  function renderHistoryStats() {
    const stats = hstate.stats || {};
    $('#hstats').innerHTML = [
      ['Modelos seguidos', stats.total || 0],
      ['Favoritos', stats.favorites || 0],
      ['No disponibles', stats.missing || 0],
      ['Avisos sin leer', stats.notifications || 0],
    ].map(([label, value]) => `<div class="stat"><small>${label}</small><b>${value}</b></div>`).join('');
  }

  function notificationHtml() {
    const notices = (hstate.notifications || []).filter((notice) => !notice.dismissed_at);
    if (!notices.length) {
      $('#notice').hidden = true;
      $('#notice').innerHTML = '';
      return;
    }
    const lines = notices.slice(0, 4).map((notice) => `<div>${esc(notice.message)} <small>${fmtDate(notice.created_at)}</small> <button type="button" class="ghost" data-dismiss="${notice.id}">Descartar</button></div>`).join('');
    const extra = notices.length > 4 ? `<div>y ${notices.length - 4} avisos más…</div>` : '';
    $('#notice').hidden = false;
    $('#notice').innerHTML = `<div><b>Avisos del histórico</b>${lines}${extra}</div><div class="actions"><button type="button" data-goto-history>Ver histórico</button></div>`;
  }

  function statusHtml(item) {
    return item.available
      ? '<span class="status ok">Disponible</span>'
      : `<span class="status missing" title="Última vez visto: ${esc(fmtDate(item.last_seen))}">No visto desde ${esc(fmtDate(item.missing_since || item.last_seen))}</span>`;
  }

  function historyRowHtml(item) {
    const favorite = FAV.has(item.key) || Boolean(item.favorite);
    const detailOpen = hstate.expanded === item.key;
    const main = `<tr>
      <td class="favcol"><button type="button" class="fav" data-fav="${esc(item.key)}" aria-pressed="${favorite}" aria-label="${favorite ? 'Quitar de favoritos' : 'Añadir a favoritos'}">${favorite ? '★' : '☆'}</button></td>
      <td>${esc(item.brand)}</td>
      <td><span class="model" title="${esc(item.title)}">${esc(item.model)}</span></td>
      <td>${fmtCap(item.capacity_gb)}</td>
      <td class="num">${eur(item.last_price)}</td>
      <td class="num">${eur(item.best_price)}</td>
      <td>${fmtDate(item.last_seen)}</td>
      <td>${statusHtml(item)}</td>
      <td><button type="button" class="ghost" data-detail="${esc(item.key)}">${detailOpen ? 'Ocultar' : 'Ver'}</button></td>
    </tr>`;
    if (!detailOpen) return main;
    const detail = hstate.details[item.key];
    if (!detail) return main + `<tr class="detail-row"><td colspan="9" class="empty">Cargando detalle…</td></tr>`;
    const offers = (detail.offers || []).map((offer) =>
      `<li>${esc(offer.store)} · ${eur(offer.last_price)} · ${offer.available ? 'disponible' : 'no disponible'} · última vez ${fmtDate(offer.last_seen)}</li>`
    ).join('') || '<li>Sin ofertas registradas.</li>';
    const prices = (detail.price_history || []).slice(0, 20).map((price) =>
      `<li>${fmtDate(price.observed_at)} · ${esc(price.store)} · ${eur(price.price)}${price.available ? '' : ' · no disponible'}</li>`
    ).join('') || '<li>Sin cambios de precio registrados.</li>';
    return main + `<tr class="detail-row"><td colspan="9"><div class="detail-box">
      <div><h4>Ofertas por tienda</h4><ul>${offers}</ul></div>
      <div><h4>Evolución de precios</h4><ul>${prices}</ul></div>
    </div></td></tr>`;
  }

  function staticHistoryItems() {
    const query = (hstate.q || '').toLowerCase().trim();
    return (hstate.items || []).filter((item) => {
      if (hstate.favorites && !(FAV.has(item.key) || item.favorite)) return false;
      if (hstate.status === 'available' && !item.available) return false;
      if (hstate.status === 'missing' && item.available) return false;
      if (query && !`${item.brand} ${item.model} ${item.title}`.toLowerCase().includes(query)) return false;
      return true;
    });
  }

  function renderHistory() {
    renderHistoryStats();
    notificationHtml();
    let visible = hstate.items || [];
    let total = hstate.total || 0;
    if (!LIVE) {
      visible = staticHistoryItems();
      total = visible.length;
      const pages = Math.max(1, Math.ceil(total / hstate.pageSize));
      hstate.page = Math.min(Math.max(1, hstate.page), pages);
      const start = (hstate.page - 1) * hstate.pageSize;
      visible = visible.slice(start, start + hstate.pageSize);
    }
    $('#hrows').innerHTML = visible.length
      ? visible.map(historyRowHtml).join('')
      : '<tr><td colspan="9" class="empty">Todavía no hay histórico. Realiza una búsqueda o marca un favorito.</td></tr>';
    $('#hpager').innerHTML = pagerHtml(total, hstate.page, hstate.pageSize, 'hpage');
    $('#hfoot').textContent = `${total} modelos en el histórico. Se marca «no visto» tras dos búsquedas fiables sin encontrarlo.`;
    const badge = $('#histbadge');
    const unread = (hstate.stats && hstate.stats.notifications) || 0;
    badge.hidden = !unread;
    badge.textContent = unread;
  }

  async function loadHistory(reset) {
    if (!LIVE) {
      hstate.loaded = true;
      renderHistory();
      return;
    }
    if (reset) hstate.page = 1;
    const params = new URLSearchParams({
      limit: hstate.pageSize,
      offset: (hstate.page - 1) * hstate.pageSize,
      favorites: hstate.favorites ? '1' : '0',
      status: hstate.status,
      q: hstate.q,
      sort: hstate.sort,
      direction: hstate.dir,
    });
    try {
      const [data, stats, notices] = await Promise.all([
        fetch('/api/history?' + params.toString()).then((response) => response.json()),
        fetch('/api/stats').then((response) => response.json()),
        fetch('/api/notifications').then((response) => response.json()),
      ]);
      hstate.items = data.items || [];
      hstate.total = data.total || 0;
      hstate.stats = stats || {};
      hstate.notifications = notices.items || [];
      hstate.loaded = true;
      renderHistory();
    } catch (error) {
      toast('No se pudo cargar el histórico.');
    }
  }

  async function loadDetail(key) {
    if (hstate.expanded === key) {
      hstate.expanded = null;
      renderHistory();
      return;
    }
    hstate.expanded = key;
    renderHistory();
    if (!LIVE) {
      hstate.details[key] = hstate.details[key] || { offers: [], price_history: [] };
      renderHistory();
      return;
    }
    if (hstate.details[key]) return;
    try {
      const detail = await fetch('/api/history/' + encodeURIComponent(key)).then((response) => response.json());
      hstate.details[key] = detail;
    } catch (error) {
      hstate.details[key] = { offers: [], price_history: [] };
    }
    renderHistory();
  }

  // ── acciones ──────────────────────────────────────────────────────────
  let toastTimer;
  function toast(message) {
    const node = $('#toast');
    node.textContent = message;
    node.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { node.hidden = true; }, 3500);
  }

  async function toggleFavorite(key) {
    if (!LIVE) {
      toast('Los favoritos se editan en modo servidor (python nas_discos.py).');
      return;
    }
    const favorite = !FAV.has(key);
    try {
      const response = await fetch('/api/favorites', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, favorite }),
      });
      if (!response.ok) throw new Error('No guardado');
      if (favorite) FAV.add(key); else FAV.delete(key);
      toast(favorite ? 'Añadido a favoritos.' : 'Quitado de favoritos.');
      renderRows();
      if (hstate.loaded) loadHistory();
    } catch (error) {
      toast('No se pudo guardar el favorito.');
    }
  }

  async function dismissNotice(id) {
    hstate.notifications = hstate.notifications.filter((notice) => Number(notice.id) !== Number(id));
    hstate.stats.notifications = Math.max(0, (hstate.stats.notifications || 1) - 1);
    renderHistory();
    if (!LIVE) return;
    try {
      await fetch('/api/notifications/dismiss', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: Number(id) }),
      });
    } catch (error) {
      toast('No se pudo descartar el aviso en el servidor.');
    }
  }

  function showTab(tab) {
    state.tab = tab;
    const isSearch = tab === 'search';
    $('#view-search').hidden = !isSearch;
    $('#view-history').hidden = isSearch;
    $('#tab-search').setAttribute('aria-selected', String(isSearch));
    $('#tab-history').setAttribute('aria-selected', String(!isSearch));
    if (!isSearch && !hstate.loaded) loadHistory(true);
    if (!isSearch) renderHistory();
  }

  // ── búsqueda en vivo ──────────────────────────────────────────────────
  const btn = $('#re');
  function setBtn(text, disabled, percent) {
    btn.disabled = disabled;
    $('#relabel').textContent = text;
    $('#fill').style.width = (percent || 0) + '%';
  }

  let cooldownTimer;
  function cooldown(seconds) {
    clearInterval(cooldownTimer);
    if (seconds <= 0) {
      setBtn('Buscar de nuevo', false, 0);
      return;
    }
    cooldownTimer = setInterval(() => {
      seconds -= 1;
      if (seconds <= 0) {
        clearInterval(cooldownTimer);
        setBtn('Buscar de nuevo', false, 0);
      } else {
        setBtn(`Disponible en ${seconds} s`, true, 0);
      }
    }, 1000);
    setBtn(`Disponible en ${seconds} s`, true, 0);
  }

  async function fetchData() {
    const data = await fetch('/api/data').then((response) => response.json());
    D = data || EMPTY;
    FAV = new Set(D.favorites || []);
    render();
  }

  async function poll() {
    try {
      const status = await fetch('/api/status').then((response) => response.json());
      if (status.running) {
        setBtn(`Buscando… ${status.label || ''}`, true, Math.round((status.progress || 0) * 100));
        setTimeout(poll, 1000);
      } else {
        await fetchData();
        render();
        cooldown(status.cooldown || 0);
        $('#rehint').textContent = status.error ? 'Error: ' + status.error : (status.history_error || '');
        loadHistory(true);
      }
    } catch (error) {
      setBtn('Buscar de nuevo', false, 0);
      $('#rehint').textContent = 'No se pudo consultar el servidor.';
    }
  }

  async function boot() {
    if (!D || !D.items) {
      try { await fetchData(); } catch (error) { D = EMPTY; render(); }
    }
    initHistoryFromBoot();
    render();
    if (!LIVE) {
      setBtn('Búsqueda en vivo: ejecuta python nas_discos.py', true, 0);
      renderHistory();
      return;
    }
    try {
      const status = await fetch('/api/status').then((response) => response.json());
      if (status.running) poll();
      else if (!D.items || !D.items.length) poll();
      else cooldown(status.cooldown || 0);
      await loadHistory(false);
    } catch (error) {
      setBtn('Buscar de nuevo', false, 0);
    }
  }

  // ── eventos ───────────────────────────────────────────────────────────
  $('#chips').addEventListener('click', (event) => {
    const chip = event.target.closest('.chip');
    if (!chip) return;
    state.brand = chip.dataset.brand;
    state.page = 1;
    renderChips();
    renderRows();
  });

  $$('th[data-key] .sort').forEach((button) => {
    button.addEventListener('click', () => setSort(button.dataset.key));
  });

  ['#q', '#form', '#iface', '#nas', '#store', '#capmin', '#capmax'].forEach((selector) => {
    $(selector).addEventListener('input', () => { state.page = 1; renderRows(); });
    $(selector).addEventListener('change', () => { state.page = 1; renderRows(); });
  });
  $('#favonly').addEventListener('change', () => { state.page = 1; renderRows(); });
  $('#reset').addEventListener('click', () => {
    ['#q', '#form', '#iface', '#nas', '#store', '#capmin', '#capmax'].forEach((selector) => { $(selector).value = ''; });
    $('#favonly').checked = false;
    state.brand = '';
    state.page = 1;
    renderChips();
    renderRows();
  });

  $('#pager').addEventListener('click', (event) => {
    const button = event.target.closest('[data-page]');
    if (!button || button.disabled) return;
    state.page = Number(button.dataset.page);
    renderRows();
  });
  $('#pager').addEventListener('change', (event) => {
    if (event.target.matches('[data-pagesize]')) {
      state.pageSize = Number(event.target.value);
      state.page = 1;
      renderRows();
    }
  });

  $('#tab-search').addEventListener('click', () => showTab('search'));
  $('#tab-history').addEventListener('click', () => showTab('history'));

  $('#hq').addEventListener('input', () => { hstate.q = $('#hq').value; loadHistory(true); });
  $('#hstatus').addEventListener('change', () => { hstate.status = $('#hstatus').value; loadHistory(true); });
  $('#hfav').addEventListener('change', () => { hstate.favorites = $('#hfav').checked; loadHistory(true); });
  $('#hsort').addEventListener('change', () => {
    const [sort, direction] = $('#hsort').value.split(':');
    hstate.sort = sort;
    hstate.dir = direction;
    loadHistory(true);
  });
  $('#hpager').addEventListener('click', (event) => {
    const button = event.target.closest('[data-hpage]');
    if (!button || button.disabled) return;
    hstate.page = Number(button.dataset.hpage);
    loadHistory(false);
  });
  $('#hpager').addEventListener('change', (event) => {
    if (event.target.matches('[data-pagesize]')) {
      hstate.pageSize = Number(event.target.value);
      loadHistory(true);
    }
  });

  document.addEventListener('click', (event) => {
    const fav = event.target.closest('[data-fav]');
    if (fav) { toggleFavorite(fav.dataset.fav); return; }
    const detail = event.target.closest('[data-detail]');
    if (detail) { loadDetail(detail.dataset.detail); return; }
    const dismiss = event.target.closest('[data-dismiss]');
    if (dismiss) { dismissNotice(dismiss.dataset.dismiss); return; }
    if (event.target.closest('[data-goto-history]')) showTab('history');
  });

  btn.addEventListener('click', async () => {
    if (!LIVE) return;
    setBtn('Iniciando…', true, 2);
    try {
      const response = await fetch('/api/refresh', { method: 'POST' });
      if (response.status === 429) {
        const data = await response.json();
        cooldown(data.cooldown || 0);
        return;
      }
      poll();
    } catch (error) {
      setBtn('Buscar de nuevo', false, 0);
      $('#rehint').textContent = 'No se pudo iniciar la búsqueda.';
    }
  });

  boot();
})();
