# First run when
HEADLESS = False
WAIT_DUR = 5
url = 'http://0.0.0.0:5000/ad?recruiter=hotair&assignmentId=459HFL&hitId=OMKY5V&workerId=C1IE7G&mode=debug'

from selenium import webdriver
from selenium.webdriver import ActionChains
import time
options = webdriver.ChromeOptions()
if HEADLESS:
    options.add_argument('headless')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
driver = webdriver.Chrome(options=options, executable_path='/usr/local/bin/chromedriver')
driver.get(url)
# Begin the experiment
driver.find_element_by_id('begin-button').click()

# Switch to experiment screen
driver.switch_to_window(driver.window_handles[1])
driver.execute_script("window.scrollTo(0, 2000)")
driver.find_element_by_id('consent').click()

# Experiment started
while True:
    next_btn = driver.find_elements_by_class_name('btn-success')
    if len(next_btn):
        btn = next_btn[0]
        if btn.is_enabled():
            btn.click()
        else:
            try:
                slider = driver.find_element_by_id('sliderpage_slider')
                move = ActionChains(driver)
                move.click_and_hold(slider).move_by_offset(10, 0).release().perform()
                time.sleep(1)
                move.click_and_hold(slider).move_by_offset(0, 10).release().perform()
                time.sleep(1)
            except Exception:
                time.sleep(WAIT_DUR)
    else:
        time.sleep(WAIT_DUR)