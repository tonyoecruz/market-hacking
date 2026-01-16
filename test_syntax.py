
import streamlit as st

def test():
    c1 = 1
    c2 = 2
    i = 0
    r = {'ticker': 'ABC', 'price': 10, 'Margem': 0.1, 'MagicRank': 1}
    format_brl = lambda x: str(x)
    sim_html = "<div></div>"
    
    with (c1 if i%2==0 else c2):
        # Card Personalizado da Elite
        st.markdown(f"""
        <div class="glass-card" style="border: 1px solid #FFD700; background: rgba(255, 215, 0, 0.05);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <div style="font-size:20px; font-weight:700; color:#FFD700;">{r['ticker']}</div>
                <div style="font-size:18px; color:#FFD700; font-weight:600;">{format_brl(r['price'])}</div>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <div>
                    <div style="font-size:11px; color:#CCC; text-transform:uppercase;">MARGEM GRAHAM</div>
                    <div style="font-size:15px; font-weight:600; color:#5DD9C2;">{r['Margem']:.1%}</div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:11px; color:#CCC; text-transform:uppercase;">RANK MAGIC</div>
                    <div style="font-size:15px; font-weight:600; color:#FFF;">#{int(r['MagicRank'])}</div>
                </div>
            </div>
            {sim_html}
        </div>
        """, unsafe_allow_html=True)
