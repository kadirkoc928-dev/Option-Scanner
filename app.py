import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# --- CONFIGURATION & PAGE SETUP ---
st.set_page_config(
    page_title="Kostenloses Optionen-Flow Terminal",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚡ Open-Source Options-Flow Terminal")
st.markdown("Nutzt kostenlose Markt-Daten zur Berechnung ungewöhnlicher Optionen-Aktivitäten (Smart Money)")

# --- SIDEBAR: CONTROLS ---
st.sidebar.header("🕹️ Kontrollzentrum")
ticker_input = st.sidebar.selectbox("NASDAQ Ticker wählen", ["NVDA", "AAPL", "TSLA", "MSFT", "AMD"], index=0)

st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Flow-Filter")
min_volume = st.sidebar.slider("Mindest-Handelsvolumen (Kontrakte)", 100, 5000, 500)
min_oi_ratio = st.sidebar.slider("Volumen / Open-Interest Verhältnis", 1.0, 5.0, 1.5, step=0.1)

# --- REAL-TIME OPTIONS DATA ENGINE ---
@st.cache_data(ttl=60)  # Aktualisiert die Optionen-Kette jede Minute live
def get_real_options_flow(symbol):
    try:
        ticker = yf.Ticker(symbol)
        if not ticker.options:
            return pd.DataFrame(), 0.0
            
        next_expiry = ticker.options[0] 
        opt_chain = ticker.option_chain(next_expiry)
        
        calls = opt_chain.calls
        puts = opt_chain.puts
        
        calls['Typ'] = 'CALL'
        puts['Typ'] = 'PUT'
        
        combined = pd.concat([calls, puts])
        
        # Holen des aktuellen Kurses über das Orderbuch/Letzten Schlusskurs
        hist = ticker.history(period="1d")
        if hist.empty:
            return pd.DataFrame(), 0.0
        current_price = hist['Close'].iloc[-1]
        
        # Berechnungen für den "Volumen-Flow"
        combined['Premium_Est ($)'] = combined['lastPrice'] * combined['volume'] * 100
        combined['Vol_OI_Ratio'] = combined['volume'] / (combined['openInterest'] + 1)
        
        # Filter nach "Ungewöhnlicher Aktivität" (Volumen bricht Open Interest)
        flow_filtered = combined[
            (combined['volume'] >= min_volume) & 
            (combined['Vol_OI_Ratio'] >= min_oi_ratio)
        ].copy()
        
        # Sentiment-Logik basierend auf dem Optionstyp
        flow_filtered['Sentiment'] = np.where(
            flow_filtered['Typ'] == 'CALL', 'Bullish', 'Bearish'
        )
        
        # Bereinigung für die Tabelle
        flow_filtered = flow_filtered.rename(columns={
            'strike': 'Strike',
            'volume': 'Volumen',
            'openInterest': 'Open Interest',
            'lastPrice': 'Preis'
        })
        
        return flow_filtered.sort_values(by='Premium_Est ($)', ascending=False), current_price
    except Exception as e:
        st.error(f"Fehler beim Abruf der Optionen-Kette: {e}")
        return pd.DataFrame(), 0.0

# --- EXECUTION ---
flow_data, live_price = get_real_options_flow(ticker_input)
ticker_obj = yf.Ticker(ticker_input)
hist_prices = ticker_obj.history(period="60d", interval="1d")

if not hist_prices.empty and live_price > 0:
    
    # --- CALCULATE REAL SWING SCORE ---
    if not flow_data.empty:
        bull_vol = flow_data[flow_data["Sentiment"] == "Bullish"]["Premium_Est ($)"].sum()
        bear_vol = flow_data[flow_data["Sentiment"] == "Bearish"]["Premium_Est ($)"].sum()
        total_vol = bull_vol + bear_vol
        flow_score = ((bull_vol - bear_vol) / total_vol * 100) if total_vol > 0 else 0
    else:
        flow_score = 0
    
    # Technische Komponente (EMA 20)
    ema20 = hist_prices['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
    tech_score = 100 if live_price > ema20 else -100
    
    # Kombinierter Score (50% Technik / 50% Real-Flow)
    final_score = (tech_score * 0.5) + (flow_score * 0.5)
    
    # --- UI METRICS ---
    col1, col2, col3 = st.columns(3)
    col1.metric(f"Echtzeit-Kurs {ticker_input}", f"${live_price:.2f}")
    
    score_color = "green" if final_score > 10 else ("red" if final_score < -10 else "orange")
    col2.markdown(f"### Real-Time Swing Score\n<h2 style='color:{score_color}; margin-top:-15px;'>{final_score:.1f} / 100</h2>", unsafe_allow_html=True)
    
    signal = "🚀 BULLISH FLOW EXPLOSION" if final_score > 20 else ("🩸 BEARISH PRESSURE" if final_score < -20 else "⏳ CONSOLIDATION")
    col3.markdown(f"### Signal\n**{signal}**")
    
    st.markdown("---")
    
    # --- SPLIT VIEW LAYOUT ---
    chart_col, flow_col = st.columns([3, 2])
    
    with chart_col:
        st.subheader("📈 Technische Chart-Validierung")
        fig = make_subplots(rows=1, cols=1)
        fig.add_trace(go.Candlestick(
            x=hist_prices.index, open=hist_prices['Open'], high=hist_prices['High'], low=hist_prices['Low'], close=hist_prices['Close'],
            name="Kurs"
        ))
        fig.add_trace(go.Scatter(x=hist_prices.index, y=hist_prices['Close'].ewm(span=20).mean(), mode='lines', name='EMA 20', line=dict(color='orange')))
        fig.update_layout(xaxis_rangeslider_visible=False, height=450, template="plotly_dark", margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        
    with flow_col:
        st.subheader("🚨 Ungewöhnlicher Optionen-Flow (Live)")
        st.markdown("*Gefiltert nach Kontrakten, deren heutiges Volumen das Open Interest übersteigt:*")
        
        if not flow_data.empty:
            def color_rows(val):
                return 'color: #22c55e; font-weight: bold;' if val == "Bullish" else 'color: #ef4444; font-weight: bold;'
                
            output_df = flow_data[["Strike", "Typ", "Volumen", "Open Interest", "Premium_Est ($)", "Sentiment"]]
            
            # HIER WAR DER FEHLER: .applymap() wurde durch .map() ersetzt
            styled_output = output_df.style.map(color_rows, subset=['Sentiment']).format({"Premium_Est ($)": "{:,.0f}"})
            st.dataframe(styled_output, height=400, use_container_width=True, hide_index=True)
        else:
            st.info("Aktuell keine ungewöhnlichen Optionen-Aktivitäten mit diesen Filtereinstellungen gefunden. Versuche, die Regler links etwas niedriger zu stellen.")

else:
    st.error("Fehler beim Laden der historischen Kursdaten.")
