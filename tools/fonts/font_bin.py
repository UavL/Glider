#!/usr/bin/env python3
import pathlib
import struct


OSD_FONT_MAGIC = 0x46534F47
OSD_FONT_VERSION = 1
OSD_FONT_TYPE_PROPORTIONAL_ASCII = 1
OSD_FONT_PIXFMT_Y1 = 1
HEADER_WORDS = 9
HEADER_SIZE = HEADER_WORDS * 4


class FontFormatError(ValueError):
    pass


class Glyph:
    def __init__(self, width, rows):
        self.width = width
        self.rows = list(rows)


class FontBin:
    def __init__(self, height, offset, chars, glyph_words, glyphs):
        self.height = height
        self.offset = offset
        self.chars = chars
        self.glyph_words = glyph_words
        self.glyphs = glyphs

    @property
    def row_words(self):
        return (self.glyph_words - 1) // self.height

    @property
    def max_width(self):
        return self.row_words * 32

    @classmethod
    def from_file(cls, path):
        return cls.from_bytes(pathlib.Path(path).read_bytes())

    @classmethod
    def from_bytes(cls, data):
        if len(data) < HEADER_SIZE:
            raise FontFormatError("font file is too small for a Glider font header")

        header = struct.unpack_from("<9I", data, 0)
        magic, version, font_type, pixfmt, height, offset, chars, glyph_words, data_words = header

        if magic != OSD_FONT_MAGIC:
            raise FontFormatError("invalid Glider font magic")
        if version != OSD_FONT_VERSION:
            raise FontFormatError(f"unsupported Glider font version {version}")
        if font_type != OSD_FONT_TYPE_PROPORTIONAL_ASCII:
            raise FontFormatError("unsupported Glider font type")
        if pixfmt != OSD_FONT_PIXFMT_Y1:
            raise FontFormatError("unsupported Glider font pixel format")
        if height == 0:
            raise FontFormatError("font height must be non-zero")
        if chars == 0:
            raise FontFormatError("font must contain at least one glyph")
        if glyph_words < 2:
            raise FontFormatError("glyph records must contain width plus bitmap words")
        if (glyph_words - 1) % height != 0:
            raise FontFormatError("glyph bitmap words are not divisible by font height")
        if data_words != chars * glyph_words:
            raise FontFormatError("font data word count does not match glyph count")

        required = HEADER_SIZE + data_words * 4
        if len(data) < required:
            raise FontFormatError("font file is truncated")
        if len(data) != required:
            raise FontFormatError("font file has trailing data")

        words = struct.unpack_from("<" + "I" * data_words, data, HEADER_SIZE)
        glyphs = []
        row_words = (glyph_words - 1) // height
        for index in range(chars):
            start = index * glyph_words
            width = words[start]
            rows = words[start + 1:start + glyph_words]
            if width > row_words * 32:
                raise FontFormatError(f"glyph {index} width exceeds stored row capacity")
            glyphs.append(Glyph(width, rows))

        return cls(height, offset, chars, glyph_words, glyphs)

    def to_bytes(self):
        data_words = self.chars * self.glyph_words
        header = struct.pack(
            "<9I",
            OSD_FONT_MAGIC,
            OSD_FONT_VERSION,
            OSD_FONT_TYPE_PROPORTIONAL_ASCII,
            OSD_FONT_PIXFMT_Y1,
            self.height,
            self.offset,
            self.chars,
            self.glyph_words,
            data_words,
        )

        words = []
        for glyph in self.glyphs:
            if glyph.width > self.max_width:
                raise ValueError("glyph width exceeds stored row capacity")
            if len(glyph.rows) != self.height * self.row_words:
                raise ValueError("glyph bitmap row count does not match font geometry")
            words.append(glyph.width)
            words.extend(glyph.rows)

        return header + struct.pack("<" + "I" * len(words), *words)

    def write_file(self, path):
        pathlib.Path(path).write_bytes(self.to_bytes())

    def characters(self):
        return [chr(self.offset + index) for index in range(self.chars)]

    def index_for_char(self, ch):
        if isinstance(ch, str):
            if len(ch) != 1:
                raise ValueError("glyph character must be exactly one codepoint")
            codepoint = ord(ch)
        else:
            codepoint = int(ch)

        index = codepoint - self.offset
        if index < 0 or index >= self.chars:
            raise ValueError(f"character U+{codepoint:04X} is not in this font")
        return index

    def glyph(self, ch):
        return self.glyphs[self.index_for_char(ch)]

    def _row_word_index(self, x, y):
        if x < 0 or x >= self.max_width:
            raise ValueError("x coordinate is outside stored glyph width")
        if y < 0 or y >= self.height:
            raise ValueError("y coordinate is outside glyph height")
        return y * self.row_words + (x // 32)

    def get_pixel(self, ch, x, y):
        glyph = self.glyph(ch)
        word = glyph.rows[self._row_word_index(x, y)]
        return (word & (0x80000000 >> (x % 32))) != 0

    def set_pixel(self, ch, x, y, value):
        glyph = self.glyph(ch)
        row_index = self._row_word_index(x, y)
        mask = 0x80000000 >> (x % 32)
        if value:
            glyph.rows[row_index] |= mask
        else:
            glyph.rows[row_index] &= ~mask

    def set_width(self, ch, width):
        width = int(width)
        if width < 1 or width > self.max_width:
            raise ValueError(f"glyph width must be between 1 and {self.max_width}")
        self.glyph(ch).width = width
