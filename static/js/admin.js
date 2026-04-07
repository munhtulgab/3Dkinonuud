/**
 * ═══════════════════════════════════════════════════════════
 *  🎬 Movie Platform — Admin Panel JavaScript
 *  TMDB хайлт, кино нэмэх, удирдах
 * ═══════════════════════════════════════════════════════════
 */

// ─── Admin State ─────────────────────────────
const adminState = {
    movies: [],
    searchResults: [],
    selectedTMDB: null,
    searchTimeout: null,
};

// ═══════════════════════════════════════════════
//  TMDB ХАЙЛТ
// ═══════════════════════════════════════════════

function onTMDBSearch(e) {
    const q = e.target.value.trim();
    clearTimeout(adminState.searchTimeout);

    if (!q) {
        document.getElementById('tmdbResults').innerHTML = '';
        return;
    }

    // ID шууд оруулсан бол
    if (/^\d+$/.test(q)) {
        document.getElementById('tmdbResults').innerHTML = `
            <div class="tmdb-result" onclick="selectTMDBId(${q})">
                <div class="tmdb-result__info">
                    <h5>TMDB ID: ${q}</h5>
                    <span>ID-аар шууд нэмэх</span>
                </div>
            </div>
        `;
        return;
    }

    // Debounce хайлт
    adminState.searchTimeout = setTimeout(async () => {
        try {
            const data = await api(`/api/admin/tmdb/search?q=${encodeURIComponent(q)}`);
            renderTMDBResults(data.results || []);
        } catch (err) {
            showToast(err.message, 'error');
        }
    }, 500);
}

function renderTMDBResults(results) {
    const container = document.getElementById('tmdbResults');

    if (results.length === 0) {
        container.innerHTML = '<div style="padding:12px;color:var(--text-muted);font-size:13px;">Үр дүн олдсонгүй</div>';
        return;
    }

    container.innerHTML = results.map(r => `
        <div class="tmdb-result" onclick="selectTMDBId(${r.tmdb_id})">
            <img src="${r.poster_path || '/static/img/no-poster.svg'}" alt="${r.title}"
                 onerror="this.src='/static/img/no-poster.svg'">
            <div class="tmdb-result__info">
                <h5>${r.title}</h5>
                <span>ID: ${r.tmdb_id} • ${r.release_date ? r.release_date.substring(0,4) : ''} • ⭐ ${r.vote_average}</span>
            </div>
        </div>
    `).join('');
}

function selectTMDBId(id) {
    document.getElementById('tmdbIdInput').value = id;
    document.getElementById('tmdbResults').innerHTML = `
        <div style="padding:8px;color:var(--green);font-size:13px;">
            ✓ TMDB ID ${id} сонгогдлоо
        </div>
    `;
}

// ═══════════════════════════════════════════════
//  КИНО НЭМЭХ
// ═══════════════════════════════════════════════

async function handleAddMovie(e) {
    e.preventDefault();

    const tmdb_id = parseInt(document.getElementById('tmdbIdInput').value);
    const price = parseInt(document.getElementById('priceInput').value);
    const download_url = document.getElementById('downloadUrlInput').value.trim();

    if (!tmdb_id || isNaN(tmdb_id)) return showToast('TMDB ID оруулна уу', 'error');
    if (!price || isNaN(price)) return showToast('Үнэ оруулна уу', 'error');
    if (!download_url) return showToast('Татах линк оруулна уу', 'error');

    const btn = e.target.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Нэмж байна...';

    try {
        const data = await api('/api/admin/movies', {
            method: 'POST',
            body: JSON.stringify({ tmdb_id, price, download_url }),
        });

        showToast(data.message, 'success');

        // Форм цэвэрлэх
        document.getElementById('tmdbIdInput').value = '';
        document.getElementById('priceInput').value = '';
        document.getElementById('downloadUrlInput').value = '';
        document.getElementById('tmdbSearchInput').value = '';
        document.getElementById('tmdbResults').innerHTML = '';

        // Жагсаалт шинэчлэх
        loadAdminMovies();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '➕ Кино нэмэх';
    }
}

// ═══════════════════════════════════════════════
//  КИНО ЖАГСААЛТ (Админ)
// ═══════════════════════════════════════════════

async function loadAdminMovies() {
    const container = document.getElementById('adminMovieList');
    if (!container) return;

    try {
        const data = await api('/api/admin/movies');
        adminState.movies = data.movies;
        renderAdminMovies(container);
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><div class="empty-state__text">${err.message}</div></div>`;
    }
}

function renderAdminMovies(container) {
    if (adminState.movies.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state__icon">📭</div>
                <div class="empty-state__text">Кино нэмэгдээгүй байна</div>
            </div>
        `;
        return;
    }

    container.innerHTML = adminState.movies.map(m => `
        <div class="admin-movie-row">
            <img src="${m.poster_path || '/static/img/no-poster.svg'}" alt="${m.title}"
                 onerror="this.src='/static/img/no-poster.svg'">
            <div class="admin-movie-info">
                <h4>${m.title}</h4>
                <span>
                    ID: ${m.tmdb_id} • ₮${numberFormat(m.price)}
                    ${m.is_active ? '' : ' • <span style="color:var(--red)">Идэвхгүй</span>'}
                </span>
            </div>
            <button class="btn btn--danger btn--sm" onclick="deleteMovie(${m.tmdb_id})" title="Устгах">
                🗑
            </button>
        </div>
    `).join('');
}

async function deleteMovie(tmdb_id) {
    if (!confirm('Энэ киног устгах уу?')) return;

    try {
        await api(`/api/admin/movies/${tmdb_id}`, { method: 'DELETE' });
        showToast('Устгагдлаа', 'success');
        loadAdminMovies();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ═══════════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
    await checkAuth();
    if (!state.user || state.user.role !== 'admin') {
        window.location.href = '/';
        return;
    }
    loadAdminMovies();
});
