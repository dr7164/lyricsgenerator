# lyricsgenerator
Generates lyrics based on existing lyrics for an artist(s).
This Python app is based on a Codecademy project I worked on a while back. The basic premise
is using a Markov Chain to generate NEW lyrics based on existing lyrics for an artist.

The original app (I'll put it up on Github) only generated new lyrics for the Arctic Monkeys. This one
will generate new lyrics for any combination of artists. 

It uses the Spotify Web API to get an artist's discography (albums and singles). Then, it scrapes the lyrics
from lyrics.wikia.com. As a learning exercise, I'm keeping a local MySQL DB to store lyrics that are found. That way, the app
will only have to get an artist's lyrics from the web ONCE.
