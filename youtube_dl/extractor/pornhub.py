# coding: utf-8
from __future__ import unicode_literals

import functools
import itertools
import operator
# import os
import re

from .common import InfoExtractor
from ..compat import (
    compat_HTTPError,
    # compat_urllib_parse_unquote,
    # compat_urllib_parse_unquote_plus,
    # compat_urllib_parse_urlparse,
)
from ..utils import (
    ExtractorError,
    int_or_none,
    js_to_json,
    orderedSet,
    # sanitized_Request,
    str_to_int,
)
# from ..aes import (
#     aes_decrypt_text
# )


class PornHubIE(InfoExtractor):
    IE_DESC = 'PornHub and Thumbzilla'
    _VALID_URL = r'''(?x)
                    https?://
                        (?:
                            (?:[a-z]+\.)?pornhub\.com/(?:view_video\.php\?viewkey=|embed/)|
                            (?:www\.)?thumbzilla\.com/video/
                        )
                        (?P<id>[\da-z]+)
                    '''
    _TESTS = [{
        'url': 'http://www.pornhub.com/view_video.php?viewkey=648719015',
        'md5': '1e19b41231a02eba417839222ac9d58e',
        'info_dict': {
            'id': '648719015',
            'ext': 'mp4',
            'title': 'Seductive Indian beauty strips down and fingers her pink pussy',
            'uploader': 'Babes',
            'duration': 361,
            'view_count': int,
            'like_count': int,
            'dislike_count': int,
            'comment_count': int,
            'age_limit': 18,
            'tags': list,
            'categories': list,
        },
    }, {
        # non-ASCII title
        'url': 'http://www.pornhub.com/view_video.php?viewkey=1331683002',
        'info_dict': {
            'id': '1331683002',
            'ext': 'mp4',
            'title': '重庆婷婷女王足交',
            'uploader': 'cj397186295',
            'duration': 1753,
            'view_count': int,
            'like_count': int,
            'dislike_count': int,
            'comment_count': int,
            'age_limit': 18,
            'tags': list,
            'categories': list,
        },
        'params': {
            'skip_download': True,
        },
    }, {
        'url': 'http://www.pornhub.com/view_video.php?viewkey=ph557bbb6676d2d',
        'only_matching': True,
    }, {
        # removed at the request of cam4.com
        'url': 'http://fr.pornhub.com/view_video.php?viewkey=ph55ca2f9760862',
        'only_matching': True,
    }, {
        # removed at the request of the copyright owner
        'url': 'http://www.pornhub.com/view_video.php?viewkey=788152859',
        'only_matching': True,
    }, {
        # removed by uploader
        'url': 'http://www.pornhub.com/view_video.php?viewkey=ph572716d15a111',
        'only_matching': True,
    }, {
        # private video
        'url': 'http://www.pornhub.com/view_video.php?viewkey=ph56fd731fce6b7',
        'only_matching': True,
    }, {
        'url': 'https://www.thumbzilla.com/video/ph56c6114abd99a/horny-girlfriend-sex',
        'only_matching': True,
    }]

    @staticmethod
    def _extract_urls(webpage):
        return re.findall(
            r'<iframe[^>]+?src=["\'](?P<url>(?:https?:)?//(?:www\.)?pornhub\.com/embed/[\da-z]+)',
            webpage)

    def _extract_count(self, pattern, webpage, name):
        return str_to_int(self._search_regex(
            pattern, webpage, '%s count' % name, fatal=False))

    def _real_extract(self, url):
        video_id = self._match_id(url)

        def dl_webpage(platform):
            return self._download_webpage(
                'http://www.pornhub.com/view_video.php?viewkey=%s' % video_id,
                video_id, headers={
                    'Cookie': 'age_verified=1; platform=%s' % platform,
                })

        webpage = dl_webpage('pc')

        error_msg = self._html_search_regex(
            r'(?s)<div[^>]+class=(["\'])(?:(?!\1).)*\b(?:removed|userMessageSection)\b(?:(?!\1).)*\1[^>]*>(?P<error>.+?)</div>',
            webpage, 'error message', default=None, group='error')
        if error_msg:
            error_msg = re.sub(r'\s+', ' ', error_msg)
            raise ExtractorError(
                'PornHub said: %s' % error_msg,
                expected=True, video_id=video_id)

        tv_webpage = dl_webpage('tv')

        encoded_url = self._search_regex(r'(var.*mediastring.*)</script>',
            tv_webpage, 'encoded url')
        assignments = encoded_url.split(";")
        js_vars = {}

        def parse_js_value(inp):
            inp = re.sub(r'/\*[^*]*\*/', "", inp)

            if "+" in inp:
                inps = inp.split("+")
                return functools.reduce(operator.concat, map(parse_js_value, inps))

            inp = inp.strip()
            if inp in js_vars:
                return js_vars[inp]

            # Hope it's a string!
            assert inp.startswith('"') and inp.endswith('"')
            return inp[1:-1]

        for assn in assignments:
            assn = assn.strip()
            if len(assn) == 0:
                continue

            assert assn.startswith("var ")
            assn = assn[4:]
            vname, value = assn.split("=", 1)

            js_vars[vname] = parse_js_value(value)

        video_url = js_vars["mediastring"]

        title = self._search_regex(
            r'<h1>([^>]+)</h1>', tv_webpage, 'title', default=None)

        # video_title from flashvars contains whitespace instead of non-ASCII (see
        # http://www.pornhub.com/view_video.php?viewkey=1331683002), not relying
        # on that anymore.
        title = title or self._html_search_meta(
            'twitter:title', webpage, default=None) or self._search_regex(
            (r'<h1[^>]+class=["\']title["\'][^>]*>(?P<title>[^<]+)',
             r'<div[^>]+data-video-title=(["\'])(?P<title>.+?)\1',
             r'shareTitle\s*=\s*(["\'])(?P<title>.+?)\1'),
            webpage, 'title', group='title')

        flashvars = self._parse_json(
            self._search_regex(
                r'var\s+flashvars_\d+\s*=\s*({.+?});', webpage, 'flashvars', default='{}'),
            video_id)
        if flashvars:
            thumbnail = flashvars.get('image_url')
            duration = int_or_none(flashvars.get('video_duration'))
        else:
            title, thumbnail, duration = [None] * 3

        video_uploader = self._html_search_regex(
            r'(?s)From:&nbsp;.+?<(?:a href="/users/|a href="/channels/|span class="username)[^>]+>(.+?)<',
            webpage, 'uploader', fatal=False)

        view_count = self._extract_count(
            r'<span class="count">([\d,\.]+)</span> views', webpage, 'view')
        like_count = self._extract_count(
            r'<span class="votesUp">([\d,\.]+)</span>', webpage, 'like')
        dislike_count = self._extract_count(
            r'<span class="votesDown">([\d,\.]+)</span>', webpage, 'dislike')
        comment_count = self._extract_count(
            r'All Comments\s*<span>\(([\d,.]+)\)', webpage, 'comment')

        page_params = self._parse_json(self._search_regex(
            r'page_params\.zoneDetails\[([\'"])[^\'"]+\1\]\s*=\s*(?P<data>{[^}]+})',
            webpage, 'page parameters', group='data', default='{}'),
            video_id, transform_source=js_to_json, fatal=False)
        tags = categories = None
        if page_params:
            tags = page_params.get('tags', '').split(',')
            categories = page_params.get('categories', '').split(',')

        return {
            'id': video_id,
            'url': video_url,
            'uploader': video_uploader,
            'title': title,
            'thumbnail': thumbnail,
            'duration': duration,
            'view_count': view_count,
            'like_count': like_count,
            'dislike_count': dislike_count,
            'comment_count': comment_count,
            # 'formats': formats,
            'age_limit': 18,
            'tags': tags,
            'categories': categories,
        }


