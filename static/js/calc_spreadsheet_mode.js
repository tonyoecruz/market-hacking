/**
 * calc_spreadsheet_mode.js — Modo Planilha
 * ========================================
 * Definitions for the 8 spreadsheet-style weighted-rank strategies.
 * This file contains ONLY strategy configuration + column display helpers.
 * All calculation is performed by the backend (spreadsheet_engine.py).
 *
 * API endpoint: GET /acoes/api/data?strategy={id}&min_liq={n}
 */

const SPREADSHEET_STRATEGIES = [
    {
        id: 'magic',
        name: 'Magic',
        icon: '✨',
        desc: 'EV/EBIT baixo + ROIC alto',
        color: 'from-violet-600 to-purple-700',
        borderColor: 'border-violet-500',
        // columns[0..4]: headers for the 5 dynamic metric columns in the table
        columns: ['EV/EBIT', 'ROIC %', 'P/L', 'P/VP', 'DY %'],
    },
    {
        id: 'magic_lucros',
        name: 'MagicLucros',
        icon: '💡',
        desc: 'Magic + CAGR Lucros alto',
        color: 'from-blue-600 to-indigo-700',
        borderColor: 'border-blue-500',
        columns: ['EV/EBIT', 'ROIC %', 'CAGR %', 'P/L', 'P/VP'],
    },
    {
        id: 'baratas',
        name: 'Baratas',
        icon: '🏷️',
        desc: 'P/VP baixo + P/L baixo + EV/EBIT baixo',
        color: 'from-green-600 to-emerald-700',
        borderColor: 'border-green-500',
        columns: ['P/VP', 'P/L', 'EV/EBIT', 'DY %', 'ROIC %'],
    },
    {
        id: 'solidas',
        name: 'Sólidas',
        icon: '🏛️',
        desc: 'ROE alto + Margem alta + baixa alavancagem',
        color: 'from-amber-600 to-yellow-700',
        borderColor: 'border-amber-500',
        columns: ['ROE %', 'Marg Líq %', 'Dív/Pat', 'P/L', 'DY %'],
    },
    {
        id: 'mix',
        name: 'Mix',
        icon: '🎯',
        desc: 'P/L + DY + ROE — balanceado',
        color: 'from-cyan-600 to-teal-700',
        borderColor: 'border-cyan-500',
        columns: ['P/L', 'DY %', 'ROE %', 'P/VP', 'ROIC %'],
    },
    {
        id: 'dividendos',
        name: 'Dividendos',
        icon: '💰',
        desc: 'Maior Dividend Yield (peso 3)',
        color: 'from-emerald-600 to-green-700',
        borderColor: 'border-emerald-500',
        columns: ['DY %', 'P/L', 'P/VP', 'ROIC %', 'Dív/Pat'],
    },
    {
        id: 'graham',
        name: 'Graham',
        icon: '📈',
        desc: 'P/L Menor + P/VP Menor',
        color: 'from-orange-600 to-red-700',
        borderColor: 'border-orange-500',
        columns: ['P/L', 'P/VP', 'DY %', 'V. Justo', 'Margem %'],
    },
    {
        id: 'greenblatt',
        name: 'GreenBla',
        icon: '📗',
        desc: 'Earnings Yield alto + ROIC alto',
        color: 'from-lime-600 to-green-700',
        borderColor: 'border-lime-500',
        columns: ['E. Yield', 'ROIC %', 'EV/EBIT', 'P/L', 'P/VP'],
    },
];

/**
 * Returns the display value for a given metric header name + stock object.
 * Used to populate all 5 metric columns in the ranking table.
 */
function spreadsheetMetricValue(stock, metricName) {
    const v = (key) => stock[key];
    const fmtNum = (n, d = 2) => (n == null ? '-' : Number(n).toFixed(d));
    const fmtPct = (n) => {
        if (n == null) return '-';
        const num = Number(n);
        const disp = Math.abs(num) < 5 ? num * 100 : num;
        return disp.toFixed(1) + '%';
    };
    const fmtLiq = (n) => {
        if (!n) return '-';
        const x = Number(n);
        if (x >= 1e9) return 'R$ ' + (x / 1e9).toFixed(2) + 'B';
        if (x >= 1e6) return 'R$ ' + (x / 1e6).toFixed(1) + 'M';
        if (x >= 1e3) return 'R$ ' + (x / 1e3).toFixed(0) + 'K';
        return 'R$ ' + x.toFixed(0);
    };

    switch (metricName) {
        case 'P/L': return fmtNum(v('pl'));
        case 'P/VP': return fmtNum(v('pvp'));
        case 'DY %': return fmtPct(v('dy'));
        case 'ROIC %': return fmtPct(v('roic'));
        case 'ROE %': return v('roe') != null ? fmtPct(v('roe')) : '-';
        case 'EV/EBIT': return fmtNum(v('ev_ebit'));
        case 'E. Yield': return (v('ev_ebit') && v('ev_ebit') > 0)
            ? fmtPct(1 / v('ev_ebit')) : '-';
        case 'V. Justo': return v('valor_justo') ? `R$ ${fmtNum(v('valor_justo'))}` : '-';
        case 'Margem %': return fmtPct(v('margem'));
        case 'Marg Líq %': return fmtPct(v('margem_liquida'));
        case 'Dív/Pat': return fmtNum(v('div_pat'));
        case 'CAGR %': return fmtPct(v('cagr_lucros'));
        case 'Liquidez': return fmtLiq(v('liquidezmediadiaria'));
        default: return '-';
    }
}

/**
 * Returns a CSS color class for the given metric value (for coloured cells).
 */
function spreadsheetMetricColor(stock, metricName) {
    switch (metricName) {
        case 'Margem %':
            return (stock.margem > 0) ? 'text-green-400' : (stock.margem < 0 ? 'text-red-400' : '');
        case 'DY %':
            return (stock.dy > 0.05 || stock.dy > 5) ? 'text-green-400' : '';
        case 'ROE %':
        case 'ROIC %':
        case 'E. Yield':
        case 'CAGR %': {
            const key = { 'ROE %': null, 'ROIC %': 'roic', 'E. Yield': null, 'CAGR %': 'cagr_lucros' };
            return ''; // neutral — let positive values speak for themselves
        }
        default: return '';
    }
}
