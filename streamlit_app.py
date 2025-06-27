import streamlit as st
import pandas as pd
import json
import os
import hashlib

USERS_FILE = "users.json"
QUESTIONS_XLSX = "Untitled spreadsheet.xlsx"

# Helpers
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users: dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

def convert_dataframe_to_list(df: pd.DataFrame) -> list:
    vragen = []
    for _, row in df.iterrows():
        vraag = {
            "vraag": str(row.get("vragen.", "")).strip(),
            "antwoord": str(row.get("goed antwoord", "")).strip(),
            "type": "invul" if "fill" in str(row.get("meerkeuze of fill in the blanks.", "")).lower() else "meerkeuze",
            "tijd": str(row.get("dag+uur (voor volgorde)", "")).strip(),
            "vak": str(row.get("vak.", "")).strip(),
        }
        if vraag["type"] == "meerkeuze":
            opties = [vraag["antwoord"]]
            fout = str(row.get("eventuele foute antwoorden (meerkeuze)", "")).strip()
            if fout:
                for opt in fout.replace(",", ";").split(";"):
                    if opt.strip():
                        opties.append(opt.strip())
            import random
            random.shuffle(opties)
            vraag["opties"] = opties
        vragen.append(vraag)
    return sorted(vragen, key=lambda v: v["tijd"])

def load_questions() -> list:
    if not os.path.exists(QUESTIONS_XLSX):
        st.error("Spreadsheet niet gevonden.")
        return []
    df = pd.read_excel(QUESTIONS_XLSX)
    return convert_dataframe_to_list(df)

# Login
def login_screen(users: dict):
    st.header("📚 Schoolquiz | Inloggen")
    login_tab, register_tab = st.tabs(["Inloggen", "Registreren"])

    with login_tab:
        uname = st.text_input("Gebruikersnaam", key="login_user")
        pw = st.text_input("Wachtwoord", type="password", key="login_pw")
        if st.button("Inloggen"):
            if uname in users and users[uname]["pw"] == hash_pw(pw):
                st.session_state.user = uname
                st.rerun()
            else:
                st.error("Onjuiste inloggegevens.")

    with register_tab:
        new_user = st.text_input("Nieuwe gebruikersnaam", key="reg_user")
        pw1 = st.text_input("Wachtwoord", type="password", key="reg_pw1")
        pw2 = st.text_input("Herhaal wachtwoord", type="password", key="reg_pw2")
        if st.button("Account aanmaken"):
            if new_user in users:
                st.error("Gebruiker bestaat al.")
            elif pw1 != pw2:
                st.error("Wachtwoorden komen niet overeen.")
            else:
                users[new_user] = {"pw": hash_pw(pw1), "highscore": 0}
                save_users(users)
                st.success("Account aangemaakt. Log nu in.")

# Quiz

def init_quiz(vragen):
    st.session_state.vragenlijst = vragen
    st.session_state.score = 0
    st.session_state.idx = 0

def quiz_view(users, vragen):
    st.sidebar.write(f"👤 Ingelogd als **{st.session_state.user}**")
    if st.sidebar.button("Uitloggen"):
        del st.session_state.user
        st.rerun()

    if "vragenlijst" not in st.session_state:
        init_quiz(vragen)

    idx = st.session_state.idx
    if idx >= len(st.session_state.vragenlijst):
        st.success(f"Klaar! Je score: {st.session_state.score}/{len(st.session_state.vragenlijst)}")
        user_info = users[st.session_state.user]
        if st.session_state.score > user_info.get("highscore", 0):
            user_info["highscore"] = st.session_state.score
            save_users(users)
            st.balloons()
            st.info("Nieuw record!")
        if st.button("Opnieuw beginnen"):
            init_quiz(vragen)
            st.rerun()
        return

    vraag = st.session_state.vragenlijst[idx]
    st.subheader(f"{vraag['tijd']} - {vraag['vak']}")
    st.write(vraag["vraag"])

    if vraag["type"] == "meerkeuze":
        keuze = st.radio("Kies een antwoord:", vraag["opties"], key=f"keuze_{idx}")
        if st.button("Bevestig", key=f"btn_{idx}"):
            if keuze == vraag["antwoord"]:
                st.success("Correct!")
                st.session_state.score += 1
            else:
                st.error(f"Fout. Antwoord was: {vraag['antwoord']}")
            st.session_state.idx += 1
            st.rerun()
    else:
        invul = st.text_input("Jouw antwoord:", key=f"invul_{idx}")
        if st.button("Bevestig", key=f"btn_{idx}"):
            if invul.strip() == vraag["antwoord"]:
                st.success("Correct!")
                st.session_state.score += 1
            else:
                st.error(f"Fout. Antwoord was: {vraag['antwoord']}")
            st.session_state.idx += 1
            st.rerun()

# Leaderboard

def leaderboard(users):
    st.header("🏆 Leaderboard")
    lijst = [(u, d.get("highscore", 0)) for u, d in users.items()]
    lijst = sorted(lijst, key=lambda x: x[1], reverse=True)
    st.table(lijst[:10])

# Main

def main():
    st.set_page_config(page_title="Schoolquiz", page_icon="📘")
    users = load_users()
    vragen = load_questions()

    if "user" not in st.session_state:
        login_screen(users)
    else:
        menu = st.sidebar.radio("Menu", ["Quiz", "Leaderboard"])
        if menu == "Leaderboard":
            leaderboard(users)
        else:
            quiz_view(users, vragen)

if __name__ == "__main__":
    main()
