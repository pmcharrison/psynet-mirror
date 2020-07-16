import pytest

def pytest_addoption(parser):
    group = parser.getgroup('selenium', 'selenium')
    group._addoption('--headless',
                     action='store_true',
                     help='enable headless mode for supported browsers.')
