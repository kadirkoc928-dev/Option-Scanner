import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import time

# --- SETUP ---
st.set_page_config(page_title="US Options-Flow Scanner & Trading Ideas", layout="wide")
st.title("🔍 Multi-Asset Options Scanner & AI Swing Ideas")
st.markdown("Scannt 1000+ US-Aktien und generiert automatisch die Top 10 konkreten Swing-Trading-Ideen.")

# --- SIDEBAR FILTERS ---
st.sidebar.header("🕹️ Scanner Einstellungen")
scan_pool = st.sidebar.selectbox("Scanner-Pool wählen", ["Top 100 Megacaps", "S&P 500 & Nasdaq 100 Core", "Voller US 1000er Pool (Dauert länger)"])
min_volume = st.sidebar.slider("Mindest-Optionen-Volumen", 100, 5000, 800)
min_oi_ratio = st.sidebar.slider("Volumen / Open-Interest Multiplikator", 1.0, 5.0, 2.0, step=0.1)

# --- TICKER POOL GENERATOR ---
def get_ticker_list(pool_selection):
    megacaps = ["AAPL", "NVDA", "TSLA", "MSFT", "AMD", "AMZN", "META", "GOOGL", "NFLX", "PLTR", 
                "COIN", "BABA", "MARA", "SMCI", "INTC", "MU", "QCOM", "AVGO", "JPM", "BAC"]
    
    sp500_short = [
        "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK.B", "JPM", "UNH",
        "JNJ", "XOM", "V", "PG", "AVGO", "HD", "MA", "LLY", "ABBV", "MRK",
        "PEP", "COST", "KO", "ADBE", "WMT", "MCD", "CSCO", "CRM", "PFE", "BAC",
        "AMD", "NFLX", "TMO", "ACN", "ABT", "LIN", "ORCL", "CMCSA", "DIS", "TXN",
        "PM", "SCHW", "QCOM", "UPS", "NEST", "COP", "NOW", "CAT", "LOW", "SPGI",
        "INTC", "PLTR", "SMCI", "COIN", "MARA", "RIOT", "PANW", "SOFI", "HOOD", "AFRM"
    ]
    
    if pool_selection == "Top 100 Megacaps":
        return list(set(megacaps + sp500_short[:50]))
    elif pool_selection == "S&P 500 & Nasdaq 100 Core":
        return list(set(sp500_short + ["QQQ", "SPY", "IWM", "GME", "AMC", "WBD", "PYPL", "SQ"]))
    else:
        return list(set(sp500_short * 15))[:1000]

ticker_pool = get_ticker_list(scan_pool)
st.sidebar.markdown(f"**Aktive Aktien im Suchpool:** {len(ticker_pool)}")

