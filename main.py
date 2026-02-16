import json
import os
import threading
import webbrowser
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional
from urllib.parse import quote_plus

import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

KV = """
<RootView>:
    orientation: "vertical"
    spacing: dp(10)
    padding: dp(10)
    canvas.before:
        Color:
            rgba: app.theme_bg
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        size_hint_y: None
        height: dp(44)
        spacing: dp(8)

        Label:
            text: "Movie Manager"
            bold: True
            font_size: "20sp"
            color: app.theme_text
            halign: "left"
            valign: "middle"
            text_size: self.size

        Button:
            text: "Theme: Dark" if app.dark_mode else "Theme: Light"
            size_hint_x: None
            width: dp(120)
            background_normal: ""
            background_color: app.theme_button
            color: app.theme_button_text
            on_release: app.toggle_theme()

    BoxLayout:
        size_hint_y: None
        height: dp(42)
        spacing: dp(8)

        TextInput:
            id: search_input
            hint_text: "Search movies..."
            multiline: False
            on_text: app.refresh_movies()

        Spinner:
            id: filter_spinner
            text: "All"
            values: ["All", "Watched", "Favorite", "Watchlist"]
            size_hint_x: None
            width: dp(120)
            on_text: app.refresh_movies()

        Spinner:
            id: sort_spinner
            text: "Title"
            values: ["Title", "Year", "Rating"]
            size_hint_x: None
            width: dp(110)
            on_text: app.refresh_movies()

    BoxLayout:
        size_hint_y: None
        height: dp(44)
        spacing: dp(8)

        Button:
            text: "Add Movie"
            background_normal: ""
            background_color: app.theme_primary
            color: app.theme_button_text
            on_release: app.open_movie_form()

        Button:
            text: "Set TMDB API Key"
            background_normal: ""
            background_color: app.theme_button
            color: app.theme_button_text
            on_release: app.open_api_key_popup()

    ScrollView:
        id: movie_scroll
        do_scroll_x: False

        GridLayout:
            id: movie_grid
            cols: 1
            spacing: dp(10)
            padding: [0, 0, 0, dp(10)]
            size_hint_y: None
            height: self.minimum_height
"""


@dataclass
class Movie:
    title: str
    year: str = ""
    rating: float = 0.0
    poster_url: str = ""
    watched: bool = False
    favorite: bool = False
    watchlist: bool = True
    trailer_url: str = ""
    local_file: str = ""
    notes: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    @classmethod
    def from_dict(cls, payload: dict) -> "Movie":
        return cls(
            title=str(payload.get("title", "")).strip(),
            year=str(payload.get("year", "")).strip(),
            rating=float(payload.get("rating", 0) or 0),
            poster_url=str(payload.get("poster_url", "")).strip(),
            watched=bool(payload.get("watched", False)),
            favorite=bool(payload.get("favorite", False)),
            watchlist=bool(payload.get("watchlist", True)),
            trailer_url=str(payload.get("trailer_url", "")).strip(),
            local_file=str(payload.get("local_file", "")).strip(),
            notes=str(payload.get("notes", "")).strip(),
            created_at=str(payload.get("created_at", "")).strip(),
        )


class RootView(BoxLayout):
    pass


