==============================
Setting up Slack notifications
==============================

To set up Slack notifications you will need to create a Slack app and install it.
After installation, each launched experiment will create a thread in a provided public channel and notifications will occur in this thread.

Creating a Slack app
--------------------
1. Go to https://api.slack.com/apps, make sure you are logged in to your Slack workspace and click on "Create New App".
2. Select make a app from a manifest and use the template from below:

::

    display_information:
      name: PsyNet Bot
      description: Experiment notifications
      background_color: "#000000"
    features:
      bot_user:
        display_name: PsyNet Bot
        always_online: true
    oauth_config:
      scopes:
        bot:
          - chat:write
          - chat:write.public
          - chat:write.customize
          - users:read
          - users:read.email
    settings:
      org_deploy_enabled: false
      socket_mode_enabled: false
      token_rotation_enabled: false

3. Scroll down to “Display Information” and set a bot icon if you like
4. Go to the menu item “Install app” and install it into the workspace
5. Copy the “Bot User OAuth Token” and put it into your ``.dallingerconfig``:

::

    slack_bot_token = xxxxxxxx-xxxxxxxx-xxxxxxxx-xxxxxxxxx

6. Now add the **public** Slack channel to report to, here ``#project``

::

    slack_channel_name = project



.. warning::
    The channel must be public. This does not work for private channels!



7. Make sure your ``experimenter_name`` matches your name on Slack

::

    experimenter_name = Max Mustermann


Usage
-----
By default PsyNet reports on the following events:
- Experiment started (and credentials for dashboard)
- Experiment finished
- Error occurred

However, you can also add custom messages to the Slack channel by using the following code: ``experiment.slack_notify("My custom message supporting **markdown**!")``