import streamlit as st
import pandas as pd

# 1. IMPOSTAZIONI DELLA PAGINA
st.set_page_config(page_title="LFM - Calcolo Rimborsi", layout="wide", page_icon="💰")

# 2. FUNZIONI DI CARICAMENTO DATI
@st.cache_data
def carica_dati_gioco():
    for enc in ['latin1', 'cp1252', 'utf-8']:
        try:
            # Caricamento Rose
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            
            # Caricamento Quotazioni
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            
            # Pulizia e conversione ID
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            df_rose = df_rose.dropna(subset=['Id'])
            
            # Unione dei dati (Left Join)
            df_merged = pd.merge(df_rose, df_quot, on='Id', how='left')
            
            # Gestione nomi mancanti
            df_merged['Nome'] = df_merged['Nome'].fillna("Fuori Lista (ID: " + df_merged['Id'].astype(str).str.replace('.0','', regex=False) + ")")
            df_merged['R'] = df_merged['R'].fillna("-")
            df_merged['Qt.I'] = df_merged['Qt.I'].fillna(0)
            df_merged['FVM'] = df_merged['FVM'].fillna(0)
            
            # --- CALCOLO RIMBORSO ---
            # Formula: FVM + (Quotazione Iniziale / 2)
            df_merged['Rimborso'] = df_merged['FVM'] + (df_merged['Qt.I'] / 2)
            
            return df_merged
        except:
            continue
    return None

def carica_mappa_leghe(nomi_squadre):
    try:
        return pd.read_csv('leghe.csv', encoding='latin1')
    except:
        return pd.DataFrame({'Squadra': nomi_squadre, 'Lega': 'Da Assegnare'})

# --- ESECUZIONE APP ---
dati_fanta = carica_dati_gioco()

if dati_fanta is not None:
    squadre_presenti = sorted(dati_fanta['Squadra_LFM'].unique())
    mappa_leghe = carica_mappa_leghe(squadre_presenti)

    st.sidebar.title("⚽ LFM Manager")
    modalita = st.sidebar.radio("Naviga tra:", ["App Fantacalcio", "⚙️ Configura Leghe"])

    if modalita == "⚙️ Configura Leghe":
        st.title("⚙️ Organizzazione Leghe")
        df_editor = st.data_editor(mappa_leghe, use_container_width=True, num_rows="fixed")
        csv_data = df_editor.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Scarica leghe.csv aggiornato", data=csv_data, file_name='leghe.csv', mime='text/csv')

    else:
        # Unione Lega + Dati
        df_finale = pd.merge(dati_fanta, mappa_leghe, left_on='Squadra_LFM', right_on='Squadra', how='left')

        st.title("🔍 Ricerca e Calcolo Rimborsi")

        # Filtro Lega
        lista_leghe = ["Tutte"] + sorted(list(df_finale['Lega'].unique().astype(str)))
        filtro_lega = st.sidebar.selectbox("Filtra per Lega:", lista_leghe)

        df_filtrato = df_finale if filtro_lega == "Tutte" else df_finale[df_finale['Lega'] == filtro_lega]

        sub_tab = st.radio("Cosa cerchi?", ["Giocatore Singolo", "Rosa Completa"], horizontal=True)

        if sub_tab == "Giocatore Singolo":
            cerca = st.text_input("Inserisci nome del giocatore:")
            if cerca:
                ris = df_filtrato[df_filtrato['Nome'].str.contains(cerca, case=False, na=False)]
                if not ris.empty:
                    # Visualizzazione con Colonna Rimborso
                    st.dataframe(
                        ris[['Nome', 'R', 'Squadra_LFM', 'Lega', 'Qt.I', 'FVM', 'Rimborso']].sort_values(by='Nome'), 
                        use_container_width=True
                    )
                    st.info("💡 Il calcolo del rimborso è basato su: FVM + (Qt.I / 2)")
                else:
                    st.warning("Nessun giocatore trovato.")
        
        else:
            squadra_sel = st.selectbox("Seleziona Squadra LFM:", sorted(df_filtrato['Squadra_LFM'].unique()))
            if squadra_sel:
                res_sq = df_filtrato[df_filtrato['Squadra_LFM'] == squadra_sel]
                
                # Identifichiamo i giocatori potenzialmente "ceduti" (quelli con Qt.I e FVM che hai impostato o quelli Fuori Lista)
                # In questa visualizzazione mostriamo il rimborso per tutti, facilitando il calcolo manuale
                
                # Statistiche veloci
                m1, m2, m3 = st.columns(3)
                m1.metric("Spesa Asta Totale", f"{int(res_sq['Prezzo_Asta'].sum())} cr")
                m2.metric("Valore FVM Totale", f"{int(res_sq['FVM'].sum())} cr")
                
                # Calcoliamo il rimborso totale potenziale per la squadra
                rimborso_totale = res_sq['Rimborso'].sum()
                m3.metric("Valore Rimborso Totale", f"{rimborso_totale} cr", delta_color="normal")
                
                st.write("### Dettaglio Rosa")
                st.table(res_sq[['Nome', 'R', 'Prezzo_Asta', 'Qt.I', 'FVM', 'Rimborso']].sort_values(by='R'))

else:
    st.error("Errore nel caricamento dei file.")
