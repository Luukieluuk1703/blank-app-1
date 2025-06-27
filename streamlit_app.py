import streamlit as st
import pandas as pd
import json
import os
import random
import hashlib

# ---------- Config ----------
USERS_FILE = "users.json"            # opslag login + scores
QUESTIONS_JSON = "vragen.json"       # voorkeur: direct JSON    
QUESTIONS_XLSX = "Untitled spreadsheet.xlsx"  # fallback: Excel
QUESTIONS_CSV  = "vragen.csv"        # fallback: CSV

# ---------- Helpers ----------

def hash_pw(pw: str) -> str:
    """Hash een wachtwoord voor (ongecodeerde) opslag."""
    return hashlib.sha256(pw.encode()).hexdigest()


def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def convert_dataframe_to_dict(df: pd.DataFrame) -> dict:
    """Zet spreadsheet om naar een nested dict {vak: [vragen...]}"""
    qdict: dict[str, list[dict]] = {}
    for vak in df["vak."].unique():
        subset = df[df["vak."] == vak]
        qdict[vak] = []
        for _, row in subset.iterrows():
            q_info = {
                "vraag": str(row["vragen."]).strip(),
                "type": "invul" if "fill" in str(row["meerkeuze of fill in the blanks."]).lower() else "meerkeuze",
                "antwoord": str(row["goed antwoord"]).strip(),
            }
            # voeg opties toe bij meerkeuze
            wrong = str(row.get("eventuele foute antwoorden (meerkeuze)", "")).strip()
            if q_info["type"] == "meerkeuze":
                opties = [q_info["antwoord"]]
                if wrong:
                    # foute antwoorden kunnen met ; of , gescheiden zijn
                    for part in wrong.replace(",", ";").split(";"):
                        part = part.strip()
                        if part:
                            opties.append(part)
                random.shuffle(opties)
                q_info["opties"] = opties
            # voeg optioneel plaatje toe
            plaatje = str(row.get("eventuele plaatjes of bijlagen.", "")).strip()
            if plaatje and plaatje.lower() != "nan":
                q_info["plaatje"] = plaatje
            qdict[vak].append(q_info)
    return qdict


def load_questions() -> dict:
    """Laad vragen.json of converteer automatisch vanuit xlsx/csv."""
    if os.path.exists(QUESTIONS_JSON):
        with open(QUESTIONS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)

    # Fallback: probeer Excel/CSV te lezen en automatisch omzetten.
    if os.path.exists(QUESTIONS_XLSX):
        df = pd.read_excel(QUESTIONS_XLSX)
    elif os.path.exists(QUESTIONS_CSV):
        df = pd.read_csv(QUESTIONS_CSV)
    else:
        st.error("Geen vragenbestand gevonden (vragen.json of spreadsheet). Voeg het toe aan de repo.")
        return {}

    qdict = convert_dataframe_to_dict(df)
    with open(QUESTIONS_JSON, "w", encoding="utf-8") as f:
        json.dump(qdict, f, indent=2, ensure_ascii=False)
    st.success("Spreadsheet succesvol omgezet naar vragen.json!")
    return qdict


# ---------- Login & Registratie ----------

def login_screen(users: dict):
    st.header("📚 Schooljaar-Quiz | Login")
    tab_login, tab_register = st.tabs(["Inloggen", "Registreren"])

    with tab_login:
        uname = st.text_input("Gebruikersnaam", key="login_user")
        pw = st.text_input("Wachtwoord", type="password", key="login_pw")
        if st.button("Inloggen"):
            if uname in users and users[uname]["pw"] == hash_pw(pw):
                st.session_state.user = uname
                st.rerun()
            else:
                st.error("Onjuiste inloggegevens.")

    with tab_register:
        new_user = st.text_input("Nieuwe gebruikersnaam", key="reg_user")
        new_pw1 = st.text_input("Wachtwoord", type="password", key="reg_pw1")
        new_pw2 = st.text_input("Herhaal wachtwoord", type="password", key="reg_pw2")
        if st.button("Account aanmaken"):
            if new_user in users:
                st.error("Gebruikersnaam bestaat al.")
            elif new_pw1 != new_pw2:
                st.error("Wachtwoorden komen niet overeen.")
            elif not new_user or not new_pw1:
                st.error("Vul alle velden in.")
            else:
                users[new_user] = {"pw": hash_pw(new_pw1), "highscore": 0}
                save_users(users)
                st.success("Account aangemaakt! Log nu in.")


