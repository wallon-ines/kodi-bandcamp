__author__ = 'thesebas'

from bs4 import BeautifulSoup
import urllib2
from urlparse import urlparse, urlunparse
from ..router import expander
import re
import json
import resources.lib.demjson as demjson
from ..utils import Memoize, MeasureTime

collection_url_tpl = expander("https://bandcamp.com/{username}?mvp=p")
wishlist_url_tpl = expander("https://bandcamp.com/{username}/wishlist?mvp=p")
following_url_tpl = expander("https://bandcamp.com/{username}/following?mvp=p")
albumcover_url_tpl = expander('https://f1.bcbits.com/img/a{albumartid}_9.jpg')
search_url_tpl = expander('https://bandcamp.com/search{?q}')


class Band(object):
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', '')
        self.url = kwargs.get('url', '')
        self.image = kwargs.get('image', '')
        self.type = kwargs.get('type', '')
        self.recommended_url = False

    def __str__(self):
        return "<Band name=%s url=%s image=%s>" % (self.name, self.url, self.image)

        # def hasRecommended(self):
        #     return self.recommended_url

class Album(object):
    def __init__(self, **kwargs):
        self.cover = kwargs.get("cover", '')
        self.title = kwargs.get("title", '')
        self.url = kwargs.get("url", '')
        self.artist = kwargs.get("artist", '')

    def __str__(self):
        return "<Album artist=%s, title=%s, cover=%s, url=%s>" % (self.artist, self.title, self.cover, self.url)

    # def __repr__(self):
    #     return 'Album(artist="%s", title="%s", cover="%s", url="%s")' % (self.artist, self.title, self.cover, self.url)

    @staticmethod
    def unserialize(data):
        if type(data) == Album:
            return data
        else:
            return Album(**data)


class Track(object):
    def __init__(self, album, **kwargs):
        self.title = kwargs.get("title", '')
        self.artist = kwargs.get("artist", '')
        self.track_url = kwargs.get("track_url", '')
        self.stream_url = kwargs.get("stream_url", '')
        self.album = album

    def __str__(self):
        return "<Track artist=%s, album=%s, title=%s, track_url=%s>" % (self.artist, self.album, self.title,  self.track_url)


@MeasureTime
@Memoize
def load_url(url):
    res = urllib2.urlopen(url)
    return res.read()


@MeasureTime
def li_to_album(li):
    cover = li.find('img', class_='collection-item-art')["src"]
    info = li.find('div', class_='collection-item-details-container')
    title = info.find('div', class_='collection-item-title').string
    artist = info.find('div', class_='collection-item-artist').string
    url = li.find('a', class_='item-link')['href']
    artist = artist[3:]
    # print li.prettify('utf-8')
    return Album(title=title, artist=artist, cover=cover, url=url)


@MeasureTime
def li_to_band(li):
    image = li.find('img', class_='lazy')['data-original']
    info = li.find('div', class_='band-name')
    name = info.find('a').string
    url = info.find('a')['href']

    return Band(name=name, url=url, image=image)


@MeasureTime
def tralbumdata_to_track(data):
    if data["file"] is None:  # not playable files
        return None
    stream_url_parts = urlparse(data["file"]["mp3-128"])
    stream_url = urlunparse(("http", stream_url_parts.netloc, stream_url_parts.path, '', stream_url_parts.query, ''))
    return Track(None, title=data["title"], artist="", track_url=data["title_link"], stream_url=stream_url)


@MeasureTime
def itemdetail_to_album(detail):
    return Album(url=detail["item_url"], artist=detail["band_name"], title=detail["item_title"],
                 cover=albumcover_url_tpl({"albumartid": detail["item_art_id"]}))


@MeasureTime
def li_to_searchresult(li):
    if "band" in li["class"]:
        name = li.find('div', class_='result-info').find('div', class_='heading').a.string.strip()
        artcont = li.find('a', class_='artcont')
        image = artcont.div.img['src']
        url_parts = urlparse(artcont['href'])
        url = urlunparse((url_parts.scheme, url_parts.netloc, '/', '', '', ''))
        bandtype = li.find('div', class_='result-info').find('div', class_='itemtype').string.strip()
        return Band(name=name, image=image, url=url, type=bandtype)
    elif "album" in li["class"]:
        url = li.find('a', class_='artcont')["href"]
        title = li.find('div', class_='result-info').find('div', class_='heading').a.string.strip()
        cover = li.find('div', class_='art').img['src']
        return Album(url=url, title=title, cover=cover)
    elif "track" in li["class"]:
        return Track(None)

    return None


@MeasureTime
def get_wishlist(user):
    url = wishlist_url_tpl({"username": user})
    body = load_url(url)
    m = re.search("^\s+item_details: (.*),$", body, re.M)
    if m:
        data = json.loads(m.group(1))
        return [itemdetail_to_album(detail) for id, detail in data.iteritems()]
    return []


