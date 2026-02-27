/**
 * calc_rendafixa.js — Renda Fixa Strategy Definitions
 * =====================================================
 * 4 investment models for Fixed Income.
 * API endpoint: GET /renda-fixa/api/data-estrategia?strategy={id}
 */

const RF_STRATEGIES = [
    {
        id: 'reserva_emergencia',
        name: 'Reserva Emergência',
        icon: '🛡️',
        desc: 'Liquidez diária, emissor seguro, maior % do CDI',
        columns: ['% CDI', 'Tipo', 'Emissor', 'Liquidez'],
        scoreKey: 'rate_val',
        scoreLabel: '% do CDI',
    },
    {
        id: 'ganho_real',
        name: 'Ganho Real (IPCA+)',
        icon: '📈',
        desc: 'Proteção contra inflação — maior spread acima do IPCA',
        columns: ['Spread', 'Tipo', 'Emissor', 'Vencimento'],
        scoreKey: 'rate_val',
        scoreLabel: 'Spread IPCA+ (%)',
    },
    {
        id: 'trava_preco',
        name: 'Trava de Preço',
        icon: '🔒',
        desc: 'Pré-fixado 1–5 anos — maior taxa nominal absoluta',
        columns: ['Taxa Anual', 'Tipo', 'Emissor', 'Vencimento'],
        scoreKey: 'rate_val',
        scoreLabel: 'Taxa Anual (%)',
    },
    {
        id: 'duelo_tributario',
        name: 'Duelo Tributário',
        icon: '⚖️',
        desc: 'Equivalência Gross-Up — LCI/LCA vs CDB ajustados por IR',
        columns: ['Taxa Equiv.', 'Tipo', 'Emissor', 'Alíquota IR'],
        scoreKey: '_taxa_bruta_equiv',
        scoreLabel: 'Taxa Bruta Equiv. (%)',
    },
];

/**
 * Returns display value for Renda Fixa metrics.
 */
function rfMetricValue(item, metricName) {
    const fmtNum = (n, d = 2) => (n == null ? '-' : Number(n).toFixed(d));

    switch (metricName) {
        case '% CDI': return item.rate_val != null ? fmtNum(item.rate_val, 1) + '%' : '-';
        case 'Spread': return item.rate_val != null ? fmtNum(item.rate_val, 1) + '%' : '-';
        case 'Taxa Anual': return item.rate_val != null ? fmtNum(item.rate_val, 1) + '%' : '-';
        case 'Taxa Equiv.': return item._taxa_bruta_equiv != null ? fmtNum(item._taxa_bruta_equiv, 1) + '%' : '-';
        case 'Tipo': return item.type || '-';
        case 'Emissor': return item.issuer || '-';
        case 'Liquidez': return item.liquidity || '-';
        case 'Vencimento': return item.maturity || '-';
        case 'Alíquota IR': return item._aliquota_ir != null ? fmtNum(item._aliquota_ir, 1) + '%' :
            (item._is_exempt ? 'Isento' : '-');
        default: return '-';
    }
}

function rfMetricColor(item, metricName) {
    if (metricName === '% CDI' || metricName === 'Taxa Anual' || metricName === 'Spread') {
        return item.rate_val > 100 ? 'text-green-400' : '';
    }
    if (metricName === 'Taxa Equiv.') {
        return item._taxa_bruta_equiv > 110 ? 'text-green-400' : '';
    }
    if (metricName === 'Tipo') {
        const t = (item.type || '').toUpperCase();
        if (t === 'LCI' || t === 'LCA') return 'text-green-400';
        if (t === 'CRI' || t === 'CRA') return 'text-yellow-400';
        return '';
    }
    if (metricName === 'Alíquota IR') {
        return item._is_exempt ? 'text-green-400' : '';
    }
    return '';
}