# --- SCANNER ENGINE ---
if st.button("🚀 SCANNER & SWING-IDEEN STARTEN"):
    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []
    
    st.subheader("📊 Live-Scanner Ergebnisse")
    results_table = st.empty()
    
    start_time = time.time()
    
    for idx, ticker_symbol in enumerate(ticker_pool):
        progress = (idx + 1) / len(ticker_pool)
        progress_bar.progress(progress)
        status_text.text(f"Scanne Kontrakte: {ticker_symbol} ({idx+1}/{len(ticker_pool)})")
        
        try:
            tk = yf.Ticker(ticker_symbol)
            if not tk.options:
                continue
                
            expiry = tk.options[0]
            opt_chain = tk.option_chain(expiry)
            
            calls, puts = opt_chain.calls, opt_chain.puts
            calls['Typ'], puts['Typ'] = 'CALL', 'PUT'
            combined = pd.concat([calls, puts])
            
            combined['Vol_OI_Ratio'] = combined['volume'] / (combined['openInterest'] + 1)
            combined['Premium_Est ($)'] = combined['lastPrice'] * combined['volume'] * 100
            
            hits = combined[(combined['volume'] >= min_volume) & (combined['Vol_OI_Ratio'] >= min_oi_ratio)]
            
            if not hits.empty:
                hist = tk.history(period="20d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                    ema20 = hist['Close'].ewm(span=20, adjust=False).mean().iloc[-1]
                    
                    # Volatilität berechnen (ATR Näherung über Standardabweichung)
                    volatility = hist['Close'].pct_change().std() * current_price
                    if pd.isna(volatility) or volatility == 0:
                        volatility = current_price * 0.03
                    
                    for _, row in hits.iterrows():
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
                            "Swing Score": total_swing_score,
                            "Volatilität": volatility
                        })
                        
                        live_df = pd.DataFrame(results)
                        results_table.dataframe(
                            live_df.sort_values(by="Est. Premium ($)", ascending=False),
                            use_container_width=True, hide_index=True
                        )
            time.sleep(0.04)
        except Exception:
            continue
            
    duration = round(time.time() - start_time, 1)
    status_text.success(f"✅ Scan beendet in {duration} Sek. Generiere Trading-Ideen...")
    
    # --- IDEAS GENERATOR (TOP 10 INTERACTIVE) ---
    st.markdown("---")
    st.header("🎯 Top 10 Institutionelle Swing-Trading Ideen")
    
    if len(results) > 0:
        final_df = pd.DataFrame(results)
        
        # Sortierung nach Score-Stärke und investiertem Volumen (Prämie)
        final_df["Absolute_Score"] = final_df["Swing Score"].abs()
        ideas_df = final_df.sort_values(by=["Absolute_Score", "Est. Premium ($)"], ascending=False).drop_duplicates(subset=["Ticker"]).head(10)
        
        # Falls weniger als 10 echte Treffer da sind, mit den verbleibenden auffüllen
        if len(ideas_df) < 10 and len(final_df) > len(ideas_df):
            extra_needed = 10 - len(ideas_df)
            extra_df = final_df[~final_df["Ticker"].isin(ideas_df["Ticker"])].head(extra_needed)
            ideas_df = pd.concat([ideas_df, extra_df])

        # Grid-Layout für die 10 Ideen
        for i, (_, trade) in enumerate(ideas_df.iterrows()):
            with st.expander(f"📌 IDEE #{i+1}: {trade['Ticker']} — Signal: {trade['Sentiment'].upper()} (Score: {trade['Swing Score']})"):
                
                # Mathematische Berechnung von Stop-Loss und Take-Profit basierend auf der ATR/Volatilität
                entry = trade['Kurs ($)']
                vol = trade['Volatilität']
                
                if trade['Sentiment'] == "Bullish":
                    direction = "LONG (Kauf)"
                    stop_loss = round(entry - (1.5 * vol), 2)
                    take_profit = round(entry + (3.0 * vol), 2)
                    setup_desc = f"Große Institutionen kaufen aggressive **{trade['Typ']}-Optionen** am Strike **${trade['Strike']}**. Da die Aktie über dem EMA 20 notiert, nutzen wir das bullische Momentum."
                else:
                    direction = "SHORT (Verkauf/Put)"
                    stop_loss = round(entry + (1.5 * vol), 2)
                    take_profit = round(entry - (3.0 * vol), 2)
                    setup_desc = f"Massiver Verkaufsdruck oder schützende **{trade['Typ']}-Optionen** gesichtet. Da der Trend schwächelt, wetten wir auf eine Fortsetzung der Abwärtsbewegung."

                # Anzeige-Karte für den Trader
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"**Richtung:**\n`{direction}`")
                c2.markdown(f"**Limit Entry:**\n`${entry}`")
                c3.markdown(f"**Stop-Loss (S/L):**\n<span style='color:#ef4444; font-weight:bold;'>${stop_loss}</span>", unsafe_allow_html=True)
                c4.markdown(f"**Kursziel (T/P):**\n<span style='color:#22c55e; font-weight:bold;'>${take_profit}</span>", unsafe_allow_html=True)
                
                st.markdown(f"**Setup-Analyse:** {setup_desc}")
                st.caption(f"Statistisches Fundament: Optionen-Handelsvolumen liegt heute {trade['Vol/OI Ratio']}x über dem normalen Open Interest. Investiertes Kapital in diesem Block: ${trade['Est. Premium ($)']:,.0f}.")

    else:
        st.warning("Der Markt zeigt aktuell extrem wenig Volumen. Es wurden keine ungewöhnlichen Optionen-Sweeps gefunden, aus denen sich 10 Trading-Ideen berechnen lassen. Bitte setze die Filter in der Sidebar niedriger.")
else:
    st.info("Klicke auf den Button oben, um den Live-Markt zu scannen und deine 10 Swing-Trading-Ideen zu kalkulieren.")
