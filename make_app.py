import streamlit as st
import requests
from datetime import datetime

API_URL = "http://localhost:8000/api"

st.set_page_config(page_title="CarSpot", page_icon="🏎️", layout="centered")

if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None

st.title("🏎️ CarSpot — Auto Meetup Finder")

menu = ["События", "Вход / Регистрация", "Мой профиль"]
choice = st.sidebar.selectbox("Навигация", menu)

if choice == "События":
    st.subheader("Automotive Events and Meetups")

    with st.expander("➕ Создать новое событие / сходку", expanded=True):
        if not st.session_state.token:
            st.warning("Для публикации события необходимо авторизоваться:")
            login_email = st.text_input("Email", key="evt_email")
            login_pass = st.text_input("Пароль", type="password", key="evt_pass")
            if st.button("Войти и продолжить", key="evt_login_btn"):
                res = requests.post(f"{API_URL}/users/login", json={"email": login_email, "password": login_pass})
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.token = data.get("access_token")
                    st.session_state.user = data.get("user")
                    st.success("Успешный вход!")
                    st.rerun()
                else:
                    st.error("Неверный email или пароль.")
        else:
            st.info(f"Вы вошли как: **{st.session_state.user.get('username')}**")
            with st.form("create_event_form"):
                title = st.text_input("Название сходки (например: BMW F10 Meetup)")
                location = st.text_input("Локация (например: Тбилиси, Парковка ТЦ)")
                description = st.text_area("Описание события, программа и время")
                submit_btn = st.form_submit_button("Опубликовать событие")
                
                if submit_btn:
                    if title and location:
                        headers = {}
                        if st.session_state.token:
                            headers["Authorization"] = f"Bearer {st.session_state.token}"

                        user_id = st.session_state.user.get("id") if st.session_state.user else None

                        payload = {
                            "title": title,
                            "location": location,
                            "description": description,
                            "date": datetime.now().isoformat(),
                            "creator_id": user_id,
                            "organizer_id": user_id
                        }

                        res = requests.post(f"{API_URL}/events/", json=payload, headers=headers)
                        if res.status_code in [200, 201]:
                            st.success("Событие успешно опубликовано!")
                            st.rerun()
                        else:
                            st.error(f"Ошибка при создании события. Код ответа: {res.status_code}. Детали: {res.text}")
                    else:
                        st.warning("Заполните название и локацию.")

    st.markdown("---")

    try:
        res = requests.get(f"{API_URL}/events/")
        if res.status_code == 200 and res.json():
            for ev in res.json():
                st.markdown(f"### 📍 {ev.get('title')}")
                st.caption(f"**Локация:** {ev.get('location')}")
                st.write(ev.get("description"))
                st.markdown("---")
        else:
            st.info("Пока нет созданных событий.")
    except Exception:
        st.error("Ошибка подключения к серверу API.")

elif choice == "Вход / Регистрация":
    st.subheader("Авторизация")
    email = st.text_input("Email для входа")
    password = st.text_input("Пароль для входа", type="password")
    
    if st.button("Войти"):
        res = requests.post(f"{API_URL}/users/login", json={"email": email, "password": password})
        if res.status_code == 200:
            data = res.json()
            st.session_state.token = data.get("access_token")
            st.session_state.user = data.get("user")
            st.success("Успешный вход!")
            st.rerun()
        else:
            st.error("Неверный email или пароль.")

    st.markdown("---")
    st.subheader("Регистрация")
    reg_email = st.text_input("Email", key="reg_email")
    reg_username = st.text_input("Username", key="reg_user")
    reg_password = st.text_input("Пароль", type="password", key="reg_pass")

    if st.button("Зарегистрироваться"):
        res = requests.post(f"{API_URL}/users/register", json={
            "email": reg_email,
            "username": reg_username,
            "password": reg_password
        })
        if res.status_code == 201:
            st.success("Аккаунт создан!")
        else:
            st.error("Ошибка регистрации.")

elif choice == "Мой профиль":
    st.subheader("Профиль пользователя")
    if st.session_state.user:
        st.write(f"**Username:** {st.session_state.user.get('username')}")
        st.write(f"**Email:** {st.session_state.user.get('email')}")
        if st.button("Выйти из аккаунта"):
            st.session_state.token = None
            st.session_state.user = None
            st.rerun()
    else:
        st.warning("Вы не авторизованы.")