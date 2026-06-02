from psynet.pytest_psynet import _create_chrome_driver


def test_create_chrome_driver_uses_local_binaries(monkeypatch):
    class DummyDriver:
        pass

    class DummyOptions:
        binary_location = None

    class DummyService:
        def __init__(self, executable_path=None):
            self.executable_path = executable_path

    driver = DummyDriver()
    captured = {}

    def fake_which(name):
        return {
            "chrome": "/usr/local/bin/chrome",
            "chromedriver": "/usr/local/bin/chromedriver",
        }.get(name)

    def fake_chrome(*, service=None, options=None):
        captured["service_path"] = service.executable_path
        captured["binary_location"] = options.binary_location
        return driver

    monkeypatch.setattr("psynet.pytest_psynet.shutil.which", fake_which)
    monkeypatch.setattr("selenium.webdriver.chrome.service.Service", DummyService)
    monkeypatch.setattr("selenium.webdriver.Chrome", fake_chrome)

    assert _create_chrome_driver(DummyOptions()) is driver
    assert captured == {
        "service_path": "/usr/local/bin/chromedriver",
        "binary_location": "/usr/local/bin/chrome",
    }
