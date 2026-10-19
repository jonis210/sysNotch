"""Fetch line-synced lyrics for the active media track with multi-tier fuzzy matching."""

from __future__ import annotations

import json
import re
import time
from difflib import SequenceMatcher
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PyQt6.QtCore import QThread, pyqtSignal


API_ROOT = "https://lrclib.net/api"
REQUEST_TIMEOUT_SECONDS = 6.5
MAX_RESPONSE_BYTES = 2_000_000
TIMESTAMP_PATTERN = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
OFFSET_PATTERN = re.compile(r"\[offset:([+-]?\d+)\]", re.IGNORECASE)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _normalize(value: str) -> str:
    """Lowercase alphanumeric stripping for fuzzy comparison."""
    return "".join(character for character in value.casefold() if character.isalnum())


def _clean_track_title(title: str, artist: str = "") -> str:
    """Thoroughly strip streaming metadata noise like (feat. ...), [Official Video], - Remastered, etc."""
    # 1. Strip leading artist prefix or trailing artist suffix if player passed combined "Artist - Song Title" or "Song Title - Artist"
    if artist:
        art_clean = artist.strip().casefold()
        prim_art = _extract_primary_artist(artist).casefold()
        if title.casefold().startswith(f"{art_clean} - "):
            title = title[len(art_clean) + 3 :].strip()
        elif prim_art and title.casefold().startswith(f"{prim_art} - "):
            title = title[len(prim_art) + 3 :].strip()
        if title.casefold().endswith(f" - {art_clean}"):
            title = title[: -(len(art_clean) + 3)].strip()
        elif prim_art and f" - {prim_art}" in title.casefold():
            idx = title.casefold().rfind(f" - {prim_art}")
            title = title[:idx].strip()

    # 2. Strip parenthesized or bracketed tag noise
    cleaned = re.sub(
        r"\s*[\(\[][^\)\]]*(?:feat|ft\.|with|bonus|official|remaster|live|acoustic|deluxe|remix|mix|version|edit|extended|radio|special|prod|ost|audio|video|lyrics?|visualizer|sped|slowed|jedag|breakbeat|clean)[^\)\]]*[\)\]]",
        "",
        title,
        flags=re.IGNORECASE,
    )
    # 3. Strip hyphenated tag suffixes (e.g. " - Remastered 2021", " - Special Remix", " - Clean Ver.", " - Artist feat. ...")
    cleaned = re.sub(
        r"\s*-\s*.*?(?:remaster|live|acoustic|radio edit|from|deluxe|extended|remix|mix|edit|single|ep|original|special|clean|ver|version|instrumental|feat|ft\.).*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # 4. Strip stray parentheses or brackets
    cleaned = re.sub(r"[\(\)\[\]]", "", cleaned)
    return cleaned.strip() or title



def _extract_primary_artist(artist: str) -> str:
    """Extract lead artist before collaboration separators (comma, &, feat, ft, x, with)."""
    parts = re.split(
        r"[,&/]|(?:\s+feat\.?|\s+ft\.?|\s+with|\s+x\s+|\s+featuring\s+)",
        artist,
        flags=re.IGNORECASE,
    )
    return parts[0].strip() if parts else artist.strip()


def _title_similarity(target: str, candidate: str) -> float:
    """Compute title similarity with bidirectional containment bonus."""
    nt = _normalize(target)
    nc = _normalize(candidate)
    if not nt or not nc:
        return 0.0
    if nt == nc:
        return 1.0
    if nt in nc or nc in nt:
        shorter = min(len(nt), len(nc))
        longer = max(len(nt), len(nc))
        return 0.85 + 0.15 * (shorter / longer)
    return SequenceMatcher(None, nt, nc).ratio()


def _artist_similarity(target: str, candidate: str) -> float:
    """Compute artist similarity taking lead artists and collaborators into account."""
    nt = _normalize(target)
    nc = _normalize(candidate)
    if not nt or not nc:
        return 0.0
    if nt == nc or nt in nc or nc in nt:
        return 1.0
    tp = _normalize(_extract_primary_artist(target))
    cp = _normalize(_extract_primary_artist(candidate))
    if tp and cp and (tp == cp or tp in cp or cp in tp):
        return 0.95
    return SequenceMatcher(None, nt, nc).ratio()


def _inject_instrumental_breaks(
    cues: list[tuple[float, str]], duration: float = 0.0, min_gap: float = 12.0
) -> list[tuple[float, str]]:
    """Inject Spotify-style musical note cues ('♪') only for true instrumental solos and interludes."""
    if not cues:
        return []

    cues = sorted(set(cues), key=lambda cue: cue[0])
    result: list[tuple[float, str]] = []

    # 1. Intro break check: only if substantial instrumental intro (>= 14.0 seconds)
    first_t, first_text = cues[0]
    if first_t >= 14.0 and first_text != "♪":
        intro_t = round(first_t / 2.0, 2)
        result.append((intro_t, "♪"))

    # 2. Interludes between lyric lines: only for real instrumental bridges/solos (>= 12.0s gap)
    for i in range(len(cues)):
        cur_t, cur_text = cues[i]
        result.append((cur_t, cur_text))

        if i < len(cues) - 1:
            next_t, next_text = cues[i + 1]
            gap = next_t - cur_t

            if cur_text == "♪" or next_text == "♪":
                continue

            if gap >= min_gap:
                words = len(cur_text.split())
                singing_est = max(3.0, min(6.0, words * 0.45 + 1.2))
                t_break = round(cur_t + singing_est, 2)
                result.append((t_break, "♪"))

    # 3. Outro break check: only if long instrumental outro (>= 16.0 seconds remaining)
    if result and duration > 0 and result[-1][1] != "♪":
        last_t, last_text = result[-1]
        if duration - last_t >= 16.0:
            words = len(last_text.split())
            singing_est = max(3.0, min(6.0, words * 0.45 + 1.2))
            t_outro = round(last_t + singing_est, 2)
            result.append((t_outro, "♪"))

    return sorted(set(result), key=lambda cue: cue[0])


def _parse_synced_lyrics(value: str, duration: float = 0.0) -> list[tuple[float, str]]:
    """Parse standard LRC timestamps into sorted (seconds, lyric) rows with instrumental breaks."""
    if not value:
        return []

    offset_match = OFFSET_PATTERN.search(value)
    offset_seconds = int(offset_match.group(1)) / 1000.0 if offset_match else 0.0
    cues: list[tuple[float, str]] = []

    for raw_line in value.splitlines():
        timestamps = list(TIMESTAMP_PATTERN.finditer(raw_line))
        if not timestamps:
            continue
        lyric = TIMESTAMP_PATTERN.sub("", raw_line)
        lyric = OFFSET_PATTERN.sub("", lyric).strip()
        if not lyric or lyric.lower() in (
            "♪",
            "♫",
            "♩",
            "(instrumental)",
            "[instrumental]",
            "instrumental",
            "...",
        ):
            cue_text = "♪"
        else:
            cue_text = lyric

        for match in timestamps:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            fraction = match.group(3) or "0"
            fractional_seconds = int(fraction) / (10 ** len(fraction))
            timestamp = max(
                0.0,
                minutes * 60.0 + seconds + fractional_seconds + offset_seconds,
            )
            cues.append((timestamp, cue_text))

    return _inject_instrumental_breaks(cues, duration)


class LyricsFetcher(QThread):
    """Perform lyrics network requests away from the UI and media polling threads."""

    result_ready = pyqtSignal(dict)

    def __init__(
        self,
        track_key: tuple[str, str, str],
        title: str,
        artist: str,
        album: str,
        duration: float,
        parent=None,
    ):
        super().__init__(parent)
        self.track_key = track_key
        self.title = title
        self.artist = artist
        self.album = album
        self.duration = max(0.0, float(duration))

    def run(self) -> None:
        try:
            cues, status = self._fetch()
        except Exception:
            cues, status = [], "error"
        self.result_ready.emit(
            {"key": self.track_key, "cues": cues, "status": status}
        )

    def _request_json(self, endpoint: str, params: dict[str, str | float]) -> list | dict | None:
        """Fetch JSON from LRCLIB with timeout, retry on transient rate-limiting, and error safety."""
        query = urlencode(params)
        request = Request(
            f"{API_ROOT}/{endpoint}?{query}",
            headers=BROWSER_HEADERS,
        )

        for attempt in range(2):
            try:
                with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                    payload = response.read(MAX_RESPONSE_BYTES + 1)
                if len(payload) > MAX_RESPONSE_BYTES:
                    return None
                return json.loads(payload.decode("utf-8"))
            except HTTPError as error:
                if error.code == 404:
                    return None
                if error.code in (429, 503) and attempt == 0:
                    time.sleep(0.4)
                    continue
                return None
            except (URLError, TimeoutError, OSError):
                if attempt == 0:
                    time.sleep(0.3)
                    continue
                return None
            except Exception:
                return None
        return None

    def _fetch(self) -> tuple[list[tuple[float, str]], str]:
        if not self.title.strip() or not self.artist.strip():
            return [], "not_found"

        clean_title = _clean_track_title(self.title, self.artist)
        primary_artist = _extract_primary_artist(self.artist)
        exact_has_unsynced = False

        # --- STAGE 1: Exact /api/get (Metadata Lookup) ---
        if self.album.strip() and self.duration > 0:
            for q_title in set([self.title, clean_title]):
                for q_artist in set([self.artist, primary_artist]):
                    exact = self._request_json(
                        "get",
                        {
                            "track_name": q_title,
                            "artist_name": q_artist,
                            "album_name": self.album,
                            "duration": self.duration,
                        },
                    )
                    if isinstance(exact, dict):
                        synced = exact.get("syncedLyrics")
                        if synced:
                            cues = _parse_synced_lyrics(synced, self.duration)
                            if cues:
                                return cues, "ready"
                        if exact.get("plainLyrics"):
                            exact_has_unsynced = True

        # --- STAGE 2: Multi-Tier Search Ladder ---
        search_queries: list[str] = []
        # Tier 1: Clean Title + Primary Artist (highest hit rate for collabs and clean songs)
        q1 = f"{clean_title} {primary_artist}".strip()
        if q1:
            search_queries.append(q1)
        # Tier 2: Clean Title + Full Artist (for established duos/groups)
        q2 = f"{clean_title} {self.artist}".strip()
        if q2 and q2 not in search_queries:
            search_queries.append(q2)
        # Tier 3: Raw Title + Primary Artist (if raw title had relevant tags)
        q3 = f"{self.title} {primary_artist}".strip()
        if q3 and q3 not in search_queries:
            search_queries.append(q3)
        # Tier 4: Clean Title Only (critical fallback for covers and unique song names)
        if clean_title and clean_title not in search_queries:
            search_queries.append(clean_title)

        candidates: list[dict] = []
        seen_ids: set[int | str] = set()

        for query in search_queries:
            res = self._request_json("search", {"q": query})
            if isinstance(res, list) and res:
                for item in res:
                    if not isinstance(item, dict):
                        continue
                    item_id = item.get("id")
                    if item_id not in seen_ids:
                        seen_ids.add(item_id)
                        candidates.append(item)
                # If we have at least one valid candidate with synced lyrics, avoid flooding the API
                if any(item.get("syncedLyrics") for item in res):
                    break

        if not candidates:
            return [], ("unsynced" if exact_has_unsynced else "not_found")

        # --- STAGE 3: Smart Hybrid Scoring ---
        best_record = None
        best_score = -1.0
        has_unsynced_match = False

        for record in candidates:
            if not isinstance(record, dict):
                continue
            record_title = str(record.get("trackName") or "")
            record_artist = str(record.get("artistName") or "")

            title_score = max(
                _title_similarity(self.title, record_title),
                _title_similarity(clean_title, record_title),
                _title_similarity(clean_title, _clean_track_title(record_title)),
            )
            artist_score = max(
                _artist_similarity(self.artist, record_artist),
                _artist_similarity(primary_artist, record_artist),
            )

            # Smooth duration scoring with realistic tolerances
            record_duration = record.get("duration")
            duration_score = 0.0
            if isinstance(record_duration, (int, float)) and self.duration > 0:
                diff = abs(float(record_duration) - self.duration)
                if diff > 45.0:
                    # Allow up to 65s difference if title and artist match strongly (>0.85)
                    if not (title_score >= 0.90 and artist_score >= 0.80 and diff <= 65.0):
                        continue
                duration_score = max(0.0, 1.0 - diff / 45.0)

            # Rejection thresholds
            if title_score < 0.65 or artist_score < 0.35:
                # If song title is a 95%+ exact match (e.g. cover version or alternate spelling),
                # allow it as a candidate rather than showing no lyrics at all.
                if not (title_score >= 0.95 and artist_score >= 0.15):
                    continue

            score = title_score * 0.55 + artist_score * 0.30 + duration_score * 0.15
            if record.get("syncedLyrics") and score > best_score:
                best_record = record
                best_score = score
            elif record.get("plainLyrics"):
                has_unsynced_match = True

        if best_record:
            cues = _parse_synced_lyrics(best_record.get("syncedLyrics") or "", self.duration)
            if cues:
                return cues, "ready"

        if has_unsynced_match or exact_has_unsynced:
            return [], "unsynced"
        return [], "not_found"
