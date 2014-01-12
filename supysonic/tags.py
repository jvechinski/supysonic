# This code comes from the ftranc (audio transcoding) project. 
# https://code.google.com/p/ftransc/   
# It can handle audio file data tags in a variety of formats.

# Some minor modifications were made to the original code to 
# handle things like automatically cleaning up track numbers
# and years.

import os
import mutagen
import mutagen.id3
import mutagen.mp3
import mutagen.asf
import mutagen.mp4
import mutagen.flac
import mutagen.musepack
import mutagen.oggvorbis

tags = {
        '.mp3': {
            'artist'      : 'TPE1',
            'album'       : 'TALB',
            'title'       : 'TIT2',
            'genre'       : 'TCON',
            'year'        : 'TDRC',
            'tracknumber' : 'TRCK',
            'discnumber'  : 'TPOS',
            'composer'    : 'TCOM',
            'publisher'   : 'TPUB',
        },
        '.wma': {
            'artist'      : 'Author',
            'album'       : 'WM/AlbumTitle',
            'title'       : 'Title',
            'genre'       : 'WM/Genre',
            'year'        : 'WM/Year',
            'tracknumber' : 'WM/TrackNumber',
            'composer'    : 'WM/Composer',
            'publisher'   : 'WM/Publisher',
            },
        '.wmv': {
            'artist'      : 'Author',
            'album'       : 'WM/AlbumTitle',
            'title'       : 'Title',
            'genre'       : 'WM/Genre',
            'year'        : 'WM/Year',
            'tracknumber' : 'WM/TrackNumber',
            'composer'    : 'WM/Composer',
            'publisher'   : 'WM/Publisher',
            },
        '.m4a': {
            'artist'      : '\xa9ART',
            'album'       : '\xa9alb',
            'title'       : '\xa9nam',
            'genre'       : '\xa9gen',
            'year'        : '\xa9day',
            'tracknumber' : 'trkn',
            'composer'    : '\xa9wrt',
            },
        '.ogg': {
            'artist'      : 'artist',
            'album'       : 'album',
            'title'       : 'title',
            'genre'       : 'genre',
            'year'        : 'date',
            'tracknumber' : 'tracknumber',
            'composer'    : 'composer',
            },
        '.flac': {
            'artist'      : 'artist',
            'album'       : 'album',
            'title'       : 'title',
            'genre'       : 'genre',
            'year'        : 'date',
            'tracknumber' : 'tracknumber',
            'composer'    : 'composer',
            },
        '.mpc': {
            'artist'      : 'Artist',
            'album'       : 'Album',
            'title'       : 'Title',
            'genre'       : 'Genre',
            'year'        : 'Year',
            'tracknumber' : 'Track',
            'composer'    : 'Composer',
            },
        }
    
class MetaTag(object):
    """
    handles tag extraction and insertion into and/or from audio files
    """
    __tag_mapping = tags.copy()
    
    __id3_mapping = {
        'artist'        : mutagen.id3.TPE1, 
        'album'         : mutagen.id3.TALB, 
        'title'         : mutagen.id3.TIT2, 
        'genre'         : mutagen.id3.TCON, 
        'year'          : mutagen.id3.TDRC, 
        'tracknumber'   : mutagen.id3.TRCK,
        'discnumber'    : mutagen.id3.TPOS,
        'composer'      : mutagen.id3.TCOM,
        'lyrics'        : mutagen.id3.USLT,
    }
    __opener = {
        '.mp3'          : mutagen.mp3.Open,
        '.wma'          : mutagen.asf.Open, 
        '.m4a'          : mutagen.mp4.Open, 
        '.flac'         : mutagen.flac.Open,
        '.mpc'          : mutagen.musepack.Open,
        '.ogg'          : mutagen.oggvorbis.Open, 
    }

    exts = (    
                '.ogg', 
                '.mp3', 
                '.flac', 
                '.mp4', 
                '.aac', 
                '.m4a',
                '.mpc', 
                '.wma', 
                '.wmv',
           )

    def __init__(self, input_file):
        self.input_file = input_file
        self.tags = {
                'title'         : None, 
                'artist'        : None, 
                'album'         : None, 
                'year'          : None, 
                'genre'         : None, 
                'tracknumber'   : None,
                'discnumber'    : None,
                'composer'      : None,
                'lyrics'        : None,
                'length'        : None,
                'bitrate'       : None,                
        }
        self.extract()
    
    def extract(self):
        """
        extracts metadata tags from the audio file
        """
        tags = mutagen.File(self.input_file)
        
        ext = os.path.splitext(self.input_file)[1].lower()
        if ext in self.exts:
            for tag, key in self.__tag_mapping[ext].items():
                if key in tags:
                    self.tags[tag] = tags[key][0]
                elif tag == 'lyrics' and key == 'USLT':
                    for id3tag in tags:
                        if id3tag.startswith(key):
                            self.tags[tag] = tags[id3tag].text
        
        # Handle info tags specially
        self.tags['length'] = int(tags.info.length)
        self.tags['bitrate'] = (tags.info.bitrate 
            if hasattr(tags.info, 'bitrate') 
            else int(os.path.getsize(path) * 8 / tags.info.length)) / 1000
    
        # Convert string values to integers for certain tags, ignoring 
        # any non-integer characters.
        for key in ['year', 'tracknumber', 'discnumber']:
            if self.tags[key] is not None:
                self.tags[key] = int(str(self.tags[key]))
    
    
    def insert(self, output_file):
        """
        inserts tags tags into an audio file.
        """        
        ext = os.path.splitext(output_file)[1].lower()
        if ext not in self.__opener:
            return 1
        tags = self.__opener[ext](output_file)
        for tag, value in self.tags.items():
            if value is None or tag not in self.__tag_mapping[ext]:
                continue
            if tag == 'tracknumber' and \
                (isinstance(value, list) or isinstance(value, tuple)) and\
                len(value) == 2:
                value = '%d/%d' % (value[0], value[1])
            if ext == '.mp3':
                if tag == 'lyrics':
                    tags[self.__tag_mapping[ext][tag]] = \
                                    self.__id3_mapping[tag](encoding=3, 
                                                            lang='eng', 
                                                            desc='lyrics',
                                                            text=u'%s' % value)
                else:
                    tags[self.__tag_mapping[ext][tag]] = \
                                self.__id3_mapping[tag](encoding=3, 
                                                        text=[u'%s' % value])
            elif ext in self.exts and ext != '.mp3':
                if tag == 'tracknumber' and ext == '.m4a':
                    try:
                        trkn = [int(i) for i in str(value).split('/')]
                        tags[self.__tag_mapping[ext][tag]] = \
                                [(trkn[0], trkn[1])]
                    except IndexError:
                        tags[self.__tag_mapping[ext][tag]] = [(trkn[0], 0)]
                else:
                    tags[self.__tag_mapping[ext][tag]] = [u'%s' % value]
        tags.save()
        
    def __getattr__(self, name):
        if name in self.tags and self.tags[name] is not None:
            return self.tags[name]
        

