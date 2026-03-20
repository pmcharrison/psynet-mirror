import os

import pytest

from psynet.testing import chrome_driver


class FakeOptions:
    def __init__(self):
        self.arguments = []
        self.binary_location = None

    def add_argument(self, argument):
        self.arguments.append(argument)


class FakeService:
    def __init__(self, log_output, service_args):
        self.log_output = log_output
        self.service_args = service_args


class FakeDriver:
    def __init__(self):
        self.session_id = "session-id"
        self.capabilities = {
            "browserVersion": "1.0",
            "chrome": {"chromedriverVersion": "1.0"},
        }
        self.quit_calls = 0
        self.window_sizes = []

    def quit(self):
        self.quit_calls += 1

    def set_window_size(self, width, height):
        self.window_sizes.append((width, height))


class FakeWebDriver:
    def __init__(self, driver=None, launch_error=None):
        self.driver = driver
        self.launch_error = launch_error
        self.last_options = None
        self.last_service = None

    def Chrome(self, options, service):
        self.last_options = options
        self.last_service = service
        if self.launch_error is not None:
            raise self.launch_error
        return self.driver


def test_create_chrome_driver_sets_options_and_cleans_artifacts(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile"
    profile_path.mkdir()
    log_path = tmp_path / "chromedriver.log"
    log_path.write_text("chromedriver output", encoding="utf-8")

    def fake_mkdtemp(prefix):
        assert prefix == "psynet-chrome-"
        return str(profile_path)

    def fake_mkstemp(prefix, suffix):
        assert prefix == "psynet-chromedriver-"
        assert suffix == ".log"
        fd = os.open(log_path, os.O_RDWR)
        return fd, str(log_path)

    fake_driver = FakeDriver()
    fake_webdriver = FakeWebDriver(driver=fake_driver)

    monkeypatch.setenv("PSYNET_CHROMEDRIVER_VERBOSE", "1")
    monkeypatch.delenv("PSYNET_KEEP_CHROMEDRIVER_LOGS", raising=False)
    monkeypatch.setattr(chrome_driver.tempfile, "mkdtemp", fake_mkdtemp)
    monkeypatch.setattr(chrome_driver.tempfile, "mkstemp", fake_mkstemp)
    monkeypatch.setattr(chrome_driver, "_find_chrome_binary", lambda: "/usr/bin/chrome")
    monkeypatch.setattr(chrome_driver, "_append_debug_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(chrome_driver, "_count_psynet_chrome_profiles", lambda: 0)
    monkeypatch.setattr(chrome_driver, "list_psynet_chrome_processes", lambda: [])
    monkeypatch.setattr(chrome_driver, "list_chromedriver_processes", lambda: [])
    monkeypatch.setattr(
        chrome_driver,
        "_get_chrome_dependencies",
        lambda: (fake_webdriver, FakeOptions, FakeService),
    )

    driver = chrome_driver.create_psynet_chrome_driver(headless=True)

    assert "--disable-dev-shm-usage" in fake_webdriver.last_options.arguments
    assert "--no-sandbox" in fake_webdriver.last_options.arguments
    assert "--disable-gpu" in fake_webdriver.last_options.arguments
    assert "--remote-debugging-pipe" in fake_webdriver.last_options.arguments
    assert "--headless=new" in fake_webdriver.last_options.arguments
    assert (
        f"--user-data-dir={profile_path}" in fake_webdriver.last_options.arguments
    )
    assert fake_webdriver.last_options.binary_location == "/usr/bin/chrome"

    assert fake_webdriver.last_service.log_output == str(log_path)
    assert fake_webdriver.last_service.service_args == ["--verbose"]
    assert profile_path.exists()
    assert log_path.exists()
    assert fake_driver.window_sizes == [(1024, 768)]

    driver.quit()

    assert not profile_path.exists()
    assert not log_path.exists()
    assert fake_driver.quit_calls == 1


def test_create_chrome_driver_cleans_profile_on_launch_error(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile"
    profile_path.mkdir()
    log_path = tmp_path / "chromedriver.log"
    log_path.write_text("chromedriver output", encoding="utf-8")

    def fake_mkdtemp(prefix):
        assert prefix == "psynet-chrome-"
        return str(profile_path)

    def fake_mkstemp(prefix, suffix):
        fd = os.open(log_path, os.O_RDWR)
        return fd, str(log_path)

    fake_webdriver = FakeWebDriver(launch_error=RuntimeError("boom"))

    monkeypatch.setattr(chrome_driver.tempfile, "mkdtemp", fake_mkdtemp)
    monkeypatch.setattr(chrome_driver.tempfile, "mkstemp", fake_mkstemp)
    monkeypatch.setattr(chrome_driver, "_append_debug_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(chrome_driver, "_count_psynet_chrome_profiles", lambda: 0)
    monkeypatch.setattr(chrome_driver, "list_psynet_chrome_processes", lambda: [])
    monkeypatch.setattr(chrome_driver, "list_chromedriver_processes", lambda: [])
    monkeypatch.setattr(
        chrome_driver,
        "_get_chrome_dependencies",
        lambda: (fake_webdriver, FakeOptions, FakeService),
    )

    with pytest.raises(RuntimeError, match="boom"):
        chrome_driver.create_psynet_chrome_driver(headless=False)

    assert not profile_path.exists()
    assert log_path.exists()


def test_find_chrome_binary_uses_fallback_paths(monkeypatch):
    monkeypatch.setattr(chrome_driver.shutil, "which", lambda _: None)
    monkeypatch.setattr(
        chrome_driver.os.path,
        "exists",
        lambda path: path == "/opt/chrome-linux64/chrome",
    )

    assert chrome_driver._find_chrome_binary() == "/opt/chrome-linux64/chrome"
