from pathlib import Path

import pytest

from recommendations.lastfm import prepare_sample, read_listens, user_bucket


def test_reader_parses_utc_and_preserves_distinct_track_ids(tmp_path: Path):
    source = tmp_path / "input.tsv"
    source.write_text(
        "u\t2009-01-01T00:00:00Z\ta\tArtist\tt1\tSame name\n"
        "u\t2009-01-02T00:00:00Z\ta\tArtist\tt2\tSame name\n",
        encoding="utf-8",
    )
    events = list(read_listens(source))
    assert [event.track_id for event in events] == ["t1", "t2"]
    assert events[0].timestamp.isoformat() == "2009-01-01T00:00:00+00:00"


def test_sample_is_deterministic_and_counts_missing_ids(tmp_path: Path):
    source = tmp_path / "input.tsv"
    output = tmp_path / "sample.tsv"
    source.write_text(
        "u\t2009-01-01T00:00:00Z\ta\tArtist\tt1\tTrack\n"
        "u\t2009-01-02T00:00:00Z\ta\tArtist\t\tUnknown\n",
        encoding="utf-8",
    )
    counts = prepare_sample(source, output, 1, 0)
    assert counts == {"source_events": 2, "selected_events": 2, "missing_track_mbid": 1, "written_events": 1}
    assert len(list(read_listens(output))) == 1
    assert user_bucket("u", 100) == user_bucket("u", 100)


def test_reader_rejects_malformed_rows(tmp_path: Path):
    source = tmp_path / "input.tsv"
    source.write_text("u\tbad\ta\tArtist\tt\tTrack\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 1: invalid timestamp"):
        list(read_listens(source))


def test_sample_cannot_overwrite_source(tmp_path: Path):
    source = tmp_path / "input.tsv"
    source.write_text("content", encoding="utf-8")
    with pytest.raises(ValueError, match="must differ"):
        prepare_sample(source, source, 1, 0)
    assert source.read_text(encoding="utf-8") == "content"
