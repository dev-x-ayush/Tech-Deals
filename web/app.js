const $ = (selector) => document.querySelector(selector);
const dialog = $('#result-dialog');
const storeDomains = { amazon: ['amazon.in','amazon.com'], flipkart: ['flipkart.com'], blinkit: ['blinkit.com'], walmart: ['walmart.com'] };

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, (char) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[char]);
}
function safeResultUrl(raw) {
  try {
    const url = new URL(raw);
    if (!['https:', 'http:'].includes(url.protocol)) return '#';
    const host = url.hostname.toLowerCase();
    const allowed = Object.values(storeDomains).flat().some((domain) => host === domain || host.endsWith(`.${domain}`));
    return allowed ? url.href : '#';
  } catch { return '#'; }
}
function printable(value) { return typeof value === 'string' ? value : JSON.stringify(value, null, 2); }
function openDialog(title, value, label = 'TINYFISH RESULT', error = false) {
  $('#dialog-title').textContent = title;
  $('#dialog-label').textContent = label;
  $('#dialog-status').textContent = '';
  const content = $('#dialog-content');
  content.classList.toggle('error-box', error);
  content.textContent = printable(value);
  dialog.showModal();
}
async function api(path, payload = {}) {
  const response = await fetch(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  let data;
  try { data = await response.json(); } catch { data = { error: `The server returned HTTP ${response.status}.` }; }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}
function savedSearches() {
  try { const value = JSON.parse(localStorage.getItem('tech-deals-saved') || '[]'); return Array.isArray(value) ? value : []; }
  catch { return []; }
}
function saveSearch(query) {
  const items = [query, ...savedSearches().filter((item) => item.toLowerCase() !== query.toLowerCase())].slice(0, 8);
  try { localStorage.setItem('tech-deals-saved', JSON.stringify(items)); } catch { /* Browsing still works if storage is disabled. */ }
  renderSaved();
}
function renderSaved() {
  const list = savedSearches();
  $('#saved-list').innerHTML = list.length
    ? list.map((query) => `<button class="saved-chip" type="button" data-query="${escapeHtml(query)}">↻ ${escapeHtml(query)}</button>`).join('')
    : '<span class="muted">No saved searches yet.</span>';
  document.querySelectorAll('.saved-chip').forEach((button) => button.addEventListener('click', () => runSearch(button.dataset.query)));
}
function selectedStores() { return [...document.querySelectorAll('input[name="store"]:checked')].map((input) => input.value); }
function renderResults(data) {
  const target = $('#results');
  const entries = Array.isArray(data.results) ? data.results : [];
  const errors = Array.isArray(data.errors) ? data.errors : [];
  const errorLine = errors.length ? `<p class="error-box">Some store searches could not finish: ${errors.map((item) => `${escapeHtml(item.store)} (${escapeHtml(item.error)})`).join(' · ')}</p>` : '';
  $('#results-meta').textContent = `${entries.length} listings returned · ${data.stores_searched.map((name) => name[0].toUpperCase() + name.slice(1)).join(', ')} · Verify price on store`;
  if (!entries.length) {
    target.innerHTML = `<div class="results-empty">${errorLine || 'No listings came back. Try a shorter product name or another store.'}</div>`;
    return;
  }
  target.innerHTML = errorLine + entries.map((item) => {
    const title = escapeHtml(item.title || 'Product listing');
    const snippet = escapeHtml(item.snippet || 'Open the source page to check its price and availability.');
    const url = safeResultUrl(item.url || '');
    const site = escapeHtml(item.site_name || item.store || 'Store');
    return `<article class="result-card"><div class="result-site">${site} · SEARCH RESULT</div><h3>${title}</h3><p>${snippet}</p><a href="${escapeHtml(url)}" ${url === '#' ? '' : 'target="_blank" rel="noopener noreferrer"'}>Open store listing ↗</a><button class="check-offer" type="button" data-url="${escapeHtml(url)}" ${url === '#' ? 'disabled' : ''}>Check displayed offer with Agent</button></article>`;
  }).join('');
  document.querySelectorAll('.check-offer:not(:disabled)').forEach((button) => button.addEventListener('click', async () => {
    button.disabled = true; button.textContent = 'Checking offer…';
    try { openDialog('Displayed offer details', await api('/api/analyze', { url: button.dataset.url }), 'TINYFISH AGENT'); }
    catch (error) { openDialog('Could not inspect this offer', { error: error.message }, 'TINYFISH AGENT', true); }
    finally { button.disabled = false; button.textContent = 'Check displayed offer with Agent'; }
  }));
}
async function runSearch(query) {
  const stores = selectedStores();
  if (!stores.length) { openDialog('Choose a store', 'Select at least one retailer, then search again.', 'SEARCH'); return; }
  saveSearch(query);
  $('#results-section').classList.remove('hidden');
  $('#results-title').textContent = `Deals for “${query}”`;
  $('#results-meta').textContent = 'Searching selected stores…';
  $('#results').innerHTML = '<div class="results-empty">Searching live product listings…</div>';
  $('#results-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
  const button = $('#search-form button[type="submit"]');
  button.disabled = true; button.textContent = 'Searching…';
  try { renderResults(await api('/api/search', { query, stores, region: $('#region').value })); }
  catch (error) { $('#results-meta').textContent = ''; $('#results').innerHTML = `<div class="results-empty error-box">${escapeHtml(error.message)}</div>`; }
  finally { button.disabled = false; button.innerHTML = 'Find deals <span>→</span>'; }
}
$('#search-form').addEventListener('submit', (event) => { event.preventDefault(); runSearch($('#product-query').value.trim()); });
$('#research-results').addEventListener('click', () => {
  const query = $('#product-query').value.trim();
  if (query) runResearch(`Research current sales and credible deals for ${query}. Cite retailer and publisher sources. Distinguish listed prices from general sale information.`);
});
function bindForm(formId, action, payload, title, label) {
  $(formId).addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = event.currentTarget.querySelector('button[type="submit"]');
    const oldText = button.textContent; button.disabled = true; button.textContent = 'Working…';
    try { openDialog(title, await api(action, payload()), label); }
    catch (error) { openDialog(`${title} failed`, { error: error.message }, label, true); }
    finally { button.disabled = false; button.textContent = oldText; }
  });
}
bindForm('#fetch-form', '/api/fetch', () => ({ url: $('#fetch-url').value.trim() }), 'Product page content', 'TINYFISH FETCH');
bindForm('#agent-form', '/api/analyze', () => ({ url: $('#agent-url').value.trim() }), 'Displayed offer details', 'TINYFISH AGENT');
bindForm('#monitor-form', '/api/monitor', () => ({ url: $('#monitor-url').value.trim(), schedule: $('#monitor-frequency').value }), 'Price monitor created', 'TINYFISH MONITOR');
bindForm('#browser-form', '/api/browser', () => ({ url: $('#browser-url').value.trim() }), 'Browser session created', 'TINYFISH BROWSER');
async function runResearch(query) {
  try { openDialog('Researching the deal landscape', await api('/api/research', { query }), 'TINYFISH RESEARCH'); }
  catch (error) { openDialog('Research could not finish', { error: error.message }, 'TINYFISH RESEARCH', true); }
}
$('#research-form').addEventListener('submit', (event) => { event.preventDefault(); runResearch($('#research-query').value.trim()); });
$('#dialog-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
renderSaved();
fetch('/api/health').then((response) => response.json()).then((health) => {
  const status = $('#connection-status');
  status.parentElement.classList.add(health.tinyfish_configured ? 'ready' : 'missing');
  status.textContent = health.tinyfish_configured ? 'TinyFish connected' : 'API key needed';
}).catch(() => { $('#connection-status').textContent = 'Server unavailable'; });
