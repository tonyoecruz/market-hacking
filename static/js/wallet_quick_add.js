/**
 * Wallet Quick-Add — reusable inline form for adding assets to wallets.
 * Include this script on any page that shows asset tables (Acoes, FIIs, ETFs, etc.)
 *
 * Usage:
 *   walletQuickAdd.open(ticker, price, buttonElement)
 *   walletQuickAdd.close()
 */
const walletQuickAdd = (function () {
    const FORM_ID = 'wallet-quick-add-form';
    let _wallets = null; // cached

    async function loadWallets() {
        if (_wallets !== null) return _wallets;
        try {
            const res = await fetch('/dashboard/api/wallets');
            const data = await res.json();
            _wallets = data.wallets || [];
        } catch {
            _wallets = [];
        }
        return _wallets;
    }

    function close() {
        const old = document.getElementById(FORM_ID);
        if (old) old.remove();
    }

    async function open(ticker, price, anchorEl) {
        close();
        const wallets = await loadWallets();
        const today = new Date().toISOString().split('T')[0];

        let walletOpts = wallets.map(w =>
            `<option value="${w.id}">${w.name}</option>`
        ).join('');

        const form = document.createElement('tr');
        form.id = FORM_ID;
        form.innerHTML = `
        <td colspan="20" class="p-0">
            <div class="bg-dark-700 border border-primary/30 rounded-xl p-4 m-2">
                <div class="flex items-center justify-between mb-3">
                    <h4 class="text-sm font-bold text-primary flex items-center gap-2">
                        <span>&#128188;</span> Adicionar ${ticker} a Carteira
                    </h4>
                    <button onclick="walletQuickAdd.close()" class="text-gray-500 hover:text-gray-300 text-lg leading-none">&times;</button>
                </div>
                <div class="flex flex-wrap items-end gap-3">
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">Carteira</label>
                        <input type="text" id="wqa-wallet" list="wqa-wallet-opts" placeholder="Principal"
                            value="${wallets.length ? wallets[0].name : 'Principal'}"
                            class="w-36 px-3 py-2 bg-dark-900 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                        <datalist id="wqa-wallet-opts">
                            ${walletOpts}
                            </datalist>
                    </div>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">Quantidade</label>
                        <input type="number" id="wqa-qty" value="1" min="1" step="1"
                            class="w-20 px-3 py-2 bg-dark-900 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                    </div>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">Preco (R$)</label>
                        <input type="number" id="wqa-price" value="${Number(price).toFixed(2)}" step="0.01" min="0.01"
                            class="w-28 px-3 py-2 bg-dark-900 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                    </div>
                    <div>
                        <label class="block text-xs text-gray-400 mb-1">Data Compra</label>
                        <input type="date" id="wqa-date" value="${today}"
                            class="w-36 px-3 py-2 bg-dark-900 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                    </div>
                    <div>
                        <button onclick="walletQuickAdd.submit('${ticker}')" id="wqa-btn"
                            class="px-5 py-2 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-500 transition text-sm flex items-center gap-2">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>
                            </svg>
                            Adicionar
                        </button>
                    </div>
                    <span id="wqa-feedback" class="text-sm hidden"></span>
                </div>
            </div>
        </td>`;

        // Insert after the row that contains the anchor button
        const row = anchorEl.closest('tr');
        if (row) {
            row.after(form);
        }

        form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    async function submit(ticker) {
        const btn = document.getElementById('wqa-btn');
        const fb = document.getElementById('wqa-feedback');
        const walletName = document.getElementById('wqa-wallet').value.trim() || 'Principal';
        const qty = parseFloat(document.getElementById('wqa-qty').value) || 1;
        const price = parseFloat(document.getElementById('wqa-price').value) || 0;
        const date = document.getElementById('wqa-date').value || new Date().toISOString().split('T')[0];

        if (price <= 0) {
            fb.classList.remove('hidden');
            fb.className = 'text-sm text-red-400';
            fb.textContent = 'Preco invalido.';
            return;
        }

        btn.disabled = true;
        btn.innerHTML = '<div class="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>';

        try {
            // First, ensure wallet exists (create if new name)
            const wallets = await loadWallets();
            let walletId = null;
            const existing = wallets.find(w => w.name === walletName);
            if (existing) {
                walletId = existing.id;
            } else {
                // Create new wallet
                const createRes = await fetch('/dashboard/api/wallet/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: walletName })
                });
                const createData = await createRes.json();
                if (createRes.ok && createData.wallet_id) {
                    walletId = createData.wallet_id;
                    _wallets = null; // invalidate cache
                } else {
                    throw new Error(createData.detail || 'Erro ao criar carteira');
                }
            }

            // Add asset
            const res = await fetch('/dashboard/api/wallet/add-json', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ticker: ticker,
                    quantity: qty,
                    price: price,
                    wallet_id: walletId,
                    date: date
                })
            });
            const data = await res.json();

            fb.classList.remove('hidden');
            if (res.ok && data.success) {
                fb.className = 'text-sm text-green-400';
                fb.textContent = `${ticker} adicionado a "${walletName}"!`;
                if (typeof showToast === 'function') showToast(`${ticker} adicionado a carteira!`, 'success');
                setTimeout(close, 2000);
            } else {
                fb.className = 'text-sm text-red-400';
                fb.textContent = data.detail || data.message || 'Erro ao adicionar.';
            }
        } catch (e) {
            fb.classList.remove('hidden');
            fb.className = 'text-sm text-red-400';
            fb.textContent = e.message || 'Faca login para adicionar a carteira.';
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg> Adicionar';
        }
    }

    return { open, close, submit };
})();
