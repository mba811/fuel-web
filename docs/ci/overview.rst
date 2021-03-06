Fuel Infrastructure
===================

Overview
--------

Fuel Infrastructure is the set of systems (servers and services) which provide
the following functionality:

* automatic tests for every patchset commited to Fuel Gerrit repositories,
* Fuel nightly builds,
* regular integration tests,
* custom builds and custom tests,
* release management and publishing,
* small helper subsystems like common ZNC-bouncer, status pages and so on.

Fuel Infrastructure servers are managed by Puppet from one Puppet Master node.

To add new server to the infrastructure you can either take any server with base
Ubuntu 14.04 installed and connect it to the Puppet Master via puppet agent, or
you can first set up the PXE-server with PXETool :ref:`pxe-tool` and then run server
provisioning in automated way.

Puppet
------

.. _pxe-tool:

Puppet Master
~~~~~~~~~~~~~


Puppet deployment with Fuel Infra manifests requires Puppet Master.
To install Puppet Master to the brand new server:

#. Get required repository with Puppet configuration:

   ::

     git clone ssh://(gerrit_user_name)@review.fuel-infra.org:29418/fuel-infra/puppet-manifests

#. Create a script to update puppet server to current version:

   ::

     #!/bin/bash

     REPO='/home/user/puppet-manifests'
     SERVER='pxetool'
     # sync repo files
     rsync -av --delete $REPO/modules/ root@$SERVER:/etc/puppet/modules/
     rsync -av --delete $REPO/manifests/ root@$SERVER:/etc/puppet/manifests/
     rsync -av --delete $REPO/bin/ root@$SERVER:/etc/puppet/bin/
     rsync -av --delete $REPO/hiera/ root@$SERVER:/etc/puppet/hiera/
     # create symlinks
     ssh root@$SERVER ln -s /etc/puppet/hiera/common-example.yaml /var/lib/hiera/common.yaml 2> /dev/null

#. Install base Ubuntu 14.04 with SSH server running (set hostname to pxetool.test.local).
   Download and install Puppet Agent package.

#. Run previously created script on your workstation to push configuration and scripts
   to new server.  Run /etc/puppet/bin/install_puppet_master.sh as root on new server.

The last script does the following:

* upgrades all packages on the system
* installs required modules
* installs puppet and Puppet Master packages
* runs puppet apply to setup Puppet Master
* runs puppet agent to do a second pass and verify installation is usable

.. note:: Puppet manifests take data (passwords, keys or configuration
  parameters) from hiera configuration. To work with our predefined test data
  script links ``hiera/common-example.yaml`` file to
  ``/var/lib/hiera/common.yaml``.  This step must be done before running
  ``bin/install_puppet_master.sh``.

Once done, you can start deploying other nodes.

Nodes and Roles
~~~~~~~~~~~~~~~

