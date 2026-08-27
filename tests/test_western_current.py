from scripts.update_western_locations import verification_times


def test_western_missing_flag_preserves_previous_verification():
    previous = {"last_verified_at": "2026-08-27T08:00:00-05:00"}
    class Now:
        def isoformat(self):
            return "2026-08-27T10:00:00-05:00"
    verified, checked = verification_times(previous, Now(), None)
    assert verified == previous["last_verified_at"]
    assert checked == "2026-08-27T10:00:00-05:00"


def test_western_explicit_flag_advances_verification():
    previous = {"last_verified_at": "2026-08-27T08:00:00-05:00"}
    class Now:
        def isoformat(self):
            return "2026-08-27T10:00:00-05:00"
    verified, checked = verification_times(previous, Now(), "Double Red")
    assert verified == "2026-08-27T10:00:00-05:00"
    assert checked == "2026-08-27T10:00:00-05:00"
