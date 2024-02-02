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

8. Select 't2.large' as the instance type.

9. Click 'Create key pair' (RSA) and give it a name, e.g. 'test-psynet'.
   When done, a .pem file should be downloaded onto your computer.
   To save it within your SSH agent, run ``ssh-add ~/Downloads/test-psynet.pem``,
   using your own file name as appropriate.

10. Click 'Create security group'. You have some decisions here about security.
    Tick all boxes (allow SSH, allow HTTPS, allow HTTP).
    If you are confident that you have a fixed IP address, and
    know how to update your AWS settings if it changes, change
    the SSH traffic option to only allow traffic from my IP address.

11. Set storage to 32 GB.

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
If it doesn't work, you may have to examine your security group/IP address combination.

15. Inside your PsyNet virtual environment, run the following to register the server for PsyNet:

::


    dallinger docker-ssh servers add --host ec2-18-170-115-131.eu-west-2.compute.amazonaws.com --user ubuntu

where the ``host`` argument (beginning with 'ec2') corresponds to your Public IPv4 DNS.

Under the line 'Checking Docker presence', you may see the following:

::

    Error: exit code was not 0 (127)

    bash: line 1: docker: command not found

This is not a real error, don't worry. The script should proceed by installing Docker, including the Docker Compose plugin.

15. Now you can try launching your own experiment by running the following within an experiment
    directory:

::

    psynet debug ssh --app test-app
