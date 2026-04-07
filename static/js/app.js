/**
 * ═══════════════════════════════════════════════════════════
 *  🎬 Movie Platform — Client-Side JavaScript
 *  Нэвтрэх, Киноны жагсаалт, QPay төлбөр, Polling
 * ═══════════════════════════════════════════════════════════
 */

// ─── Төлөв (State) ──────────────────────────
const state = {
    user: null,           // Одоогийн хэрэглэгч
    movies: [],           // Киноны жагсаалт
    pollingTimer: null,   // Төлбөр шалгах interval
    pollingCount: 0,      // Polling тоолуур
    MAX_POLL: 120,        // Хамгийн ихдээ 120 удаа (10 минут)
};

// ─── API Helper ──────────────────────────────
async function api(url, options = {}) {
    try {
        const res = await fetch(url, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || data.message || `Алдаа: ${res.status}`);
        }
        return data;
    } catch (err) {
        if (err instanceof TypeError && err.message.includes('fetch')) {
            throw new Error('Сервертэй холбогдож чадсангүй');
        }
        throw err;
    }
}

// ═══════════════════════════════════════════════
//  TOAST МЭДЭГДЭЛ
// ═══════════════════════════════════════════════

function showToast(message, type = 'info') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = '0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ═══════════════════════════════════════════════
//  MODAL УДИРДЛАГА
// ═══════════════════════════════════════════════

function openModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('active');
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
    // Polling зогсоох
    if (state.pollingTimer) {
        clearInterval(state.pollingTimer);
        state.pollingTimer = null;
    }
}

// Backdrop дээр дарахад хаах
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-backdrop')) {
        e.target.classList.remove('active');
        if (state.pollingTimer) {
            clearInterval(state.pollingTimer);
            state.pollingTimer = null;
        }
    }
});

// ═══════════════════════════════════════════════
//  AUTH (Нэвтрэх / Бүртгүүлэх)
// ═══════════════════════════════════════════════

async function checkAuth() {
    try {
        const data = await api('/api/auth/me');
        if (data.logged_in) {
            state.user = data.user;
            updateNavUI();
            return true;
        }
    } catch (e) { /* silent */ }
    state.user = null;
    updateNavUI();
    return false;
}

function updateNavUI() {
    const actions = document.getElementById('navActions');
    if (!actions) return;

    if (state.user) {
        let adminBtn = '';
        if (state.user.role === 'admin') {
            adminBtn = `<a href="/admin" class="btn btn--outline btn--sm">⚙️ Админ</a>`;
        }
        actions.innerHTML = `
            ${adminBtn}
            <span class="nav__user">👤 ${state.user.username}</span>
            <button class="btn btn--ghost btn--sm" onclick="logout()">Гарах</button>
        `;
    } else {
        actions.innerHTML = `
            <button class="btn btn--gold btn--sm" onclick="openModal('authModal')">Нэвтрэх</button>
        `;
    }
}

function switchAuthTab(tab) {
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.auth-tab[data-tab="${tab}"]`).classList.add('active');

    document.getElementById('loginForm').style.display = tab === 'login' ? 'flex' : 'none';
    document.getElementById('registerForm').style.display = tab === 'register' ? 'flex' : 'none';
}

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;

    if (!username || !password) return showToast('Мэдээлэл бүрэн оруулна уу', 'error');

    try {
        const data = await api('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        });
        state.user = data.user;
        closeModal('authModal');
        updateNavUI();
        loadMovies();
        showToast('Амжилттай нэвтэрлээ!', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const username = document.getElementById('regUsername').value.trim();
    const email = document.getElementById('regEmail').value.trim();
    const password = document.getElementById('regPassword').value;

    if (!username || !email || !password) return showToast('Бүх талбарыг бөглөнө үү', 'error');

    try {
        await api('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({ username, email, password }),
        });
        showToast('Амжилттай бүртгэгдлээ! Нэвтэрнэ үү.', 'success');
        switchAuthTab('login');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function logout() {
    try {
        await api('/api/auth/logout', { method: 'POST' });
    } catch (e) { /* silent */ }
    state.user = null;
    updateNavUI();
    loadMovies();
    showToast('Гарлаа', 'info');
}

// ═══════════════════════════════════════════════
//  КИНОНЫ ЖАГСААЛТ
// ═══════════════════════════════════════════════

async function loadMovies() {
    const grid = document.getElementById('movieGrid');
    if (!grid) return;

    grid.innerHTML = `
        <div class="loading-screen" style="grid-column: 1/-1;">
            <div class="spinner-lg"></div>
            <span>Ачаалж байна...</span>
        </div>
    `;

    try {
        const data = await api('/api/movies');
        state.movies = data.movies;
        renderMovies(grid);
    } catch (err) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1/-1;">
                <div class="empty-state__icon">⚠️</div>
                <div class="empty-state__text">${err.message}</div>
            </div>
        `;
    }
}

