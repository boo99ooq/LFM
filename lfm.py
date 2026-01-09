import streamlit as st
import pandas as pd

# 1. Configurazione della pagina (deve essere il primo comando Streamlit)
st.set_page_config(page_title="LFM Manager League", layout="wide", page_icon="⚽")

# 2. Funzione per caricare e unire i dati con gestione errori codifica
@st.cache_data
def load_data():
    # Proviamo diverse codifiche per evitare l'errore 'utf-8' codec can't decode
    encodings = ['latin1', 'cp1252', 'utf-8']
    
    df_rose = None
    df_quot = None

    # Caricamento Rose
    for enc in encodings:
        try:
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            break
        except Exception:
            continue

    # Caricamento Quotazioni
    for enc in encodings:
        try:
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            break
        except Exception:
            continue

    if df_rose is not None and df_quot is not None:
        # Pulizia e Unione
        df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
        df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
        df_merged = pd.merge(df_rose, df_quot, on='Id', how='inner')
        return df_merged
    else:
        return None

# 3. Interfaccia Principale
st.title("⚽ LFM - Manager League")
st.write("Strumento di ricerca e calcolo valori rose.")

try:
    df = load_data()

    if df is not None:
        # Sidebar per navigazione
        st.sidebar.header("Filtri")
        modalita = st.sidebar.radio("Scegli visualizzazione:", ["Cerca Giocatore", "Analisi Squadra"])

        if modalita == "Cerca Giocatore":
            st.header("🔍 Cerca un calciatore")
            nome_ricerca = st.text_input("Inserisci il nome (es: Lautaro, Dybala...):")
            
            if nome_ricerca:
                risultati = df[df['Nome'].str.contains(nome_ricerca, case=False, na=False)]
                if not risultati.empty:
                    st.dataframe(risultati[['Nome', 'R', 'Squadra_LFM', 'Prezzo_Asta', 'Qt.I', 'FVM']], use_container_width=True)
                else:
                    st.warning("Nessun giocatore trovato.")

        elif modalita == "Analisi Squadra":
            st.header("📋 Rose della Lega")
            lista_squadre = sorted(df['Squadra_LFM'].unique())
            scelta_squadra = st.selectbox("Seleziona una squadra:", lista_squadre)
            
            if scelta_squadra:
                df_squadra = df[df['Squadra_LFM'] == scelta_squadra]
                
                # Metriche riassuntive
                c1, c2, c3 = st.columns(3)
                c1.metric("Giocatori in rosa", len(df_squadra))
                c2.metric("Spesa Totale Asta", f"{int(df_squadra['Prezzo_Asta'].sum())} cr")
                c3.metric("Valore FVM Totale", f"{int(df_squadra['FVM'].sum())} cr")
                
                st.table(df_squadra[['Nome', 'R', 'Prezzo_Asta', 'Qt.I', 'FVM']])
    else:
        st.error("Errore: Non è stato possibile caricare i file CSV. Controlla che i nomi siano corretti nella repository.")

except Exception as e:
    st.error(f"Si è verificato un errore imprevisto: {e}")
