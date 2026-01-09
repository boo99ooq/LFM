# --- 🏆 COPPE E PRELIMINARI ---
    elif menu == "🏆 Coppe e Preliminari":
        st.title("🏆 Coppe e Preliminari")
        # Cerchiamo tutti i file che contengono "CHAMPIONS" o "PRELIMINARI"
        files = [f for f in os.listdir('.') if ("CHAMPIONS" in f.upper() or "PRELIMINARI" in f.upper()) and f.endswith(".csv")]
        
        if files:
            camp = st.selectbox("Seleziona Competizione:", files)
            # Carichiamo il file con encoding latin1 per gestire i caratteri speciali
            df_co = pd.read_csv(camp, header=None, encoding='latin1').fillna("")
            
            # Individuiamo le posizioni delle "Giornate" nel foglio
            g_pos = []
            for r in range(len(df_co)):
                for c in range(len(df_co.columns)):
                    cell_val = str(df_co.iloc[r, c]).strip()
                    if "Giornata" in cell_val and "serie a" not in cell_val.lower():
                        g_pos.append((cell_val, r, c))
            
            if g_pos:
                sel_g = st.selectbox("Seleziona Giornata:", sorted(list(set([x[0] for x in g_pos])), key=natural_sort_key))
                
                res = []
                rip = []
                
                # Cerchiamo i match relativi alla giornata selezionata
                for label, r, c in [x for x in g_pos if x[0] == sel_g]:
                    # Analizziamo le righe successive alla scritta "Giornata"
                    # Di solito i match sono nelle 15 righe successive
                    for i in range(1, 16):
                        if r+i < len(df_co):
                            row = df_co.iloc[r+i]
                            
                            # Se incontriamo un'altra "Giornata", fermiamo la ricerca per questo blocco
                            if "Giornata" in str(row[c]): break
                            
                            # Logica per gestire i riposi
                            if "Riposa" in str(row).get(c, "") or "Riposa" in str(row).get(c+1, ""):
                                nome_rip = str(row[c] if "Riposa" in str(row[c]) else row[c+1]).replace("Riposa", "").strip()
                                if nome_rip: rip.append(nome_rip)
                                continue

                            # Identificazione Casa e Trasferta (adattato al tuo CSV)
                            # Nel tuo file Fase 3, la squadra casa è in colonna C+1, trasferta in C+4
                            try:
                                h = str(row[c+1]).strip()
                                a = str(row[c+4]).strip()
                                
                                # Verifichiamo che non siano celle vuote o metadati
                                if h and h != "nan" and a and a != "nan" and len(h) > 2:
                                    cap_h = df_stadi[df_stadi['Squadra']==h]['Stadio'].values[0] if h in df_stadi['Squadra'].values else 0
                                    cap_a = df_stadi[df_stadi['Squadra']==a]['Stadio'].values[0] if a in df_stadi['Squadra'].values else 0
                                    
                                    bh, _ = calculate_stadium_bonus(cap_h)
                                    _, ba = calculate_stadium_bonus(cap_a)
                                    
                                    res.append({
                                        "Girone": str(row[c]).strip(),
                                        "Match": f"{h} vs {a}",
                                        "Bonus Casa": f"+{bh}",
                                        "Bonus Fuori": f"+{ba}"
                                    })
                            except:
                                continue
                
                if res:
                    st.table(pd.DataFrame(res))
                else:
                    st.warning("Nessun match trovato per questa giornata. Verifica la struttura del file.")
                    
                if rip:
                    st.info("☕ **Riposano:** " + ", ".join(sorted(list(set(rip)))))
            else:
                st.error("Non ho trovato scritte 'Giornata' nel file. Controlla il formato.")
        else:
            st.info("Carica un file CSV che contenga 'CHAMPIONS' o 'PRELIMINARI' nel nome per visualizzare i dati.")