function renderMovies(grid) {
    if (state.movies.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1/-1;">
                <div class="empty-state__icon">🎬</div>
                <div class="empty-state__text">Одоогоор кино нэмэгдээгүй байна</div>
            </div>
        `;
        return;
    }

    grid.innerHTML = state.movies.map(m => `
        <div class="movie-card" onclick="showMovieDetail(${m.tmdb_id})">
            ${m.is_purchased ? '<div class="movie-card__badge">✓ Авсан</div>' : ''}
            <div class="movie-card__rating">⭐ ${m.vote_average}</div>
            <img class="movie-card__poster"
                 src="${m.poster_path || '/static/img/no-poster.svg'}"
                 alt="${m.title}"
                 loading="lazy"
                 onerror="this.src='/static/img/no-poster.svg'">
            <div class="movie-card__overlay">
                <div class="movie-card__title">${m.title}</div>
                <div class="movie-card__meta">
                    ${m.release_date ? m.release_date.substring(0, 4) : ''} 
                    ${m.runtime ? `• ${m.runtime} мин` : ''}
                </div>
                <div class="movie-card__price">
                    ${m.is_purchased ? '✓ Худалдаж авсан' : `₮${numberFormat(m.price)}`}
                </div>
            </div>
        </div>
    `).join('');
}

function numberFormat(n) {
    return new Intl.NumberFormat('mn-MN').format(n);
}

// ═══════════════════════════════════════════════
//  КИНОНЫ ДЭЛГЭРЭНГҮЙ MODAL
// ═══════════════════════════════════════════════

async function showMovieDetail(tmdb_id) {
    const body = document.getElementById('detailBody');
    if (!body) return;

    body.innerHTML = `
        <div class="loading-screen">
            <div class="spinner-lg"></div>
        </div>
    `;
    openModal('detailModal');

    try {
        const m = await api(`/api/movies/${tmdb_id}`);
        body.innerHTML = `
            ${m.backdrop_path
                ? `<img class="detail__poster" src="${m.backdrop_path}" alt="${m.title}"
                        onerror="this.style.display='none'">`
                : ''
            }
            <div class="detail__genres">
                ${(m.genres || []).map(g => `<span class="detail__genre">${g}</span>`).join('')}
            </div>
            <h2 style="font-family:var(--font-display);font-size:28px;letter-spacing:1px;margin-bottom:4px;">
                ${m.title}
            </h2>
            ${m.original_title && m.original_title !== m.title
                ? `<div style="color:var(--text-muted);font-size:13px;margin-bottom:14px;">${m.original_title}</div>`
                : ''
            }
            <p class="detail__overview">${m.overview || 'Тайлбар байхгүй'}</p>

            <div class="detail__info-row">
                <span class="detail__info-label">Үнэлгээ</span>
                <span class="detail__info-value" style="color:var(--gold);">⭐ ${m.vote_average} / 10</span>
            </div>
            <div class="detail__info-row">
                <span class="detail__info-label">Нээлт</span>
                <span class="detail__info-value">${m.release_date || '—'}</span>
            </div>
            <div class="detail__info-row">
                <span class="detail__info-label">Хугацаа</span>
                <span class="detail__info-value">${m.runtime ? m.runtime + ' мин' : '—'}</span>
            </div>

            <div class="detail__price-row">
                <span class="detail__price">₮${numberFormat(m.price)}</span>
                ${m.is_purchased
                    ? `<a href="${m.download_url}" target="_blank" class="btn btn--green btn--lg">
                         📥 Татаж авах
                       </a>`
                    : `<button class="btn btn--gold btn--lg" onclick="startPurchase(${m.tmdb_id})">
                         🛒 Худалдаж авах
                       </button>`
                }
            </div>
        `;
    } catch (err) {
        body.innerHTML = `<div class="empty-state"><div class="empty-state__text">${err.message}</div></div>`;
    }
}

// ═══════════════════════════════════════════════
//  ТӨЛБӨР: QPay Invoice → QR → Polling
// ═══════════════════════════════════════════════

async function startPurchase(tmdb_id) {
    // Нэвтэрсэн эсэх
    if (!state.user) {
        closeModal('detailModal');
        openModal('authModal');
        showToast('Эхлээд нэвтэрнэ үү', 'info');
        return;
    }

    const body = document.getElementById('detailBody');
    body.innerHTML = `
        <div class="payment-section">
            <div class="spinner-lg" style="margin:0 auto 12px;"></div>
            <p style="color:var(--text-secondary)">QPay нэхэмжлэх үүсгэж байна...</p>
        </div>
    `;

    try {
        const data = await api('/api/payments/create-invoice', {
            method: 'POST',
            body: JSON.stringify({ movie_tmdb_id: tmdb_id }),
        });

        renderPaymentQR(data, body);
        startPaymentPolling(data.sender_invoice_no, tmdb_id);

    } catch (err) {
        body.innerHTML = `
            <div class="empty-state">
                <div class="empty-state__icon">❌</div>
                <div class="empty-state__text">${err.message}</div>
                <button class="btn btn--outline" style="margin-top:16px" onclick="showMovieDetail(${tmdb_id})">
                    Буцах
                </button>
            </div>
        `;
    }
}

function renderPaymentQR(data, container) {
    // Банкны апп линкүүд
    const deeplinks = (data.deeplinks || []).map(d => `
        <a href="${d.link}" class="bank-link" target="_blank">
            <img src="${d.logo}" alt="${d.name}" onerror="this.style.display='none'">
            <span>${d.description || d.name}</span>
        </a>
    `).join('');

    container.innerHTML = `
        <div class="payment-section">
            <h3 style="font-family:var(--font-display);font-size:22px;letter-spacing:1px;margin-bottom:4px;">
                ${data.movie_title}
            </h3>
            <div style="font-size:24px;color:var(--gold);font-weight:700;margin-bottom:16px;">
                ₮${numberFormat(data.amount)}
            </div>

            <div class="qr-container">
                <img src="data:image/png;base64,${data.qr_image}" alt="QPay QR Code">
            </div>

            <div class="payment-status" id="paymentStatus">
                <div class="spinner"></div>
                <span>Төлбөр хүлээж байна...</span>
            </div>

            ${data.qpay_short_url
                ? `<div style="margin:8px 0;">
                     <a href="${data.qpay_short_url}" target="_blank" class="btn btn--outline btn--sm">
                       📱 QPay апп нээх
                     </a>
                   </div>`
                : ''
            }

            ${deeplinks
                ? `<div style="margin-top:20px;">
                     <div style="font-size:13px;color:var(--text-muted);margin-bottom:10px;">
                       Банкны апп-аар төлөх:
                     </div>
                     <div class="bank-links">${deeplinks}</div>
                   </div>`
                : ''
            }
        </div>
    `;
}

// ─── Төлбөр шалгах Interval Polling ──────────
function startPaymentPolling(senderInvoiceNo, tmdb_id) {
    // Өмнөх polling зогсоох
    if (state.pollingTimer) clearInterval(state.pollingTimer);
    state.pollingCount = 0;

    state.pollingTimer = setInterval(async () => {
        state.pollingCount++;

        // Хязгаар шалгах
        if (state.pollingCount > state.MAX_POLL) {
            clearInterval(state.pollingTimer);
            state.pollingTimer = null;
            const statusEl = document.getElementById('paymentStatus');
            if (statusEl) {
                statusEl.innerHTML = `
                    <span style="color:var(--red)">⏱ Хугацаа дууслаа. Дахин оролдоно уу.</span>
                `;
            }
            return;
        }

        try {
            const data = await api('/api/payments/check', {
                method: 'POST',
                body: JSON.stringify({ sender_invoice_no: senderInvoiceNo }),
            });

            if (data.paid) {
                // Амжилттай!
                clearInterval(state.pollingTimer);
                state.pollingTimer = null;

                // UI шинэчлэх
                const body = document.getElementById('detailBody');
                body.innerHTML = `
                    <div class="payment-success">
                        <div class="payment-success__icon">✓</div>
                        <div class="payment-success__title">ТӨЛБӨР АМЖИЛТТАЙ!</div>
                        <div class="payment-success__text">
                            Таны худалдан авалт амжилттай боллоо.
                        </div>
                        <button class="btn btn--green btn--lg" onclick="afterPurchaseSuccess(${tmdb_id})">
                            📥 Татаж авах хуудас руу очих
                        </button>
                    </div>
                `;

                showToast('Төлбөр амжилттай!', 'success');

                // Жагсаалт шинэчлэх
                loadMovies();
            }
        } catch (err) {
            console.warn('Polling алдаа:', err.message);
            // Алдаа гарсан ч polling үргэлжлэнэ
        }
    }, 5000); // 5 секунд тутам шалгах
}

async function afterPurchaseSuccess(tmdb_id) {
    closeModal('detailModal');
    // Шинэчилсэн мэдээлэлтэй modal нээх
    setTimeout(() => showMovieDetail(tmdb_id), 300);
}

// ═══════════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', async () => {
    await checkAuth();
    await loadMovies();
});
