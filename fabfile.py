import fabric.api as fab


def vagrant():
    """Configure Fabric to use a Vagrant environment."""
    # grab vagrant's ssh config information
    ssh_config = fab.local('vagrant ssh-config', capture=True)
    # split the config so we can index into it (will break for multiple hosts)
    ssh_config = [line.strip() for line in ssh_config.split('\n')]
    ssh_config = dict(tuple(line.split(None, 1)) for line in ssh_config)
    # paths are wrapped with double quotes, which we don't need
    ssh_config = dict((k, v.strip('"')) for k, v in ssh_config.iteritems())

    fab.env.user = ssh_config['User']
    fab.env.hosts = ['%s:%s' % (ssh_config['HostName'], ssh_config['Port'])]
    fab.env.key_filename = ssh_config['IdentityFile']


def uname():
    """Print the operating system name, version, etc, of the remote server."""
    fab.run('uname -a')


def bootstrap():
    """Bootstrap a server with application dependencies."""
    apt_dependencies = [
        'apache2',
        'libapache2-mod-wsgi',
        'python-setuptools']

    fab.sudo('apt-get update')
    fab.sudo('apt-get install -y %s' % ' '.join(apt_dependencies))

    # clean up apache2 install
    fab.sudo('rm -f /etc/apache2/sites-enabled/000-default')
    fab.sudo('rm -f /var/www/index.html')

    # setup our flask app
    fab.put('config/apache2/flaskr.wsgi', '/var/www/', use_sudo=True)
    fab.put(
        'config/apache2/flaskr',
        '/etc/apache2/sites-available/',
        use_sudo=True)
    fab.sudo('a2ensite flaskr')


def config(url):
    """Deploy the instance specific configuration file located at the URL.

    Example::

        $ fab config:"http://example.com/my_config.file"

    """
    import os
    import urllib

    # get a copy of the specified configuration
    local_filename, headers = urllib.urlretrieve(url)

    # discover the instance path
    cmd = (
        "import os, sys; "
        "print os.path.join(sys.prefix, \'var\', \'flaskr-instance\');")
    instance_dir = fab.run('python -c "%s"' % cmd)
    instance_filename = os.path.join(instance_dir, 'flaskr_config.py')

    # copy the configuration to the instance path
    fab.sudo('mkdir -p %s' % instance_dir)
    fab.put(local_filename, instance_filename, use_sudo=True)
    fab.sudo('chmod 400 %s' % instance_filename)
    fab.sudo('chown www-data:www-data %s' % instance_filename)


def deploy():
    """Test, package and deploy the application."""
    # let's not deploy something that's known to be broken...
    fab.local('python setup.py test')

    # create a new source distribution as tarball
    fab.local('python setup.py sdist --formats=gztar')

    # figure out the release name and version
    dist = fab.local('python setup.py --fullname', capture=True).strip()

    # upload the source tarball to the temporary folder on the server
    fab.put('dist/%s.tar.gz' % dist, '/tmp/flaskr.tar.gz')

    # unpack the tarball, install it and cleanup
    fab.run('mkdir -p /tmp/flaskr')
    with fab.cd('/tmp/flaskr'):
        fab.run('tar xzf /tmp/flaskr.tar.gz')
        fab.run('ls -R')
        with fab.cd('/tmp/flaskr/%s' % dist):
            fab.sudo('python setup.py install')
    fab.sudo('rm -rf /tmp/flaskr /tmp/flaskr.tar.gz')
    fab.sudo('service apache2 reload')