import streamlit as st
import pandas as pd
import os
from datetime import datetime
from io import BytesIO

# --- CONFIGURAZIONE PDF ---
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    PDF_OK = True
except ImportError:
    PDF_OK = False

# --- COSTANTI ---
FILE_STAFF = 'Housekeeping_DB - Staff.csv'
FILE_CONFIG = 'config_tempi.csv'
LISTA_HOTEL = [
    "Hotel Castello", "Hotel Castello Garden", "Hotel Castello 4 Piano", 
    "Cala del Forte", "Le Dune", "Villa del Parco", "Hotel Pineta", 
    "Bouganville", "Le Palme", "Il Borgo", "Le Ville", "Spazi Comuni"
]

# --- 1. LOGICA DATI ---

def load_data():
    if os.path.exists(FILE_STAFF):
        df = pd.read_csv(FILE_STAFF)
        df.columns = [c.strip() for c in df.columns]
        cols_default = {
            'Part_Time': 0, 'Jolly': 0, 'Pendolare': 0, 'Riposo_Pref': '',
            'Viaggia_Con': '', 'Lavora_Bene_Con': 'Nessuna', 'Zone_Padronanza': '',
            'Professionalita': 5, 'Esperienza': 5, 'Tenuta_Fisica': 5, 
            'Disponibilita': 5, 'Empatia': 5, 'Capacita_Guida': 5
        }
        for col, val in cols_default.items():
            if col not in df.columns: df[col] = val
        df['Nome'] = df['Nome'].astype(str).str.strip()
        return df.fillna("")
    return pd.DataFrame()

def save_data(df):
    df.to_csv(FILE_STAFF, index=False)

def get_rating_bar(row):
    try:
        if 'overnante' in str(row.get('Ruolo', '')).lower(): return "⭐ (Coord.)"
        v = (pd.to_numeric(row.get('Professionalita', 5))*0.25 + pd.to_numeric(row.get('Esperienza', 5))*0.20 + 
             pd.to_numeric(row.get('Tenuta_Fisica', 5))*0.20 + pd.to_numeric(row.get('Disponibilita', 5))*0.15)
        voto = round((v/2)*2)/2
        return "🟩"*int(voto) + ("🟨" if (voto%1)>=0.5 else "")
    except: return "⬜"*5

# --- 2. LOGICA PDF ---

def genera_pdf_planning(data_str, schieramento, assenti):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4
    p.setFont("Helvetica-Bold", 18); p.drawString(50, h-50, f"PLANNING - {data_str}")
    p.line(50, h-60, 540, h-60); y = h-85
    if assenti:
        p.setFont("Helvetica-Bold", 10); p.setFillColorRGB(0.7, 0, 0)
        p.drawString(50, y, f"🛌 ASSENTI: {', '.join(assenti)}")
        y -= 25; p.setFillColorRGB(0,0,0)
    for res in schieramento:
        if y < 100: p.showPage(); y = h-70
        p.setFont("Helvetica-Bold", 12); p.drawString(50, y, f"ZONA: {res['Hotel'].upper()}")
        y -= 15; p.setFont("Helvetica", 10); p.drawString(60, y, f"Team: {res['Team']}")
        y -= 25
    p.save(); buffer.seek(0)
    return buffer

# --- 3. SEZIONI INTERFACCIA ---

def sezione_staff(df):
    nomi_db = sorted(df['Nome'].unique().tolist()) if not df.empty else []
    sel_n = st.selectbox("Modifica collaboratrice:", ["--- NUOVA ---"] + nomi_db)
    curr = df[df['Nome'] == sel_n].iloc[0] if sel_n != "--- NUOVA ---" else None
    
    with st.form("form_staff"):
        c1, c2, c3 = st.columns(3)
        f_nome = c1.text_input("Nome", value=str(curr['Nome']) if curr is not None else "")
        f_ruolo = c2.selectbox("Ruolo", ["Cameriera", "Governante"], index=1 if curr and "overnante" in str(curr['Ruolo']).lower() else 0)
        f_padro = c3.multiselect("Zone", LISTA_HOTEL, default=[z.strip() for z in str(curr['Zone_Padronanza']).split(",") if z.strip() in LISTA_HOTEL] if curr else [])
        
        st.divider()
        # Qui puoi aggiungere gli slider e i checkbox come nel tuo codice originale
        
        if st.form_submit_button("💾 SALVA"):
            # Logica di salvataggio (concat e save_data)
            st.success("Salvato!")
            st.rerun()

def sezione_planning(df):
    c_d, c_a = st.columns([1, 2])
    data_p = c_d.date_input("Data:", datetime.now())
    assenti = c_a.multiselect("🛌 Assenti:", sorted(df['Nome'].tolist()) if not df.empty else [])
    
    # Input carichi hotel
    cur_inp = {}
    for h in LISTA_HOTEL:
        cols = st.columns([2, 1, 1, 1, 1, 1, 1])
        cols[0].write(f"**{h}**")
        cur_inp[h] = { "AI": cols[1].number_input("AI", 0, 100, 0, key=f"p_ai_{h}", label_visibility="collapsed") }
        # ... aggiungi gli altri input (FI, AG, ecc) qui

    if st.button("🚀 GENERA", use_container_width=True):
        # Inserisci qui il tuo algoritmo di calcolo fabbisogno
        st.session_state['res_v_fin'] = [{"Hotel": "Esempio", "Team": "Nome 1, Nome 2", "Info": "G:1 | Cam:2", "Req": 15.0}]
        st.rerun()

# --- 4. MAIN ---

def main():
    st.set_page_config(page_title="Forte Village Housekeeping", layout="wide")
    df = load_data()
    
    t_dash, t_staff, t_tempi, t_plan = st.tabs(["🏆 Dashboard", "👥 Staff", "⚙️ Tempi", "🚀 Planning"])
    
    with t_dash:
        if not df.empty:
            df_v = df.copy()
            df_v['Rating'] = df_v.apply(get_rating_bar, axis=1)
            st.dataframe(df_v[['Nome', 'Ruolo', 'Rating', 'Zone_Padronanza']], use_container_width=True)
            
    with t_staff:
        sezione_staff(df)
        
    with t_plan:
        sezione_planning(df)

if __name__ == "__main__":
    main()
