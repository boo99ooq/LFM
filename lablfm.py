# --- 📊 RANKING FVM AGGIORNATO (Inclusi Liberi) ---
    elif menu == "📊 Ranking FVM":
        st.title("📊 Ranking FVM Globale")
        
        # Carichiamo TUTTI i giocatori dal file quotazioni per trovare i liberi
        df_all_players = df_static[['Id', 'Nome', 'R', 'FVM', 'Qt.I']].drop_duplicates('Id')
        
        c1, c2, c3 = st.columns(3)
        ruolo_filt = c1.multiselect("Filtra Ruolo:", ["P", "D", "C", "A"], default=["P", "D", "C", "A"])
        leghe_filt = c2.multiselect("Visualizza Colonne Leghe:", ORDINE_LEGHE, default=ORDINE_LEGHE)
        mostra_liberi = c3.checkbox("Mostra solo giocatori LIBERI", value=False)
        
        # Uniamo i dati delle rose con la lista completa dei giocatori
        df_rank = pd.merge(df_all_players, df_base[['Id', 'Squadra_LFM', 'Lega', 'Rimborsato_Star', 'Rimborsato_Taglio']], on='Id', how='left')
        
        if ruolo_filt:
            df_rank = df_rank[df_rank['R'].isin(ruolo_filt)]

        def format_owner(row):
            if pd.isna(row['Squadra_LFM']): return "🟢 LIBERO" # Giocatore mai acquistato
            name = row['Squadra_LFM']
            if row['Rimborsato_Star']: return f"✈️ {name}" 
            if row['Rimborsato_Taglio']: return f"✂️ {name}" 
            return name

        df_rank['Squadra_Display'] = df_rank.apply(format_owner, axis=1)
        
        # Creazione Matrice
        pivot_rank = df_rank.pivot_table(
            index=['FVM', 'Nome', 'R'], 
            columns='Lega', 
            values='Squadra_Display', 
            aggfunc=lambda x: " | ".join(str(v) for v in x if v != 'nan'),
            dropna=False # Importante per non perdere i liberi
        ).reset_index()

        # Riempie le celle vuote (dove non c'è squadra in quella lega) con "LIBERO"
        for lega in leghe_filt:
            if lega in pivot_rank.columns:
                pivot_rank[lega] = pivot_rank[lega].fillna("🟢 LIBERO")

        # Filtro per mostrare solo chi è libero ovunque
        if mostra_liberi:
            condizione = True
            for lega in leghe_filt:
                if lega in pivot_rank.columns:
                    condizione &= (pivot_rank[lega] == "🟢 LIBERO")
            pivot_rank = pivot_rank[condizione]

        pivot_rank = pivot_rank.sort_values(by='FVM', ascending=False)
        colonne_finali = ['FVM', 'Nome', 'R'] + [l for l in leghe_filt if l in pivot_rank.columns]
        
        st.dataframe(
            pivot_rank[colonne_finali],
            column_config={
                "FVM": st.column_config.NumberColumn("FVM", format="%d"),
                "R": "Ruolo",
                **{l: st.column_config.TextColumn(f"🏆 {l}") for l in ORDINE_LEGHE}
            },
            use_container_width=True,
            hide_index=True
        )
        st.info("🟢 LIBERO = Giocatore disponibile sul mercato | ✈️ = Partito | ✂️ = Tagliato")