class CoverTag(object):
    """
    Handles insertion or extraction of album cover art
    """

    __tag_mapping = {
                        '.mp3'  : 'APIC:',
                        '.m4a'  : 'covr',
                        '.wma'  : None,
                        '.ogg'  : 'metadata_block_picture',
                        '.flac' : 'metadata_block_picture',
                        '.mpc'  : None,
                    }

    def __init__(self, filename):
        self.coverart = {   
                            'mime'  : 'image/jpeg', 
                            'type'  : 3, 
                            'ext'   : None, 
                            'data'  : None,
                        }
        self.extract(filename)

    def extract(self, input_file):
        ext = os.path.splitext(input_file)[1]
        if ext not in self.__tag_mapping:
            return
        tag = self.__tag_mapping[ext]
        if tag is None:
            return
        
        tags = mutagen.File(input_file)
        if tag in tags:
            self.coverart['ext'] = ext
            if ext == '.mp3':
                apic = tags[tag]
                self.coverart['mime'] = apic.mime
                self.coverart['data'] = apic.data
            elif ext == '.m4a':
                self.coverart['data'] = tags[tag][0]
            elif ext in ('.ogg', '.flac'):
                encoded_image = tags[tag][0]
                image = mutagen.flac.Picture(base64.b64decode(encoded_image))
                self.coverart['data'] = image.data
                self.coverart['mime'] = image.mime
        elif ext == '.mp3':
            for key in tags:
                if key.startswith(tag):
                    apic = tags[key]
                    self.coverart['mime'] = apic.mime
                    self.coverart['data'] = apic.data

    def insert(self, output_file):
        ext = os.path.splitext(output_file)[1]
        if ext not in self.__tag_mapping:
            return
        tag = self.__tag_mapping[ext]
        if tag is None:
            return
        if self.coverart['data'] is None:
            return

        if ext == '.m4a':
            tags = mutagen.mp4.MP4(output_file)
            if self.coverart['ext'] == '.mp3':
                if self.coverart['mime'] == 'image/png':
                    mime = mutagen.mp4.MP4Cover.FORMAT_PNG
                else:
                    mime = mutagen.mp4.MP4Cover.FORMAT_JPEG
                
                coverart = mutagen.mp4.MP4Cover(self.coverart['data'], mime)
                tags['covr'] = [coverart]
                tags.save()
                return

        elif ext == '.mp3':
            audio = mutagen.mp3.MP3(output_file, ID3=mutagen.id3.ID3)
            if self.coverart['ext'] in ('.m4a', '.ogg', '.flac'):
                apic = mutagen.id3.APIC(
                                            desc     = u'',
                                            encoding = 3,
                                            data     = self.coverart['data'],
                                            type     = self.coverart['type'],
                                            mime     = self.coverart['mime']
                                       )
                audio.tags.add(apic)
                audio.save()
                return

    def __getattr__(self, name):
        if name in self.coverart and self.coverart[name] is not None:
            return self.coverart[name]
