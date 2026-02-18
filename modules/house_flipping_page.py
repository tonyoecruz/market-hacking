import streamlit as st
import pandas as pd
import asyncio
import time
from modules.house_flipping import SerperAgencyDiscovery, AgencyCrawler, calculate_flipping_opportunity


def _run_async(coro):
    """Run an async coroutine from synchronous Streamlit context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def render_house_flipping_page():
    st.title("🏠 House Flipping! - Sistema de Arbitragem Imobiliaria")
    st.markdown("Identifique imoveis subprecificados comparando o valor do m2 com a media da regiao.")

    # --- Sidebar Filters ---
    with st.sidebar:
        st.header("🔍 Configuracao da Busca")
        city_input = st.text_input("Cidade (ex: Sorocaba)", value="Sorocaba")
        run_scan = st.button("🚀 Iniciar Varredura", type="primary")

        st.divider()
        st.info("💡 **Dica:** O sistema descobre imobiliarias locais, visita seus sites e calcula o desvio do preco por m2.")

    # --- Main Content ---
    if run_scan and city_input:
        st.success(f"Iniciando varredura em **{city_input}**...")

        # 1. Discover agencies via Serper
        progress_text = "Descobrindo imobiliarias locais..."
        my_bar = st.progress(0, text=progress_text)

        discovery = SerperAgencyDiscovery()
        agencies = _run_async(discovery.discover(city_input))

        if not agencies:
            st.warning("Nenhuma imobiliaria encontrada. Verifique a SERPER_API_KEY.")
            my_bar.empty()
            return

        with st.expander(f"🏢 Imobiliarias Identificadas em {city_input} ({len(agencies)})", expanded=False):
            for ag in agencies:
                st.write(f"- [{ag['name']}](https://{ag['domain']})")

        my_bar.progress(20, text="Visitando sites das imobiliarias...")

        # 2. Crawl agencies and extract listings
        crawler = AgencyCrawler()
        listings = _run_async(crawler.crawl_all_agencies(agencies, city_input))
        my_bar.progress(70, text="Calculando oportunidades de arbitragem...")

        if not listings:
            st.warning("Nenhum imovel encontrado nos sites das imobiliarias.")
            my_bar.empty()
            return

        # 3. Calculate Logic (Pandas)
        df = pd.DataFrame(listings)
        df['Valor Total'] = pd.to_numeric(df['Valor Total'], errors='coerce')
        df['Area (m2)'] = pd.to_numeric(df['Area (m2)'], errors='coerce')
        df = df.dropna(subset=['Valor Total', 'Area (m2)'])

        df_analyzed = calculate_flipping_opportunity(df)

        my_bar.progress(100, text="Concluido!")
        time.sleep(0.5)
        my_bar.empty()

        # 4. Display Results
        col1, col2, col3 = st.columns(3)
        col1.metric("Imoveis Analisados", len(df_analyzed))
        if not df_analyzed.empty:
            avg_m2 = df_analyzed['Valor/m2'].mean()
            col2.metric("Media Geral R$/m2", f"R$ {avg_m2:,.2f}")

            best_deal = df_analyzed.iloc[0]
            col3.metric("Maior Oportunidade", f"{best_deal['Dif vs Med (%)']}%", f"R$ {best_deal['Valor Total']:,.2f}")

        st.subheader("📊 Tabela de Oportunidades")
        st.markdown("Ordenado pelos imoveis mais **baratos** em relacao a media do bairro.")

        # Formatting for display
        df_display = df_analyzed[['Bairro', 'Imobiliaria', 'Tipo', 'Area (m2)', 'Valor Total', 'Valor/m2', 'Media Setor (m2)', 'Dif vs Med (%)', 'Link']].copy()

        st.dataframe(
            df_display,
            column_config={
                "Link": st.column_config.LinkColumn("Anuncio"),
                "Dif vs Med (%)": st.column_config.NumberColumn(
                    "Desconto x Media",
                    format="%.2f %%",
                    help="Quanto % mais barato que a media"
                ),
                "Valor Total": st.column_config.NumberColumn(format="R$ %.2f"),
                "Valor/m2": st.column_config.NumberColumn(format="R$ %.2f"),
            },
            hide_index=True,
            use_container_width=True
        )

    else:
        st.write("👈 Digite a cidade e clique em iniciar para buscar oportunidades.")