class MovieManagerApp(App):
    dark_mode = BooleanProperty(True)
    theme_bg = ListProperty([0.08, 0.09, 0.11, 1])
    theme_card = ListProperty([0.13, 0.14, 0.18, 1])
    theme_text = ListProperty([0.92, 0.92, 0.95, 1])
    theme_primary = ListProperty([0.22, 0.53, 0.98, 1])
    theme_button = ListProperty([0.22, 0.24, 0.31, 1])
    theme_button_text = ListProperty([1, 1, 1, 1])
    data_file = StringProperty("")
    settings_file = StringProperty("")
    root_view = ObjectProperty(None)

    def build(self):
        Builder.load_string(KV)
        self.title = "Offline Movie Manager"
        self.data_file = os.path.join(self.user_data_dir, "movies.json")
        self.settings_file = os.path.join(self.user_data_dir, "settings.json")

        self.movies: List[Movie] = []
        self.tmdb_api_key = os.environ.get("TMDB_API_KEY", "").strip()

        self._load_settings()
        self._apply_theme()
        self.movies = self._load_movies()

        self.root_view = RootView()
        Clock.schedule_once(lambda *_: self.refresh_movies(), 0)
        return self.root_view

    def _load_movies(self) -> List[Movie]:
        if not os.path.exists(self.data_file):
            return []
        try:
            with open(self.data_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, list):
                return []
            return [Movie.from_dict(item) for item in data if isinstance(item, dict)]
        except Exception:
            return []

    def _save_movies(self) -> None:
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, "w", encoding="utf-8") as fh:
            json.dump([asdict(m) for m in self.movies], fh, indent=2)

    def _load_settings(self) -> None:
        if not os.path.exists(self.settings_file):
            return
        try:
            with open(self.settings_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.dark_mode = bool(data.get("dark_mode", True))
            if not self.tmdb_api_key:
                self.tmdb_api_key = str(data.get("tmdb_api_key", "")).strip()
        except Exception:
            return

    def _save_settings(self) -> None:
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        with open(self.settings_file, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "dark_mode": self.dark_mode,
                    "tmdb_api_key": self.tmdb_api_key,
                },
                fh,
                indent=2,
            )

    def _apply_theme(self) -> None:
        if self.dark_mode:
            self.theme_bg = [0.08, 0.09, 0.11, 1]
            self.theme_card = [0.13, 0.14, 0.18, 1]
            self.theme_text = [0.92, 0.92, 0.95, 1]
            self.theme_primary = [0.22, 0.53, 0.98, 1]
            self.theme_button = [0.22, 0.24, 0.31, 1]
        else:
            self.theme_bg = [0.95, 0.96, 0.98, 1]
            self.theme_card = [1, 1, 1, 1]
            self.theme_text = [0.12, 0.14, 0.18, 1]
            self.theme_primary = [0.19, 0.46, 0.85, 1]
            self.theme_button = [0.75, 0.79, 0.87, 1]

    def toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self._apply_theme()
        self._save_settings()
        self.refresh_movies()

    def open_api_key_popup(self) -> None:
        content = BoxLayout(orientation="vertical", spacing=8, padding=10)
        key_input = TextInput(text=self.tmdb_api_key, hint_text="TMDB API key", multiline=False)
        content.add_widget(key_input)

        actions = BoxLayout(size_hint_y=None, height=42, spacing=8)
        save_btn = Button(text="Save")
        cancel_btn = Button(text="Cancel")
        actions.add_widget(save_btn)
        actions.add_widget(cancel_btn)
        content.add_widget(actions)

        popup = Popup(title="TMDB API Key", content=content, size_hint=(0.9, 0.35))

        def save_key(*_):
            self.tmdb_api_key = key_input.text.strip()
            self._save_settings()
            popup.dismiss()

        save_btn.bind(on_release=save_key)
        cancel_btn.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    def _filtered_movies(self) -> List[Movie]:
        search = self.root_view.ids.search_input.text.strip().lower()
        filter_value = self.root_view.ids.filter_spinner.text
        sort_value = self.root_view.ids.sort_spinner.text

        items = self.movies
        if search:
            items = [m for m in items if search in m.title.lower() or search in m.notes.lower()]

        if filter_value == "Watched":
            items = [m for m in items if m.watched]
        elif filter_value == "Favorite":
            items = [m for m in items if m.favorite]
        elif filter_value == "Watchlist":
            items = [m for m in items if m.watchlist]

        if sort_value == "Title":
            items = sorted(items, key=lambda m: m.title.lower())
        elif sort_value == "Year":
            items = sorted(items, key=lambda m: m.year or "0", reverse=True)
        elif sort_value == "Rating":
            items = sorted(items, key=lambda m: m.rating, reverse=True)

        return items

    def refresh_movies(self) -> None:
        if not self.root_view:
            return
        grid = self.root_view.ids.movie_grid
        grid.clear_widgets()

        filtered = self._filtered_movies()
        if not filtered:
            empty = Label(
                text="No movies found. Add your first movie.",
                color=self.theme_text,
                size_hint_y=None,
                height=40,
            )
            grid.add_widget(empty)
            return

        for movie in filtered:
            grid.add_widget(self._build_movie_card(movie))

    def _build_movie_card(self, movie: Movie) -> BoxLayout:
        card = BoxLayout(orientation="vertical", spacing=8, padding=8, size_hint_y=None, height=310)
        with card.canvas.before:
            from kivy.graphics import Color, RoundedRectangle

            Color(*self.theme_card)
            card.bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[12])

        def update_bg(instance, _value):
            instance.bg.pos = instance.pos
            instance.bg.size = instance.size

        card.bind(pos=update_bg, size=update_bg)

        top = BoxLayout(size_hint_y=None, height=180, spacing=8)
        poster = AsyncImage(source=movie.poster_url or "", allow_stretch=True)
        poster.size_hint_x = None
        poster.width = 120
        top.add_widget(poster)

        info = BoxLayout(orientation="vertical", spacing=6)
        info.add_widget(Label(text=f"[b]{movie.title}[/b]", markup=True, color=self.theme_text, halign="left", text_size=(0, None)))
        info.add_widget(Label(text=f"Year: {movie.year or '-'}", color=self.theme_text, halign="left", text_size=(0, None)))
        info.add_widget(Label(text=f"Rating: {movie.rating:.1f}", color=self.theme_text, halign="left", text_size=(0, None)))
        info.add_widget(Label(text=f"Watched: {'Yes' if movie.watched else 'No'}", color=self.theme_text, halign="left", text_size=(0, None)))
        info.add_widget(Label(text=f"Favorite: {'Yes' if movie.favorite else 'No'}", color=self.theme_text, halign="left", text_size=(0, None)))
        top.add_widget(info)
        card.add_widget(top)

        actions = GridLayout(cols=3, size_hint_y=None, height=40, spacing=6)
        actions.add_widget(self._btn("Edit", lambda *_: self.open_movie_form(movie)))
        actions.add_widget(self._btn("Delete", lambda *_: self.delete_movie(movie)))
        actions.add_widget(self._btn("Trailer", lambda *_: self.open_trailer(movie)))
        card.add_widget(actions)

        actions2 = GridLayout(cols=3, size_hint_y=None, height=40, spacing=6)
        actions2.add_widget(self._btn("Play File", lambda *_: self.play_local(movie)))
        actions2.add_widget(self._btn("Watched", lambda *_: self.toggle_flag(movie, "watched")))
        actions2.add_widget(self._btn("Favorite", lambda *_: self.toggle_flag(movie, "favorite")))
        card.add_widget(actions2)

        return card

    def _btn(self, text: str, on_press):
        btn = Button(text=text, background_normal="", background_color=self.theme_button, color=self.theme_button_text)
        btn.bind(on_release=on_press)
        return btn

    def toggle_flag(self, movie: Movie, field: str) -> None:
        setattr(movie, field, not getattr(movie, field))
        if field == "watched" and movie.watched:
            movie.watchlist = False
        self._save_movies()
        self.refresh_movies()

    def delete_movie(self, movie: Movie) -> None:
        if movie in self.movies:
            self.movies.remove(movie)
            self._save_movies()
            self.refresh_movies()

    def open_trailer(self, movie: Movie) -> None:
        url = movie.trailer_url.strip()
        if not url:
            query = quote_plus(f"{movie.title} official trailer")
            url = f"https://www.youtube.com/results?search_query={query}"
        webbrowser.open(url)

    def play_local(self, movie: Movie) -> None:
        path = movie.local_file.strip()
        if not path:
            return
        if os.path.exists(path):
            try:
                from kivy.utils import platform

                if platform == "android":
                    from jnius import autoclass

                    PythonActivity = autoclass("org.kivy.android.PythonActivity")
                    Intent = autoclass("android.content.Intent")
                    Uri = autoclass("android.net.Uri")
                    intent = Intent(Intent.ACTION_VIEW)
                    intent.setDataAndType(Uri.parse("file://" + path), "video/*")
                    currentActivity = PythonActivity.mActivity
                    currentActivity.startActivity(intent)
                else:
                    webbrowser.open("file://" + os.path.abspath(path))
            except Exception:
                webbrowser.open("file://" + os.path.abspath(path))

    def open_movie_form(self, movie: Optional[Movie] = None) -> None:
        editing = movie is not None
        model = movie or Movie(title="")

        form = BoxLayout(orientation="vertical", spacing=7, padding=10)
        fields = {
            "title": TextInput(text=model.title, hint_text="Title", multiline=False),
            "year": TextInput(text=model.year, hint_text="Year", multiline=False),
            "rating": TextInput(text=str(model.rating or ""), hint_text="Rating 0-10", multiline=False),
            "poster_url": TextInput(text=model.poster_url, hint_text="Poster URL", multiline=False),
            "trailer_url": TextInput(text=model.trailer_url, hint_text="YouTube Trailer URL", multiline=False),
            "local_file": TextInput(text=model.local_file, hint_text="Local movie file path", multiline=False),
            "notes": TextInput(text=model.notes, hint_text="Notes", multiline=True),
        }

        for widget in fields.values():
            widget.size_hint_y = None
            widget.height = 40 if widget is not fields["notes"] else 80
            form.add_widget(widget)

        checks = BoxLayout(size_hint_y=None, height=34, spacing=8)
        watched = CheckBox(active=model.watched)
        favorite = CheckBox(active=model.favorite)
        watchlist = CheckBox(active=model.watchlist)
        checks.add_widget(Label(text="Watched", color=self.theme_text))
        checks.add_widget(watched)
        checks.add_widget(Label(text="Favorite", color=self.theme_text))
        checks.add_widget(favorite)
        checks.add_widget(Label(text="Watchlist", color=self.theme_text))
        checks.add_widget(watchlist)
        form.add_widget(checks)

        status = Label(text="", size_hint_y=None, height=24, color=self.theme_text)
        form.add_widget(status)

        controls = GridLayout(cols=4, size_hint_y=None, height=44, spacing=7)
        btn_tmdb = Button(text="Fetch TMDB")
        btn_save = Button(text="Save")
        btn_cancel = Button(text="Cancel")
        btn_clear = Button(text="Clear")
        controls.add_widget(btn_tmdb)
        controls.add_widget(btn_save)
        controls.add_widget(btn_cancel)
        controls.add_widget(btn_clear)
        form.add_widget(controls)

        popup = Popup(title="Edit Movie" if editing else "Add Movie", content=form, size_hint=(0.95, 0.95))

        def fetch_tmdb(*_):
            title = fields["title"].text.strip()
            year = fields["year"].text.strip()
            if not title:
                status.text = "Enter a title first."
                return
            if not self.tmdb_api_key:
                status.text = "Set TMDB API key first."
                return

            status.text = "Fetching from TMDB..."

            def worker():
                try:
                    params = {"api_key": self.tmdb_api_key, "query": title}
                    if year:
                        params["primary_release_year"] = year
                    resp = requests.get("https://api.themoviedb.org/3/search/movie", params=params, timeout=12)
                    resp.raise_for_status()
                    results = resp.json().get("results", [])
                    if not results:
                        Clock.schedule_once(lambda *_: setattr(status, "text", "No TMDB match found."), 0)
                        return
                    best = results[0]
                    poster_path = best.get("poster_path") or ""
                    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ""
                    release_date = str(best.get("release_date", ""))
                    movie_year = release_date[:4] if release_date else ""
                    movie_rating = float(best.get("vote_average") or 0)

                    def apply():
                        fields["year"].text = movie_year or fields["year"].text
                        fields["rating"].text = f"{movie_rating:.1f}" if movie_rating else fields["rating"].text
                        fields["poster_url"].text = poster_url or fields["poster_url"].text
                        if not fields["trailer_url"].text.strip():
                            query = quote_plus(f"{title} official trailer")
                            fields["trailer_url"].text = f"https://www.youtube.com/results?search_query={query}"
                        status.text = "TMDB data fetched."

                    Clock.schedule_once(lambda *_: apply(), 0)
                except Exception as exc:
                    Clock.schedule_once(lambda *_: setattr(status, "text", f"TMDB error: {exc}"), 0)

            threading.Thread(target=worker, daemon=True).start()

        def save(*_):
            title = fields["title"].text.strip()
            if not title:
                status.text = "Title is required."
                return
            try:
                rating = float(fields["rating"].text.strip() or 0)
            except ValueError:
                rating = 0.0

            if editing:
                target = movie
            else:
                target = Movie(title=title)

            target.title = title
            target.year = fields["year"].text.strip()
            target.rating = max(0.0, min(10.0, rating))
            target.poster_url = fields["poster_url"].text.strip()
            target.trailer_url = fields["trailer_url"].text.strip()
            target.local_file = fields["local_file"].text.strip()
            target.notes = fields["notes"].text.strip()
            target.watched = watched.active
            target.favorite = favorite.active
            target.watchlist = watchlist.active

            if not editing:
                self.movies.append(target)

            self._save_movies()
            self.refresh_movies()
            popup.dismiss()

        def clear(*_):
            for field in fields.values():
                field.text = ""
            watched.active = False
            favorite.active = False
            watchlist.active = True
            status.text = ""

        btn_tmdb.bind(on_release=fetch_tmdb)
        btn_save.bind(on_release=save)
        btn_cancel.bind(on_release=lambda *_: popup.dismiss())
        btn_clear.bind(on_release=clear)

        popup.open()


if __name__ == "__main__":
    MovieManagerApp().run()