# ---------- Quiz View ----------

def init_quiz_state():
    st.session_state.score = 0
    st.session_state.idx = 0
    st.session_state.selected_vak = None
    st.session_state.questions_order = []


def quiz_view(users: dict, qdict: dict):
    st.sidebar.write(f"👋 Ingelogd als **{st.session_state.user}**")
    if st.sidebar.button("Uitloggen"):
        del st.session_state.user
        st.rerun()

    menu_choice = st.sidebar.radio("Menu", ["Quiz", "Leaderboard"])

    if menu_choice == "Leaderboard":
        leaderboard_view(users)
        return

    # ---- Quiz ----
    st.header("🎯 Kies een vak en start de quiz!")
    vakken = list(qdict.keys())
    if not vakken:
        st.warning("Geen vakken/vragen beschikbaar.")
        return

    if "selected_vak" not in st.session_state:
        init_quiz_state()

    if st.session_state.selected_vak is None:
        gekozen_vak = st.selectbox("Vak", vakken)
        if st.button("Start Quiz"):
            st.session_state.selected_vak = gekozen_vak
            st.session_state.questions_order = random.sample(qdict[gekozen_vak], k=len(qdict[gekozen_vak]))
            st.rerun()
        return

    # Toon vraag op basis van index
    vragenlijst = st.session_state.questions_order
    idx = st.session_state.idx
    if idx >= len(vragenlijst):
        st.success(f"Klaar! Je score: **{st.session_state.score}/{len(vragenlijst)}**")
        # update highscore
        user_info = users[st.session_state.user]
        if st.session_state.score > user_info.get("highscore", 0):
            user_info["highscore"] = st.session_state.score
            save_users(users)
            st.balloons()
            st.info("Nieuw persoonlijk record! 🎉")
        if st.button("Opnieuw" ):
            init_quiz_state()
        return

    vraag = vragenlijst[idx]
    st.subheader(f"Vraag {idx+1} van {len(vragenlijst)}")
    st.write(vraag["vraag"])
    if "plaatje" in vraag and os.path.exists(vraag["plaatje"]):
        st.image(vraag["plaatje"], use_column_width=True)

    antwoord_juiste = vraag["antwoord"]
    if vraag["type"] == "meerkeuze":
        keuze = st.radio("Opties", vraag["opties"], key=f"keuze_{idx}")
        if st.button("Bevestig antwoord"):
            if keuze == antwoord_juiste:
                st.success("Correct!")
                st.session_state.score += 1
            else:
                st.error(f"Fout! Juiste antwoord: {antwoord_juiste}")
            st.session_state.idx += 1
            st.rerun()
    else:
        invul = st.text_input("Jouw antwoord", key=f"invul_{idx}")
        if st.button("Bevestig antwoord"):
            if invul.strip() == str(antwoord_juiste):
                st.success("Correct!")
                st.session_state.score += 1
            else:
                st.error(f"Fout! Juiste antwoord: {antwoord_juiste}")
            st.session_state.idx += 1
            st.rerun()


def leaderboard_view(users: dict):
    st.header("🏆 Leaderboard")
    scores = [(u, info.get("highscore", 0)) for u, info in users.items()]
    scores_sorted = sorted(scores, key=lambda x: x[1], reverse=True)
    st.table(scores_sorted[:10])


# ---------- Main ----------

def main():
    st.set_page_config(page_title="Schooljaar Quiz", page_icon="📚", layout="centered")
    users = load_users()
    qdict = load_questions()

    if "user" not in st.session_state:
        login_screen(users)
    else:
        quiz_view(users, qdict)

if __name__ == "__main__":
    main()
