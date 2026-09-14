from sincro.gui_main import requested_pyspark_module


def test_requested_pyspark_module_detects_worker():
    assert (
        requested_pyspark_module(["sincro.exe", "-m", "pyspark.worker"])
        == "pyspark.worker"
    )


def test_requested_pyspark_module_ignores_normal_start():
    assert requested_pyspark_module(["sincro.exe"]) is None


# @hugaojanuario


def test_gui_main_propagates_desktop_exit_code(monkeypatch):
    from sincro import gui_main
    from sincro.desktop import app
    monkeypatch.setattr(gui_main, 'freeze_support', lambda: None)
    monkeypatch.setattr(gui_main.sys, 'argv', ['sincro', '--demo'])
    monkeypatch.setattr(app, 'main', lambda: 3)
    assert gui_main.main() == 3
