CHROME_VERSION=$(curl https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json | jq .channels.Stable.version | tr -d '"') && \
echo Installing Chrome $CHROME_VERSION && \
  wget -O chrome.deb https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-linux64.zip && \
  unzip chrome.deb -d /opt/ && \
  ln -s /opt/chrome-linux64/chrome /usr/local/bin/chrome && \
  echo "Successfully installed Chrome $(chrome --version)" && \
  echo Installing ChromeDriver $CHROME_VERSION && \
  wget -O chrome-driver.zip https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip && \
  unzip chrome-driver.zip -d /usr/local/bin/ && \
  ln -s /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
  echo "Successfully installed ChromeDriver $(chromedriver --version)"

pip-compile dev-requirements.in /dallinger/requirements.txt --verbose --output-file dev-requirements.txt
pip install --no-cache-dir -r dev-requirements.txt
pip install pytest-test-groups
pip install -r demos/requirements.txt
