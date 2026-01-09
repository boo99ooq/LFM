import streamlit as st
import pandas as pd

st.set_page_config(page_title="LFM Dashboard", layout="wide", page_icon="⚖️")

# --- 1. CARICAMENTO DATI ---
@st.cache_data
def load_static_data():
    for enc in ['latin1', 'cp1252', 'utf-8']:
        try:
            df_rose = pd.read_csv('fantamanager-2021-rosters.csv', header=None, skiprows=1, encoding=enc)
            df_rose.columns = ['Squadra_LFM', 'Id', 'Prezzo_Asta']
            df_quot = pd.read_csv('quot.csv', encoding=enc)
            df_rose['Id'] = pd.to_numeric(df_rose['Id'], errors='coerce')
            df_quot['Id'] = pd.to_numeric(df_quot['Id'], errors='coerce')
            df_rose = df_rose.dropna(subset=['Id'])
            df = pd.merge(df_rose, df_quot, on='Id', how='left')
            df['Nome'] = df['Nome'].fillna("ID: " + df['Id'].astype(int, errors='ignore').astype(str))
            df['Qt.I'] = pd.to_numeric(df['Qt.I'], errors='coerce').fillna(0)
            df['FVM'] = pd.to_numeric(df['FVM'], errors='coerce').fillna(0)
            df['Rimborso'] = df['FVM'] + (df['Qt.I'] / 2)
            df['Squadra_LFM'] = df['Squadra_LFM'].str.strip()
            return df
        except: continue
    return None

# --- 2. GESTIONE SESSIONE ---
if 'refunded_ids' not in st.session_state:
    try:
        db_p = pd.read_csv('database_lfm.csv')
        st.session_state.refunded_ids = set(db_p[db_p['Rimborsato'] == True]['Id'].tolist())
    except: st.session_state.refunded_ids = set()

if 'df_leghe_full' not in st.session_state:
    try:
        df_temp = pd.read_csv('leghe.csv', encoding='latin1')
        df_temp['Squadra'] = df_temp['Squadra'].str.strip()
        df_temp['Lega'] = df_temp['Lega'].str.strip()
        df_temp['Crediti'] = pd.to_numeric(df_temp['Crediti'], errors='coerce').fillna(0)
        st.session_state.df_leghe_full = df_temp
    except:
        df_base_init = load_static_data()
        if df_base_init is not None:
            squadre = sorted(df_base_init['Squadra_LFM'].unique())
            st.session_state.df_leghe_full = pd.DataFrame({'Squadra': squadre, 'Lega': 'Da Assegnare', 'Crediti': 0})

# --- 3. UNIFICAZIONE FIORENTINA ---
def fix_fiorentina(df_leghe):
    df = df_leghe.copy()
    df.loc[df['Lega'].str.contains("Serie A", case=False, na=False), 'Lega'] = "LEGA A"
    df.loc[df['Squadra'].str.contains("Fiorentina", case=False, na=False), 'Lega'] = "LEGA A"
    return df

st.session_state.df_leghe_full = fix_fiorentina(st.session_state.df_leghe_full)

