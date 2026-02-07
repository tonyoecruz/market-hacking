import streamlit as st
import pandas as pd
import time
from modules.house_flipping import OLXScraper, AgencyFinder, calculate_flipping_opportunity

def render_house_flipping_page():
    st.title("🏠 House Flipping! - Sistema de Arbitragem Imobiliária")
    st.markdown("Identifique imóveis subprecificados comparando o valor do m² com a média da região.")

    # --- Sidebar Filters ---
    with st.sidebar:
        st.header("🔍 Configuração da Busca")
        city_input = st.text_input("Cidade (ex: Sorocaba)", value="Sorocaba")
        run_scan = st.button("🚀 Iniciar Varredura", type="primary")
        
        st.divider()
        st.info("💡 **Dica:** O sistema busca ofertas em grandes portais e calcula o desvio padrão do preço por m².")

    # --- Main Content ---
    if run_scan and city_input:
        st.success(f"Iniciando varredura em **{city_input}**...")
        
        # 1. Simulate Agency Finding (Requirement)
        finder = AgencyFinder()
        agencies = finder.find_agencies(city_input)
        with st.expander(f"🏢 Imobiliárias Identificadas em {city_input}", expanded=False):
            for ag in agencies:
                st.write(f"- [{ag['name']}](http://{ag['site']})")
        
        # 2. Scrape Listings (Real Work)
        scraper = OLXScraper()
        
        # Progress Bar Logic
        progress_text = "Percorrendo sites e extraindo anúncios..."
        my_bar = st.progress(0, text=progress_text)
        
        listings = scraper.search_city(city_input)
        my_bar.progress(50, text="Calculando oportunidades de arbitragem...")
        
        if not listings:
            st.warning("Nenhum imóvel encontrado ou bloqueio de bot detectado.")
            my_bar.empty()
            return

        # 3. Calculate Logic (Pandas)
        df = pd.DataFrame(listings)
        
        # Ensure numeric types
        df['Valor Total'] = pd.to_numeric(df['Valor Total'], errors='coerce')
        df['Área (m²)'] = pd.to_numeric(df['Área (m²)'], errors='coerce')
        df = df.dropna(subset=['Valor Total', 'Área (m²)'])
        
        df_analyzed = calculate_flipping_opportunity(df)
        
        my_bar.progress(100, text="Concluído!")
        time.sleep(0.5)
        my_bar.empty()
        
        # 4. Display Results
        col1, col2, col3 = st.columns(3)
        col1.metric("Imóveis Analisados", len(df_analyzed))
        if not df_analyzed.empty:
            avg_m2 = df_analyzed['Valor/m²'].mean()
            col2.metric("Média Geral R$/m²", f"R$ {avg_m2:,.2f}")
            
            best_deal = df_analyzed.iloc[0]
            col3.metric("Maior Oportunidade", f"{best_deal['Dif vs Med (%)']}%", f"R$ {best_deal['Valor Total']:,.2f}")

        st.subheader("📊 Tabela de Oportunidades")
        st.markdown("Ordenado pelos imóveis mais **baratos** em relação à média do bairro.")
        
        # Formatting for display
        df_display = df_analyzed[['Bairro', 'Tipo', 'Área (m²)', 'Valor Total', 'Valor/m²', 'Média Setor (m²)', 'Dif vs Med (%)', 'Link']].copy()
        
        # Style Dataframe
        st.dataframe(
            df_display,
            column_config={
                "Link": st.column_config.LinkColumn("Anúncio"),
                "Dif vs Med (%)": st.column_config.NumberColumn(
                    "Desconto x Média",
                    format="%.2f %%",
                    help="Quanto % mais barato que a média"
                ),
                "Valor Total": st.column_config.NumberColumn(format="R$ %.2f"),
                "Valor/m²": st.column_config.NumberColumn(format="R$ %.2f"),
            },
            hide_index=True,
            use_container_width=True
        )

    else:
        st.write("👈 Digite a cidade e clique em iniciar para buscar oportunidades.")
