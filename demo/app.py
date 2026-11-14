"""Run with: streamlit run demo/app.py"""

import os

import streamlit as st

from demo.api_client import APIError, MusicAPI


def call(action, *args):
    try:
        return action(*args)
    except APIError as error:
        st.error(str(error))
        return None


def clear_user_state() -> None:
    for key in ("artist_options", "artist_selection", "recommendation_result",
                "catalog_result", "similar_result", "similar_seed"):
        st.session_state.pop(key, None)


def auth_view(api: MusicAPI) -> None:
    st.title("Music recommendations")
    st.caption("Демо використовує API, каталог Last.fm 1K та збережену ALS-модель.")
    login_tab, register_tab = st.tabs(["Увійти", "Створити акаунт"])
    with login_tab, st.form("login_form"):
        username = st.text_input("Ім’я користувача", key="login_name")
        password = st.text_input("Пароль", type="password", key="login_password")
        if st.form_submit_button("Увійти"):
            result = call(api.login, username, password)
            if result is not None:
                clear_user_state()
                st.session_state["token"] = result["token"]
                st.session_state["username"] = result["username"]
                st.rerun()
    with register_tab, st.form("register_form"):
        username = st.text_input("Ім’я користувача", key="register_name")
        password = st.text_input("Пароль", type="password", key="register_password")
        confirm = st.text_input("Повторіть пароль", type="password")
        if st.form_submit_button("Зареєструватися"):
            if password != confirm:
                st.error("Паролі не збігаються.")
            else:
                result = call(api.register, username, password)
                if result is not None:
                    clear_user_state()
                    st.session_state["token"] = result["token"]
                    st.session_state["username"] = result["username"]
                    st.rerun()


def render_tracks(api: MusicAPI, tracks: list[dict], prefix: str) -> None:
    if not tracks:
        st.info("Треків для показу немає.")
        return
    for track in tracks:
        mbid = track["mbid"]
        with st.container(border=True):
            st.write(f"**{track['name'] or 'Без назви'}** — "
                     f"{track['artist_name'] or 'Невідомий виконавець'}")
            st.caption(f"Track MBID: {mbid}")
            listen_col, similar_col = st.columns(2)
            if listen_col.button("Записати прослуховування", key=f"{prefix}_listen_{mbid}"):
                if call(api.listen, mbid) is not None:
                    st.session_state.pop("recommendation_result", None)
                    st.success("Прослуховування збережено. Оновіть рекомендації.")
            if similar_col.button("Схожі треки", key=f"{prefix}_similar_{mbid}"):
                result = call(api.similar, mbid)
                if result is not None:
                    st.session_state["similar_result"] = result
                    st.session_state["similar_seed"] = track["name"] or mbid


def artist_view(api: MusicAPI) -> None:
    st.subheader("Виберіть виконавців")
    st.caption("Пошук повертає MusicBrainz ID; однакові назви не об’єднуються.")
    with st.form("artist_search_form"):
        query = st.text_input("Пошук виконавця", key="artist_query")
        search = st.form_submit_button("Знайти виконавців")
    if search and query.strip():
        results = call(api.search_artists, query.strip())
        if results is not None:
            options = st.session_state.setdefault("artist_options", {})
            options.update({row["mbid"]: row["name"] for row in results})
            if not results:
                st.info("Виконавців не знайдено.")
    saved = call(api.artist_choices)
    if saved is None:
        return
    options = st.session_state.setdefault("artist_options", {})
    for mbid in saved:
        options.setdefault(mbid, "Збережений виконавець")
    st.session_state.setdefault("artist_selection", saved)
    st.multiselect("Вибрані виконавці (до 10)", options=list(options),
                   format_func=lambda mbid: f"{options[mbid]} · {mbid}",
                   key="artist_selection", max_selections=10)
    if st.button("Зберегти вибір", key="save_artists"):
        result = call(api.save_artist_choices, st.session_state["artist_selection"])
        if result is not None:
            st.session_state.pop("recommendation_result", None)
            st.success("Вибір збережено. Отримайте рекомендації.")
    st.caption("Якщо вибрані виконавці не мають треків у моделі, API покаже популярні треки.")


def recommendation_view(api: MusicAPI) -> None:
    st.subheader("Ваші рекомендації")
    if st.button("Отримати рекомендації", key="get_recommendations"):
        result = call(api.recommendations)
        if result is not None:
            st.session_state["recommendation_result"] = result
    result = st.session_state.get("recommendation_result")
    if result:
        st.caption(f"Джерело: {result['source']} · Модель: {result['model_version']}")
        render_tracks(api, result["items"], "recommendation")


def catalog_view(api: MusicAPI) -> None:
    st.subheader("Каталог треків")
    with st.form("track_search_form"):
        query = st.text_input("Назва треку або виконавця", key="track_query")
        search = st.form_submit_button("Знайти треки")
    if search and query.strip():
        result = call(api.search_tracks, query.strip())
        if result is not None:
            st.session_state["catalog_result"] = result
    if "catalog_result" in st.session_state:
        render_tracks(api, st.session_state["catalog_result"], "catalog")


def main() -> None:
    st.set_page_config(page_title="Music recommendations", page_icon="🎵")
    api_url = st.sidebar.text_input("Адреса API", value=os.environ.get(
        "MUSIC_API_URL", "http://127.0.0.1:8001"))
    try:
        api = MusicAPI(api_url, st.session_state.get("token"))
    except APIError as error:
        st.error(str(error))
        return
    if not st.session_state.get("token"):
        auth_view(api)
        return
    st.sidebar.write(f"Користувач: **{st.session_state['username']}**")
    if st.sidebar.button("Вийти"):
        try:
            api.logout()
        except APIError as error:
            st.sidebar.error(str(error))
        else:
            st.session_state.pop("token", None)
            st.session_state.pop("username", None)
            clear_user_state()
            st.rerun()
    st.title("Music recommendations")
    st.caption("Прототип рекомендацій, а не музичний плеєр.")
    recommendations_tab, artists_tab, catalog_tab = st.tabs(
        ["Рекомендації", "Виконавці", "Каталог"])
    with recommendations_tab:
        recommendation_view(api)
    with artists_tab:
        artist_view(api)
    with catalog_tab:
        catalog_view(api)
    if st.session_state.get("similar_result"):
        st.divider()
        st.subheader(f"Схожі на: {st.session_state['similar_seed']}")
        result = st.session_state["similar_result"]
        st.caption(f"Фактори ALS · Модель: {result['model_version']}")
        render_tracks(api, result["items"], "similar")


if __name__ == "__main__":
    main()
