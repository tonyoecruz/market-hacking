/**
 * calc_real_mode.js — Modo Teórico
 * ===================================
 * Definitions for the 9 literature-based investment model strategies.
 * This file contains ONLY strategy configuration + column display helpers.
 * All calculation is performed by the backend (teorico_engine.py).
 *
 * API endpoint: GET /acoes/api/data-teorico?strategy={id}&min_liq={n}
 */

const TEORICO_STRATEGIES = [
    {
        id: 'graham',
        name: 'Modelo Graham',
        icon: '📐',
        desc: 'Valor Intrínseco √(22.5×LPA×VPA) — filtro P/L≤15 e P/VP≤1.5',
        color: 'from-orange-600 to-red-700',
        borderColor: 'border-orange-500',
        // columns[0]: main score column, [1..4]: secondary display columns
        columns: ['Upside Graham', 'P/L', 'P/VP', 'V. Intrínseco', 'DY %'],
        scoreKey: '_upside',
        scoreLabel: 'Upside Graham',
        scorePct: true,
    },
    {
        id: 'crescimento',
        name: 'Modelo Crescimento',
        icon: '🚀',
        desc: 'PEG Ratio = P/L ÷ (CAGR×100) — melhor abaixo de 1.0',
        color: 'from-cyan-600 to-teal-700',
        borderColor: 'border-cyan-500',
        columns: ['PEG Ratio', 'P/L', 'CAGR %', 'ROE %', 'P/VP'],
        scoreKey: '_peg',
        scoreLabel: 'PEG Ratio',
        scorePct: false,
    },
    {
        id: 'valor',
        name: 'Modelo Valor',
        icon: '💎',
        desc: 'EV/EBIT positivo — menor EV/EBIT + menor P/VP',
        color: 'from-blue-600 to-indigo-700',
        borderColor: 'border-blue-500',
        columns: ['EV/EBIT', 'P/VP', 'P/L', 'DY %', 'ROIC %'],
        scoreKey: 'ev_ebit',
        scoreLabel: 'EV/EBIT',
        scorePct: false,
    },
    {
        id: 'rentabilidade',
        name: 'Modelo Rentabilidade',
        icon: '🏆',
        desc: 'ROIC>10% + DívPat<2 — ordenado por ROE depois ROIC',
        color: 'from-amber-600 to-yellow-700',
        borderColor: 'border-amber-500',
        columns: ['ROE %', 'ROIC %', 'Dív/Pat', 'P/L', 'Margem %'],
        scoreKey: 'roe',
        scoreLabel: 'ROE',
        scorePct: true,
    },
    {
        id: 'gordon',
        name: 'Modelo Balanceado',
        icon: '⚖️',
        desc: 'Gordon DDM: P.Justo = Div/(k-g) com k=10%, g=3%',
        color: 'from-pink-600 to-rose-700',
        borderColor: 'border-pink-500',
        columns: ['Upside Gordon', 'DY %', 'P/L', 'P/VP', 'ROIC %'],
        scoreKey: '_upside',
        scoreLabel: 'Upside Gordon',
        scorePct: true,
    },
    {
        id: 'dividendos',
        name: 'Dividendos Clássico',
        icon: '💵',
        desc: 'DY > 6% e Payout 30–80% — ordenado pelo maior DY',
        color: 'from-emerald-600 to-green-700',
        borderColor: 'border-emerald-500',
        columns: ['DY %', 'P/L', 'P/VP', 'Dív/Pat', 'ROIC %'],
        scoreKey: '_dy_norm',
        scoreLabel: 'Dividend Yield',
        scorePct: true,
    },
    {
        id: 'bazin',
        name: 'Preço Justo (Bazin)',
        icon: '🎯',
        desc: 'Preço Teto = Div÷0.06 — upside vs preço atual',
        color: 'from-violet-600 to-purple-700',
        borderColor: 'border-violet-500',
        columns: ['Upside Bazin', 'DY %', 'Dív/Pat', 'P/L', 'P/VP'],
        scoreKey: '_upside',
        scoreLabel: 'Upside Bazin',
        scorePct: true,
    },
    {
        id: 'greenblatt',
        name: 'Magic Formula',
        icon: '🧙',
        desc: 'Earnings Yield + ROIC — excl. Financeiro — menor soma ganha',
        color: 'from-lime-600 to-green-700',
        borderColor: 'border-lime-500',
        columns: ['Score MF', 'E. Yield', 'ROIC %', 'EV/EBIT', 'P/L'],
        scoreKey: '_score',
        scoreLabel: 'Score MF',
        scorePct: false,
    },
    {
        id: 'small_caps',
        name: 'Small Caps',
        icon: '🔬',
        desc: 'Liq < P75 + Liq > 500K — ordenado pelo menor P/L',
        color: 'from-slate-600 to-gray-700',
        borderColor: 'border-slate-500',
        columns: ['P/L', 'Liquidez', 'P/VP', 'DY %', 'ROIC %'],
        scoreKey: 'pl',
        scoreLabel: 'P/L',
        scorePct: false,
    },
];

