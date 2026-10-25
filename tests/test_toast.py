from ui import toast


def test_persistent_toast_does_not_expire_until_replaced(monkeypatch):
    for key, value in toast._s.copy().items():
        monkeypatch.setitem(toast._s, key, value)

    monkeypatch.setattr(toast, "_load", lambda text, kind, persistent: toast._s.update(
        text=text, kind=kind, persistent=persistent
    ))
    monkeypatch.setattr(toast, "_paint", lambda opacity, rise: None)
    now = [100.0]
    monkeypatch.setattr(toast.time, "time", lambda: now[0])

    toast._s.update(
        pending=("Checking for system updates...", "info", True),
        mode="idle",
        t0=0.0,
        persistent=False,
    )
    toast._step()

    now[0] += toast.TOAST_SECONDS + 1
    toast._step()
    assert toast._s["mode"] == "hold"
    assert toast._s["persistent"] is True

    toast._s["pending"] = ("AYAWrus is up to date", "success", False)
    toast._step()
    assert toast._s["persistent"] is False
