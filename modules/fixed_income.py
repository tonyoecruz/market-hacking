"""
Fixed Income (Renda Fixa) Analysis Module
Analyzes and ranks current Fixed Income opportunities (CDB, LCI, LCA) based on market data.
"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class FixedIncomeManager:
    """
    Manages Fixed Income data, scraping (simulated or real), and ranking.
    """

    @staticmethod
    def get_top_opportunities() -> List[Dict]:
        """
        Returns a curated list of Top 10 Fixed Income opportunities.
        In a real scenario, this would scrape aggregators like Youbbo or bank sites.
        Here we analyze based on current Selic (approx 10.75% -> 11.25% scenario) and realistic market rates.
        """
        
        # ⚠️ BLACKLIST — NUNCA incluir estas instituições:
        # - Banco Master → Em processo de LIQUIDAÇÃO JUDICIAL
        # - Caruana Financeira → Alto risco, problemas regulatórios
        # Sempre verificar a situação regulatória do emissor antes de incluir.
        
        # Simulated "Live" Market Data
        # Base CDI assumption: ~11.15% (just an example for calculation if needed)
        
        opportunities = [
            {
                "type": "CDB",
                "issuer": "BTG Pactual",
                "rate_type": "Pos-fixado",
                "rate_val": 118.0, # % CDI
                "maturity": "2027-05-15",
                "min_investment": 1000.00,
                "risk_score": 2, # 1-5 (1=safest, 5=riskiest)
                "safety_rating": "FGC Garantido",
                "liquidity": "No Vencimento"
            },
            {
                "type": "LCA",
                "issuer": "Banco ABC",
                "rate_type": "Isento",
                "rate_val": 94.0, # % CDI (equivalent to ~121% CDB taxable)
                "maturity": "2025-11-20",
                "min_investment": 1000.00,
                "risk_score": 2,
                "safety_rating": "FGC Garantido",
                "liquidity": "90 dias"
            },
            {
                "type": "CDB",
                "issuer": "Banco Sofisa",
                "rate_type": "Pos-fixado",
                "rate_val": 110.0,
                "maturity": "2026-02-10",
                "min_investment": 1.00,
                "risk_score": 1,
                "safety_rating": "FGC Garantido",
                "liquidity": "Diária"
            },
            {
                "type": "LCI",
                "issuer": "Banco Inter",
                "rate_type": "Isento",
                "rate_val": 88.0,
                "maturity": "2026-08-15",
                "min_investment": 50.00,
                "risk_score": 1,
                "safety_rating": "FGC Garantido",
                "liquidity": "90 dias"
            },
            {
                "type": "CDB",
                "issuer": "PagBank",
                "rate_type": "Pos-fixado",
                "rate_val": 105.0,
                "maturity": "2025-08-01",
                "min_investment": 1.00,
                "risk_score": 1,
                "safety_rating": "FGC Garantido",
                "liquidity": "Diária"
            },
             {
                "type": "CDB",
                "issuer": "C6 Bank",
                "rate_type": "Pré-fixado",
                "rate_val": 12.5, # % a.a.
                "maturity": "2028-01-01",
                "min_investment": 100.00,
                "risk_score": 2,
                "safety_rating": "FGC Garantido",
                "liquidity": "No Vencimento"
            },
            {
                "type": "LCI",
                "issuer": "Bradesco",
                "rate_type": "Isento",
                "rate_val": 90.0,
                "maturity": "2026-12-10",
                "min_investment": 500.00,
                "risk_score": 1,
                "safety_rating": "FGC Garantido",
                "liquidity": "90 dias"
            },
             {
                "type": "CDB",
                "issuer": "Banco Pine",
                "rate_type": "Pos-fixado",
                "rate_val": 118.0,
                "maturity": "2026-05-15",
                "min_investment": 1000.00,
                "risk_score": 3,
                "safety_rating": "FGC Garantido",
                "liquidity": "No Vencimento"
            },
            {
                "type": "LCI",
                "issuer": "Caixa Economica",
                "rate_type": "Isento",
                "rate_val": 85.0,
                "maturity": "2025-10-01",
                "min_investment": 500.00,
                "risk_score": 1,
                "safety_rating": "FGC Garantido",
                "liquidity": "90 dias"
            },
            {
                "type": "CDB",
                "issuer": "Banco Daycoval",
                "rate_type": "Pos-fixado",
                "rate_val": 110.0,
                "maturity": "2025-09-20",
                "min_investment": 1000.00,
                "risk_score": 2,
                "safety_rating": "FGC Garantido",
                "liquidity": "No Vencimento"
            }
        ]
        
        # Calculate 'Score' (Simple heuristic: High Rate / Low Risk)
        # Normalize: Rate 100% CDI = 1.0. Risk 1 = 1.0.
        # Score = RateFactor / RiskFactor
        
        for opp in opportunities:
            rate_norm = opp['rate_val']
            # Boost exemption (LCI/LCA is worth more than equivalent CDB)
            if opp['rate_type'] == "Isento":
                rate_norm = rate_norm * 1.225 # Approx Income Tax adjustment
            elif opp['rate_type'] == "Pré-fixado":
                rate_norm = opp['rate_val'] * 8.5 # Rough conversion to % CDI scale for comparison
                
            opp['score'] = round(rate_norm / (opp['risk_score'] * 0.5 + 0.5), 1)
            
        # Sort by Score Descending
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        
        return opportunities
