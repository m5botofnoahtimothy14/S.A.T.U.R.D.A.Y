"""Tray + silent-boot proofs. No boot executed (icon.run blocks); safe offline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_tray_icon_draws():
    from saturday.tray import _draw_icon
    im = _draw_icon(active=True)
    assert im.size == (64, 64)
    assert im.getbbox() is not None, "icon is fully transparent"


def test_tray_menu_builds():
    from saturday.tray import _menu
    m = _menu()
    labels = [i.text for i in m]
    for want in ("Open Control Center", "Status", "Glow on", "Glow off",
                 "Share on (phone link)", "Quit SATURDAY"):
        assert want in labels, f"menu item missing: {want}"


def test_glow_signal_bus():
    from saturday import edgeglow as eg
    assert eg.signal("speaking", 1.0) is False, "no instance: must be silent no-op"
    assert eg.STATES["speaking"]["bands"] >= 1


def test_launcher_exists():
    root = Path(__file__).parent.parent
    assert (root / "Saturday.pyw").exists()
    assert (root / "scripts" / "install_autostart.ps1").exists()


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("TRAY GREEN")
