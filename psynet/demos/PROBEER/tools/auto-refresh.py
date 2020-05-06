import time
from selenium import webdriver
network_url = 'https://dlgr-pro.herokuapp.com/monitor'

options = webdriver.ChromeOptions()
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
driver = webdriver.Chrome(options=options, executable_path='/usr/local/bin/chromedriver')

while True:
    driver.get(network_url)
    time.sleep(60)