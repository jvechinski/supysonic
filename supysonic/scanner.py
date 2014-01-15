# coding: utf-8

import os, os.path
import time, mimetypes

from tags import MetaTag, CoverTag
import config, db

def get_mime(ext):
    return mimetypes.guess_type('dummy.' + ext, False)[0] or config.get('mimetypes', ext) or 'application/octet-stream'

class Scanner:
    def __init__(self, session):
        self.__session = session
        self.__tracks  = db.Track.query.all()
        self.__albums = db.Album.query.all()
        self.__artists = db.Artist.query.all()
        self.__folders = db.Folder.query.all()
        self.__cover_art = db.CoverArt.query.all()

        #for cover_art in self.__cover_art:
        #    print '{0} {0.path} {0.id}'.format(cover_art)

        #for track in self.__tracks:
        #    print '{0} {0.path} {0.cover_art} {0.cover_art_id} {0.album} {0.album_id}'.format(track)

        #for folder in self.__folders:
        #    print '{0} {0.path} {0.cover_art} {0.cover_art_id}'.format(folder)

        #raise Hell

        self.__added_artists = 0
        self.__added_albums  = 0
        self.__added_tracks  = 0
        self.__added_folders  = 0
        self.__added_cover_art = 0
        self.__deleted_artists = 0
        self.__deleted_albums  = 0
        self.__deleted_tracks  = 0
        self.__deleted_folders  = 0
        self.__deleted_cover_art = 0

        extensions = config.get('base', 'scanner_extensions')
        self.__extensions = map(str.lower, extensions.split()) if extensions else None

    def scan(self, folder):
        for root, subfolders, files in os.walk(unicode(folder.path)):
            for f in files:
                path = os.path.join(root, f)
                if self.__is_valid_path(path):
                    this_folder = self.__find_folder(path, folder)
                    self.__scan_file(path, folder, this_folder)
        folder.last_scan = int(time.time())

    def prune(self, folder):
        # TODO Fix this!
        return
        
        for track in [ t for t in self.__tracks if t.root_folder.id == folder.id and not self.__is_valid_path(t.path) ]:
            self.__remove_track(track)

        for album in [ album for artist in self.__artists for album in artist.albums if len(album.tracks) == 0 ]:
            album.artist.albums.remove(album)
            self.__session.delete(album)
            self.__deleted_albums += 1

        for artist in [ a for a in self.__artists if len(a.albums) == 0 ]:
            self.__session.delete(artist)
            self.__deleted_artists += 1

        self.__cleanup_folder(folder)

    def check_cover_art(self, folder):
        folder.has_cover_art = os.path.isfile(os.path.join(folder.path, 'cover.jpg'))
        for f in folder.children:
            self.check_cover_art(f)

    def __is_valid_path(self, path):
        if not os.path.exists(path):
            return False
        if not self.__extensions:
            return True
        return os.path.splitext(path)[1][1:].lower() in self.__extensions

    def __scan_file(self, path, root_folder, this_folder):
        print path
        tr = filter(lambda t: t.path == path, self.__tracks)
        if tr:
            tr = tr[0]
            if not os.path.getmtime(path) > tr.last_modification:
                return

            try:
                tag = MetaTag(path)
            except:
                self.__remove_track(tr)
                return
        else:
            try:
                tag = MetaTag(path)
            except:
                return

            tr = db.Track(path = path, root_folder = root_folder, 
                folder = this_folder)
            self.__tracks.append(tr)
            self.__added_tracks += 1

        tr.disc     = getattr(tag, 'discnumber', 1)
        tr.number   = getattr(tag, 'tracknumber', 1)
        tr.title    = getattr(tag, 'title', '')
        tr.year     = getattr(tag, 'year', None)
        tr.genre    = getattr(tag, 'genre', None)
        tr.duration = tag.length
        tr.artist   = self.__find_artist(getattr(tag, 'artist', ''))                                                                            
        #print 'Track artist:', tr.artist
        tr.album    = self.__find_album(getattr(tag, 'album', ''),  
                                        tr.artist,
                                        this_folder)        
        tr.bitrate  = tag.bitrate
        tr.content_type = get_mime(os.path.splitext(path)[1][1:])
        tr.last_modification = os.path.getmtime(path)
        
        #try:
        cover_tag = CoverTag(path)
        if getattr(cover_tag, 'data', None):
            tr.cover_art = self.__find_cover_art(path, 
                is_embedded=True, data=cover_tag.data)

            #print 'Track cover art:', tr.cover_art

            # Also add the cover art to the album if it doesn't 
            # already have any.
            if getattr(tr.album, 'cover_art', None) is None:
                tr.album.cover_art = tr.cover_art
                
            # Also add the cover art to this track's folder if
            # it doesn't have any already.
            if getattr(tr.folder, 'cover_art', None) is None:
                tr.folder.cover_art = tr.cover_art
                print 'Folder cover art: ', tr.folder.cover_art                
        #except:    
        #    pass

    def __find_album(self, album, artist, folder):
        if config.get('base', 'one_album_per_folder'):
            al = filter(lambda a: a.folder == folder, self.__albums)
            if al:
                return al[0]
        else:
            al = filter(lambda a: a.name == album, artist.albums)
            if al:
                return al[0]

        al = db.Album(name = album, artist = artist, folder = folder)
        self.__albums.append(al)
        self.__session.add(al)
        self.__added_albums += 1

        return al

    def __find_artist(self, artist):
        ar = filter(lambda a: a.name.lower() == artist.lower(), self.__artists)
        if ar:
            return ar[0]

        ar = db.Artist(name = artist)
        self.__artists.append(ar)
        self.__session.add(ar)
        self.__added_artists += 1

        return ar

    def __find_folder(self, path, folder):
        path = os.path.dirname(path)
        fold = filter(lambda f: f.path == path, self.__folders)
        if fold:
            return fold[0]

        full_path = folder.path
        path = path[len(folder.path) + 1:]

        for name in path.split(os.sep):
            full_path = os.path.join(full_path, name)
            fold = filter(lambda f: f.path == full_path, self.__folders)
            if fold:
                folder = fold[0]
            else:
                folder = db.Folder(root = False, name = name, path = full_path, parent = folder)
                self.__folders.append(folder)
                self.__added_folders += 1

        return folder

    def __find_cover_art(self, path, is_embedded = False, data = None):
        # If this is not embedded cover art (i.e. a separate image
        # alongside the music files), then search for an existing
        # file by path.
        if not is_embedded:
            
            c = filter(lambda c: c.path == path, self.__cover_art)            
            if c:
                return c[0]

            hash_value = db.CoverArt.calculate_hash(path=path)
        
        # If this is embedded cover art, then we calculate a hash
        # value over the data, and search for existing cover art
        # with this same hash (unique id)
        # (reason: multiple tracks or albums may have the same album
        # art embedded... no sense creating multiple entries).
        else:
            hash_value = db.CoverArt.calculate_hash(path=path, data=data)
            
            c = filter(lambda c: c.hash_value == hash_value, self.__cover_art)            
            if c:
                return c[0]            

        cover_art = db.CoverArt(path=path, is_embedded=is_embedded, 
            hash_value=hash_value)
        self.__cover_art.append(cover_art)
        self.__added_cover_art += 1
        
        return cover_art

    def __remove_track(self, track):
        track.album.tracks.remove(track)
        track.folder.tracks.remove(track)
        # As we don't have a track -> playlists relationship, SQLAlchemy doesn't know it has to remove tracks
        # from playlists as well, so let's help it
        for playlist in db.Playlist.query.filter(db.Playlist.tracks.contains(track)):
            playlist.tracks.remove(track)
        self.__session.delete(track)
        self.__deleted_tracks += 1

    def __cleanup_folder(self, folder):
        for f in folder.children:
            self.__cleanup_folder(f)
        if len(folder.children) == 0 and len(folder.tracks) == 0 and not folder.root:
            folder.parent = None
            self.__session.delete(folder)

    def stats(self):
        return (self.__added_artists, self.__added_albums, self.__added_tracks), (self.__deleted_artists, self.__deleted_albums, self.__deleted_tracks)

