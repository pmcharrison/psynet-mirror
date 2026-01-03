You can get Docker Desktop from the following link: https://www.docker.com/products/docker-desktop/
Normally Docker Desktop will work out of the box on Linux and macOS machines,
but there is lots of help available online if you get stuck.

You may need to set some settings in Docker Desktop once it's installed.
Navigate to Docker Desktop settings, then look for an 'Advanced' tab.
If you don't see such a tab, you can skip the following instructions.
If you do see such a tab, do the following:

1. Select 'System (requires password)' installation of Docker's CLI tools, rather than 'User'.
2. Tick the box that says 'Allow the default Docker socket to be used'.
3. Tick the box that says 'Allow privileged port mapping'.

If you are on a Mac that uses Apple Silicon (i.e. most new Macs since 2021...?)
then you should go to Preferences and tick the box that says
'Use Rosetta for x86/amd64 emulation on Apple Silicon'.
If you don't tick this box PsyNet will run very slowly.




