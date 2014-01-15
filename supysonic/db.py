# coding: utf-8

import config

from sqlalchemy import create_engine, Table, Column, ForeignKey, func
from sqlalchemy import Integer, String, Boolean, DateTime
from sqlalchemy.orm import scoped_session, sessionmaker, relationship, backref
from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.types import TypeDecorator, BINARY
from sqlalchemy.dialects.postgresql import UUID as pgUUID

import uuid, datetime, time, hashlib
import os.path
 
class UUID(TypeDecorator):
    """Platform-somewhat-independent UUID type

    Uses Postgresql's UUID type, otherwise uses BINARY(16),
    should be more efficient than a CHAR(32).

    Mix of http://stackoverflow.com/a/812363
    and http://www.sqlalchemy.org/docs/core/types.html#backend-agnostic-guid-type
    """

    impl = BINARY

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(pgUUID())
        else:
            return dialect.type_descriptor(BINARY(16))

    def process_bind_param(self, value, dialect):
        if value and isinstance(value, uuid.UUID):
            if dialect.name == 'postgresql':
                return str(value)
            return value.bytes
        if value and not isinstance(value, uuid.UUID):
            raise ValueError, 'value %s is not a valid uuid.UUID' % value
        return None

    def process_result_value(self, value, dialect):
        if value:
            if dialect.name == 'postgresql':
                return uuid.UUID(value)
            return uuid.UUID(bytes = value)
        return None

    def is_mutable(self):
        return False

    @staticmethod
    def gen_id_column():
        return Column(UUID, primary_key = True, default = uuid.uuid4)

def now():
    return datetime.datetime.now().replace(microsecond = 0)

Base = declarative_base()

class User(Base):
    __tablename__ = 'user'

    id = UUID.gen_id_column()
    name = Column(String(64), unique = True)
    mail = Column(String(256))
    password = Column(String(40))
    salt = Column(String(6))
    admin = Column(Boolean, default = False)
    lastfm_session = Column(String(32), nullable = True)
    lastfm_status = Column(Boolean, default = True) # True: ok/unlinked, False: invalid session

    last_play_id = Column(UUID, ForeignKey('track.id'), nullable = True)
    last_play = relationship('Track')
    last_play_date = Column(DateTime, nullable = True)

    def as_subsonic_user(self):
        return {
            'username': self.name,
            'email': self.mail,
            'scrobblingEnabled': self.lastfm_session is not None and self.lastfm_status,
            'adminRole': self.admin,
            'settingsRole': True,
            'downloadRole': True,
            'uploadRole': False,
            'playlistRole': True,
            'coverArtRole': False,
            'commentRole': False,
            'podcastRole': False,
            'streamRole': True,
            'jukeboxRole': False,
            'shareRole': False
        }

class CoverArt(Base):
    __tablename__ = 'cover_art'

    id = UUID.gen_id_column()
    path = Column(String(4096))
    hash_value = Column(String(256))
    is_embedded = Column(Boolean, default = False)
    hello = Column(String(256))
       
    @staticmethod
    def calculate_hash(path=None, data=None):
        if not data:
            data = file(path, 'rb').read() 
        
        hv = hashlib.sha1(data).hexdigest()
        
        return hv

class Folder(Base):
    __tablename__ = 'folder'

    id = UUID.gen_id_column()
    root = Column(Boolean, default = False)
    name = Column(String(256))
    path = Column(String(4096)) # should be unique, but mysql don't like such large columns
    created = Column(DateTime, default = now)
    last_scan = Column(Integer, default = 0)
    cover_art_id = Column(UUID, ForeignKey('cover_art.id'), nullable = True)
    cover_art = relationship('CoverArt', primaryjoin = CoverArt.id == cover_art_id)    

    parent_id = Column(UUID, ForeignKey('folder.id'), nullable = True)
    children = relationship('Folder', backref = backref('parent', remote_side = [ id ]))

    def as_subsonic_child(self, user):
        info = {
            'id': str(self.id),
            'isDir': True,
            'title': self.name,
            'album': self.name,
            'created': self.created.isoformat()
        }
        if not self.root:
            info['parent'] = str(self.parent_id)
            info['artist'] = self.parent.name
            
        if self.cover_art_id:
            info['coverArt'] = str(self.cover_art_id)

        starred = StarredFolder.query.get((user.id, self.id))
        if starred:
            info['starred'] = starred.date.isoformat()

        rating = RatingFolder.query.get((user.id, self.id))
        if rating:
            info['userRating'] = rating.rating
        avgRating = RatingFolder.query.filter(RatingFolder.rated_id == self.id).value(func.avg(RatingFolder.rating))
        if avgRating:
            info['averageRating'] = avgRating

        return info

