/**
 * calc_fiis.js — FII Strategy Definitions
 * ==========================================
 * 5 investment models for Fundos Imobiliários.
 * API endpoint: GET /fiis/api/data-estrategia?strategy={id}
 */

const FII_STRATEGIES = [
    {
        id: 'renda_constante',
        name: 'Renda Constante',
        icon: '💰',
        desc: 'Max Yield — Liq > 500K, P/VP 0.8–1.10, ordenado por maior DY',
        columns: ['DY 12m', 'P/VP', 'Preço', 'Liquidez'],
        scoreKey: '_dy_display',
        scoreLabel: 'DY 12m (%)',
    },
    {
        id: 'desconto_patrimonial',
        name: 'Desconto Patrimonial',
        icon: '🏷️',
        desc: 'Deep Value — DY > 6%, P/VP 0.4–0.95, menor P/VP vence',
        columns: ['P/VP', 'DY 12m', 'Preço', 'Liquidez'],
        scoreKey: 'pvp',
        scoreLabel: 'P/VP',
    },
    {
        id: 'bazin_fii',
        name: 'Bazin Imobiliário',
        icon: '🎯',
        desc: 'Preço Teto = DivAnual ÷ 0.08 — margem de segurança',
        columns: ['Margem Seg.', 'Preço Teto', 'DY 12m', 'P/VP'],
        scoreKey: '_margem_seg',
        scoreLabel: 'Margem Seg. (%)',
    },
    {
        id: 'magic_fii',
        name: 'Magic Formula FII',
        icon: '🧙',
        desc: 'Rank DY + Rank P/VP — menor soma ganha',
        columns: ['Score', 'Rank DY', 'Rank P/VP', 'DY 12m'],
        scoreKey: '_score',
        scoreLabel: 'Score (menor=melhor)',
    },
    {
        id: 'qualidade_premium',
        name: 'Qualidade Premium',
        icon: '🏢',
        desc: 'Tijolo Seguro — multi-imóvel, baixa vacância, P/VP < 1.05',
        columns: ['DY 12m', 'P/VP', 'Preço', 'Liquidez'],
        scoreKey: '_dy_display',
        scoreLabel: 'DY 12m (%)',
    },
];

/**
 * Returns display value for FII metrics.
 */
function fiiMetricValue(item, metricName) {
    const fmtNum = (n, d = 2) => (n == null ? '-' : Number(n).toFixed(d));
    const fmtPct = (n) => {
        if (n == null) return '-';
        const num = Number(n);
        const disp = Math.abs(num) < 1 ? num * 100 : num;
        return disp.toFixed(2) + '%';
    };
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
        case 'DY 12m': return item._dy_display != null ? fmtNum(item._dy_display) + '%' : fmtPct(item.dy);
        case 'P/VP': return fmtNum(item.pvp);
        case 'Preço': return fmtMoney(item.price);
        case 'Liquidez': return fmtLiq(item.liquidezmediadiaria);
        case 'Margem Seg.': return item._margem_seg != null ? fmtNum(item._margem_seg) + '%' : '-';
        case 'Preço Teto': return item._preco_teto != null ? fmtMoney(item._preco_teto) : '-';
        case 'Score': return item._score != null ? fmtNum(item._score, 0) : '-';
        case 'Rank DY': return item._rank_dy != null ? fmtNum(item._rank_dy, 0) : '-';
        case 'Rank P/VP': return item._rank_pvp != null ? fmtNum(item._rank_pvp, 0) : '-';
        default: return '-';
    }
}

function fiiMetricColor(item, metricName) {
    if (metricName === 'DY 12m') {
        const dy = item._dy_display || (item.dy > 1 ? item.dy : item.dy * 100);
        return dy > 8 ? 'text-green-400' : dy > 5 ? 'text-yellow-400' : '';
    }
    if (metricName === 'P/VP') {
        return item.pvp < 1 ? 'text-green-400' : item.pvp > 1.1 ? 'text-red-400' : '';
    }
    if (metricName === 'Margem Seg.') {
        return item._margem_seg > 0 ? 'text-green-400' : 'text-red-400';
    }
    return '';
}
