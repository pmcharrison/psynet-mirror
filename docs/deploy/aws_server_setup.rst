.. _aws_server_setup:

========================================
Setting up an experiment server with AWS
========================================

If you want to deploy your experiments online but don't want the cost of
Heroku, another option is to set up a server on Amazon Web Services (AWS).
This can cost quite a lot less, perhaps $30 or so a month assuming you leave
the server running all the time (but check the AWS documentation to confirm
exact pricing.

Here is a brief summary of the steps involved:

1. Sign into your AWS account at https://aws.amazon.com/.

2. Go to the EC2 panel.

3. (Optional) Switch to the most local availability region to you
   using the dropdown in the top-right corner of the screen.
   For example, I might switch to 'eu-west-2'. You should see a dropdown
   for this in the top right of the page.

4. Click on 'Instances'.

5. Click 'Launch instances'.

6. Give your instance a name, for example 'Test PsyNet server'.

7. Select 'Ubuntu' as the OS image.

8. Choose an appropriate instance type. Different instance types have different costs 
   and different performances. The appropriate instance type will depend on your use case.
   You can explore options online at 
   https://aws.amazon.com/ec2/instance-types/
   and 
   https://aws.amazon.com/ec2/pricing/on-demand/.
   Note that you need an instance with x86 rather than ARM architecture.
   For prototyping, something like `m7i.large` might work fine (2 vCPU, 8 GB RAM, c. $2.5/day);
   for running an experiment with multiple simultaneous participants, it might 
   be better to go with something larger like `m7i.xlarge` (4 vCPU, 16 GB RAM, c. $5/day).
   In order to avoid unnecessary costs, we recommend that you 'stop' or 'terminate' your instance
   when you're not using it. 'Stopping' pauses the instance, but you will still pay a small ongoing fee
   for storage. 'Terminating' completely deletes the instance and associated data, and eliminates your
   ongoing fees.

9. Click 'Create key pair' (RSA) and give it a name, e.g. 'test-psynet'.
   When done, a .pem file should be downloaded onto your computer.
   Change this files permissions so that it can be used by the SSH client
   by running ``chmod 400 ~/Downloads/test-psynet.pem``
   using your own file name as appropriate. 
   Move the file somewhere safe, for example ``~/Documents``.
   To save it within your SSH agent, run ``ssh-add ~/Documents/test-psynet.pem``,
   using your own file name as appropriate.

10. Click 'Create security group'. You have some decisions here about security.
    Tick all boxes (allow SSH, allow HTTPS, allow HTTP).
    If you are confident that you have a fixed IP address, and
    know how to update your AWS settings if it changes, change
    the SSH traffic option to only allow traffic from my IP address.

11. Set storage to 30 GB.

12. Leave all other options at their defaults, and click launch instance.
    Your instance will take a while to boot. You can click on the instances
    tab to see the current status of them. While the 'status check'
    column still says 'initializing', you'll still have to wait longer.

13. Once the instance is ready, select it in the AWS panel,
    and find the Public IPv4 DNS. This is the URL of your instance. It should
    look something like this: ec2-18-170-115-131.eu-west-2.compute.amazonaws.com

14. Verify that you can SSH to this instance by running the following in your terminal:

::

    ssh ubuntu@ec2-18-170-115-131.eu-west-2.compute.amazonaws.com


replacing the example with your own IPv4 DNS as appropriate.
You will probably see a warning message of the form 'The authenticity of host XXX can't be established';
this is to be accepted. Type yes and press enter.
If your login doesn't work (especially if it freezes with no output printed to the terminal), 
you may have to examine your security group/IP address combination.

15. If your lab is doing this for the first time, you probably need to acquire a domain name for your
    experiment server. This is the parent URL that will be used to host your experiments.
    If your lab already has a domain name, you can skip this step.
    On the AWS online console, navigate to the Route 53 service.
    On the Dashboard you can register a domain name. Note that different domain names
    come with different costs, and that registering a domain name can take from a few minutes to several hours.
    Before proceeding with the next steps, please wait until the AWS console tells you that the registration
    is complete.

16. We will now set up a subdomain that corresponds to your individual server.
    In the below we will set up a subdomain for a server called 'bob' under the domain 'psych-experiments.org'.
    In this scenario 'bob' would be the researcher's name (i.e. it's Bob's server), and 'psych-experiments.org'
    would be the domain name shared by everyone in the research group of which Bob is a member.
    Using this approach we can have multiple researchers in the same research group each with their own server.

    First we need to create a subdomain for ``bob.psych-experiments.org``.
    To do this, go to the 'Hosted zones' page, and select your domain name.
    Click on Create record, then type `bob` under record name.
    Set the record type to 'CNAME', and set the value to your instances Public IPv4 DNS
    as copied above (it looks something like `ec2-23-54-234-12.eu-west-2.compute.amazonaws.com`).
    Click 'Create records' to finalize.

    This change can take up to a minute to enact; you can click 'View status' to confirm that your
    changes have been enacted.
    Once it is done, you should be able to SSH to your server using the following command
    (replacing the example with your own domain name as appropriate):

::

    ssh ubuntu@bob.psych-experiments.org

    Now we need to create a wildcard subdomain for the apps you wish to deploy.
    Your apps will be accessible at URLs like `my-fun-app.bob.psych-experiments.org`.
    To do this, repeat the same steps for creating a subdomain as before,
    except instead of typing `bob` under record name,
    type `*.bob`. As before, you will need to to wait a minute or so for the changes to take effect.
    To test that this worked, try the following
    (as before, replacing the example with your own domain name as appropriate):

::

    ssh ubuntu@my-app.bob.psych-experiments.org

17. Now, switching back to your local computer terminal (i.e. not the SSH terminal you just opened),
    make sure you are on your PsyNet virtual environment on your local computer, 
    and run the following to register the server for PsyNet:

::

    dallinger docker-ssh servers add --host bob.psych-experiments.org --user ubuntu

where the ``host`` argument corresponds to the domain name you just registered.
Here ``ubuntu`` is the default user for AWS instances, you shouldn't need to change this.

Under the line 'Checking Docker presence', you may see the following:

::

    Error: exit code was not 0 (127)

    bash: line 1: docker: command not found

This is not a real error, don't worry. The script should proceed by installing Docker, including the Docker Compose plugin.

18. Now go back to your SSH terminal, and run the following:

::

    sudo usermod -aG docker ${USER}

This adds your user to the Docker group so that you can run Docker commands without ``sudo``.
Log out of your SSH session with CTRL-D, then open a new SSH session using the same ``ssh`` command as before.


19. Then run the following command to open a live log of the web server:

::

    cd ~/dallinger
    docker compose logs -f


20. Now you can try launching your own experiment by running the following within an experiment
    directory, on your local machine (not on the SSH terminal):

::

    psynet debug ssh --app my-fun-app --dns-host bob.psych-experiments.org

where you have placed ``bob.psych-experiments.org`` with the appropriate text corresponding to your own
research/domain name combination.

21. Remember, AWS resources cost money and are billed incrementally. Once you are done using a server
    you should stop (if you want to use it again in the future) or terminate it (if you're completely done with it).
