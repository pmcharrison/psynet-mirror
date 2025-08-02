# PsyNet Automatic Tab Completion

This directory contains shell completion scripts for the `psynet` command that provide automatic tab completion for all available psynet commands, subcommands, and options.

## Files

- `psynet-completion.bash` - Bash completion script
- `psynet-completion.zsh` - Zsh completion script

## Installation

### Easy Installation (Recommended)

Run the installation script:
```bash
./install-completion.sh
```

This will automatically detect your shell and add the appropriate completion setup to your shell configuration file.

### Manual Installation

#### Method 1: Direct Eval (Fastest)

Add this line to your shell configuration file:

**For Bash (`~/.bashrc`):**
```bash
eval "$(_PSYNET_COMPLETE=bash_source psynet)"
```

**For Zsh (`~/.zshrc`):**
```bash
eval "$(_PSYNET_COMPLETE=zsh_source psynet)"
```

#### Method 2: Source Completion Scripts

**For Bash:**
```bash
# Copy script to system location
sudo cp psynet-completion.bash /etc/bash_completion.d/psynet

# Or source it directly in ~/.bashrc
echo "source $(pwd)/psynet-completion.bash" >> ~/.bashrc
```

**For Zsh:**
```bash
# Copy script to system location
sudo cp psynet-completion.zsh /usr/local/share/zsh/site-functions/_psynet

# Or source it directly in ~/.zshrc
echo "source $(pwd)/psynet-completion.zsh" >> ~/.zshrc
```

### Activate Completion

After installation, either restart your terminal or reload your shell configuration:
```bash
source ~/.bashrc  # for bash
source ~/.zshrc   # for zsh
```

## Usage

Once installed, you can use tab completion with the `psynet` command:

### Basic Command Completion

```bash
psynet <TAB>
```

This will show all available commands:
- prepare
- experiment-variables
- db
- debug
- deploy
- docs
- update
- estimate
- generate-constraints
- check-constraints
- export
- rpdb
- load
- generate-config
- update-scripts
- destroy
- apps
- stats
- test
- simulate
- list-experiment-dirs
- list-isolated-tests
- lucid
- translate
- run-bot

### Subcommand Completion

```bash
psynet debug <TAB>
```

This will show available subcommands:
- local
- heroku
- ssh

### Option Completion

```bash
psynet debug local --<TAB>
```

This will show available options for the debug local command:
- --docker
- --archive
- --legacy
- --no-browsers

### Partial Completion

```bash
psynet d<TAB>
```

This will complete to `psynet debug` (or show other commands starting with 'd').

## How It Works

The completion system uses Click's built-in shell completion functionality:

1. **Automatic Detection**: When you press tab, the shell calls the completion function
2. **Environment Variables**: The completion function sets environment variables with the current command state
3. **PsyNet Integration**: The psynet command detects these environment variables and returns completion suggestions
4. **Dynamic Completion**: All commands, subcommands, and options are automatically discovered from the Click command structure

## Supported Commands and Options

The completion scripts automatically support all psynet commands and their options:

### Main Commands
- `prepare` - Prepare the experiment
- `experiment-variables` - Show experiment variables
- `db` - Show database URI
- `debug` - Debug commands (local, heroku, ssh)
- `deploy` - Deploy commands (local, heroku, ssh)
- `docs` - Build documentation
- `update` - Update PsyNet and Dallinger
- `estimate` - Estimate experiment parameters
- `generate-constraints` - Generate constraints.txt
- `check-constraints` - Check constraints.txt
- `export` - Export commands (local, heroku, ssh)
- `rpdb` - Remote debugger
- `load` - Load data from archive
- `generate-config` - Generate config file
- `update-scripts` - Update experiment scripts
- `destroy` - Destroy commands (heroku, ssh)
- `apps` - App management commands (ssh)
- `stats` - Statistics commands (ssh)
- `test` - Test commands (local, ssh)
- `simulate` - Generate simulated data
- `list-experiment-dirs` - List experiment directories
- `list-isolated-tests` - List isolated tests
- `lucid` - Lucid commands
- `translate` - Translate experiment
- `run-bot` - Run a bot through the experiment

### Common Options
- `--help` - Show help
- `--version` / `-v` - Show version
- `--docker` - Use Docker mode
- `--archive` - Path to experiment archive
- `--app` - Experiment app name
- `--server` - Server name
- `--no-browsers` - Skip opening browsers
- `--legacy` - Use legacy mode
- `--verbose` - Verbose mode

### Lucid Subcommands
- `cost` - Get cost summary
- `compensate` - Compensate participants
- `locale` - Show locale information
- `estimate` - Estimate survey costs
- `status` - Change survey status
- `qualifications` - Get qualifications
- `studies` - List studies
- `submissions` - List submissions

## Examples

```bash
# Complete to debug command
psynet d<TAB> → psynet debug

# Complete to debug local
psynet debug l<TAB> → psynet debug local

# Complete to debug local with docker option
psynet debug local --d<TAB> → psynet debug local --docker

# Complete to deploy ssh with app
psynet deploy s<TAB> → psynet deploy ssh
psynet deploy ssh --a<TAB> → psynet deploy ssh --app

# Complete to lucid commands
psynet lucid <TAB> → shows all lucid subcommands

# Complete to lucid estimate with options
psynet lucid estimate --l<TAB> → psynet lucid estimate --language-code
```

## Troubleshooting

If completion doesn't work:

1. Make sure the completion script is properly sourced
2. Check that your shell supports completion (bash or zsh)
3. Try restarting your terminal
4. For zsh, make sure completion is enabled: `autoload -U compinit && compinit`
5. Verify that psynet is in your PATH: `which psynet`

## Notes

- The completion scripts use Click's built-in completion system
- All completion is dynamic and based on the actual command structure
- File path completion is available for options that expect file paths
- The scripts work with both the regular `psynet` command and the Docker version
- No additional commands or setup required - just source the script and start using tab completion