class PornHubPlaylistBaseIE(InfoExtractor):
    def _extract_entries(self, webpage):
        return [
            self.url_result(
                'http://www.pornhub.com/%s' % video_url,
                PornHubIE.ie_key(), video_title=title)
            for video_url, title in orderedSet(re.findall(
                r'href="/?(view_video\.php\?.*\bviewkey=[\da-z]+[^"]*)"[^>]*\s+title="([^"]+)"',
                webpage))
        ]

    def _real_extract(self, url):
        playlist_id = self._match_id(url)

        webpage = self._download_webpage(url, playlist_id)

        # Only process container div with main playlist content skipping
        # drop-down menu that uses similar pattern for videos (see
        # https://github.com/rg3/youtube-dl/issues/11594).
        container = self._search_regex(
            r'(?s)(<div[^>]+class=["\']container.+)', webpage,
            'container', default=webpage)

        entries = self._extract_entries(container)

        playlist = self._parse_json(
            self._search_regex(
                r'playlistObject\s*=\s*({.+?});', webpage, 'playlist'),
            playlist_id)

        return self.playlist_result(
            entries, playlist_id, playlist.get('title'), playlist.get('description'))


class PornHubPlaylistIE(PornHubPlaylistBaseIE):
    _VALID_URL = r'https?://(?:www\.)?pornhub\.com/playlist/(?P<id>\d+)'
    _TESTS = [{
        'url': 'http://www.pornhub.com/playlist/4667351',
        'info_dict': {
            'id': '4667351',
            'title': 'Nataly Hot',
        },
        'playlist_mincount': 2,
    }]


class PornHubUserVideosIE(PornHubPlaylistBaseIE):
    _VALID_URL = r'https?://(?:www\.)?pornhub\.com/users/(?P<id>[^/]+)/videos'
    _TESTS = [{
        'url': 'http://www.pornhub.com/users/zoe_ph/videos/public',
        'info_dict': {
            'id': 'zoe_ph',
        },
        'playlist_mincount': 171,
    }, {
        'url': 'http://www.pornhub.com/users/rushandlia/videos',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        user_id = self._match_id(url)

        entries = []
        for page_num in itertools.count(1):
            try:
                webpage = self._download_webpage(
                    url, user_id, 'Downloading page %d' % page_num,
                    query={'page': page_num})
            except ExtractorError as e:
                if isinstance(e.cause, compat_HTTPError) and e.cause.code == 404:
                    break
            page_entries = self._extract_entries(webpage)
            if not page_entries:
                break
            entries.extend(page_entries)

        return self.playlist_result(entries, user_id)
