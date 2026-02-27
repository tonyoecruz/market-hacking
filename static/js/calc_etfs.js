/**
 * calc_etfs.js — ETF Strategy Definitions
 * ==========================================
 * 4 investment models for ETFs.
 * API endpoint: GET /etfs/api/data-estrategia?strategy={id}
 */

const ETF_STRATEGIES = [
    {
        id: 'boglehead',
        name: 'Boglehead',
        icon: '📉',
        desc: 'Eficiência de Custo — menor taxa de administração',
        columns: ['Taxa Admin', 'Preço', 'Liquidez', 'Nome'],
        scoreKey: 'taxa_admin',
        scoreLabel: 'Taxa Admin (%)',
    },
    {
        id: 'sharpe',
        name: 'Risco-Retorno',
        icon: '📊',
        desc: 'Maior Índice Sharpe — melhor retorno ajustado ao risco',
        columns: ['Sharpe', 'Retorno 12m', 'Volatilidade', 'Liquidez'],
        scoreKey: '_sharpe',
        scoreLabel: 'Índice Sharpe',
    },
    {
        id: 'momentum',
        name: 'Momentum',
        icon: '🚀',
        desc: 'Trend Following — maior rentabilidade acumulada 12 meses',
        columns: ['Retorno 12m', 'Preço', 'Liquidez', 'Nome'],
        scoreKey: '_ret_display',
        scoreLabel: 'Retorno 12m (%)',
    },
    {
        id: 'renda_etf',
        name: 'Renda ETF',
        icon: '💵',
        desc: 'Foco em Distribuição — ETFs que pagam dividendos',
        columns: ['DY 12m', 'Preço', 'Liquidez', 'Nome'],
        scoreKey: '_dy_display',
        scoreLabel: 'DY 12m (%)',
    },
];

/**
 * Returns display value for ETF metrics.
 */
function etfMetricValue(item, metricName) {
    const fmtNum = (n, d = 2) => (n == null ? '-' : Number(n).toFixed(d));
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
        case 'Taxa Admin': return item.taxa_admin != null ? fmtNum(item.taxa_admin) + '%' : '-';
        case 'Preço': return fmtMoney(item.price);
        case 'Liquidez': return fmtLiq(item.liquidezmediadiaria);
        case 'Nome': return item.empresa || item.ticker || '-';
        case 'Sharpe': return item._sharpe != null ? fmtNum(item._sharpe) : '-';
        case 'Retorno 12m': return item._ret_display != null ? fmtNum(item._ret_display) + '%' :
            (item.retorno_12m != null ? fmtNum(item.retorno_12m) + '%' : '-');
        case 'Volatilidade': return item.volatilidade != null ? fmtNum(item.volatilidade) + '%' : '-';
        case 'DY 12m': return item._dy_display != null ? fmtNum(item._dy_display) + '%' : '-';
        default: return '-';
    }
}

function etfMetricColor(item, metricName) {
    if (metricName === 'Sharpe') {
        if (item._sharpe == null) return '';
        return item._sharpe > 0.5 ? 'text-green-400' : item._sharpe < 0 ? 'text-red-400' : '';
    }
    if (metricName === 'Retorno 12m') {
        const v = item._ret_display || item.retorno_12m;
        return v > 0 ? 'text-green-400' : v < 0 ? 'text-red-400' : '';
    }
    if (metricName === 'DY 12m') {
        const v = item._dy_display;
        return v > 0 ? 'text-green-400' : '';
    }
    return '';
}