Currently, we define server roles via our hiera configuration (ssh://review.fuel-infra.org:29418/fuel-infra/puppet-manifests) using facter value ``ROLE``. Several roles are defined in ``hiera/roles``:

* anon_stat.yaml
* gerrit.yaml
* glusterfs_testing.yaml
* jenkins_master.yaml
* jenkins_slave.yaml
* lab.yaml
* mongo_testing.yaml
* nailgun_demo.yaml
* puppetmaster.yaml
* seed.yaml
* tools.yaml
* tracker.yaml
* web.yaml
* zbxproxy.yaml
* zbxserver.yaml
* znc.yaml

The most of roles are self explainable.

Generic Node Installation
~~~~~~~~~~~~~~~~~~~~~~~~~

Follow these steps to deploy chosen node:

* install base Ubuntu 14.04
* install puppetlabs agent package
* append to ``/etc/hosts`` - ``<Puppet Master IP> puppet pxetool.test.local``
* run ``FACTER_ROLE=<role name> puppet agent --test`` to apply configuration

Jenkins
-------

Our Jenkins instances are configured to run in master-slave mode. We have
Jenkins master instance on a virtual machine and a number of hardware nodes
working as Jenkins slaves.

Jenkins slaves setup
~~~~~~~~~~~~~~~~~~~~

There are several ways to setup Jenkins master-slave connection, and we use two
of them. The first one is organized simply by putting Jenkins master SSH-key in
authorized_keys file for jenkins user on a slave machine. Then you go to the
Jenkins Web UI and create node manually by specifying node IP address. Jenkins
master connects to the slave via SSH, downloads slave.jar file and runs jenkins
process on a slave.

The second approach requires more configuration steps to take, but allows you to
create slave node automatically from a slave node itself. To use it you need:

* install Swarm Plugin on Jenkins master
* create Jenkins user with ability to create nodes
* install jenkins-swarm-slave package on the slave
* configure the slave to use the mentioned Jenkins user
* run jenkins-swarm-slave service on the slave

Service will automatically connect to Jenkins master and create a node with proper
name and IP address.

Though this approach seems to be complicated, it is quite easy to implement it
with Puppet, as we do in jenkins::slave Puppet class (defined in
puppet-manifests/modules/jenkins/manifests/slave.pp).

If you use Gerrit slave with HTTPs support (default hiera value), please also
include jenkins::swarm_slave as it will trust Jenkins Master certificate on
Node side.

The downside of the swarm slave plugin is that every time you reboot Jenkins
master instance, slaves are recreated and, therefore, lose all the labels
assigned to them via Jenkins WebUI.

Jenkins Jobs
------------

Our CI requires many jobs and configuration, it is not convenient to configure
everything with jenkins GUI. We use dedicated
`repository <https://github.com/fuel-infra/jenkins-jobs>`_ and
`JJB <http://docs.openstack.org/infra/jenkins-job-builder/>`_
to store and manage our jobs.

Install Jenkins Job Builder
~~~~~~~~~~~~~~~~~~~~~~~~~~~

To begin work with jenkins job builder we need to install it and configure.

#. Install packages required to work with JJB

   ::

     apt-get install -y git python-tox
     # or
     yum install git python-tox

#. Download git repository and install JJB

   ::

     git clone https://github.com/fuel-infra/jenkins-jobs.git
     cd jenkins-jobs
     tox

#. Enable python environment, please replace <server> with server name, for
   example fuel-ci

   ::

     source .tox/<server>/bin/activate

#. Create file jenkins_jobs.ini with JJB configuration. It could be created
   at any place, for this documentation we assume that it will be placed in
   conf/ directory, inside local copy of jenkins-jobs repository.

   ::

    [jenkins]
    user=<JENKINS USER>
    password=<JENKINS PASSWORD OR API-TOKEN>
    url=https://<JENKINS URL>/

    [job_builder]
    ignore_cache=True
    keep_descriptions=False
    recursive=True
    include_path=.:scripts

  .. note:: <JENKINS_USER> is the user already defined in Jenkins with an
   appropriate permissions set:

   * Read - under the Global group of permissions
   * Create, Delete, Configure and Read - under the Job group of permissions

Upload jobs to Jenkins
~~~~~~~~~~~~~~~~~~~~~~

When JJB is installed and configured you can upload jobs to jenkins master.

.. note:: We assume that you are in main directory of jenkins-jobs repository
   and you have enabled python environment.

Upload all jobs configured for one specified server, for example upload of
fule-ci can be done in this way:

   ::

     jenkins-jobs --conf conf/jenkins_jobs.ini update servers/fuel-ci:common


Upload only one job

   ::

     jenkins-jobs --conf conf/jenkins_jobs.ini update servers/fuel-ci:common 8.0-community.all

Building ISO with Jenkins
-------------------------

Requirements
~~~~~~~~~~~~

For minimal environment we need 3 systems:

* Jenkins master
* Jenkins slave with enabled slave function for ISO building and deployment
  testing. This can be done in different ways. For instance, you can create
  hiera role for such server with the values provided below. Please keep in
  mind that you have to explicitely set run_test and build_fuel_iso variables
  to true, as ones are not enabled by default.

   ::

    ---
    classes:
      - '::fuel_project::jenkins::slave'

    fuel_project::jenkins::slave::run_test: true
    fuel_project::jenkins::slave::build_fuel_iso: true

  .. note:: Every slave which will be used for ISO deployment testing, like
    BVT, requires additional preparation.

    Once puppet is applied, and slave is configured in Jenkins master, you need
    to run the prepare_env job on it. Job will setup the python virtual
    environment with fuel-devops installed (:doc:`../devops`).

    If you build ISO newer than 6.1 there is no need to change default job
    parameters. For older versions you need to run build with
    update_devops_2_5_x option checked.

* Seed server - it is the server where you plan to store built ISO


Create Jenkins jobs
~~~~~~~~~~~~~~~~~~~

To build your own ISO you need to create job configurations for it, it requires
a few steps:

#. Create your own jobs repository, for start we will use fuel-ci jobs

   ::

     cd jenkins-jobs/servers
     cp -pr fuel-ci test-ci

#. To build and test ISO we will use files:

   * servers/test-ci/8.0/community.all.yaml
   * servers/test-ci/8.0/fuel_community_publish_iso.yaml
   * servers/test-ci/8.0/fuel_community.centos.bvt_2.yaml
   * servers/test-ci/8.0/fuel_community.ubuntu.bvt_2.yaml

#. In all files you need to make changes:

   * Change email devops+alert@mirantis.com to your own

   * If you don't need reporting jobs you should delete triggering of
     fuel_community_build_reports in all jobs or disable reporting job

    ::

     - job:
        ...
        publishers:
           ...
           - trigger-parameterized-builds:
             ...
             - project: fuel_community_build_reports

   * Update seed name server in file
     servers/test-ci/8.0/fuel_community_publish_iso.yaml

    ::

     - job:
        ...
        publishers:
           ...
           - trigger-parameterized-builds:
             ...
             - project:  8.0.fuel_community.centos.bvt_2, 8.0.fuel_community.ubuntu.bvt_2
                ...
                predefined-parameters: |
                   ISO_TORRENT=http://seed.fuel-infra.org/fuelweb-iso/fuel-community-$ISO_ID.iso.torrent

   * Update seed name server in file
     servers/test-ci/8.0/builders/publish_fuel_community_iso.sh

    ::

      sed -i 's/seed-us1.fuel-infra.org/seed.test.local/g' servers/test-ci/8.0/builders/publish_fuel_community_iso.sh
      sed -i 's/seed-cz1.fuel-infra.org/seed.test.local/g' servers/test-ci/8.0/builders/publish_fuel_community_iso.sh

#. Create jobs on jenkins master

   .. note:: Please remember to:

      * change current directory to the root directory of cloned jenkins-jobs repository
      * enable python environment
      * use correct jenkins_jobs.ini file (with correct jenkins master server)

   ::

     jenkins-jobs --conf conf/jenkins_jobs.ini update servers/test-ci:common 8.0-community.all
     jenkins-jobs --conf conf/jenkins_jobs.ini update servers/test-ci:common 8.0.publish_fuel_community_iso
     jenkins-jobs --conf conf/jenkins_jobs.ini update servers/test-ci:common 8.0.fuel_community.centos.bvt_2
     jenkins-jobs --conf conf/jenkins_jobs.ini update servers/test-ci:common 8.0.fuel_community.ubuntu.bvt_2


Start ISO building
~~~~~~~~~~~~~~~~~~

When you finish setting jobs up on jenkins master you will see project with
name 8.0-community.all there, to start ISO build and test procedure you need
to run mentioned project.

Build and test procedure have 3 steps:

* ISO building (8.0-community.all)
* when ISO is successfully created it will be uploaded to the seed server
  (by triggering 8.0.publish_fuel_community_iso)
* successful upload will start BVT test (8.0.fuel_community.centos.bvt_2 and
  8.0.fuel_community.ubuntu.bvt_2)


Gerrit
------

Although fuel-* repositories are hosted by the `OpenStack Gerrit <http://review.openstack.org>`_,
we use additional Gerrit instance to host OpenStack packages, internal projects and all the code
related to Infrastructure itself.

Our Gerrit instance is installed and configured by Puppet, including specifying
the exact Java WAR file that is used(link). To manage Gerrit instance we use
`Jeepyb <http://docs.openstack.org/infra/system-config/jeepyb.html>`_ - the tool written by Openstack Infra
team, which allows to store projects configuration in YAML format.

To use Jeepyb with gerrit you need to create "projects.yaml" configuration file,
where for each project you add the following information:

* project name
* project description
* project ACL
* project upstream

If "upstream" option is specified, Jeepyb will automaticaly import the upstream
repository to this new project. To apply the configuration, use "manage-projects" command.

Every project has ACL file. One ACL file can be reused in several projects. In
ACL file, access rights are defined based on the Gerrit user groups.
For example, in this file you can allow certain group to use the Code-Review
+/-2 marks.

In our gerrit, we have some global projects - <projects>/. The Core Reviewers
for these projects are <one-core-group>.

Contributing
~~~~~~~~~~~~

Feedback
~~~~~~~~