# --- 4. LOGICA DASHBOARD ---
df_static = load_static_data()
if df_static is not None:
    df_base = pd.merge(df_static, st.session_state.df_leghe_full, left_on='Squadra_LFM', right_on='Squadra', how='left')
    df_base['Rimborsato'] = df_base['Id'].isin(st.session_state.refunded_ids)

    st.sidebar.title("LFM Admin")
    menu = st.sidebar.radio("Vai a:", ["🏠 Dashboard", "🔍 Spunta Giocatori", "⚙️ Gestione Squadre"])

    if menu == "🏠 Dashboard":
        st.title("🏠 Situazione Crediti per Squadra")
        
        leghe_valide = sorted([str(l) for l in df_base['Lega'].unique() if pd.notna(l) and str(l) != 'nan'])
        
        # LAYOUT 2x2
        cols_container = st.columns(2)
        
        for i, nome_lega in enumerate(leghe_valide):
            with cols_container[i % 2]:
                st.markdown(f"## 🏆 {nome_lega}")
                df_l = df_base[df_base['Lega'] == nome_lega]
                
                # Dati rimborsi
                df_rimb_active = df_l[df_l['Rimborsato'] == True]
                res_rimborsi = df_rimb_active.groupby('Squadra_LFM')['Rimborso'].sum().reset_index()
                res_nomi = df_rimb_active.groupby('Squadra_LFM')['Nome'].apply(lambda x: ", ".join(x)).reset_index()
                res_nomi.columns = ['Squadra_LFM', 'Dettaglio']
                
                df_crediti = df_l[['Squadra_LFM', 'Crediti']].drop_duplicates()
                
                tabella = pd.merge(df_crediti, res_rimborsi, on='Squadra_LFM', how='left').fillna(0)
                tabella = pd.merge(tabella, res_nomi, on='Squadra_LFM', how='left').fillna("")
                tabella['Totale'] = tabella['Crediti'] + tabella['Rimborso']
                tabella = tabella.sort_values(by='Squadra_LFM')

                for _, sq in tabella.iterrows():
                    with st.container(border=True):
                        # NOME E TOTALE affiancati con lo stesso font (H4)
                        st.markdown(f"#### {sq['Squadra_LFM']} — {int(sq['Totale'])} cr")
                        
                        # Voci in chiaro senza abbreviazioni
                        col_a, col_b = st.columns(2)
                        col_a.write(f"**Crediti Residui:** {int(sq['Crediti'])}")
                        col_b.write(f"**Rimborsi Ottenuti:** {int(sq['Rimborso'])}")
                        
                        if sq['Dettaglio']:
                            st.caption(f"📝 {sq['Dettaglio']}")
                        else:
                            st.caption("Nessun rimborso attivo")
                st.divider()

    elif menu == "🔍 Spunta Giocatori":
        st.title("🔍 Gestione Svincoli")
        cerca = st.text_input("Cerca nome giocatore:")
        df_display = df_base.drop_duplicates('Id').copy()
        if cerca:
            df_filtered = df_display[df_display['Nome'].str.contains(cerca, case=False, na=False)]
        else:
            df_filtered = df_display.head(5)
        
        df_edit_view = df_filtered[['Rimborsato', 'Nome', 'R', 'Qt.I', 'FVM', 'Rimborso', 'Id']].copy()
        for col in ['Qt.I', 'FVM', 'Rimborso']:
            df_edit_view[col] = df_edit_view[col].apply(lambda x: int(x) if x == int(x) else x)

        res_editor = st.data_editor(df_edit_view, column_config={"Rimborsato": st.column_config.CheckboxColumn("Svincola"), "Id": None}, use_container_width=True)
        if st.button("💾 Applica Modifiche"):
            for _, row in res_editor.iterrows():
                if row['Rimborsato']: st.session_state.refunded_ids.add(row['Id'])
                else: st.session_state.refunded_ids.discard(row['Id'])
            st.success("Fatto!")
            st.rerun()

        st.divider()
        st.subheader("📋 Giocatori Svincolati")
        df_svincolati = df_base[df_base['Rimborsato'] == True].drop_duplicates('Id').copy()
        if not df_svincolati.empty:
            for col in ['Qt.I', 'FVM', 'Rimborso']:
                df_svincolati[col] = df_svincolati[col].apply(lambda x: int(x) if x == int(x) else x)
            st.dataframe(df_svincolati[['Nome', 'R', 'Qt.I', 'FVM', 'Rimborso']], hide_index=True)

    elif menu == "⚙️ Gestione Squadre":
        st.title("⚙️ Gestione Leghe e Crediti")
        opzioni_lega = ["Tutte"] + sorted([str(l) for l in st.session_state.df_leghe_full['Lega'].unique() if pd.notna(l)])
        lega_selezionata = st.selectbox("Filtra per Lega:", opzioni_lega)
        df_to_edit = st.session_state.df_leghe_full if lega_selezionata == "Tutte" else st.session_state.df_leghe_full[st.session_state.df_leghe_full['Lega'] == lega_selezionata]
        edited_view = st.data_editor(df_to_edit, use_container_width=True, num_rows="fixed")
        if st.button("Applica Modifiche"):
            temp_df = st.session_state.df_leghe_full.copy().set_index('Squadra')
            temp_df.update(edited_view.set_index('Squadra'))
            st.session_state.df_leghe_full = temp_df.reset_index()
            st.session_state.df_leghe_full = fix_fiorentina(st.session_state.df_leghe_full)
            st.success("Dati aggiornati!")
            st.rerun()
        st.download_button("📥 Scarica leghe.csv", st.session_state.df_leghe_full.to_csv(index=False).encode('utf-8'), "leghe.csv")
        df_save_rimborsi = pd.DataFrame({'Id': list(st.session_state.refunded_ids), 'Rimborsato': True})
        st.download_button("📥 Scarica database_lfm.csv", df_save_rimborsi.to_csv(index=False).encode('utf-8'), "database_lfm.csv")

else: st.error("Errore caricamento file.")
