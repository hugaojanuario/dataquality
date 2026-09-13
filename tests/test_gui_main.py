from dataqualy.gui_main import requested_pyspark_module


def test_requested_pyspark_module_detects_worker():
    assert (
        requested_pyspark_module(["dataqualy.exe", "-m", "pyspark.worker"])
        == "pyspark.worker"
    )


def test_requested_pyspark_module_ignores_normal_start():
    assert requested_pyspark_module(["dataqualy.exe"]) is None


# @hugaojanuario


def test_gui_main_propagates_desktop_exit_code(monkeypatch):
    from dataqualy import gui_main
    from dataqualy.desktop import app
    monkeypatch.setattr(gui_main, 'freeze_support', lambda: None)
    monkeypatch.setattr(gui_main.sys, 'argv', ['dataqualy', '--demo'])
    monkeypatch.setattr(app, 'main', lambda: 3)
    assert gui_main.main() == 3
