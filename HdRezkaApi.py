import requests
from bs4 import BeautifulSoup
import base64
from itertools import product
import re
import json

class HdRezkaStream():
	def __init__(self, season, episode):
		self.videos = {}
		self.season = season
		self.episode = episode
	def append(self, resolution, link):
		self.videos[resolution] = link
	def __str__(self):
		resolutions = list(self.videos.keys())
		return "<HdRezkaStream 2> : " + str(resolutions)
	def __repr__(self):
		return f"<HdRezkaStream 3(season:{self.season}, episode:{self.episode})>"
	def __call__(self, resolution):
		last_key = list(self.videos)[-1]
		return self.videos[last_key]

class HdRezkaApi():
	def __init__(self, url):
		self.frag = None
		index = url.find("#")
		if index != -1: 
			fragment = url[index + 1:]
			self.frag = re.findall(r'\d+', fragment)
		self.HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'}
		self.url = url.split(".html")[0] + ".html"
		self.page = self.getPage()
		self.page.raise_for_status() # Перевірка на HTTP помилки (4xx, 5xx)
		self.soup = self.getSoup()

		# Перевіряємо, чи не заблокувала нас сторінка (наприклад, Cloudflare)
		if not self.soup.find(id="post_id"):
			raise ValueError("Не вдалося знайти 'post_id'. Можливо, доступ заблоковано або URL невірний.")

		# Ліниве завантаження властивостей
		self._id = None
		self._name = None
		self._type = None

		#other
		self.translators = None
		self.seriesInfo = None

	@property
	def id(self):
		if self._id is None:
			self._id = self.extractId()
		return self._id

	@property
	def name(self):
		if self._name is None:
			self._name = self.getName()
		return self._name

	@property
	def type(self):
		if self._type is None:
			self._type = self.getType()
		return self._type

	def getPage(self):
		return requests.get(self.url, headers=self.HEADERS)

	def getSoup(self):
		return BeautifulSoup(self.page.content, 'html.parser')

	def extractId(self):
		element = self.soup.find(id="post_id")
		if not element:
			raise ValueError("Не вдалося витягти ID")
		return element.attrs['value']

	def getName(self):
		element = self.soup.find(class_="b-post__title")
		if not element:
			return "Назву не знайдено"
		return element.get_text().strip()

	def getType(self):
		element = self.soup.find('meta', property="og:type")
		if not element:
			return "video.unknown"
		return element.attrs['content']

	@staticmethod
	def clearTrash(data):
		# Додаємо перевірку типу
		if not isinstance(data, str):
			print(f"Warning: clearTrash received {type(data)}, expected str")
			return str(data)
		
		if not data or data.strip() == "":
			print("Warning: clearTrash received empty data")
			return ""
		
		try:
			trashList = ["@","#","!","^","$"]
			trashCodesSet = []
			for i in range(2,4):
				startchar = ''
				for chars in product(trashList, repeat=i):
					data_bytes = startchar.join(chars).encode("utf-8")
					trashcombo = base64.b64encode(data_bytes)
					trashCodesSet.append(trashcombo)

			arr = data.replace("#h", "").split("//_//")
			trashString = ''.join(arr)

			for i in trashCodesSet:
				temp = i.decode("utf-8")
				trashString = trashString.replace(temp, '')

			finalString = base64.b64decode(trashString+"==")
			return finalString.decode("utf-8")
		except Exception as e:
			print(f"Error in clearTrash: {e}")
			return data

	def getTranslations(self):
		arr = {}
		translators = self.soup.find(id="translators-list")
		if translators:
			children = translators.findChildren(recursive=False)
			for child in children:
				if child.text:
					arr[child.text] = child.attrs['data-translator_id']

		if not arr:
			#auto-detect
			def getTranslationName(s):
				table = s.find(class_="b-post__info")
				if table:
					for i in table.findAll("tr"):
						tmp = i.get_text()
						if tmp.find("переводе") > 0:
							return tmp.split("В переводе:")[-1].strip()
				return "Оригінал"
			
			def getTranslationID(s):
				try:
					initCDNEvents = {'video.tv_series': 'initCDNSeriesEvents',
									 'video.movie'    : 'initCDNMoviesEvents'}
					tmp = s.text.split(f"sof.tv.{initCDNEvents[self.type]}")[-1].split("{")[0]
					return tmp.split(",")[1].strip()
				except:
					return "1"

			arr[getTranslationName(self.soup)] = getTranslationID(self.page)

		self.translators = arr
		return arr

	@staticmethod
	def getEpisodes(s, e):
		seasons = BeautifulSoup(s, 'html.parser')
		episodes = BeautifulSoup(e, 'html.parser')

		seasons_ = {}
		for season in seasons.findAll(class_="b-simple_season__item"):
			seasons_[ season.attrs['data-tab_id'] ] = season.text

		episodes_ = {}
		for episode in episodes.findAll(class_="b-simple_episode__item"):
			if episode.attrs['data-season_id'] in episodes_:
				episodes_[episode.attrs['data-season_id']] [ episode.attrs['data-episode_id'] ] = episode.text
			else:
				episodes_[episode.attrs['data-season_id']] = {episode.attrs['data-episode_id']: episode.text}

		return seasons_, episodes_

	def getSeasons(self):
		if not self.translators:
			self.translators = self.getTranslations()

		arr = {}
		for i in self.translators:
			js = {
				"id": self.id,
				"translator_id": self.translators[i],
				"action": "get_episodes"
			}
			try:
				r = requests.post("https://rezka.ag/ajax/get_cdn_series/", data=js, headers=self.HEADERS)
				response = r.json()
				if response['success']:
					seasons, episodes = self.getEpisodes(response['seasons'], response['episodes'])
					arr[i] = {
						"translator_id": self.translators[i],
						"seasons": seasons, "episodes": episodes
					}
			except Exception as e:
				print(f"Error getting seasons for translator {i}: {e}")
				continue
		
		self.seriesInfo = arr
		return arr

	def getStream(self, season=None, episode=None, translation=None, index=0):

		def makeRequest(data):
			try:
				r = requests.post("https://rezka.ag/ajax/get_cdn_series/", data=data, headers=self.HEADERS)
				r = r.json()

				if r['success']:
					# Перевіряємо, чи є url у відповіді
					if 'url' not in r or not r['url']:
						print("No URL in response")
						return None
					
					# Очищаємо URL від сміття
					cleaned_url = self.clearTrash(r['url'])
					if not cleaned_url:
						print("Failed to clean URL")
						return None
					
					arr = cleaned_url.split(",")
					stream = HdRezkaStream(season, episode)
					
					for i in arr:
						try:
							if "[" in i and "]" in i:
								res = i.split("[")[1].split("]")[0]
								video = i.split("[")[1].split("]")[1].split(" or ")[1]
								stream.append(res, video)
						except Exception as e:
							print(f"Error parsing video quality: {e}")
							continue
					
					return stream
				else:
					print(f"Request failed: {r}")
					return None
			except Exception as e:
				print(f"Error in makeRequest: {e}")
				return None

		def getStreamSeries(self, season, episode, translation_id):
			if not (season and episode):
				raise TypeError("getStream() missing required arguments (season and episode)")
			
			season = str(season)
			episode = str(episode)

			if not self.seriesInfo:
				self.getSeasons()
			
			if not self.seriesInfo:
				raise ValueError("No series info available")

			seasons = self.seriesInfo

			# Знаходимо назву перекладача за ID
			tr_str = None
			for name, tid in self.translators.items():
				if tid == translation_id:
					tr_str = name
					break
			
			if not tr_str or tr_str not in seasons:
				raise ValueError(f'Translation with ID "{translation_id}" not found')

			if not season in list(seasons[tr_str]['episodes']):
				raise ValueError(f'Season "{season}" is not defined')

			if not episode in list(seasons[tr_str]['episodes'][season]):
				raise ValueError(f'Episode "{episode}" is not defined')

			return makeRequest({
				"id": self.id,
				"translator_id": translation_id,
				"season": season,
				"episode": episode,
				"action": "get_stream"
			})

		def getStreamMovie(self, translation_id):
			return makeRequest({
				"id": self.id,
				"translator_id": translation_id,
				"action": "get_movie"
			})

		if not self.translators:
			self.translators = self.getTranslations()

		if translation:
			if translation.isnumeric():
				if translation in self.translators.values():
					tr_id = translation
				else:
					raise ValueError(f'Translation with code "{translation}" is not defined')
			elif translation in self.translators:
				tr_id = self.translators[translation]
			else:
				raise ValueError(f'Translation "{translation}" is not defined')
		else:
			tr_id = list(self.translators.values())[index]

		if self.type == "video.tv_series":
			return getStreamSeries(self, season, episode, tr_id)
		elif self.type == "video.movie":
			return getStreamMovie(self, tr_id)
		else:
			raise TypeError("Undefined content type")