@MeasureTime
def get_following(user):
    url = following_url_tpl({"username": user})
    body = load_url(url)
    soup = BeautifulSoup(body, 'html.parser')

    lis = soup.find(None, id='following-artists-container').find_all('li', class_='follow-grid-item')
    return [li_to_band(li) for li in lis]


@MeasureTime
def get_collection(user):
    url = collection_url_tpl({"username": user})
    body = load_url(url)
    soup = BeautifulSoup(body, 'html.parser')

    return [li_to_album(li) for li in soup.find_all('li', class_='collection-item-container')]


@MeasureTime
def get_album_tracks(url):
    body = load_url(url)
    #print body
    m = re.search("trackinfo: (.*),", body, re.M)
    #print m
    if m:
        data = json.loads(m.group(1))
        #print data
        m = re.search('artist: "(.*)"', body, re.M)
        artist = m.group(1)
        tracks = [track for track in [tralbumdata_to_track(track) for track in data] if track is not None]
        album = get_album_by_url(url)
        def fill_data(track):
            track.artist = artist
            track.album = album
            return track

        return map(fill_data, tracks)

    return []


@MeasureTime
def get_search_results(query):
    print "searching for '%s'" % (query,)
    body = load_url(search_url_tpl(dict(q=query)))

    soup = BeautifulSoup(body, 'html.parser')
    return [item for item in [li_to_searchresult(li) for li in
                              soup.find('ul', class_='result-items').find_all('li', class_='searchresult')] if item]


@MeasureTime
@Memoize
def get_band_by_url(url):
    url_parts = urlparse(url, 'http')
    url = urlunparse((url_parts.scheme, url_parts.netloc, url_parts.path, None, "mvp=p", None))
    print "get_band_by_url", url

    body = load_url(url)
    soup = BeautifulSoup(body, 'html.parser')

    band_data = get_band_data_by_url(url)

    band = Band(name=band_data["name"], url=url)

    recommended = soup.find('div', class_='recommended')
    if recommended:
        recommended_url = recommended.a['href']
        band.recommended_url = recommended_url

    div = soup.find('div', class_='artists-bio-pic')
    if div:
        band.image = div.find('a', class_='popupImage')['href']

    return band


@MeasureTime
@Memoize
def get_album_data_by_url(url):
    body = load_url(url)
    m = re.search("var TralbumData = .*?current: ({.*}),\n.*?(is_preorder.*?)trackinfo ?:", body, re.S)
    data = json.loads(m.group(1))
    data.update(demjson.decode("{%s}" % (m.group(2),)))
    
    return data

def get_album_cover(url):
    body = load_url(url)
    #m = re.search("<a class=\"popupImage\" href=\"(.*?)\">", body, re.S)
    m = re.findall(r'<a class=\"popupImage\" href=\"(.*?)\">',body)[0]
    return m



@MeasureTime
@Memoize
def get_album_by_url(url):
    album_data = get_album_data_by_url(url)
    album_cover=get_album_cover(url)
    #album = Album(title=album_data['title'], cover=album_data["artFullsizeUrl"])
    album = Album(title=album_data['title'],cover=album_cover)
    print album
    return album


@MeasureTime
@Memoize
def get_band_data_by_url(url):
    body = load_url(url)
    band_data = re.search("var BandData = ({.*?})[,;]\n", body, re.S)

    band_data = demjson.decode(band_data.group(1))

    return band_data


@MeasureTime
def get_band_music_by_url(url):
    body = load_url(url)
    soup = BeautifulSoup(body, 'html.parser')

    musicgrid = soup.find('ol', class_='music-grid')
    if musicgrid:
        return get_band_music_by_url_via_musicgrid(musicgrid, url)

    discography = soup.find('div', id='discography')
    if discography:
        return get_band_music_by_url_via_discography(discography, url)

    return []


@MeasureTime
def get_band_music_by_url_via_musicgrid(musicgrid, url):
    data = json.loads(musicgrid['data-initial-values'])
    band_data = get_band_data_by_url(url)

    url_parts = urlparse(url)
    items = []
    for item in data:
        if item['type'] == 'album':
            title = item['title']
            url = urlunparse((url_parts.scheme, url_parts.netloc, item["page_url"], '', '', ''))
            cover = albumcover_url_tpl(dict(albumartid=item["art_id"]))
            album = Album(title=title, url=url, cover=cover)
            if item['artist']:
                album.artist = item['artist']
            else:
                album.artist = band_data["name"]
            items.append(album)
        elif item['type'] == 'track':
            # todo, later...
            pass

    return items


@MeasureTime
def get_band_music_by_url_via_discography(discography, url):
    lis = discography.find('ul').find_all('li')

    band = get_band_by_url(url)

    def li2album(li):
        a = li.find('a', class_='thumbthumb')
        album_url = a['href']
        cover = a.find('img')['src']
        title = li.find('div', class_='trackTitle').find('a').string
        url_parts = urlparse(url)

        album_url = urlunparse((url_parts.scheme, url_parts.netloc, album_url, None, None, None))
        return Album(title=title, cover=cover, url=album_url, artist=band)

    return map(li2album, lis)