class Artist(Base):
    __tablename__ = 'artist'

    id = UUID.gen_id_column()
    name = Column(String(256), unique = True)
    cover_art_id = Column(UUID, ForeignKey('cover_art.id'), nullable = True)
    cover_art = relationship('CoverArt', primaryjoin = CoverArt.id == cover_art_id)    
    albums = relationship('Album', backref = 'artist')

    def as_subsonic_artist(self, user):
        info = {
            'id': str(self.id),
            'name': self.name,
            'albumCount': len(self.albums)
        }

        starred = StarredArtist.query.get((user.id, self.id))
        if starred:
            info['starred'] = starred.date.isoformat()

        if self.cover_art_id:
            info['coverArt'] = str(self.cover_art_id)

        return info

class Album(Base):
    __tablename__ = 'album'

    id = UUID.gen_id_column()
    name = Column(String(256))
    artist_id = Column(UUID, ForeignKey('artist.id'))
    cover_art_id = Column(UUID, ForeignKey('cover_art.id'), nullable = True)
    cover_art = relationship('CoverArt', primaryjoin = CoverArt.id == cover_art_id)    
    tracks = relationship('Track', backref = 'album')
    folder_id = Column(UUID, ForeignKey('folder.id'))
    folder = relationship('Folder', primaryjoin = Folder.id == folder_id)    

    def as_subsonic_album(self, user):
        info = {
            'id': str(self.id),
            'name': self.name,
            'artist': self.artist.name,
            'artistId': str(self.artist_id),
            'songCount': len(self.tracks),
            'duration': sum(map(lambda t: t.duration, self.tracks)),
            'created': min(map(lambda t: t.created, self.tracks)).isoformat()
        }
        if self.cover_art_id:
            info['coverArt'] = str(self.cover_art_id)

        starred = StarredAlbum.query.get((user.id, self.id))
        if starred:
            info['starred'] = starred.date.isoformat()

        return info

    def sort_key(self):
        year = min(map(lambda t: t.year if t.year else 9999, self.tracks))
        return '%i%s' % (year, self.name.lower())

class Track(Base):
    __tablename__ = 'track'

    id = UUID.gen_id_column()
    disc = Column(Integer)
    number = Column(Integer)
    title = Column(String(256))
    year = Column(Integer, nullable = True)
    genre = Column(String(256), nullable = True)
    duration = Column(Integer)
    album_id = Column(UUID, ForeignKey('album.id'))
    artist_id = Column(UUID, ForeignKey('artist.id'))
    artist = relationship('Artist', primaryjoin = Artist.id == artist_id)    
    bitrate = Column(Integer)
    
    cover_art_id = Column(UUID, ForeignKey('cover_art.id'), nullable = True)
    cover_art = relationship('CoverArt', primaryjoin = CoverArt.id == cover_art_id)    

    path = Column(String(4096)) # should be unique, but mysql don't like such large columns
    content_type = Column(String(32))
    created = Column(DateTime, default = now)
    last_modification = Column(Integer)

    play_count = Column(Integer, default = 0)
    last_play = Column(DateTime, nullable = True)

    root_folder_id = Column(UUID, ForeignKey('folder.id'))
    root_folder = relationship('Folder', primaryjoin = Folder.id == root_folder_id)
    folder_id = Column(UUID, ForeignKey('folder.id'))
    folder = relationship('Folder', primaryjoin = Folder.id == folder_id, backref = 'tracks')

    def as_subsonic_child(self, user, from_music_dir=False):
        info = {
            'id': str(self.id),
            'parent': str(self.folder.id),
            'isDir': False,
            'title': self.title,
            'album': self.album.name,
            'artist': self.artist.name,
            'track': self.number,
            'size': os.path.getsize(self.path),
            'contentType': self.content_type,
            'suffix': self.suffix(),
            'duration': self.duration,
            'bitRate': self.bitrate,
            'path': self.path[len(self.root_folder.path) + 1:],
            'isVideo': False,
            'discNumber': self.disc,
            'created': self.created.isoformat(),
            'albumId': str(self.album.id),
            'artistId': str(self.artist.id),
            'type': 'music'
        }

        if self.year:
            info['year'] = self.year
        if self.genre:
            info['genre'] = self.genre

        if self.cover_art_id:
            info['coverArt'] = str(self.cover_art_id)

        starred = StarredTrack.query.get((user.id, self.id))
        if starred:
            info['starred'] = starred.date.isoformat()

        rating = RatingTrack.query.get((user.id, self.id))
        if rating:
            info['userRating'] = rating.rating
        avgRating = RatingTrack.query.filter(RatingTrack.rated_id == self.id).value(func.avg(RatingTrack.rating))
        if avgRating:
            info['averageRating'] = avgRating

        # transcodedContentType
        # transcodedSuffix

        # This hack returns the same "album artist" for all tracks in a
        # folder to trick old clients that use the folder browse 
        # method and assume each new album name + artist name 
        # combination is a new album.
        if from_music_dir:
            info['artist'] = self.album.artist.name
            info['artistId'] = str(self.album.artist.id)

        return info

    def duration_str(self):
        ret = '%02i:%02i' % ((self.duration % 3600) / 60, self.duration % 60)
        if self.duration >= 3600:
            ret = '%02i:%s' % (self.duration / 3600, ret)
        return ret

    def suffix(self):
        return os.path.splitext(self.path)[1][1:].lower()

    def sort_key(self):
        return (self.album.name + 
            ("%02i" % self.disc) + ("%02i" % self.number) + 
            self.title).lower()
        
        # @note Original code is below... not sure why you would want
        # the artist name in there.  This totally goofs up things
        # when there is a "various artists" album.
        #return (self.album.artist.name + self.album.name + ("%02i" % self.disc) + ("%02i" % self.number) + self.title).lower()