/**
 * Returns the display value for a given metric header name + stock object.
 * Handles Teórico-specific computed fields (_upside, _peg, _vi, etc.).
 */
function teoricoMetricValue(stock, metricName) {
    const v = (key) => stock[key];
    const fmtNum = (n, d = 2) => (n == null ? '-' : Number(n).toFixed(d));
    const fmtPct = (n) => {
        if (n == null) return '-';
        const num = Number(n);
        // Backend stores some as 0-1 fractions, some as whole percent
        const disp = Math.abs(num) < 5 ? num * 100 : num;
        return disp.toFixed(1) + '%';
    };
    const fmtPctRaw = (n) => n == null ? '-' : (Number(n) * 100).toFixed(1) + '%';
    const fmtLiq = (n) => {
        if (!n) return '-';
        const x = Number(n);
        if (x >= 1e9) return 'R$ ' + (x / 1e9).toFixed(2) + 'B';
        if (x >= 1e6) return 'R$ ' + (x / 1e6).toFixed(1) + 'M';
        if (x >= 1e3) return 'R$ ' + (x / 1e3).toFixed(0) + 'K';
        return 'R$ ' + x.toFixed(0);
    };
    const fmtMoney = (n) => n == null ? '-' : `R$ ${fmtNum(n)}`;

    switch (metricName) {
        // Standard fundamentals
        case 'P/L': return fmtNum(v('pl'));
        case 'P/VP': return fmtNum(v('pvp'));
        case 'DY %': return fmtPct(v('dy'));
        case 'ROIC %': return fmtPct(v('roic'));
        case 'ROE %': return (v('lpa') && v('vpa') && v('vpa') !== 0)
            ? fmtPct(v('lpa') / v('vpa')) : '-';
        case 'EV/EBIT': return fmtNum(v('ev_ebit'));
        case 'E. Yield': return (v('ev_ebit') && v('ev_ebit') > 0)
            ? fmtPct(1 / v('ev_ebit')) : '-';
        case 'Dív/Pat': return fmtNum(v('div_pat'));
        case 'CAGR %': return fmtPct(v('cagr_lucros'));
        case 'Margem %': return fmtPct(v('margem'));
        case 'Liquidez': return fmtLiq(v('liquidezmediadiaria'));
        // Teórico computed (returned by backend in row data)
        case 'Upside Graham': return v('_upside') != null ? fmtPctRaw(v('_upside')) : '-';
        case 'Upside Bazin': return v('_upside') != null ? fmtPctRaw(v('_upside')) : '-';
        case 'Upside Gordon': return v('_upside') != null ? fmtPctRaw(v('_upside')) : '-';
        case 'V. Intrínseco': return v('_vi') != null ? fmtMoney(v('_vi')) : '-';
        case 'PEG Ratio': return v('_peg') != null ? fmtNum(v('_peg'), 2) : '-';
        case 'Score MF': return v('_score') != null ? fmtNum(v('_score'), 0) : '-';
        default: return '-';
    }
}

/**
 * Returns a CSS color class for the given metric value.
 */
function teoricoMetricColor(stock, metricName) {
    const positiveGreen = ['Upside Graham', 'Upside Bazin', 'Upside Gordon'];
    const negRed = ['PEG Ratio'];

    if (positiveGreen.includes(metricName)) {
        return (stock._upside > 0) ? 'text-green-400' : 'text-red-400';
    }
    if (metricName === 'PEG Ratio') {
        if (stock._peg == null) return '';
        return (stock._peg < 1) ? 'text-green-400' : (stock._peg > 2 ? 'text-red-400' : 'text-yellow-400');
    }
    if (metricName === 'DY %') {
        return (stock.dy > 0.05 || stock.dy > 5) ? 'text-green-400' : '';
    }
    if (metricName === 'Margem %') {
        return (stock.margem > 0) ? 'text-green-400' : 'text-red-400';
    }
    return '';
}
