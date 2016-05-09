import requests
from lxml import html
import json
import MySQLdb as mysql
import re
from markov_python.cc_markov import MarkovChain

spotifyBaseURL = "http://api.spotify.com"
lyricsWikiBaseURL = "http://lyrics.wikia.com/wiki"

# turn this on to store lyric results
# in a MySQL database.
# this will decrease time to fetch lyrics
# for artists that have been fetched before
USE_DATABASE = False

# artists is an array of artists
# to generate lyrics from
# could be one or more artists
def generateLyrics(artists):
	allLyrics = []
	for artist in artists:
		allLyrics += [item[1] for item in getAllLyrics(artist)]
	# end for

	#print allLyrics

	mc = MarkovChain(2)
	for song in allLyrics:
		mc.add_string(song)
	# end
	
	newLyrics = mc.generate_text(80)

	print newLyrics
	return newLyrics


# get a list of tuples (song, lyrics) 
# containing all lyrics 
# for a given artist
def getAllLyrics(artistName):
	# get all the songs the artist has on spotify
	(artist, songList) = getArtistDiscogFromSpotify(artistName)

	##########
	# Try to get the lyrics for the artist's songs
	##########
	print "Fetching lyrics for", artist
	allLyrics = []
	for song in songList:
		lyrics = getLyricsFromLyricsWiki(artist, song)
		if lyrics != None:
			# try to prevent duplicate lyrics 
			# (similar song names may redirect)
			# for example:
			# Let Go by RAC
			# and 
			# Let Go (feat. Lizy Ryan) by RAC
			# both redirect to the same lyrics
			# it is important that duplicate lyrics
			# are caught because it will affect the Markov Chain
			if not lyrics in [item[1] for item in allLyrics]:
				allLyrics.append((song, lyrics))
			# end if
		# end if
	# end for

	return allLyrics

# returns a list containing all tracks on Spotify from 
# albums and singles by <artistName>
def getArtistDiscogFromSpotify(artistName):
	# Step 1: Search Artist, and get Spotify Artist ID
	# Step 2: Get Artist's albums
	# Step 3: Get list of songs from each album
	# return list of songs from all albums

	##########
	## Search for artist. Take the top result
	## and get the artist ID
	##
	## TODO: Ask user if the result is what 
	## they were looking for. Provide alternatives.
	##########
	print "Searching Spotify for", artistName

	artistName = spotifyString(artistName)
	artistSearch = spotifyBaseURL + "/v1/search?q=" + artistName + "&type=artist"

	response = requests.get(artistSearch).text
	jsonObj = json.loads(response)

	# assume the first result is what we're looking for
	# the first result is denoted by the 0
	artistID = jsonObj['artists']['items'][0]['id']
	officialArtistName = jsonObj['artists']['items'][0]['name']
	print "Using top result from Spotify:", officialArtistName

	##########
	## Using the artist ID, get
	## a list of the artist's albums and singles
	##########
	print "Getting albums and singles for", officialArtistName

	albumSearch = spotifyBaseURL + "/v1/artists/" + artistID
	albumSearch += "/albums?market=US&album_type=album,single"

	response = requests.get(albumSearch).text
	jsonObj = json.loads(response)

	albumIDs = []

	for album in jsonObj['items']:

		albumIDs.append(album['id'])
		# end if
	# end for

	##########
	## Get the list of songs
	## for each album using its
	## respective album ID
	## and add those songs to the discog
	##########
	print "Getting songs from each album/single by", officialArtistName
	discog = []

	for albID in albumIDs:
		albumTracksSearch = spotifyBaseURL + '/v1/albums/' + albID + '/tracks'

		response = requests.get(albumTracksSearch).text
		jsonObj = json.loads(response)

		songs = jsonObj['items']
		for song in songs:
			name = song['name']
			name = unicodeToAsciiWithDataLoss(name)

			if not name in discog:
				discog.append(name)
			# end if 
		# end for
	# end for
	return (officialArtistName, discog)

def getLyricsFromLyricsWiki(artist, song):
	##########
	# Create URL
	##########
	searchUrl = lyricsWikiBaseURL
	searchUrl += "/%s:%s" % (wikifyString(artist), wikifyString(song))

	##########
	# Get webpage
	# and pull lyrics content
	##########
	response = requests.get(searchUrl)
	tree = html.fromstring(response.content)

	lyrics = tree.xpath('//div[@class="lyricbox"]/text()')

	if len(lyrics) == 0:
		return None

	fullLyric = ""
	for line in lyrics:
		fullLyric += line + " "
	# end for

	return sanitizeLyrics(fullLyric)

# add or update lyrics of a particular song
# for an artist
def updateLyricsInDB(artist, song, lyrics):
	artist = sqlifyArtist(artist)
	lyrics = sanitizeLyrics(lyrics)
	print lyrics
	##########
	# create database if it doesnt exist
	##########
	try :
		db = mysql.connect("localhost","root","root", "lyrics")
	except:
		print "Couldn't connect to DB. Make sure there is an existing database called 'lyrics'"
		return None

	# abort if I can't connect
	if db == None:
		raise ConnectionError("Could not connect to db.")
	# end if

	cursor = db.cursor()
	##########
	# check if artist table exists
	# create it if not
	##########
	if cursor.execute("SHOW TABLES LIKE '%s'" % artist) == 0:
		cursor.execute("CREATE TABLE %s (song TEXT, lyrics TEXT)" % artist)
	# end if

	##########
	# delete the song row if it exists
	# add the updated lyric
	##########
	cursor.execute("DELETE FROM %s WHERE song = '%s'" % (artist, song))
	cursor.execute("INSERT INTO %s (song, lyrics) VALUES ('%s', '%s')" % (artist, song, lyrics))

	db.commit()
	db.close()
	# done

# replace whitespace with +
# for spotify url
def spotifyString(stringIn):
	return stringIn.replace(" ", "+")

# assume artist name is already capitalized
# properly a la spotify API
def wikifyString(stringIn):
	# replace whitespace with underscore
	# replace ? with %3F
	out = re.sub(" +", " ", stringIn)
	out = out.replace(" ", "_")
	out = out.replace("?", "%3F")
	out = re.sub("[^a-zA-Z0-9_%.'(),-]", "", out)
	return out

# so there's consistency among 
# the artist names in the db
def sqlifyArtist(artist):
	out = artist.lower()
	out = re.sub("[^a-zA-Z0-9]", "", out)
	return out

def sanitizeLyrics(lyrics):
	out = unicodeToAsciiWithDataLoss(lyrics)
	out = out.translate(None, "'\",()")
	out = re.sub('[\\\n\\\r]', ' ', out)
	out = re.sub(' +', ' ', out)
	return out.lower()

# convert unicode to ascii 
# and ignore values that 
# can't be converted
def unicodeToAsciiWithDataLoss(uni):
	out = ''
	for char in uni:
		try:
			out += str(char)
		except UnicodeEncodeError:
			out += ""
	# end for
	return out


#getArtistDiscogFromSpotify("arctic monkeys")
#getArtistDiscogFromSpotify("grouplove")
#print getArtistDiscogFromSpotify("RAC")
#getArtistDiscogFromSpotify("portugal. the man")
#getArtistDiscogFromSpotify("strokes")

#getLyricsFromLyricsWiki("Arctic Monkeys", "R U Mine?")
#getLyricsFromLyricsWiki("RAC", "Cheap Sunglasses")
#getLyricsFromLyricsWiki("Jack's Mannequin", "Holiday From Real")

#generateLyrics(["the strokes", "arctic monkeys"])

#updateLyricsInDB("arctic monkeys", "hey", "blah")
