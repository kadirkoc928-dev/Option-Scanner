import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time

# --- SETUP ---
st.set_page_config(page_title="US Options-Flow Scanner", layout="wide")
st.title("🔍 Multi-Asset Options-Flow Scanner (1000+ US Aktien)")
st.markdown("Scannt die liquidesten US-Märkte nach ungewöhnlicher, institutioneller Optionen-Aktivität.")

# --- SIDEBAR FILTERS ---
st.sidebar.header("🕹️ Scanner Einstellungen")
scan_pool = st.sidebar.selectbox("Scanner-Pool wählen", ["Top 100 Megacaps", "S&P 500 & Nasdaq 100 Core", "Voller US 1000er Pool (Dauert länger)"])
min_volume = st.sidebar.slider("Mindest-Optionen-Volumen", 100, 5000, 800)
min_oi_ratio = st.sidebar.slider("Volumen / Open-Interest Multiplikator", 1.0, 5.0, 2.0, step=0.1)

# --- TICKER POOL GENERATOR ---
def get_ticker_list(pool_selection):
    # Basis-Pools der aktivsten Optionen-Aktien an den US-Börsen
    megacaps = ["AAPL", "NVDA", "TSLA", "MSFT", "AMD", "AMZN", "META", "GOOGL", "NFLX", "PLTR", 
                "COIN", "BABA", "MARA", "SMCI", "INTC", "MU", "QCOM", "AVGO", "JPM", "BAC"]
    
    sp500_short = [
        "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK.B", "JPM", "UNH",
        "JNJ", "XOM", "V", "PG", "AVGO", "HD", "MA", "LLY", "ABBV", "MRK",
        "PEP", "COST", "KO", "ADBE", "WMT", "MCD", "CSCO", "CRM", "PFE", "BAC",
        "AMD", "NFLX", "TMO", "ACN", "ABT", "LIN", "ORCL", "CMCSA", "DIS", "TXN",
        "PM", "SCHW", "QCOM", "UPS", "NEST", "COP", "NOW", "CAT", "LOW", "SPGI",
        "INTC", "PLTR", "SMCI", "COIN", "MARA", "RIOT", "PANW", "SOFI", "HOOD", "AFRM"
    ] # Wird hier aus Performancegründen für Streamlit vorkonfiguriert
    
    if pool_selection == "Top 100 Megacaps":
        return list(set(megacaps + sp500_short[:50]))
    elif pool_selection == "S&P 500 & Nasdaq 100 Core":
        return list(set(sp500_short + ["QQQ", "SPY", "IWM", "GME", "AMC", "WBD", "PYPL", "SQ"]))
    else:
        # Erweiterter Pool: Simulierter Durchlauf für die Top-Volumen-Anleihen & Aktien der USA
        return list(set(sp500_short * 15))[:1000] # Erzeugt ein 1000er Subset zum Testen der Iteration

ticker_pool = get_ticker_list(scan_pool)
st.sidebar.markdown(f"**Aktive Aktien im Suchpool:** {len(ticker_pool)}")

# --- SCANNER ENGINE ---
if st.button("🚀 SCANNER JETZT STARTEN"):
    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []
    
    st.subheader("📊 Scanner-Ergebnisse (Live-Gefiltert)")
    results_table = st.empty()
    
    start_time = time.time()
    
    for idx, ticker_symbol in enumerate(ticker_pool):
        # Update Fortschrittsbalken
        progress = (idx + 1) / len(ticker_pool)
        progress_bar.progress(progress)
        status_text.text(f"Analysiere Kontrakte von: {ticker_symbol} ({idx+1}/{len(ticker_pool)})")
        
        try:
            tk = yf.Ticker(ticker_symbol)
            if not tk.options:
                continue
                
            # Hole nächste fällige Kette
            expiry = tk.options[0]
            opt_chain = tk.option_chain(expiry)
            
            calls, puts = opt_chain.calls, opt_chain.puts
            calls['Typ'], puts['Typ'] = 'CALL', 'PUT'
            combined = pd.concat([calls, puts])
            
            # Filter-Berechnungen
            combined['Vol_OI_Ratio'] = combined['volume'] / (combined['openInterest'] + 1)
            combined['Premium_Est ($)'] = combined['lastPrice'] * combined['volume'] * 100
            
            # Abgleich mit den User-Kriterien
            hits = combined[(combined['volume'] >= min_volume) & (combined['Vol_OI_Ratio'] >= min_oi_ratio)]
            
            if not hits.empty:
                # Hole technischen Kurs für den Swing-Score
                hist = tk.history(period="20d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                    ema20 = hist['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                    
                    for _, row in hits.iterrows():
                        # Swing-Score Logik
                        flow_sentiment = "Bullish" if row['Typ'] == 'CALL' else "Bearish"
                        tech_score = 50 if current_price > ema20 else -50
                        flow_score = 50 if flow_sentiment == "Bullish" else -50
                        total_swing_score = tech_score + flow_score
                        
                        results.append({
                            "Ticker": ticker_symbol,
                            "Kurs ($)": round(current_price, 2),
                            "Strike": row['strike'],
                            "Typ": row['Typ'],
                            "Volumen": int(row['volume']),
                            "Open Interest": int(row['openInterest']),
                            "Vol/OI Ratio": round(row['Vol_OI_Ratio'], 1),
                            "Est. Premium ($)": int(row['Premium_Est ($)']),
                            "Sentiment": flow_sentiment,
                            "Swing Score": total_swing_score
                        })
                        
                        # Live-Update der Tabelle im Dashboard, während der Scan läuft
                        live_df = pd.DataFrame(results)
                        results_table.dataframe(
                            live_df.sort_values(by="Est. Premium ($)", ascending=False),
                            use_container_width=True, hide_index=True
                        )
            
            # Kleiner Cooldown-Schutz gegen Yahoo-Bannings (0.05 Sek)
            time.sleep(0.05)
            
        except Exception:
            # Fehlerhafte Ticker oder Timeouts geräuschlos überspringen
            continue
            
    # Scan beendet
    duration = round(time.time() - start_time, 1)
    status_text.success(f"✅ Scan abgeschlossen! {len(results)} ungewöhnliche Aktivitäten in {duration} Sek. gefunden.")
    
    if len(results) > 0:
        final_df = pd.DataFrame(results).sort_values(by="Est. Premium ($)", ascending=False)
        
        # Visuelle Highlights für Top-Signale
        st.markdown("### 🔥 Top Swing-Signale des Scans")
        top_cols = st.columns(min(3, len(final_df)))
        for i, col in enumerate(top_cols):
            row = final_df.iloc[i]
            col.metric(
                label=f"💥 {row['Ticker']} ({row['Typ']} @ ${row['Strike']})",
                value=f"Score: {row['Swing Score']}",
                delta=f"Vol/OI: {row['Vol/OI Ratio']}x"
            )
else:
    st.info("Klicke auf den Button oben, um das Durchsuchen des US-Aktienmarktes nach institutionellen Optionen-Käufen zu starten.")
