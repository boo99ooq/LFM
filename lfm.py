import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM Admin Pro", layout="wide", page_icon="⚖️")

# --- 1. CARICAMENTO E PULIZIA DATI ---
@st.cache_data
def load_data():
    for enc in ['latin1', 'cp1252', 'utf-8']:
        try:
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            df_rose = df_rose.dropna(subset=['Id'])
            
            df = pd.merge(df_rose, df_quot, on='Id', how='left')
            
            # Gestione Leghe e Crediti Manuali
            try: 
                leghe = pd.read_csv('leghe.csv', encoding=enc)
                # Assicuriamoci che esistano le colonne Squadra, Lega, Crediti
                if 'Crediti' not in leghe.columns:
                    leghe['Crediti'] = 0
                
                leghe['Squadra'] = leghe['Squadra'].str.strip()
                leghe['Lega'] = leghe['Lega'].str.strip()
                
                # Unificazione forzata Fiorentina/Serie A -> LEGA A
                leghe.loc[leghe['Lega'].str.contains("Serie A", case=False, na=False), 'Lega'] = "LEGA A"
                leghe.loc[leghe['Squadra'].str.contains("Fiorentina", case=False, na=False), 'Lega'] = "LEGA A"
                
                df['Squadra_LFM'] = df['Squadra_LFM'].str.strip()
                df = pd.merge(df, leghe[['Squadra', 'Lega', 'Crediti']], left_on='Squadra_LFM', right_on='Squadra', how='left')
            except: 
                df['Lega'] = 'Da Assegnare'
                df['Crediti'] = 0

            df['Nome'] = df['Nome'].fillna("ID: " + df['Id'].astype(int, errors='ignore').astype(str))
            df['Qt.I'] = pd.to_numeric(df['Qt.I'], errors='coerce').fillna(0)
            df['FVM'] = pd.to_numeric(df['FVM'], errors='coerce').fillna(0)
            df['Rimborso'] = df['FVM'] + (df['Qt.I'] / 2)
            
            return df
        except: continue
    return None

# --- 2. STATO RIMBORSI ---
if 'refunded_ids' not in st.session_state:
    try:
        db_p = pd.read_csv('database_lfm.csv')
        st.session_state.refunded_ids = set(db_p[db_p['Rimborsato'] == True]['Id'].tolist())
    except:
        st.session_state.refunded_ids = set()

# --- 3. INTERFACCIA ---
df_base = load_data()

if df_base is not None:
    df_base['Rimborsato'] = df_base['Id'].isin(st.session_state.refunded_ids)

    st.sidebar.title("LFM Admin")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🔍 Spunta Giocatori", "⚙️ Gestione Squadre"])

    if menu == "🏠 Dashboard":
        st.title("🏠 Riepilogo Leghe")
        
        leghe_valide = sorted([l for l in df_base['Lega'].unique() if pd.notna(l) and l != 'nan'])
        
        cols = st.columns(2)
        for i, nome_lega in enumerate(leghe_valide):
            with cols[i % 2]:
                with st.container(border=True):
                    st.subheader(f"🏆 {nome_lega}")
                    df_l = df_base[df_base['Lega'] == nome_lega]
                    
                    # Calcolo rimborsi spuntati
                    res_rimborsi = df_l[df_l['Rimborsato'] == True].groupby('Squadra_LFM')['Rimborso'].sum().reset_index()
                    
                    # Prendiamo i crediti manuali (una riga per squadra)
                    df_crediti = df_l[['Squadra_LFM', 'Crediti']].drop_duplicates()
                    
                    tabella = pd.merge(df_crediti, res_rimborsi, on='Squadra_LFM', how='left').fillna(0)
                    tabella.columns = ['Squadra', 'Crediti Manuali', 'Rimborsi da Erogare']
                    
                    st.table(tabella.sort_values(by='Squadra'))

    elif menu == "🔍 Spunta Giocatori":
        st.title("🔍 Ricerca e Svincolo")
        cerca = st.text_input("Cerca nome giocatore:")
        
        df_display = df_base.drop_duplicates('Id').copy()
        if cerca:
            df_filtered = df_display[df_display['Nome'].str.contains(cerca, case=False, na=False)]
        else:
            df_filtered = df_display.head(10)

        res_editor = st.data_editor(
            df_filtered[['Rimborsato', 'Nome', 'R', 'Qt.I', 'FVM', 'Rimborso', 'Id']],
            column_config={"Rimborsato": st.column_config.CheckboxColumn("Svincola"), "Id": None},
            disabled=["Nome", "R", "Qt.I", "FVM", "Rimborso"],
            use_container_width=True
        )

        if st.button("Salva modifiche rimborsi"):
            for _, row in res_editor.iterrows():
                if row['Rimborsato']: st.session_state.refunded_ids.add(row['Id'])
                else: st.session_state.refunded_ids.discard(row['Id'])
            st.success("Dati rimborsi aggiornati!")
            st.rerun()

    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Gestione Leghe e Crediti")
        st.write("Qui puoi spostare le squadre tra le leghe e inserire i crediti residui manualmente.")
        
        # Carichiamo il file leghe.csv per l'editing
        try:
            df_leghe_edit = pd.read_csv('leghe.csv', encoding='latin1')
            if 'Crediti' not in df_leghe_edit.columns:
                df_leghe_edit['Crediti'] = 0
        except:
            squadre = sorted(df_base['Squadra_LFM'].unique())
            df_leghe_edit = pd.DataFrame({'Squadra': squadre, 'Lega': 'Da Assegnare', 'Crediti': 0})

        new_leghe = st.data_editor(df_leghe_edit, use_container_width=True, num_rows="fixed")
        
        csv_leghe = new_leghe.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Scarica leghe.csv aggiornato", csv_leghe, "leghe.csv", "text/csv")
        
        st.divider()
        st.write("### Backup Rimborsi")
        df_save_rimborsi = pd.DataFrame({'Id': list(st.session_state.refunded_ids), 'Rimborsato': True})
        st.download_button("📥 Scarica database_lfm.csv", df_save_rimborsi.to_csv(index=False).encode('utf-8'), "database_lfm.csv")

else:
    st.error("Verifica i file su GitHub.")
