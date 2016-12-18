import urllib

import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmc
from resources.lib.router import Router, expander
import resources.lib.bc as bc
import sys

addon = xbmcaddon.Addon()
language = addon.getLocalizedString
addon_id = addon.getAddonInfo('id')
icon = addon.getAddonInfo('icon')
fanart = addon.getAddonInfo('fanart')
addon_version = addon.getAddonInfo('version')
current_path = sys.argv[0]
handle = int(sys.argv[1])
query = sys.argv[2]

current_path = current_path + query

dbg = True
try:
    import StorageServer

    print 'real storage'
except ImportError:
    import storageserverdummy as StorageServer

    print 'dummy storage'

cache = StorageServer.StorageServer(addon_id, 24)

router = Router(host="plugin://%s" % (addon_id,))


class PluginHelper(object):
    def __init__(self, handle):
        self.handle = handle

    def listingAction(self, func):
        def inner(*args):
            items = func(*args)
            if items is None:
                print args
            else:
                xbmcplugin.addDirectoryItems(self.handle, items)
            xbmcplugin.endOfDirectory(self.handle)

        return inner


plghelper = PluginHelper(handle)


def album_to_listitem(album):
    artist_datatype = type(album.artist)
    artist_name = album.artist if artist_datatype is str or artist_datatype is unicode else album.artist.name
    label = "Album: %s by %s" % (album.title, artist_name)
    return router.make('album', {'url': album.url}), xbmcgui.ListItem(label, '', album.cover, album.cover), True


def band_to_listitem(band):
    label = "Band: %s (%s)" % (band.name, band.type)
    return router.make('artist', dict(url=band.url)), xbmcgui.ListItem(label, '', band.image, band.image), True


def track_to_listitem(track):
    #return router.make('album', {'url': track.url}), xbmcgui.ListItem(track.title), False
    #label = "Track: %s" % (track.title,)
    item = xbmcgui.ListItem(label=track.title, thumbnailImage=track.album.cover if track.album is not None else None)
    artist_name = track.artist if type(track.artist) is str else track.artist.name

    item.setInfo(type='music', infoLabels=dict(Title=track.title, Artist=artist_name))
    return track.stream_url, item, False

settings_username = 'username'
settings_firstrun = 'firstrun'

me = addon.getSetting(settings_username)
firstrun = addon.getSetting(settings_firstrun)


if me == '' and firstrun == 'true':
    addon.setSetting(settings_firstrun, "false")
    addon.openSettings()
    me = addon.getSetting(settings_username)


anon = True if me == "" else False


@router.route('home', R"^/$", expander("/"))
@plghelper.listingAction
def home(params, parts, route):
    print params, parts, route
    return filter(lambda x: x is not None, [
        #(router.make('discover'), xbmcgui.ListItem('discover', 'discover-2'), True),
        (router.make('search'), xbmcgui.ListItem('search', 'search-2'), True),
        (router.make('user', {"username": me}), xbmcgui.ListItem('user', 'user-2'), True) if not anon else None,
    ])


#@router.route('discover', R"^/discover$", expander("/discover"))
@plghelper.listingAction
#def discover(params, parts, route):
#    return []


@router.route('search', R"^/search$", expander("/search{?query}"))
@plghelper.listingAction
def search(params, parts, route):
    if "query" not in params:
        kb = xbmc.Keyboard()
        kb.doModal()
        if kb.isConfirmed():
            return search(dict(query=kb.getText()), parts, route)
        else:
            return []
    else:
        results = bc.get_search_results(params["query"])
        # print results
        ret = []
        for item in results:
            if type(item) is bc.Album:
                ret.append(album_to_listitem(item))
            #if type(item) is bc.Track:
            #    ret.append(track_to_listitem(item))
            if type(item) is bc.Band:
                ret.append(band_to_listitem(item))

        # results = [item for item in ret if item is not None]
        # print ret
        return ret


@router.route('own-collection', R"^/own/collection$", expander("/own/collection"))
def owncollection(params, parts, route):
    return usercollection({"username": me}, parts, route)


@router.route('user-collection', R"^/user/(?P<username>.*?)/collection$", expander("/user/{username}/collection"))
@plghelper.listingAction
def usercollection(params, parts, route):
    albums = bc.get_collection(params["username"])
    return [album_to_listitem(album) for album in albums]


@router.route('own-wishlist', R"^/own/wishlist$", expander("/own/wishlist"))
def ownwishlist(params, parts, route):
    return userwishlist({"username": me}, parts, route)


@router.route('user-wishlist', R"^/user/(?P<username>.*?)/wishlist$", expander("/user/{username}/wishlist"))
@plghelper.listingAction
def userwishlist(params, parts, route):
    albums = bc.get_wishlist(params["username"])
    return [album_to_listitem(album) for album in albums]

@router.route('own-following', R"^/own/following", expander("/own/following"))
def ownfollowing(params, parts, route):
    return usercollection({"username": me}, parts, route)

@router.route('user-following', R"^/user/(?P<username>.*?)/following", expander("/user/{username}/following"))
@plghelper.listingAction
def userfollowing(params, parts, route):
    bands = bc.get_following(params["username"])
    return [band_to_listitem(band) for band in bands]

@router.route('album', R"^/album$", expander("/album{?url}"))
@plghelper.listingAction
def albumlist(params, parts, route):
    album_url = urllib.unquote(params["url"][0])
    print "getting album: %s" % album_url
    tracks = bc.get_album_tracks(album_url)
    return [track_to_listitem(track) for track in tracks]


@router.route('user', R"^/user/(?P<username>[^/]*?)$", expander("/user/{username}"))
@plghelper.listingAction
def user(params, parts, route):
    return [
        (router.make('user-collection', {"username": params["username"]}), xbmcgui.ListItem("collection"), True),
        (router.make('user-wishlist', {"username": params["username"]}), xbmcgui.ListItem("wishlist"), True),
        (router.make('user-following', {"username": params["username"]}), xbmcgui.ListItem("following"), True),
    ]


@router.route('artist', R"^/artist$", expander("/artist{?url}"))
@plghelper.listingAction
def artist(params, parts, route):
    artist = bc.get_band_by_url(urllib.unquote(params["url"][0]))
    ret = [
        (router.make('artist-albums', dict(url=params["url"])), xbmcgui.ListItem("Albums"), True),
    ]
    if artist.recommended_url:
        ret.append(
            (router.make('artist-recommeded', dict(url=params["url"])), xbmcgui.ListItem("Recommended"), True),
        )
    return ret


@router.route('artist-albums', R"^/artist-albums$", expander("/artist-albums{?url}"))
@plghelper.listingAction
def artist_albums(params, parts, route):
    url = urllib.unquote(urllib.unquote(params["url"][0]))
    albums = bc.get_band_music_by_url(url)

    return [album_to_listitem(item) for item in albums if type(item) is bc.Album]


print "current path: %s" % current_path
print "handle: %d" % handle

router.run(current_path)
