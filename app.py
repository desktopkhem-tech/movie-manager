from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label

from core.data_store import MovieRepository
from core.models import Movie

class MovieApp(App):
    def build(self):
        self.repo = MovieRepository()
        self.movies = self.repo.load_movies()

        layout = BoxLayout(orientation='vertical')

        self.input = TextInput(hint_text="Movie Name")
        layout.add_widget(self.input)

        btn = Button(text="Add Movie")
        btn.bind(on_press=self.add_movie)
        layout.add_widget(btn)

        self.label = Label(text="")
        layout.add_widget(self.label)

        return layout

    def add_movie(self, instance):
        name = self.input.text.strip()
        if name:
            movie = Movie(name=name)
            self.movies.append(movie)
            self.repo.save_movies(self.movies)
            self.label.text = f"Added: {name}"

MovieApp().run()
