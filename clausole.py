# --- DASHBOARD AGGIORNATA CON NOMI EVIDENTI ---
else:
    st.title(f"🛡️ Blindaggio: {st.session_state.squadra}")
    if st.sidebar.button("Logout"):
        st.session_state.loggato = False
        st.rerun()

    df_rosters = carica_csv("fantamanager-2021-rosters.csv")
    df_quot = carica_csv("quot.csv")
    
    # Pulizia ID e Nomi
    df_rosters['Squadra_LFM'] = df_rosters['Squadra_LFM'].astype(str).str.strip()
    df_rosters['Id'] = df_rosters['Id'].astype(str).str.strip()
    df_quot['Id'] = df_quot['Id'].astype(str).str.strip()
    
    ids_miei = df_rosters[df_rosters['Squadra_LFM'] == st.session_state.squadra.strip()]['Id'].tolist()

    if not ids_miei:
        st.warning(f"Nessun giocatore trovato per {st.session_state.squadra}")
    else:
        miei_giocatori = df_quot[df_quot['Id'].isin(ids_miei)].copy()
        miei_giocatori['FVM'] = pd.to_numeric(miei_giocatori['FVM'], errors='coerce').fillna(0)
        top_3 = miei_giocatori.nlargest(3, 'FVM')

        max_crediti_rivali = df_leghe[df_leghe['Squadra'] != st.session_state.squadra]['Crediti'].max()
        
        st.write("---")
        st.subheader("Configura le tue clausole")

        tot_tasse = 0
        dati_invio = []

        # CICLO PER I 3 GIOCATORI
        for i, (_, row) in enumerate(top_3.iterrows()):
            nome, fvm = row['Nome'], int(row['FVM'])
            
            # RENDIAMO IL NOME MOLTO EVIDENTE
            with st.container():
                # Titolo Gigante con Markdown
                st.markdown(f"## {i+1}. {nome.upper()}")
                
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    clausola = st.number_input(f"Imposta Clausola (Min: {fvm})", 
                                               min_value=fvm, 
                                               value=fvm*2, 
                                               key=f"cl_{nome}")
                with col2:
                    tassa = calcola_tassa(clausola)
                    tot_tasse += tassa
                    st.metric("Tassa da pagare", f"{tassa} cr")
                
                with col3:
                    if clausola <= max_crediti_rivali:
                        st.error("🟠 VULNERABILE")
                        st.caption(f"Serve > {max_crediti_rivali}")
                    else:
                        st.success("🟢 BLINDATO")
                        st.caption("Al sicuro!")
                
                st.write("---") # Separatore tra un giocatore e l'altro
                dati_invio.append(f"{nome}:{clausola}")

        # RIEPILOGO FINALE
        spesa_netta = max(0, tot_tasse - 60)
        
        st.info(f"💡 Il Bonus Lega di 60cr copre le tue tasse fino a {tot_tasse}cr.")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Totale Tasse", f"{tot_tasse} cr")
        c2.metric("Bonus", "-60 cr")
        c3.metric("COSTO NETTO", f"{spesa_netta} cr", delta=-spesa_netta if spesa_netta > 0 else 0)

        if st.button("SALVA DEFINITIVAMENTE", type="primary", use_container_width=True):
            salva_blindato(st.session_state.squadra, ";".join(dati_invio))
            st.success(f"✅ Clausole per {st.session_state.squadra} salvate!")
            st.balloons()