class StarredFolder(Base):
    __tablename__ = 'starred_folder'

    user_id = Column(UUID, ForeignKey('user.id'), primary_key = True)
    starred_id = Column(UUID, ForeignKey('folder.id'), primary_key = True)
    date = Column(DateTime, default = now)

    user = relationship('User')
    starred = relationship('Folder')

class StarredArtist(Base):
    __tablename__ = 'starred_artist'

    user_id = Column(UUID, ForeignKey('user.id'), primary_key = True)
    starred_id = Column(UUID, ForeignKey('artist.id'), primary_key = True)
    date = Column(DateTime, default = now)

    user = relationship('User')
    starred = relationship('Artist')

class StarredAlbum(Base):
    __tablename__ = 'starred_album'

    user_id = Column(UUID, ForeignKey('user.id'), primary_key = True)
    starred_id = Column(UUID, ForeignKey('album.id'), primary_key = True)
    date = Column(DateTime, default = now)

    user = relationship('User')
    starred = relationship('Album')

class StarredTrack(Base):
    __tablename__ = 'starred_track'

    user_id = Column(UUID, ForeignKey('user.id'), primary_key = True)
    starred_id = Column(UUID, ForeignKey('track.id'), primary_key = True)
    date = Column(DateTime, default = now)

    user = relationship('User')
    starred = relationship('Track')

class RatingFolder(Base):
    __tablename__ = 'rating_folder'

    user_id = Column(UUID, ForeignKey('user.id'), primary_key = True)
    rated_id = Column(UUID, ForeignKey('folder.id'), primary_key = True)
    rating = Column(Integer)

    user = relationship('User')
    rated = relationship('Folder')

class RatingTrack(Base):
    __tablename__ = 'rating_track'

    user_id = Column(UUID, ForeignKey('user.id'), primary_key = True)
    rated_id = Column(UUID, ForeignKey('track.id'), primary_key = True)
    rating = Column(Integer)

    user = relationship('User')
    rated = relationship('Track')

class ChatMessage(Base):
    __tablename__ = 'chat_message'

    id = UUID.gen_id_column()
    user_id = Column(UUID, ForeignKey('user.id'))
    time = Column(Integer, default = lambda: int(time.time()))
    message = Column(String(512))

    user = relationship('User')

    def responsize(self):
        return {
            'username': self.user.name,
            'time': self.time * 1000,
            'message': self.message
        }

playlist_track_assoc = Table('playlist_track', Base.metadata,
    Column('playlist_id', UUID, ForeignKey('playlist.id')),
    Column('track_id', UUID, ForeignKey('track.id'))
)

class Playlist(Base):
    __tablename__ = 'playlist'

    id = UUID.gen_id_column()
    user_id = Column(UUID, ForeignKey('user.id'))
    name = Column(String(256))
    comment = Column(String(256), nullable = True)
    public = Column(Boolean, default = False)
    created = Column(DateTime, default = now)

    user = relationship('User')
    tracks = relationship('Track', secondary = playlist_track_assoc)

    def as_subsonic_playlist(self, user):
        info = {
            'id': str(self.id),
            'name': self.name if self.user_id == user.id else '[%s] %s' % (self.user.name, self.name),
            'owner': self.user.name,
            'public': self.public,
            'songCount': len(self.tracks),
            'duration': sum(map(lambda t: t.duration, self.tracks)),
            'created': self.created.isoformat()
        }
        if self.comment:
            info['comment'] = self.comment
        return info

engine = None
session = None

def init_db():
    global engine
    global session

    engine = create_engine(config.get('base', 'database_uri'), convert_unicode = True)
    session = scoped_session(sessionmaker(autocommit = False, autoflush = False, bind = engine))

    Base.query = session.query_property()

    Base.metadata.create_all(bind = engine)

def recreate_db():
    
    Base.metadata.drop_all(bind = engine)
    Base.metadata.create_all(bind = engine)
    
def get_session():
    return session    

