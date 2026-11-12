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
  const HFILTERS_KEY = 'disksearch-hfilters';
  const hstate = {
    q: '', status: '', favorites: false, sort: 'last_seen', dir: 'desc',
    page: 1, pageSize: 25, total: 0, items: [], stats: {}, notifications: [],
    expanded: null, details: {}, loaded: false,
    series: [], compare: [], compareOn: false, detailView: 'table', barMode: 'day',
    from: '', to: '', pmin: '', pmax: '', form: '', change: false, stores: [],
  };

  // ── filtros del histórico persistentes ────────────────────────────────
  function saveHFilters() {
    try {
      localStorage.setItem(HFILTERS_KEY, JSON.stringify({
        q: hstate.q, status: hstate.status, favorites: hstate.favorites,
        from: hstate.from, to: hstate.to, pmin: hstate.pmin, pmax: hstate.pmax,
        form: hstate.form, change: hstate.change, stores: hstate.stores,
      }));
    } catch (error) { /* sin localStorage: no pasa nada */ }
  }

  function loadHFilters() {
    try {
      const saved = JSON.parse(localStorage.getItem(HFILTERS_KEY) || '{}');
      Object.assign(hstate, {
        q: saved.q || '', status: saved.status || '', favorites: Boolean(saved.favorites),
        from: saved.from || '', to: saved.to || '', pmin: saved.pmin || '', pmax: saved.pmax || '',
        form: saved.form || '', change: Boolean(saved.change), stores: saved.stores || [],
      });
    } catch (error) { /* datos corruptos: filtros por defecto */ }
    $('#hq').value = hstate.q;
    $('#hstatus').value = hstate.status;
    $('#hfav').checked = hstate.favorites;
    $('#hfrom').value = hstate.from;
    $('#hto').value = hstate.to;
    $('#hpmin').value = hstate.pmin;
    $('#hpmax').value = hstate.pmax;
    $('#hform').value = hstate.form;
    $('#hchange').checked = hstate.change;
  }

  // ── tema (claro/oscuro/sistema) ───────────────────────────────────────
  const THEME_KEY = 'disksearch-theme';
  const media = window.matchMedia('(prefers-color-scheme: dark)');

  function applyTheme() {
    const saved = localStorage.getItem(THEME_KEY) || 'system';
    const theme = saved === 'system' ? (media.matches ? 'dark' : 'light') : saved;
    document.documentElement.dataset.theme = theme;
    $$('[data-theme-opt]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.themeOpt === saved));
    });
  }

  function initTheme() {
    applyTheme();
    $$('[data-theme-opt]').forEach((button) => {
      button.addEventListener('click', () => {
        localStorage.setItem(THEME_KEY, button.dataset.themeOpt);
        applyTheme();
      });
    });
    media.addEventListener('change', () => {
      if ((localStorage.getItem(THEME_KEY) || 'system') === 'system') applyTheme();
    });
  }

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
    hstate.series = boot.series || [];
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
    const url = item.last_url || item.url || '';
    const main = `<tr>
      <td class="favcol"><button type="button" class="fav" data-fav="${esc(item.key)}" aria-pressed="${favorite}" aria-label="${favorite ? 'Quitar de favoritos' : 'Añadir a favoritos'}">${favorite ? '★' : '☆'}</button></td>
      <td>${esc(item.brand)}</td>
      <td><span class="model" title="${esc(item.title)}">${esc(item.model)}</span></td>
      <td>${fmtCap(item.capacity_gb)}</td>
      <td class="num">${eur(item.last_price)}</td>
      <td class="num">${eur(item.best_price)}</td>
      <td>${fmtDate(item.last_seen)}</td>
      <td>${statusHtml(item)}</td>
      <td>${url ? `<a href="${esc(url)}" target="_blank" rel="noopener">Abrir</a>` : '—'}</td>
      <td><button type="button" class="ghost" data-detail="${esc(item.key)}">${detailOpen ? 'Ocultar' : 'Ver'}</button></td>
    </tr>`;
    if (!detailOpen) return main;
    return main + `<tr class="detail-row"><td colspan="10">
      <div class="chips" role="group" aria-label="Vista del histórico del producto">
        <button type="button" class="chip" data-dview="table" aria-pressed="${hstate.detailView === 'table'}">Tabla</button>
        <button type="button" class="chip" data-dview="line" aria-pressed="${hstate.detailView === 'line'}">Líneas</button>
        <button type="button" class="chip" data-dview="bars" aria-pressed="${hstate.detailView === 'bars'}">Barras</button>
      </div>
      <div class="detail-panel" id="dpanel"></div>
    </td></tr>`;
  }

  function staticHistoryItems() {
    const query = (hstate.q || '').toLowerCase().trim();
    const stores = new Set(hstate.stores);
    const pmin = parseFloat(hstate.pmin);
    const pmax = parseFloat(hstate.pmax);
    return (hstate.items || []).filter((item) => {
      if (hstate.favorites && !(FAV.has(item.key) || item.favorite)) return false;
      if (hstate.status === 'available' && !item.available) return false;
      if (hstate.status === 'missing' && item.available) return false;
      if (hstate.form && item.form_factor !== hstate.form) return false;
      if (hstate.change && item.last_price === item.best_price) return false;
      if (stores.size && !stores.has(item.last_store || item.store)) return false;
      const price = item.last_price ?? item.price;
      if (!Number.isNaN(pmin) && hstate.pmin !== '' && (price == null || price < pmin)) return false;
      if (!Number.isNaN(pmax) && hstate.pmax !== '' && (price == null || price > pmax)) return false;
      if (hstate.from && item.last_seen && String(item.last_seen).slice(0, 10) < hstate.from) return false;
      if (hstate.to && item.last_seen && String(item.last_seen).slice(0, 10) > hstate.to) return false;
      if (query && !`${item.brand} ${item.model} ${item.title}`.toLowerCase().includes(query)) return false;
      return true;
    });
  }

  // ── detalle del producto: histórico por producto ─────────────────────
  function serieFor(key) {
    return (hstate.series || []).find((serie) => serie.key === key) || null;
  }

  function recordsOf(serie) {
    if (serie.records && serie.records.length) return serie.records;
    return (serie.points || []).map((p) => ({ day: p.day, store: '', price: p.price }));
  }

  function productStats(serie) {
    const records = recordsOf(serie);
    if (!records.length) return null;
    const days = [...new Set(records.map((r) => r.day))].sort();
    const byDay = days.map((day) => {
      const prices = records.filter((r) => r.day === day).map((r) => r.price);
      return { day, price: Math.min(...prices) };
    });
    const max = byDay.reduce((a, b) => (b.price > a.price ? b : a));
    const min = byDay.reduce((a, b) => (b.price < a.price ? b : a));
    const avg = byDay.reduce((sum, d) => sum + d.price, 0) / byDay.length;
    const current = byDay[byDay.length - 1];
    const prev = byDay.length > 1 ? byDay[byDay.length - 2] : null;
    const pct = (from) => (from && from.price)
      ? ((current.price - from.price) / from.price) * 100 : null;
    return {
      max, min, avg, current, prev,
      vsPrev: prev ? pct(prev) : null,
      vsMin: pct(min),
      vsMax: pct(max),
    };
  }

  function palette(index) {
    return `hsl(${(index * 67 + 210) % 360} 70% 45%)`;
  }

  function labelOf(serie) {
    return `${serie.brand} ${serie.model} · ${fmtCap(serie.capacity_gb)}`.trim();
  }

  function compareSeries(mainKey) {
    const keys = [mainKey, ...hstate.compare.filter((k) => k !== mainKey)];
    return keys.map(serieFor).filter(Boolean);
  }

  function compareHtml(main) {
    const candidates = (hstate.series || [])
      .filter((s) => s.key !== main.key)
      .sort((a, b) => {
        const ca = a.capacity_gb === main.capacity_gb ? 0 : 1;
        const cb = b.capacity_gb === main.capacity_gb ? 0 : 1;
        if (ca !== cb) return ca - cb;
        return (a.last_price || 0) - (b.last_price || 0);
      })
      .slice(0, 50);
    const options = candidates.map((s) =>
      `<option value="${esc(s.key)}">${esc(labelOf(s))} — ${eur(s.last_price)}</option>`).join('');
    const chips = hstate.compare.filter((k) => k !== main.key).map((key) => {
      const s = serieFor(key);
      return s
        ? `<button type="button" class="chip" data-compare-remove="${esc(key)}" aria-pressed="true" title="Quitar de la comparativa">${esc(s.model || key)} ✕</button>`
        : '';
    }).join('');
    return `
      <label class="check compare-check"><input type="checkbox" data-compare-check ${hstate.compareOn ? 'checked' : ''}> Comparar con otro producto</label>
      ${hstate.compareOn ? `
      <div class="compare-row">
        <label for="dcompare">Comparar con:</label>
        <select id="dcompare" data-compare-add><option value="">Elige un producto…</option>${options}</select>
        ${chips ? `<div class="chips">${chips}</div>` : ''}
      </div>` : ''}`;
  }

  function pctText(value) {
    if (value == null) return '—';
    return `${value > 0 ? '+' : ''}${value.toLocaleString('es-ES', { maximumFractionDigits: 1 })}%`;
  }

  function detailColumnHtml(serie, title) {
    const st = productStats(serie);
    if (!st) return `<div class="detail-col"><h4>${title}</h4><p class="foot">Sin precios registrados todavía.</p></div>`;
    const card = (label, value, date) =>
      `<div class="pstat"><small>${label}</small><b>${eur(value)}</b><span>${date}</span></div>`;
    return `
      <div class="detail-col">
        <h4>${title}</h4>
        <div class="pstats">
          ${card('Precio más alto', st.max.price, fmtDate(st.max.day))}
          ${card('Precio medio', st.avg, `entre ${fmtDate(st.min.day)} y ${fmtDate(st.current.day)}`)}
          ${card('Precio más bajo', st.min.price, fmtDate(st.min.day))}
          ${card('Precio actual', st.current.price, fmtDate(st.current.day))}
        </div>
        <div class="pvars"><h5>Variación de precio</h5><ul>
          <li>Última búsqueda (${fmtDate(st.current.day)}) vs. anterior (${fmtDate(st.prev ? st.prev.day : '')}): <b>${pctText(st.vsPrev)}</b></li>
          <li>Actual vs. mínimo (${fmtDate(st.min.day)}): <b>${pctText(st.vsMin)}</b></li>
          <li>Actual vs. máximo (${fmtDate(st.max.day)}): <b>${pctText(st.vsMax)}</b></li>
        </ul></div>
      </div>`;
  }

  function detailTableHtml(main) {
    const others = compareSeries(main.key).filter((s) => s.key !== main.key);
    const columns = [detailColumnHtml(main, `${esc(labelOf(main))} · seleccionado`)]
      .concat(others.map((s) => detailColumnHtml(s, `${esc(labelOf(s))} · comparado`)));
    const offersOf = (serie) => {
      const detail = hstate.details[serie.key];
      const list = detail && detail.offers && detail.offers.length
        ? detail.offers.map((offer) =>
            `<li>${esc(offer.store)} · <b>${eur(offer.last_price)}</b> · ${offer.available ? 'disponible' : 'no disponible'}${offer.url ? ` · <a href="${esc(offer.url)}" target="_blank" rel="noopener">abrir</a>` : ''}</li>`).join('')
        : Object.entries(serie.stores || {}).sort((a, b) => a[1].price - b[1].price)
          .map(([store, info]) =>
            `<li>${esc(store)} · <b>${eur(info.price)}</b> · ${fmtDate(info.date)}</li>`).join('');
      return `<div class="detail-col"><h4>Ofertas por tienda</h4><ul>${list || '<li>Sin ofertas registradas.</li>'}</ul></div>`;
    };
    return `<div class="detail-cols">${columns.join('')}</div>
      <div class="detail-cols">${compareSeries(main.key).map(offersOf).join('')}</div>`;
  }

  function chartSvg(seriesList, kind) {
    const recordsList = seriesList.map((serie) => ({ serie, records: recordsOf(serie) }));
    const days = [...new Set(recordsList.flatMap((s) => s.records.map((r) => r.day)))]
      .filter((day) => (!hstate.from || day >= hstate.from) && (!hstate.to || day <= hstate.to)).sort();
    if (!days.length) return '<p class="empty">Sin datos en el rango de fechas seleccionado.</p>';
    const w = 900, h = 320, padL = 60, padR = 16, padT = 16, padB = 40;
    const x = (day) => padL + (days.indexOf(day) / Math.max(1, days.length - 1)) * (w - padL - padR);
    const prices = recordsList.flatMap((s) =>
      s.records.filter((r) => days.includes(r.day)).map((r) => r.price));
    const yMax = Math.max(...prices, 1) * 1.05;
    const yMin = Math.min(...prices, yMax) * 0.95;
    const y = (price) => padT + (1 - (price - yMin) / Math.max(yMax - yMin, 0.01)) * (h - padT - padB);
    const parts = [];
    for (let i = 0; i <= 3; i += 1) {
      const value = yMin + ((yMax - yMin) * i) / 3;
      const yy = y(value);
      parts.push(`<line x1="${padL}" y1="${yy}" x2="${w - padR}" y2="${yy}" stroke="var(--line)"/>`);
      parts.push(`<text x="${padL - 6}" y="${yy + 4}" fill="var(--mute)" font-size="11" text-anchor="end">${Math.round(value)}€</text>`);
    }
    days.forEach((day, i) => {
      if (days.length <= 8 || i % Math.ceil(days.length / 8) === 0) {
        parts.push(`<text x="${x(day)}" y="${h - 10}" fill="var(--mute)" font-size="11" text-anchor="middle">${esc(day.slice(5))}</text>`);
      }
    });
    if (kind === 'line') {
      recordsList.forEach(({ serie, records }, index) => {
        const color = palette(index);
        const visible = records.filter((r) => days.includes(r.day));
        const byDay = new Map();
        visible.forEach((r) => byDay.set(r.day, Math.min(byDay.get(r.day) ?? Infinity, r.price)));
        const pts = days.filter((d) => byDay.has(d)).map((d) => `${x(d)},${y(byDay.get(d))}`);
        parts.push(`<polyline points="${pts.join(' ')}" fill="none" stroke="${color}" stroke-width="2"/>`);
        visible.forEach((r) => {
          parts.push(`<circle cx="${x(r.day)}" cy="${y(r.price)}" r="3.5" fill="${color}"><title>${esc(labelOf(serie))} · ${esc(r.day)} · ${esc(r.store || '—')} · ${eur(r.price)}</title></circle>`);
        });
      });
    } else {
      const slot = (w - padL - padR) / days.length;
      const barW = Math.max(2, (slot * 0.8) / recordsList.length);
      recordsList.forEach(({ serie, records }, index) => {
        const color = palette(index);
        records.filter((r) => days.includes(r.day)).forEach((r) => {
          const bx = x(r.day) - (slot * 0.4) + index * barW;
          parts.push(`<rect x="${bx}" y="${y(r.price)}" width="${barW}" height="${h - padB - y(r.price)}" fill="${color}"><title>${esc(labelOf(serie))} · ${esc(r.day)} · ${esc(r.store || '—')} · ${eur(r.price)}</title></rect>`);
        });
      });
    }
    return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Evolución de precios" style="width:100%;height:auto">${parts.join('')}</svg>`;
  }

  function barsStoreHtml(seriesList) {
    return seriesList.map((serie) => {
      const stores = Object.entries(serie.stores || {}).sort((a, b) => a[1].price - b[1].price);
      const max = Math.max(1, ...stores.map(([, info]) => info.price));
      const rows = stores.length
        ? stores.map(([store, info]) => {
            const width = Math.max(4, (info.price / max) * 100);
            const best = info.price === stores[0][1].price;
            return `<div class="bar-row"><span title="${esc(store)}">${esc(store)}</span><span class="bar"><u style="width:${width}%"></u></span><span class="num"><b>${eur(info.price)}</b>${best ? ' · mejor' : ''}</span></div>`;
          }).join('')
        : '<p class="foot">Sin ofertas disponibles registradas.</p>';
      return `<div class="bar-set"><h4>${esc(labelOf(serie))} · último precio por tienda</h4>${rows}</div>`;
    }).join('');
  }

  function barsProductHtml(seriesList) {
    const entries = seriesList.map((serie) => {
      const st = productStats(serie);
      return { serie, price: serie.last_price ?? (st ? st.current.price : null) };
    }).filter((entry) => entry.price != null).sort((a, b) => a.price - b.price);
    if (!entries.length) return '<p class="empty">Sin precios actuales para comparar.</p>';
    const max = Math.max(...entries.map((entry) => entry.price));
    return `<div class="bar-set"><h4>Precio actual por producto</h4>${entries.map(({ serie, price }, i) =>
      `<div class="bar-row"><span title="${esc(labelOf(serie))}">${esc(serie.model || serie.key)}</span><span class="bar"><u style="width:${Math.max(4, (price / max) * 100)}%"></u></span><span class="num"><b>${eur(price)}</b>${i === 0 ? ' · mejor' : ''}</span></div>`).join('')}</div>`;
  }

  function renderDetailPanel() {
    const panel = $('#dpanel');
    if (!panel || !hstate.expanded) return;
    const main = serieFor(hstate.expanded);
    if (!main) {
      panel.innerHTML = '<p class="empty">Sin datos registrados para este producto todavía.</p>';
      return;
    }
    const seriesList = compareSeries(hstate.expanded);
    const head = compareHtml(main);
    if (hstate.detailView === 'table') {
      panel.innerHTML = head + detailTableHtml(main);
    } else if (hstate.detailView === 'line') {
      panel.innerHTML = head + `<div class="chart-wrap">${chartSvg(seriesList, 'line')}</div>`;
    } else {
      const modes = [['day', 'Evolución por día'], ['store', 'Por tienda'], ['product', 'Por producto']];
      const modeChips = `<div class="chips sm">${modes.map(([value, label]) =>
        `<button type="button" class="chip" data-barmode="${value}" aria-pressed="${hstate.barMode === value}">${label}</button>`).join('')}</div>`;
      const body = hstate.barMode === 'store' ? barsStoreHtml(seriesList)
        : hstate.barMode === 'product' ? barsProductHtml(seriesList)
        : `<div class="chart-wrap">${chartSvg(seriesList, 'bars')}</div>`;
      panel.innerHTML = head + modeChips + body;
    }
  }

  function renderHistoryView() {
    renderHistoryTable();
  }

  function fillHistoryFilters() {
    setOptions('#hform', [...new Set([
      ...(hstate.items || []).map((item) => item.form_factor),
      ...(hstate.series || []).map((serie) => serie.form_factor),
    ].filter(Boolean))].sort());
    const stores = [...new Set([
      ...(hstate.series || []).flatMap((serie) => Object.keys(serie.stores || {})),
    ])].sort((a, b) => a.localeCompare(b, 'es'));
    $('#hchips').innerHTML = stores.map((store) =>
      `<button type="button" class="chip" data-hstore="${esc(store)}" aria-pressed="${hstate.stores.includes(store)}">${esc(store)}</button>`
    ).join('');
  }

  function renderHistoryTable() {
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
    // el desplegable solo vive mientras su producto esté en el listado visible
    if (hstate.expanded && !visible.some((item) => item.key === hstate.expanded)) {
      hstate.expanded = null;
    }
    $('#hrows').innerHTML = visible.length
      ? visible.map(historyRowHtml).join('')
      : '<tr><td colspan="10" class="empty">Todavía no hay histórico. Realiza una búsqueda o marca un favorito.</td></tr>';
    $('#hpager').innerHTML = pagerHtml(total, hstate.page, hstate.pageSize, 'hpage');
    $('#hfoot').textContent = `${total} modelos en el histórico. Se marca «no visto» tras dos búsquedas fiables sin encontrarlo.`;
    renderDetailPanel();
  }

  function renderHistory() {
    renderHistoryStats();
    notificationHtml();
    fillHistoryFilters();
    renderHistoryView();
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
      const [data, stats, notices, series] = await Promise.all([
        fetch('/api/history?' + params.toString()).then((response) => response.json()),
        fetch('/api/stats').then((response) => response.json()),
        fetch('/api/notifications').then((response) => response.json()),
        hstate.series.length
          ? Promise.resolve({ series: hstate.series })
          : fetch('/api/series').then((response) => response.json()),
      ]);
      hstate.items = data.items || [];
      hstate.total = data.total || 0;
      hstate.stats = stats || {};
      hstate.notifications = notices.items || [];
      if (series && series.series) hstate.series = series.series;
      hstate.loaded = true;
      renderHistory();
    } catch (error) {
      toast('No se pudo cargar el histórico.');
    }
  }

  function loadDetail(key) {
    if (hstate.expanded === key) {
      hstate.expanded = null;
      renderHistory();
      return;
    }
    hstate.expanded = key;
    hstate.detailView = 'table';
    renderHistory();
    if (!LIVE || hstate.details[key]) return;
    fetch('/api/history/' + encodeURIComponent(key))
      .then((response) => response.json())
      .then((detail) => {
        hstate.details[key] = detail;
        if (hstate.expanded === key) renderHistory();
      })
      .catch(() => {
        hstate.details[key] = { offers: [] };
      });
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
    initTheme();
    if (!D || !D.items) {
      try { await fetchData(); } catch (error) { D = EMPTY; render(); }
    }
    initHistoryFromBoot();
    loadHFilters();
    updateHApplyLabel();
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

  // ── filtros del histórico: se aplican solo al pulsar «Aplicar filtros» ─
  function applyHFilters() {
    hstate.q = $('#hq').value;
    hstate.status = $('#hstatus').value;
    hstate.favorites = $('#hfav').checked;
    hstate.from = $('#hfrom').value; hstate.to = $('#hto').value;
    hstate.pmin = $('#hpmin').value; hstate.pmax = $('#hpmax').value;
    hstate.form = $('#hform').value;
    hstate.change = $('#hchange').checked;
    hstate.expanded = null;
    saveHFilters();
    updateHApplyLabel();
    if (!LIVE) renderHistory(); else loadHistory(true);
  }

  function updateHApplyLabel() {
    const n = [
      hstate.q, hstate.from, hstate.to, hstate.pmin, hstate.pmax, hstate.form,
      hstate.status, hstate.change ? 'x' : '', hstate.favorites ? 'x' : '',
      ...hstate.stores,
    ].filter(Boolean).length;
    $('#happly').textContent = n ? `Aplicar filtros (${n})` : 'Aplicar filtros';
  }

  $('#happly').addEventListener('click', applyHFilters);
  $('#hq').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') applyHFilters();
  });
  $('#hreset').addEventListener('click', () => {
    ['#hq', '#hfrom', '#hto', '#hpmin', '#hpmax', '#hform'].forEach((selector) => { $(selector).value = ''; });
    $('#hstatus').value = '';
    $('#hchange').checked = false;
    $('#hfav').checked = false;
    Object.assign(hstate, { q: '', from: '', to: '', pmin: '', pmax: '', form: '', change: false, favorites: false, status: '', stores: [] });
    hstate.expanded = null;
    saveHFilters();
    updateHApplyLabel();
    if (!LIVE) renderHistory(); else loadHistory(true);
  });
  $('#hchips').addEventListener('click', (event) => {
    const chip = event.target.closest('[data-hstore]');
    if (!chip) return;
    const store = chip.dataset.hstore;
    hstate.stores = hstate.stores.includes(store)
      ? hstate.stores.filter((value) => value !== store)
      : [...hstate.stores, store];
    chip.setAttribute('aria-pressed', String(hstate.stores.includes(store)));
    saveHFilters();
    updateHApplyLabel();
    if (!LIVE) renderHistory(); else loadHistory(true);
  });
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

  // ── vistas y comparativa dentro del desplegable del producto ──────────
  $('#hrows').addEventListener('click', (event) => {
    const check = event.target.closest('[data-compare-check]');
    if (check) {
      hstate.compareOn = check.checked;
      if (!check.checked) hstate.compare = [];
      renderHistory();
      return;
    }
    const dview = event.target.closest('[data-dview]');
    if (dview) {
      hstate.detailView = dview.dataset.dview;
      renderHistory();
      return;
    }
    const barmode = event.target.closest('[data-barmode]');
    if (barmode) {
      hstate.barMode = barmode.dataset.barmode;
      renderHistory();
      return;
    }
    const remove = event.target.closest('[data-compare-remove]');
    if (remove) {
      hstate.compare = hstate.compare.filter((key) => key !== remove.dataset.compareRemove);
      renderHistory();
    }
  });

  $('#hrows').addEventListener('change', (event) => {
    const add = event.target.closest('[data-compare-add]');
    if (!add || !add.value || hstate.compare.includes(add.value)) return;
    if (hstate.compare.length >= 4) {
      toast('Máximo 4 productos en la comparativa.');
      add.value = '';
      return;
    }
    hstate.compare = [...hstate.compare, add.value];
    add.value = '';
    renderHistory();
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
