from app.camera import CameraDetector


def test_debounce_uses_first_confirmed_entry_frame_timestamp():
    calls = []
    cam = CameraDetector(lambda: {"camera": {}}, lambda marker, gate, source, at_ms: calls.append((marker, gate, source, at_ms)))
    cam._update_gate(1, "START", True, enter_frames=2, release_frames=2, frame_at_ms=1000)
    assert calls == []
    cam._update_gate(1, "START", True, enter_frames=2, release_frames=2, frame_at_ms=1033)
    assert calls == [(1, "START", "camera", 1000)]
    # Staying inside remains latched.
    cam._update_gate(1, "START", True, enter_frames=2, release_frames=2, frame_at_ms=1066)
    assert len(calls) == 1
    # Must leave for two frames before re-arming.
    cam._update_gate(1, "START", False, enter_frames=2, release_frames=2, frame_at_ms=1099)
    cam._update_gate(1, "START", False, enter_frames=2, release_frames=2, frame_at_ms=1132)
    cam._update_gate(1, "START", True, enter_frames=2, release_frames=2, frame_at_ms=1200)
    cam._update_gate(1, "START", True, enter_frames=2, release_frames=2, frame_at_ms=1233)
    assert calls[-1][-1] == 1200
    assert len(calls) == 2
