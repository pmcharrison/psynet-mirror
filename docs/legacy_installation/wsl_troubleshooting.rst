
WSL 2 installation is incomplete
--------------------------------

If you see a message beginning with "WSL 2 installation is incomplete", you probably need to do the following:

- Click on the link it gives you
- Click on the link under 'download the latest package', open and run the installer once it has downloaded
- Continue with the next steps of the installation
- Note: if you run Powershell, it might fail if you run it on admin mode! If you get stuck (Access Denied),
  try running it again without admin mode and see if it works.

Hardware assisted virtualization
--------------------------------

If you see a message beginning "Hardware assisted virtualization and data execution protection must be enabled in the
BIOS", you need to restart your computer into BIOS and change some settings to enable those two things. The precise set
of steps will depend on your computer. The first step though is to restart your computer, and press a certain key to
launch into BIOS -- ordinarily that key will be printed on the screen at some point during the startup sequence.
Hint -- you might find that the option you need to select is called 'SVM mode'...
