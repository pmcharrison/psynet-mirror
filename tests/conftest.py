import pytest

def pytest_addoption(parser):
    group = parser.getgroup('selenium', 'selenium')
    group._addoption('--headless',
                     action='store_true',
                     help='enable headless mode for supported browsers.')

@pytest.fixture
def chrome_options(chrome_options, pytestconfig):
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    if pytestconfig.getoption('headless'):
        chrome_options.add_argument('--headless')
    return chrome_options

@pytest.fixture
def firefox_options(firefox_options, pytestconfig):
    if pytestconfig.getoption('headless'):
        firefox_options.add_argument('-headless')
    return firefox_options