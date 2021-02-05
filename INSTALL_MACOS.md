# Installation of PsyNet/Dallinger on macOS Big Sur (11.1)

## Install and setup necessary software

First make sure you have the latest macOS updates installed.

#### Homebrew
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### PostgreSQL
```bash
brew install postgresql
brew services start postgresql
createuser -P dallinger --createdb 
```

Password: dallinger

```bash
createdb -O dallinger dallinger
createdb -O dallinger dallinger-import
exit

brew services restart postgresql
```

#### Heroku
```bash
brew install heroku/brew/heroku
```

#### Redis
```bash
brew install redis
brew services start redis
```

#### Setup Git
```bash
git config --global user.email "you@example.com"
git config --global user.name "Your Name"
```

## Install and setup Python
### Install Python3.7
```bash
brew install python@3.7
echo 'export PATH="/usr/local/opt/python@3.7/bin:$PATH"' >> ~/.profile
```

### Setup virtual environment
```bash
pip3 install virtualenv
pip3 install virtualenvwrapper
export WORKON_HOME=$HOME/.virtualenvs
mkdir -p $WORKON_HOME
export VIRTUALENVWRAPPER_PYTHON=$(which python3.7)
source $(which virtualenvwrapper.sh)
mkvirtualenv dlgr_env --python /usr/local/opt/python@3.7/bin/python3
workon dlgr_env
echo "export VIRTUALENVWRAPPER_PYTHON=$(which python3.7)" >> ~/.bash_profile
echo "source $(which virtualenvwrapper.sh)" >> ~/.bash_profile
```

## Install Dallinger (in your home directory)
```bash
cd ~
git clone https://github.com/Dallinger/Dallinger
cd Dallinger
pip install -r dev-requirements.txt
pip install --editable .[data]
```
#### Verify successful installation
```bash
dallinger --version
```

## Install PsyNet (in your home directory)
First make sure you have added an SSH Public Key under your GitLab profile
```bash
cd ~
git clone git@gitlab.com:computational-audition-lab/psynet
cd psynet
pip3 install -e .
```

#### Verify successful installation
```bash
psynet --version
```
